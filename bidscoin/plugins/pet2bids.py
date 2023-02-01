"""
This module contains the interface with pet2bids to add or correct the PET meta data produced by dcm2niix.


See also:
- https://github.com/openneuropet/PET2BIDS
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
import pydicom

try:
    from bidscoin import bidscoin, bids
except ImportError:
    import bidscoin, bids     # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger(__name__)

# The default options that are set when installing the plugin
OPTIONS = {'command': 'dcm2niix4pet',
           'args': '',
           'anon': 'y',
           'meta': ['.json', '.tsv', '.xls', '.xlsx']}


def test(options=None) -> bool:
    """
    Performs shell tests of pypet2bids

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']['dcm2niix2bids']
    :return:        The errorcode (e.g 0 if the tool generated the expected result, > 0 if there was a tool error)
    """

    LOGGER.info('Testing the dcm2niix4pet installation:')
    check = subprocess.run('dcm2niix4pet -h', capture_output=True, shell=True)

    return check.returncode


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

    if bids.is_dicomfile(file):
        if 'pt' == bids.get_dicomfield('Modality', file).lower():
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
        for sourcedir in bidscoin.lsdirs(session, '**/*'):
            for n in range(1):      # Option: Use range(2) to scan two files and catch e.g. magnitude1/2 fieldmap files that are stored in one Series folder (but bidscoiner sees only the first file anyhow and it makes bidsmapper 2x slower :-()
                sourcefile = bids.get_dicomfile(sourcedir, n)
                if sourcefile.name:
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
                run['provenance']      = str(shutil.copy2(sourcefile, targetfile))
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
        sources = bidscoin.lsdirs(session, '**/*')
        manufacturer = datasource.attributes('Manufacturer')
    else:
        LOGGER.exception(f"Unsupported dataformat '{dataformat}'")

    # Read or create a scans_table and tsv-file
    scans_tsv = bidsses / f"{subid}{'_' + sesid if sesid else ''}_scans.tsv"
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
            if not sourcefile.name:
                continue

            # Get a matching run from the bidsmap
            datasource = bids.DataSource(sourcefile, {'pet2bids': options}, dataformat)
            run, match = bids.get_matching_run(datasource, bidsmap, runtime=True)

            # Check if we should ignore this run
            if datasource.datatype in bidsmap['Options']['bidscoin']['ignoretypes']:
                LOGGER.info(f"--> Leaving out: {source}")
                continue
            bidsignore = datasource.datatype in bidsmap['Options']['bidscoin']['bidsignore']

            # Check if we already know this run
            if not match:
                LOGGER.error(f"--> Skipping unknown '{datasource.datatype}' run: {sourcefile}\n"
                             f"Re-run the bidsmapper and delete {bidsses} to solve this warning")
                continue

            LOGGER.info(f"--> Coining: {source}")

            # Create the BIDS session/datatype output folder
            if run['bids']['suffix'] in bids.get_derivatives(datasource.datatype):
                outfolder = bidsfolder / 'derivatives' / manufacturer.replace(' ', '') / subid / sesid / datasource.datatype
            else:
                outfolder = bidsses / datasource.datatype
            outfolder.mkdir(parents=True, exist_ok=True)

            # Compose the BIDS filename using the matched run
            bidsname = bids.get_bidsname(subid, sesid, run, bidsignore, runtime=True)
            runindex = run['bids'].get('run')
            runindex = str(runindex) if runindex else ''
            if runindex.startswith('<<') and runindex.endswith('>>'):
                bidsname = bids.increment_runindex(outfolder, bidsname)
            jsonfiles = [(outfolder / bidsname).with_suffix('.json')]  # List -> Collect the associated json-files (for updating them later) -- possibly > 1

            # Check if the bidsname is valid
            bidstest = (Path('/') / subid / sesid / datasource.datatype / bidsname).with_suffix('.json').as_posix()
            isbids = BIDSValidator().is_bids(bidstest)
            if not isbids and not bidsignore:
                LOGGER.warning(f"The '{bidstest}' ouput name did not pass the bids-validator test")

            # Check if file already exists (-> e.g. when a static runindex is used)
            if (outfolder / bidsname).with_suffix('.json').is_file():
                LOGGER.warning(f"{outfolder / bidsname}.* already exists and will be deleted -- check your results carefully!")
                for ext in ('.nii.gz', '.nii', '.json', '.tsv', '.tsv.gz'):
                    (outfolder / bidsname).with_suffix(ext).unlink(missing_ok=True)

            # Convert the source-files in the run folder to nifti's in the BIDS-folder
            else:
                command = f'{options["command"]} "{source}" -d {outfolder / Path(bidsname).with_suffix(".nii.gz")}'
                # pass in data added via bidseditor/bidsmap
                if len(run.get('meta', {})) > 0:
                    command += ' --kwargs '
                for metadata_key, metadata_value in run.get('meta', {}).items():
                    if metadata_value:
                        command += f' {metadata_key}={metadata_value}'
                if bidscoin.run_command(command):
                    if not list(outfolder.glob(f"{bidsname}.*nii*")): continue


        # Collect personal data from a source header (PAR/XML does not contain personal info)
        personals = {}
        if sesid and 'session_id' not in personals:
            personals['session_id'] = sesid
        personals['age'] = ''
        if dataformat == 'DICOM':
            age = datasource.attributes(
                'PatientAge')  # A string of characters with one of the following formats: nnnD, nnnW, nnnM, nnnY
            if age.endswith('D'):
                age = float(age.rstrip('D')) / 365.2524
            elif age.endswith('W'):
                age = float(age.rstrip('W')) / 52.1775
            elif age.endswith('M'):
                age = float(age.rstrip('M')) / 12
            elif age.endswith('Y'):
                age = float(age.rstrip('Y'))
            if age:
                if options.get('anon', 'y') in ('y', 'yes'):
                    age = int(float(age))
                personals['age'] = str(age)
            personals['sex'] = datasource.attributes('PatientSex')
            personals['size'] = datasource.attributes('PatientSize')
            personals['weight'] = datasource.attributes('PatientWeight')

        # Store the collected personals in the participants_table
        participants_tsv = bidsfolder / 'participants.tsv'
        if participants_tsv.is_file():
            participants_table = pd.read_csv(participants_tsv, sep='\t', dtype=str)
            participants_table.set_index(['participant_id'], verify_integrity=True, inplace=True)
        else:
            participants_table = pd.DataFrame()
            participants_table.index.name = 'participant_id'
        if subid in participants_table.index and 'session_id' in participants_table.keys() and participants_table.loc[subid, 'session_id']:
            return  # Only take data from the first session -> BIDS specification
        for key in personals:  # TODO: Check that only values that are consistent over sessions go in the participants.tsv file, otherwise put them in a sessions.tsv file
            if key not in participants_table or participants_table[key].isnull().get(subid, True) or participants_table[key].get(subid) == 'n/a':
                participants_table.loc[subid, key] = personals[key]

        # Write the collected data to the participants tsv-file
        LOGGER.verbose(f"Writing {subid} subject data to: {participants_tsv}")
        participants_table.replace('', 'n/a').to_csv(participants_tsv, sep='\t', encoding='utf-8', na_rep='n/a')
