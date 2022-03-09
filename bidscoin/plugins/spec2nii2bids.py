"""
This module contains the interface with spec2nii to convert MRS data to BIDS:

- test:                 A test routine for the plugin + its bidsmap options. Can also be called by the user from the bidseditor GUI
- is_sourcefile:        A routine to assess whether the file is of a valid dataformat for this plugin
- get_attribute:        A routine for reading an attribute from a sourcefile
- bidsmapper_plugin:    A routine that can be called by the bidsmapper to make a bidsmap of the source data
- bidscoiner_plugin:    A routine that can be called by the bidscoiner to convert the source data to bids

See also:
- https://github.com/wexeee/spec2nii
"""

import logging
import shutil
import json
import pandas as pd
import dateutil.parser
import ast
from pathlib import Path
try:
    from bidscoin import bidscoin, bids
except ImportError:
    import bidscoin, bids     # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger(__name__)

# The default options that are set when installing the plugin
OPTIONS = {'command': 'spec2nii',   # Command to run spec2nii, e.g. "module add spec2nii; spec2nii" or "PATH=/opt/spec2nii/bin:$PATH; spec2nii" or /opt/spec2nii/bin/spec2nii or '"C:\Program Files\spec2nii\spec2nii.exe"' (note the quotes to deal with the whitespace)
           'args': None,            # Argument string that is passed to spec2nii (see spec2nii -h for more information)
           'anon': 'y',             # Set this anonymization flag to 'y' to round off age and discard acquisition date from the meta data
           'multiraid': 2}          # The mapVBVD argument for selecting the multiraid Twix file to load (default = 2, i.e. 2nd file)


def test(options: dict) -> bool:
    """
    This plugin shell tests the working of the spec2nii2bids plugin + its bidsmap options

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']['spec2nii2bids']
    :return:        True if the tool generated the expected result, False if there was a tool error, None if not tested
    """

    LOGGER.info('Testing the spec2nii2bids installation:')

    if 'command' not in options:
        LOGGER.error(f"The expected 'command' key is not defined in the spec2nii2bids options")
        return False
    if 'args' not in options:
        LOGGER.warning(f"The expected 'args' key is not defined in the spec2nii2bids options")

    # Test the spec2nii installation
    return bidscoin.run_command(f"{options['command']} -h")


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
    elif suffix == '.7':
        return 'Pfile'

    return ''


def get_attribute(dataformat: str, sourcefile: Path, attribute: str, options: dict) -> str:
    """
    This plugin function reads attributes from the supported sourcefile

    :param dataformat:  The dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which key-value data needs to be read
    :param attribute:   The attribute key for which the value needs to be retrieved
    :param options:     The bidsmap['Options']['spec2nii2bids'] dictionary with the plugin options
    :return:            The retrieved attribute value
    """

    if dataformat in ('Twix', 'SPAR', 'Pfile'):
        LOGGER.debug(f'This is the spec2nii2bids-plugin get_attribute routine, reading the {dataformat} "{attribute}" attribute value from "{sourcefile}"')
    else:
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


def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
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
    plugin = {'spec2nii2bids': bidsmap_new['Options']['plugins']['spec2nii2bids']}

    # Update the bidsmap with the info from the source files
    for sourcefile in [file for file in session.rglob('*') if is_sourcefile(file)]:

        datasource = bids.DataSource(sourcefile, plugin)
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
                LOGGER.info(f"Found '{datasource.datatype}' {dataformat} sample: {sourcefile}")

            # Now work from the provenance store
            if store:
                targetfile        = store['target']/sourcefile.relative_to(store['source'])
                targetfile.parent.mkdir(parents=True, exist_ok=True)
                run['provenance'] = str(shutil.copy2(sourcefile, targetfile))

            # Copy the filled-in run over to the new bidsmap
            bids.append_run(bidsmap_new, run)

        else:
            # Communicate with the user if the run was already present in bidsmap_old or in template
            LOGGER.debug(f"Known '{datasource.datatype}' {dataformat} sample: {sourcefile}")


def bidscoiner_plugin(session: Path, bidsmap: dict, bidsses: Path) -> None:
    """
    This wrapper funtion around spec2nii converts the MRS data in the session folder and saves it in the bidsfolder.
    Each saved datafile should be accompanied with a json sidecar file. The bidsmap options for this plugin can be found in:

    bidsmap_new['Options']['plugins']['spec2nii2bids']

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsses:     The full-path name of the BIDS output `sub-/ses-` folder
    :return:            Nothing
    """

    # Get the subject identifiers and the BIDS root folder from the bidsses folder
    if bidsses.name.startswith('ses-'):
        bidsfolder = bidsses.parent.parent
        subid      = bidsses.parent.name
        sesid      = bidsses.name
    else:
        bidsfolder = bidsses.parent
        subid      = bidsses.name
        sesid      = ''

    # Get started and see what dataformat we have
    options     = bidsmap['Options']['plugins']['spec2nii2bids']
    datasource  = bids.get_datasource(session, {'spec2nii2bids':options})
    dataformat  = datasource.dataformat
    sourcefiles = [file for file in session.rglob('*') if is_sourcefile(file)]
    if not sourcefiles:
        LOGGER.info(f"No {__name__} sourcedata found in: {session}")
        return

    # Read or create a scans_table and tsv-file
    scans_tsv = bidsses/f"{subid}{bids.add_prefix('_',sesid)}_scans.tsv"
    if scans_tsv.is_file():
        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
    else:
        scans_table = pd.DataFrame(columns=['acq_time'], dtype='str')
        scans_table.index.name = 'filename'

    # Loop over all MRS source data files and convert them to BIDS
    for sourcefile in sourcefiles:

        # Get a data source, a matching run from the bidsmap
        datasource = bids.DataSource(sourcefile, {'spec2nii2bids':options})
        run, index = bids.get_matching_run(datasource, bidsmap, runtime=True)

        # Check if we should ignore this run
        if datasource.datatype in bidsmap['Options']['bidscoin']['ignoretypes']:
            LOGGER.info(f"Leaving out: {sourcefile}")
            continue

        # Check that we know this run
        if index is None:
            LOGGER.error(f"Skipping unknown '{datasource.datatype}' run: {sourcefile}\n-> Re-run the bidsmapper and delete the MRS output data in {bidsses} to solve this warning")
            continue

        LOGGER.info(f"Processing: {sourcefile}")

        # Create the BIDS session/datatype output folder
        outfolder = bidsses/datasource.datatype
        outfolder.mkdir(parents=True, exist_ok=True)

        # Compose the BIDS filename using the matched run
        bidsname  = bids.get_bidsname(subid, sesid, run, runtime=True)
        runindex  = run['bids'].get('run', '')
        if runindex.startswith('<<') and runindex.endswith('>>'):
            bidsname = bids.increment_runindex(outfolder, bidsname)
        jsonfile  = (outfolder/bidsname).with_suffix('.json')

        # Check if file already exists (-> e.g. when a static runindex is used)
        if jsonfile.is_file():
            LOGGER.warning(f"{outfolder/bidsname}.* already exists and will be deleted -- check your results carefully!")
            for ext in ('.nii.gz', '.nii', '.json', '.bval', '.bvec', '.tsv.gz'):
                (outfolder/bidsname).with_suffix(ext).unlink(missing_ok=True)

        # Run spec2nii to convert the source-files in the run folder to nifti's in the BIDS-folder
        arg  = ''
        args = options.get('args', OPTIONS['args'])
        if args is None:
            args = ''
        if dataformat == 'SPAR':
            dformat = 'philips'
            arg     = f'"{sourcefile.with_suffix(".SDAT")}"'
        elif dataformat == 'Twix':
            dformat = 'twix'
            arg     = '-e image'
        elif dataformat == 'Pfile':
            dformat = 'ge'
        else:
            LOGGER.exception(f"Unsupported dataformat: {dataformat}")
        command = options.get("command", "spec2nii")
        if not bidscoin.run_command(f'{command} {dformat} -j -f "{bidsname}" -o "{outfolder}" {args} {arg} "{sourcefile}"'):
            if not list(outfolder.glob(f"{bidsname}.nii*")): continue

        # Load and adapt the newly produced json sidecar-file (NB: assumes every nifti-file comes with a json-file)
        with jsonfile.open('r') as json_fid:
            jsondata = json.load(json_fid)

        # Add all the meta data to the json-file
        for metakey, metaval in run['meta'].items():
            metaval = datasource.dynamicvalue(metaval, cleanup=False, runtime=True)
            try: metaval = ast.literal_eval(str(metaval))
            except (ValueError, SyntaxError): pass
            LOGGER.info(f"Adding '{metakey}: {metaval}' to: {jsonfile}")
            if not metaval:
                metaval = None
            jsondata[metakey] = metaval

        # Save the meta data to disk
        with jsonfile.open('w') as json_fid:
            json.dump(jsondata, json_fid, indent=4)

        # Parse the acquisition time from the source header or else from the json file (NB: assuming the source file represents the first acquisition)
        if datasource.datatype not in bidsmap['Options']['bidscoin']['bidsignore'] and not run['bids']['suffix'] in bids.get_derivatives(datasource.datatype):
            acq_time = ''
            if dataformat == 'SPAR':
                acq_time = datasource.attributes('scan_date')
            elif dataformat == 'Twix':
                acq_time = f"{datasource.attributes('AcquisitionDate')}T{datasource.attributes('AcquisitionTime')}"
            elif dataformat == 'Pfile':
                acq_time = f"{datasource.attributes('rhr_rh_scan_date')}T{datasource.attributes('rhr_rh_scan_time')}"
            if not acq_time or acq_time == 'T':
                acq_time = f"1925-01-01T{jsondata.get('AcquisitionTime','')}"
            try:
                acq_time = dateutil.parser.parse(acq_time)
                if options.get('anon',OPTIONS['anon']) in ('y','yes'):
                    acq_time = acq_time.replace(year=1925, month=1, day=1)      # Privacy protection (see BIDS specification)
                acq_time = acq_time.isoformat()
            except Exception as jsonerror:
                LOGGER.warning(f"Could not parse the acquisition time from: {sourcefile}\n{jsonerror}")
                acq_time = 'n/a'
            scans_table.loc[sourcefile.relative_to(bidsses).as_posix(), 'acq_time'] = acq_time

    # Write the scans_table to disk
    LOGGER.info(f"Writing acquisition time data to: {scans_tsv}")
    scans_table.sort_values(by=['acq_time','filename'], inplace=True)
    scans_table.replace('','n/a').to_csv(scans_tsv, sep='\t', encoding='utf-8', na_rep='n/a')

    # Collect personal data from a source header
    personals = {}
    if sesid and 'session_id' not in personals:
        personals['session_id'] = sesid
    age = ''
    if sesid and 'session_id' not in personals:
        personals['session_id'] = sesid
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
        age = dateutil.parser.parse(datasource.attributes('rhr_rh_scan_date')) - dateutil.parser.parse(datasource.attributes('rhe_dateofbirth'))
        age = str(age.days) + 'D'
    if age.endswith('D'):   age = float(age.rstrip('D')) / 365.2524
    elif age.endswith('W'): age = float(age.rstrip('W')) / 52.1775
    elif age.endswith('M'): age = float(age.rstrip('M')) / 12
    elif age.endswith('Y'): age = float(age.rstrip('Y'))
    if age and options.get('anon',OPTIONS['anon']) in ('y','yes'):
        age = int(float(age))
    personals['age'] = str(age)

    # Store the collected personals in the participants_table
    participants_tsv = bidsfolder/'participants.tsv'
    if participants_tsv.is_file():
        participants_table = pd.read_csv(participants_tsv, sep='\t', dtype=str)
        participants_table.set_index(['participant_id'], verify_integrity=True, inplace=True)
    else:
        participants_table = pd.DataFrame()
        participants_table.index.name = 'participant_id'
    if subid in participants_table.index and 'session_id' in participants_table.keys() and participants_table.loc[subid, 'session_id']:
        return                                          # Only take data from the first session -> BIDS specification
    for key in personals:           # TODO: Check that only values that are consistent over sessions go in the participants.tsv file, otherwise put them in a sessions.tsv file
        if key not in participants_table or participants_table[key].isnull().get(subid, True) or participants_table[key].get(subid) == 'n/a':
            participants_table.loc[subid, key] = personals[key]

    # Write the collected data to the participants tsv-file
    LOGGER.info(f"Writing {subid} subject data to: {participants_tsv}")
    participants_table.replace('','n/a').to_csv(participants_tsv, sep='\t', encoding='utf-8', na_rep='n/a')
