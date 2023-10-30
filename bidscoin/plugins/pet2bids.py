"""
The 'pet2bids' plugin is a wrapper around the `PET2BIDS <https://github.com/openneuropet/PET2BIDS>`__ tool. PET2BIDS accepts
PET imaging and blood data as inputs (e.g. DICOM, ECAT, spreadsheets) and delivers BIDS formatted outputs. An installation
of dcm2niix (https://github.com/rordenlab/dcm2niix) is required to convert DICOM data.


See also:
- https://pet2bids.readthedocs.io
"""

import logging
import shutil
import subprocess
import pandas as pd
import json
from typing import Union
from pathlib import Path
from functools import lru_cache
from bids_validator import BIDSValidator
from bidscoin import bcoin, bids, lsdirs

LOGGER = logging.getLogger(__name__)

# The default options that are set when installing the plugin
OPTIONS = {'command': 'dcm2niix4pet',
           'args': '',
           'anon': 'y',
           'meta': ['.json', '.tsv', '.xls', '.xlsx']}

# ---------------------------------------------------------
LOGGER.warning('The pet2bids plugin is still experimental')
# ---------------------------------------------------------


def test(options=None) -> int:
    """
    Performs shell tests of pypet2bids

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']['dcm2niix2bids']
    :return:        The errorcode (e.g 0 if the tool generated the expected result, > 0 if there was a tool error)
    """

    # LOGGER.info('Testing the dcm2niix4pet installation:')
    # check = subprocess.run('dcm2niix4pet -h', capture_output=True, shell=True)

    return 0     # check.returncode


@lru_cache(maxsize=4096)
def is_sourcefile(file: Path) -> str:
    """
    This plugin function supports assessing whether the file is a valid sourcefile

    :param file:    The file that is assessed
    :return:        The valid dataformat of the file for this plugin
    """

    # if file.suffix.lower().startswith('.xls') or file.suffix.lower().startswith('.tsv') or file.suffix.lower().startswith('.csv'):
    #     data = pet.helper_functions.single_spreadsheet_reader(file)
    #     try:
    #         with open(pet.helper_functions.pet_metadata_json, 'r') as pet_field_requirements_json:
    #             pet_field_requirements = json.load(pet_field_requirements_json)
    #     except (FileNotFoundError, json.JSONDecodeError) as error:
    #         logging.error(f"Unable to load list of required, recommended, and optional PET BIDS fields from"
    #                       f" {pet.helper_functions.pet_metadata_json}, will not be able to determine if {file} contains"
    #                       f" PET BIDS specific metadata")
    #         raise error
    #
    #     mandatory_fields = pet_field_requirements.get('mandatory', [])
    #     recommended_fields = pet_field_requirements.get('recommended', [])
    #     optional_fields = pet_field_requirements.get('optional', [])
    #     intersection = set(mandatory_fields + recommended_fields + optional_fields) & set(data.keys())
    #
    #     # 3 seems like a reasonable amount of fields to determine whether the spreadsheet is a pet recording
    #     if len(intersection) > 3:
    #         return 'PETXLS'

    if bids.is_dicomfile(file) and bids.get_dicomfield('Modality', file) == 'PT':
        return 'DICOM'

    return ''


def get_attribute(dataformat: str, sourcefile: Path, attribute: str, options: dict = {}) -> Union[str, int]:
    """
    This plugin supports reading attributes from the PET Excel sidecar file

    :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. DICOM
    :param sourcefile:  The sourcefile from which the attribute value should be read
    :param attribute:   The attribute key for which the value should be read
    :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
    :return:            The attribute value
    """

    for ext in options['meta']:
        if sourcefile.with_suffix(ext).is_file():
            LOGGER.warning(f"Reading metadata from an '{ext}' sidecar file is not implemented yet...")
            #  data = pet.helper_functions.single_spreadsheet_reader(sourcefile)
            #
            #  return data.get(attribute)

    if dataformat == 'DICOM':
        return bids.get_dicomfield(attribute, sourcefile)

    # TODO: add ecat support

    return ''


def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
    """
    All the logic to map the DICOM and spreadsheet source fields onto bids labels go into this function

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The new study bidsmap that we are building
    :param bidsmap_old: The previous study bidsmap that has precedence over the template bidsmap
    :param template:    The template bidsmap with the default heuristics
    :param store:       The paths of the source- and target-folder
    :return:
    """

    # Get started
    plugin     = {'pet2bids': bidsmap_new['Options']['plugins']['pet2bids']}
    datasource = bids.get_datasource(session, plugin)
    dataformat = datasource.dataformat
    if not dataformat:
        return

    # Collect the different DICOM/PAR source files for all runs in the session
    sourcefiles = []
    if dataformat == 'DICOM':
        for sourcedir in lsdirs(session, '**/*'):
            for n in range(1):      # Option: Use range(2) to scan two files and catch e.g. magnitude1/2 fieldmap files that are stored in one Series folder (but bidscoiner sees only the first file anyhow, and it makes bidsmapper 2x slower :-()
                sourcefile = bids.get_dicomfile(sourcedir, n)
                if sourcefile.name and is_sourcefile(sourcefile):
                    sourcefiles.append(sourcefile)

    else:
        LOGGER.exception(f"Unsupported dataformat '{dataformat}'")

    # Update the bidsmap with the info from the source files
    for sourcefile in sourcefiles:

        # Input checks
        if not template[dataformat] and not bidsmap_old[dataformat]:
            LOGGER.error(f"No {dataformat} source information found in the study and template bidsmap for: {sourcefile}")
            return

        # See if we can find a matching run in the old bidsmap
        datasource = bids.DataSource(sourcefile, plugin, dataformat)
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


def bidscoiner_plugin(session: Path, bidsmap: dict, bidsses: Path) -> None:
    """
    The bidscoiner plugin to run dcm2niix4pet, this will run dcm2niix4pet on session folders
    containing PET dicoms and include metadata from meta-dataspreadsheets if present

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsses:     The full-path name of the BIDS output `ses-` folder
    :return:            Nothing
    """

    # Get the subject identifiers and the BIDS root folder from the bidsses folder
    if bidsses.name.startswith('ses-'):
        bidsfolder = bidsses.parent.parent
        subid = bidsses.parent.name
        sesid = bidsses.name
    else:
        bidsfolder = bidsses.parent
        subid = bidsses.name
        sesid = ''

    # Get started and see what data format we have
    options = bidsmap['Options']['plugins']['pet2bids']
    datasource = bids.get_datasource(session, {'pet2bids': options})
    dataformat = datasource.dataformat
    if not dataformat:
        LOGGER.info(f"No {__name__} sourcedata found in: {session}")
        return

    # make a list of all the data sources / runs
    manufacturer = 'UNKOWN'
    sources = []
    if dataformat == 'DICOM':
        sources = lsdirs(session, '**/*')
        manufacturer = datasource.attributes('Manufacturer')
    else:
        LOGGER.exception(f"Unsupported dataformat '{dataformat}'")

    # Read or create a scans_table and tsv-file
    scans_tsv = bidsses/f"{subid}{'_' + sesid if sesid else ''}_scans.tsv"
    scans_table = pd.DataFrame()
    if scans_tsv.is_file():
        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
        print('debug')
    if scans_table.empty:
        scans_table = pd.DataFrame(columns=['acq_time'], dtype='str')
        scans_table.index.name = 'filename'

        # Process all the source files or run subfolders
        sourcefile = Path()
        for source in sources:

            # Get a sourcefile
            if dataformat == 'DICOM':
                sourcefile = bids.get_dicomfile(source)
            if not sourcefile.name or not is_sourcefile(sourcefile):
                continue

            # Get a matching run from the bidsmap
            datasource = bids.DataSource(sourcefile, {'pet2bids': options}, dataformat)
            run, match = bids.get_matching_run(datasource, bidsmap, runtime=True)

            # Check if we should ignore this run
            if datasource.datatype in bidsmap['Options']['bidscoin']['ignoretypes']:
                LOGGER.info(f"--> Leaving out: {source}")
                continue

            # Check if we already know this run
            if not match:
                LOGGER.error(f"--> Skipping unknown '{datasource.datatype}' run: {sourcefile}\n"
                             f"Re-run the bidsmapper and delete {bidsses} to solve this warning")
                continue

            LOGGER.info(f"--> Coining: {source}")

            # Create the BIDS session/datatype output folder
            suffix = datasource.dynamicvalue(run['bids']['suffix'], True, True)
            if suffix in bids.get_derivatives(datasource.datatype):
                outfolder = bidsfolder/'derivatives'/manufacturer.replace(' ', '')/subid/sesid/datasource.datatype
            else:
                outfolder = bidsses/datasource.datatype
            outfolder.mkdir(parents=True, exist_ok=True)

            # Compose the BIDS filename using the matched run
            bidsignore = bids.check_ignore(datasource.datatype, bidsmap['Options']['bidscoin']['bidsignore'])
            bidsname   = bids.get_bidsname(subid, sesid, run, not bidsignore, runtime=True)
            bidsignore = bidsignore or bids.check_ignore(bidsname+'.json', bidsmap['Options']['bidscoin']['bidsignore'], 'file')
            bidsname   = bids.increment_runindex(outfolder, bidsname, run, scans_table)

            # Check if the bidsname is valid
            bidstest = (Path('/')/subid/sesid/datasource.datatype/bidsname).with_suffix('.json').as_posix()
            isbids = BIDSValidator().is_bids(bidstest)
            if not isbids and not bidsignore:
                LOGGER.warning(f"The '{bidstest}' output name did not pass the bids-validator test")

            # Check if file already exists (-> e.g. when a static runindex is used)
            if (outfolder/bidsname).with_suffix('.json').is_file():
                LOGGER.warning(f"{outfolder/bidsname}.* already exists and will be deleted -- check your results carefully!")
                for ext in ('.nii.gz', '.nii', '.json', '.tsv', '.tsv.gz'):
                    (outfolder/bidsname).with_suffix(ext).unlink(missing_ok=True)

            # Convert the source-files in the run folder to nifti's in the BIDS-folder
            else:
                command = f'{options["command"]} "{source}" -d {(outfolder/bidsname).with_suffix(".nii.gz")}'
                # pass in data added via bidseditor/bidsmap
                if len(run.get('meta', {})) > 0:
                    command += ' --kwargs '
                for metadata_key, metadata_value in run.get('meta', {}).items():
                    if metadata_value:
                        command += f' {metadata_key}="{metadata_value}"'
                if bcoin.run_command(command):
                    if not list(outfolder.glob(f"{bidsname}.*nii*")): continue

            # Load / copy over the source meta-data
            sidecar  = (outfolder/bidsname).with_suffix('.json')
            metadata = bids.poolmetadata(sourcefile, sidecar, run['meta'], options['meta'], datasource)
            with sidecar.open('w') as json_fid:
                json.dump(metadata, json_fid, indent=4)

    # Collect personal data from a source header and store it in the participants.tsv file
    if dataformat == 'DICOM':
        personals = {}
        age       = datasource.attributes('PatientAge')     # A string of characters with one of the following formats: nnnD, nnnW, nnnM, nnnY
        if   age.endswith('D'): age = float(age.rstrip('D')) / 365.2524
        elif age.endswith('W'): age = float(age.rstrip('W')) / 52.1775
        elif age.endswith('M'): age = float(age.rstrip('M')) / 12
        elif age.endswith('Y'): age = float(age.rstrip('Y'))
        if age and options.get('anon','y') in ('y','yes'):
            age = int(float(age))
        personals['age']    = str(age)
        personals['sex']    = datasource.attributes('PatientSex')
        personals['size']   = datasource.attributes('PatientSize')
        personals['weight'] = datasource.attributes('PatientWeight')
        bids.addparticipant(bidsfolder/'participants.tsv', subid, sesid, personals)
