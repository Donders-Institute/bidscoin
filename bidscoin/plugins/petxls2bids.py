"""
This module contains the interface with pet2bids to add or correct the PET meta data produced by dcm2niix.


See also:
- https://github.com/openneuropet/PET2BIDS
"""

import logging
import pandas as pd
import json
from typing import Union
from pathlib import Path
from functools import lru_cache
try:
    from bidscoin import bidscoin, bids
except ImportError:
    import bidscoin, bids     # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger(__name__)

# The default options that are set when installing the plugin
OPTIONS = {'anon': 'y'}                                 # Set this anonymization flag to 'y' to round off age and discard acquisition date from the meta data


def test(options) -> bool:
    """
    Performs shell tests of dcm2niix

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']['dcm2niix2bids']
    :return:        True if the tool generated the expected result, False if there was a tool error
    """

    LOGGER.info('Testing pet2bidscoin is not implemented (yet):')

    return True


@lru_cache(maxsize=4096)
def is_sourcefile(file: Path) -> str:
    """
    This plugin function supports assessing whether the file is a valid sourcefile

    :param file:    The file that is assessed
    :return:        The valid dataformat of the file for this plugin
    """

    if file.suffix.lower().startswith('.xls'):
        data = pd.read_excel(file)
        if "PatientID" in data:
            return 'PET2BIDS'

    return ''


def get_attribute(dataformat: str, sourcefile: Path, attribute: str, options: dict) -> Union[str, int]:
    """
    This plugin supports reading attributes from DICOM and PAR dataformats

    :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which the attribute value should be read
    :param attribute:   The attribute key for which the value should be read
    :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
    :return:            The attribute value
    """
    if dataformat == 'PET2BIDS':

        data = pd.read_excel(sourcefile)

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
    plugin     = {'pet2bidscoin': bidsmap['Options']['plugins']['pet2bidscoin']}
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

            # Load the Excel data. TODO: Discuss this with Anthony and Cyril
            metadata = pd.read_excel(file)

            # Load the json sidecar data (there should be only one)
            jsonfile = sorted((bidsses/'pet').rglob('*.json'))
            if len(jsonfile) > 1:
                LOGGER.error(f"Found ambiguous PET sidecar files: {jsonfile}")
                return
            with jsonfile[0].open('r') as json_fid:
                jsondata = json.load(json_fid)

            # Add the meta-data. TODO: implement this once we know how `metadata` is organised
            for key in metadata:
                jsondata[key] = metadata[key]

            # Save the meta-data to the json sidecar file
            with jsonfile[0].open('w') as json_fid:
                json.dump(jsondata, json_fid, indent=4)
