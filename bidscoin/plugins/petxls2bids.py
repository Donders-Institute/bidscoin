"""
This module contains the interface with pet2bids to add or correct the PET meta data produced by dcm2niix.


See also:
- https://github.com/openneuropet/PET2BIDS
"""

import logging
import pandas as pd
import json
import pypet2bids as pet
import subprocess
from typing import Union
from pathlib import Path
from functools import lru_cache

import pypet2bids.helper_functions

try:
    from bidscoin import bidscoin, bids
except ImportError:
    import bidscoin, bids     # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger(__name__)

# The default options that are set when installing the plugin
OPTIONS = {'anon': 'y'}                     # Set this anonymization flag to 'y' to round off age and discard acquisition date from the meta data


def test(options) -> bool:
    """
    Performs shell tests of pypet2bids

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']['dcm2niix2bids']
    :return:        True if the tool generated the expected result, False if there was a tool error
    """

    LOGGER.info('Testing petxls2bids:')
    check = subprocess.run('dcm2niix4pet -h', capture_output=True, shell=True)
    if check.returncode == 0:
        return True
    else:
        return False


@lru_cache(maxsize=4096)
def is_sourcefile(file: Path) -> str:
    """
    This plugin function supports assessing whether the file is a valid sourcefile

    :param file:    The file that is assessed
    :return:        The valid dataformat of the file for this plugin
    """

    if file.suffix.lower().startswith('.xls'):
        data = pet.helper_functions.single_spreadsheet_reader(file)
        try:
            with open(pet.helper_functions.pet_metadata_json, 'r') as pet_field_requirements_json:
                pet_field_requirements = json.load(pet_field_requirements_json)
        except (FileNotFoundError, json.JSONDecodeError) as error:
            logging.error(f"Unable to load list of required, recommended, and optional PET BIDS fields from"
                          f" {pet.helper_functions.pet_metadata_json}, will not be able to determine if {file} contains"
                          f" PET BIDS specific metadata")
            raise error

        mandatory_fields = pet_field_requirements.get('mandatory', [])
        recommended_fields = pet_field_requirements.get('recommended', [])
        optional_fields = pet_field_requirements.get('optional', [])
        intersection = set(mandatory_fields + recommended_fields + optional_fields) & set(data.keys())

        # 3 seems like a reasonable amount of fields to determine whether the spreadsheet is a pet recording
        if len(intersection) > 3:
            return 'PETXLS'

    return ''


def get_attribute(dataformat: str, sourcefile: Path, attribute: str, options: dict) -> Union[str, int]:
    """
    This plugin supports reading attributes from the PET Excel file

    :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. PETXLS
    :param sourcefile:  The sourcefile from which the attribute value should be read
    :param attribute:   The attribute key for which the value should be read
    :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
    :return:            The attribute value
    """
    if dataformat == 'PETXLS':

        data = pet.helper_functions.single_spreadsheet_reader(sourcefile)

        return data.get(attribute)


def bidscoiner_plugin(session: Path, bidsmap: dict, bidsses: Path) -> None:
    """
    The bidscoiner plugin to add the PET meta data in the excel file to the json-file

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsses:     The full-path name of the BIDS output `ses-` folder
    :return:            Nothing
    """

    # Get started and see what data format we have
    plugin     = {'petxls2bids': bidsmap['Options']['plugins']['petxls2bids']}
    datasource = bids.get_datasource(session, plugin)
    dataformat = datasource.dataformat
    if not dataformat:
        LOGGER.info(f"No {__name__} sourcedata found in: {session}")
        return

    n = 0
    for file in sorted(session.iterdir()):
        if is_sourcefile(file):

            # Check if there is only one Excel file and one sidecar file (as expected in PET)
            n += 1
            if n > 1:
                LOGGER.error(f"Found ambiguous PET meta data file: {file}")
                return

            # Load the json sidecar data (there should be only one)
            jsonfile = sorted((bidsses/'pet').rglob('*.json'))
            if len(jsonfile) > 1:
                LOGGER.error(f"Found ambiguous PET sidecar files: {jsonfile}")
                return
            with jsonfile[0].open('r') as json_fid:
                jsondata = json.load(json_fid)

            # Load the Excel data and combine it with the existing sidecar json data
            metadata = pypet2bids.helper_functions.single_spreadsheet_reader(path_to_spreadsheet=file,
                                                                             metadata=jsondata)

            # Save the meta-data to the json sidecar file
            with jsonfile[0].open('w') as json_fid:
                json.dump(metadata, json_fid, indent=4, default=str)
