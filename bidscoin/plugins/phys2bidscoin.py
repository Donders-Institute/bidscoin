"""
This module contains the interface with phys2bids, both for the bidsmapper and for the bidscoiner:

- test:                 A test routine for the plugin + its bidsmap options. Can also be called by the user from the bidseditor GUI
- is_sourcefile:        A routine to assess whether the file is of a valid dataformat for this plugin
- get_attribute:        A routine for reading an attribute from a sourcefile
- bidsmapper_plugin:    A routine that can be called by the bidsmapper to make a bidsmap of the source data
- bidscoiner_plugin:    A routine that can be called by the bidscoiner to convert the source data to bids

See also:
- https://github.com/ohbm/hackathon2021/issues/12
"""

try:
    import phys2bids
except ImportError:
    pass
import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def test(options: dict) -> bool:
    """
    This plugin function tests the working of the plugin + its bidsmap options

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
    :return:        True if the test was successful
    """

    LOGGER.debug(f'This is the phys2bids-plugin test routine, validating its working with options: {options}')

    return True


def is_sourcefile(file: Path) -> str:
    """
    This plugin function assesses whether a sourcefile is of a supported dataformat

    :param file:    The sourcefile that is assessed
    :return:        The valid / supported dataformat of the sourcefile
    """

    if file.is_file():

        LOGGER.debug(f'This is the phys2bids-plugin is_sourcefile routine, assessing whether "{file}" has a valid dataformat')
        if phys2bids.info:
            return 'Physio'

    return ''



def get_attribute(dataformat: str, sourcefile: Path, attribute: str) -> str:
    """
    This plugin function reads attributes from the supported sourcefile

    :param dataformat:  The dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which key-value data needs to be read
    :param attribute:   The attribute key for which the value needs to be retrieved
    :return:            The retrieved attribute value
    """

    if dataformat == 'Physio':
        LOGGER.debug(f'This is the phys2bids-plugin get_attribute routine, reading the {dataformat} "{attribute}" attribute value from "{sourcefile}"')
    else:
        return ''

    return phys2bids.info(attribute)


def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
    """
    All the heuristics format phys2bids attributes and properties onto bids labels and meta-data go into this plugin function.
    The function is expected to update / append new runs to the bidsmap_new data structure. The bidsmap options for this plugin
    are stored in:

    bidsmap_new['Options']['plugins']['phys2bidscoin']

    See also the dcm2bidsmap plugin for reference implementation

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The study bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure (with all options, BIDS labels and attributes, etc) that was created previously
    :param template:    The template bidsmap with the default heuristics
    :param store:       The paths of the source- and target-folder
    :return:
    """

    LOGGER.debug(f'This is the bidsmapper phys2bids-plugin working on: {session}')


def bidscoiner_plugin(session: Path, bidsmap: dict, bidsfolder: Path, personals: dict) -> None:
    """
    This wrapper funtion around phys2bids converts the physio data in the session folder and saves it in the bidsfolder.
    Each saved datafile should be accompanied with a json sidecar file. The bidsmap options for this plugin can be found in:

    bidsmap_new['Options']['plugins']['phys2bidscoin']

    See also the dcm2niix2bids plugin for reference implementation

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    LOGGER.debug(f'This is the bidscoiner phys2bids-plugin working on: {session} -> {bidsfolder}')
