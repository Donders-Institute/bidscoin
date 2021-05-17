"""
This module contains placeholder code demonstrating the bidscoin plugin API, both for the bidsmapper and for
the bidscoiner. The functions in this module are called if the basename of this module (when located in the
plugins-folder; otherwise the full path must be provided) is listed in the bidsmap. The presence of the
plugin functions is optional but should be named:

- test:                 A test routine for the plugin + its bidsmap options. Can be called in the bidseditor
- is_sourcefile:        A routine to assess whether the file is of a valid dataformat for this plugin
- get_attribute:        A routine for reading an attribute from a sourcefile
- bidsmapper_plugin:    A routine that can be called by the bidsmapper to make a bidsmap of the source data
- bidscoiner_plugin:    A routine that can be called by the bidscoiner to convert the source data to bids
"""

import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def test(options: dict) -> bool:
    """
    An internal routine to test the working of the plugin + its bidsmap options

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
    :return:        True if the test was successful
    """

    LOGGER.debug(f'This is a demo-plugin test routine, validating its working with options: {options}')

    return True


def is_sourcefile(file: Path) -> str:
    """
    This plugin function supports assessing whether the file is a valid sourcefile

    :param file:    The file that is assessed
    :return:        The valid dataformat of the file for this plugin
    """

    if file.is_file():

        LOGGER.debug(f'This is a demo-plugin is_sourcefile routine, assessing whether "{file}" has a valid dataformat')
        return 'dataformat'

    return ''



def get_attribute(dataformat: str, sourcefile: Path, attribute: str) -> str:
    """
    This plugin function supports reading attributes from DICOM and PAR dataformats

    :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which the attribute value should be read
    :param attribute:   The attribute key for which the value should be read
    :return:            The attribute value
    """

    if dataformat in ('DICOM','PAR'):
        LOGGER.debug(f'This is a demo-plugin get_attribute routine, reading the {dataformat} "{attribute}" attribute value from "{sourcefile}"')

    return ''


def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
    """
    All the logic to map the Philips PAR/XML fields onto bids labels go into this plugin function. The function is
    expecte to update / append new runs to the bidsmap_new data structure. The bidsmap options for this plugin can
    be found in:

    bidsmap_new/old['Options']['plugins']['README']

    See e.g. dcm2bidsmap.py for an example implementation

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The study bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param template:    The template bidsmap with the default heuristics
    :param store:       The paths of the source- and target-folder
    :return:
    """

    LOGGER.debug(f'This is a bidsmapper demo-plugin working on: {session}')


def bidscoiner_plugin(session: Path, bidsmap: dict, bidsfolder: Path, personals: dict, subprefix: str, sesprefix: str) -> None:
    """
    The plugin to convert the runs in the source folder and save them in the bids folder. Each saved datafile should be
    accompanied with a json sidecar file. The bidsmap options for this plugin can be found in:

    bidsmap_new/old['Options']['plugins']['README']

    See e.g. dcm2niix2bids.py for an example implementation

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :param subprefix:   The prefix common for all source subject-folders
    :param sesprefix:   The prefix common for all source session-folders
    :return:            Nothing
    """

    LOGGER.debug(f'This is a bidscoiner demo-plugin working on: {session} -> {bidsfolder}')
