"""The 'spec2nii2bids' plugin is a wrapper around the recent spec2nii (https://github.com/wexeee/spec2nii) Python
library to interact with and convert MR spectroscopy source data. Presently, the spec2nii2bids plugin is a first
implementation that supports the conversion of Philips SPAR/SDAT files, Siemens Twix files and GE P-files to NIfTI,
in conjunction with BIDS sidecar files"""

import logging
import shutil
import json
import pandas as pd
import dateutil.parser
from typing import Union
from bids_validator import BIDSValidator
from pathlib import Path
from bidscoin import bcoin, bids, due, Doi
from bidscoin.bids import Bidsmap, Plugin

LOGGER = logging.getLogger(__name__)

# The default options that are set when installing the plugin
OPTIONS = Plugin({'command': 'spec2nii',    # Command to run spec2nii, e.g. "module add spec2nii; spec2nii" or "PATH=/opt/spec2nii/bin:$PATH; spec2nii" or /opt/spec2nii/bin/spec2nii or 'C:\"Program Files"\spec2nii\spec2nii.exe' (note the quotes to deal with the whitespace)
                  'args': None,             # Argument string that is passed to spec2nii (see spec2nii -h for more information)
                  'anon': 'y',              # Set this anonymization flag to 'y' to round off age and discard acquisition date from the metadata
                  'meta': ['.json', '.tsv', '.tsv.gz'],  # The file extensions of the equally named metadata source files that are copied over as BIDS sidecar files
                  'multiraid': 2})          # The mapVBVD argument for selecting the multiraid Twix file to load (default = 2, i.e. 2nd file)


def test(options: Plugin=OPTIONS) -> int:
    """
    This plugin shell tests the working of the spec2nii2bids plugin + its bidsmap options

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']['spec2nii2bids']
    :return:        The errorcode (e.g 0 if the tool generated the expected result, > 0 if there was a tool error)
    """

    LOGGER.info('Testing the spec2nii2bids installation:')

    if 'get_twixfield' not in dir(bids) or 'get_sparfield' not in dir(bids) or 'get_p7field' not in dir(bids):
        LOGGER.error("Could not import the expected 'get_twixfield', 'get_sparfield' and/or 'get_p7field' from the bids.py library")
        return 1
    if 'command' not in {**OPTIONS, **options}:
        LOGGER.error(f"The expected 'command' key is not defined in the spec2nii2bids options")
        return 1
    if 'args' not in {**OPTIONS, **options}:
        LOGGER.warning(f"The expected 'args' key is not defined in the spec2nii2bids options")

    # Test the spec2nii installation
    return bcoin.run_command(f"{options.get('command',OPTIONS['command'])} -v")


def is_sourcefile(file: Path) -> str:
    """
    This plugin function assesses whether a sourcefile is of a supported dataformat

    :param file:    The sourcefile that is assessed
    :return:        The valid / supported dataformat of the sourcefile
    """

    suffix = file.suffix.lower()
    if suffix == '.dat':
        return 'Twix'
    elif suffix == '.spar':
        return 'SPAR'
    elif suffix == '.7' and not bids.is_dicomfile(file):
        return 'Pfile'

    return ''


def get_attribute(dataformat: str, sourcefile: Path, attribute: str, options: Plugin) -> str:
    """
    This plugin function reads attributes from the supported sourcefile

    :param dataformat:  The dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which key-value data needs to be read
    :param attribute:   The attribute key for which the value needs to be retrieved
    :param options:     The bidsmap['Options']['spec2nii2bids'] dictionary with the plugin options
    :return:            The retrieved attribute value
    """

    if dataformat not in ('Twix', 'SPAR', 'Pfile'):
        return ''

    if not sourcefile.is_file():
        LOGGER.error(f"Could not find {sourcefile}")
        return ''

    if dataformat == 'Twix':

        return bids.get_twixfield(attribute, sourcefile, options.get('multiraid', OPTIONS['multiraid']))

    if dataformat == 'SPAR':

        return bids.get_sparfield(attribute, sourcefile)

    if dataformat == 'Pfile':

        return bids.get_p7field(attribute, sourcefile)

    LOGGER.error(f"Unsupported MRS data-format: {dataformat}")


def bidsmapper_plugin(session: Path, bidsmap_new: Bidsmap, bidsmap_old: Bidsmap, template: Bidsmap, store: dict) -> None:
    """
    All the heuristics spec2nii2bids attributes and properties onto bids labels and meta-data go into this plugin function.
    The function is expected to update / append new runs to the bidsmap_new data structure. The bidsmap options for this plugin
    are stored in:

    bidsmap_new['Options']['plugins']['spec2nii2bids']

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The new study bidsmap that we are building
    :param bidsmap_old: The previous study bidsmap that has precedence over the template bidsmap
    :param template:    The template bidsmap with the default heuristics
    :param store:       The paths of the source- and target-folder
    :return:
    """

    # Get the plugin settings
    plugins = {'spec2nii2bids': Plugin(bidsmap_new['Options']['plugins']['spec2nii2bids'])}

    # Update the bidsmap with the info from the source files
    for sourcefile in [file for file in session.rglob('*') if is_sourcefile(file)]:

        datasource = bids.DataSource(sourcefile, plugins)
        dataformat = datasource.dataformat

        # Input checks
        if not template[dataformat] and not bidsmap_old[dataformat]:
            LOGGER.error(f"No {dataformat} source information found in the bidsmap and template for: {sourcefile}")
            return
        if not template.get(dataformat) and not bidsmap_old.get(dataformat):
            LOGGER.error(f"No {dataformat} source information found in the bidsmap and template for: {sourcefile}")
            return

        # See if we can find a matching run in the old bidsmap
        run, match = bids.get_matching_run(datasource, bidsmap_old)

        # If not, see if we can find a matching run in the template
        if not match:
            run, _ = bids.get_matching_run(datasource, template)

        # See if we have collected the run somewhere in our new bidsmap
        if not bids.exist_run(bidsmap_new, '', run):

            # Communicate with the user if the run was not present in bidsmap_old or in template, i.e. that we found a new sample
            if not match:
                LOGGER.info(f"Discovered '{datasource.datatype}' {dataformat} sample: {sourcefile}")

            # Now work from the provenance store
            if store:
                targetfile             = store['target']/sourcefile.relative_to(store['source'])
                targetfile.parent.mkdir(parents=True, exist_ok=True)
                LOGGER.verbose(f"Storing the discovered {dataformat} sample as: {targetfile}")
                run['provenance']      = str(shutil.copyfile(sourcefile, targetfile))
                run['datasource'].path = targetfile

            # Copy the filled-in run over to the new bidsmap
            bids.append_run(bidsmap_new, run)


@due.dcite(Doi('10.1002/mrm.29418'), description='Multi-format in vivo MR spectroscopy conversion to NIFTI', tags=['reference-implementation'])
def bidscoiner_plugin(session: Path, bidsmap: Bidsmap, bidsses: Path) -> Union[None, dict]:
    """
    This wrapper function around spec2nii converts the MRS data in the session folder and saves it in the bidsfolder.
    Each saved datafile should be accompanied by a json sidecar file. The bidsmap options for this plugin can be found in:

    bidsmap_new['Options']['plugins']['spec2nii2bids']

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsses:     The full-path name of the BIDS output `sub-/ses-` folder
    :return:            A dictionary with personal data for the participants.tsv file (such as sex or age)
    """

    # Get the subject identifiers and the BIDS root folder from the bidsses folder
    if bidsses.name.startswith('ses-'):
        subid      = bidsses.parent.name
        sesid      = bidsses.name
    else:
        subid      = bidsses.name
        sesid      = ''

    # Get started and see what dataformat we have
    options     = bidsmap['Options']['plugins']['spec2nii2bids']
    datasource  = bids.get_datasource(session, {'spec2nii2bids':options})
    dataformat  = datasource.dataformat
    sourcefiles = [file for file in session.rglob('*') if is_sourcefile(file)]
    if not sourcefiles:
        LOGGER.info(f"--> No {__name__} sourcedata found in: {session}")
        return

    # Read or create a scans_table and tsv-file
    scans_tsv = bidsses/f"{subid}{'_'+sesid if sesid else ''}_scans.tsv"
    if scans_tsv.is_file():
        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
    else:
        scans_table = pd.DataFrame(columns=['acq_time'], dtype='str')
        scans_table.index.name = 'filename'

    # Loop over all MRS source data files and convert them to BIDS
    for source in sourcefiles:

        # Get a data source, a matching run from the bidsmap
        datasource = bids.DataSource(source, {'spec2nii2bids': options})
        run, runid = bids.get_matching_run(datasource, bidsmap, runtime=True)

        # Check if we should ignore this run
        if datasource.datatype in bidsmap['Options']['bidscoin']['ignoretypes']:
            LOGGER.info(f"--> Leaving out: {source}")
            bids.bidsprov(bidsses, source, runid, datasource.datatype)              # Write out empty provenance data
            continue

        # Check that we know this run
        if not runid:
            LOGGER.error(f"Skipping unknown '{datasource.datatype}' run: {source}\n-> Re-run the bidsmapper and delete the MRS output data in {bidsses} to solve this warning")
            bids.bidsprov(bidsses, source)                  # Write out empty provenance data
            continue

        LOGGER.info(f"--> Coining: {source}")

        # Create the BIDS session/datatype output folder
        outfolder = bidsses/datasource.datatype
        outfolder.mkdir(parents=True, exist_ok=True)

        # Compose the BIDS filename using the matched run
        bidsignore = bids.check_ignore(datasource.datatype, bidsmap['Options']['bidscoin']['bidsignore'])
        bidsname   = bids.get_bidsname(subid, sesid, run, not bidsignore, runtime=True)
        bidsignore = bidsignore or bids.check_ignore(bidsname+'.json', bidsmap['Options']['bidscoin']['bidsignore'], 'file')
        bidsname   = bids.increment_runindex(outfolder, bidsname, run, scans_table)
        target     = (outfolder/bidsname).with_suffix('.nii.gz')

        # Check if the bidsname is valid
        bidstest = (Path('/')/subid/sesid/datasource.datatype/bidsname).with_suffix('.json').as_posix()
        isbids   = BIDSValidator().is_bids(bidstest)
        if not isbids and not bidsignore:
            LOGGER.warning(f"The '{bidstest}' output name did not pass the bids-validator test")

        # Check if file already exists (-> e.g. when a static runindex is used)
        if target.is_file():
            LOGGER.warning(f"{outfolder/bidsname}.* already exists and will be deleted -- check your results carefully!")
            for ext in ('.nii.gz', '.nii', '.json', '.tsv', '.tsv.gz', '.bval', '.bvec'):
                target.with_suffix('').with_suffix(ext).unlink(missing_ok=True)

        # Run spec2nii to convert the source-files in the run folder to NIfTI's in the BIDS-folder
        arg  = ''
        args = options.get('args', OPTIONS['args']) or ''
        if dataformat == 'SPAR':
            dformat = 'philips'
            arg     = f'"{source.with_suffix(".SDAT")}"'
        elif dataformat == 'Twix':
            dformat = 'twix'
            arg     = '-e image'
        elif dataformat == 'Pfile':
            dformat = 'ge'
        else:
            LOGGER.error(f"Unsupported dataformat: {dataformat}")
            return
        command = options.get('command', 'spec2nii')
        errcode = bcoin.run_command(f'{command} {dformat} -j -f "{bidsname}" -o "{outfolder}" {args} {arg} "{source}"')
        bids.bidsprov(bidsses, source, runid, datasource.datatype, [target] if target.is_file() else [])
        if not target.is_file():
            if not errcode:
                LOGGER.error(f"Output file not found: {target}")
            continue

        # Load/copy over and adapt the newly produced json sidecar-file
        sidecar  = target.with_suffix('').with_suffix('.json')
        metadata = bids.updatemetadata(datasource, sidecar, run['meta'], options.get('meta',[]))
        if metadata:
            with sidecar.open('w') as json_fid:
                json.dump(metadata, json_fid, indent=4)

        # Parse the acquisition time from the source header or else from the json file (NB: assuming the source file represents the first acquisition)
        if not bidsignore:
            acq_time = ''
            if dataformat == 'SPAR':
                acq_time = datasource.attributes('scan_date')
            elif dataformat == 'Twix':
                acq_time = f"{datasource.attributes('AcquisitionDate')}T{datasource.attributes('AcquisitionTime')}"
            elif dataformat == 'Pfile':
                acq_time = f"{datasource.attributes('rhr_rh_scan_date')}T{datasource.attributes('rhr_rh_scan_time')}"
            if not acq_time or acq_time == 'T':
                acq_time = f"1925-01-01T{metadata.get('AcquisitionTime','')}"
            try:
                acq_time = dateutil.parser.parse(acq_time)
                if options.get('anon',OPTIONS['anon']) in ('y','yes'):
                    acq_time = acq_time.replace(year=1925, month=1, day=1)      # Privacy protection (see BIDS specification)
                acq_time = acq_time.isoformat()
            except Exception as jsonerror:
                LOGGER.warning(f"Could not parse the acquisition time from: {source}\n{jsonerror}")
                acq_time = 'n/a'
            scans_table.loc[target.relative_to(bidsses).as_posix(), 'acq_time'] = acq_time

    # Write the scans_table to disk
    LOGGER.verbose(f"Writing acquisition time data to: {scans_tsv}")
    scans_table.sort_values(by=['acq_time','filename'], inplace=True)
    scans_table.replace('','n/a').to_csv(scans_tsv, sep='\t', encoding='utf-8', na_rep='n/a')

    # Collect personal data for the participants.tsv file
    personals = {}
    age       = ''
    if dataformat == 'Twix':
        personals['sex']    = datasource.attributes('PatientSex')
        personals['size']   = datasource.attributes('PatientSize')
        personals['weight'] = datasource.attributes('PatientWeight')
        age = datasource.attributes('PatientAge')                   # A string of characters with one of the following formats: nnnD, nnnW, nnnM, nnnY
    elif dataformat == 'Pfile':
        sex = datasource.attributes('rhe_patsex')
        if   sex == '0': personals['sex'] = 'O'
        elif sex == '1': personals['sex'] = 'M'
        elif sex == '2': personals['sex'] = 'F'
        try:
            age = dateutil.parser.parse(datasource.attributes('rhr_rh_scan_date')) - dateutil.parser.parse(datasource.attributes('rhe_dateofbirth'))
            age = str(age.days) + 'D'
        except dateutil.parser.ParserError as dateerror:
            pass
    if   age.endswith('D'): age = float(age.rstrip('D')) / 365.2524
    elif age.endswith('W'): age = float(age.rstrip('W')) / 52.1775
    elif age.endswith('M'): age = float(age.rstrip('M')) / 12
    elif age.endswith('Y'): age = float(age.rstrip('Y'))
    if age:
        if options.get('anon',OPTIONS['anon']) in ('y','yes'):
            age = int(float(age))
        personals['age'] = str(age)

    return personals
