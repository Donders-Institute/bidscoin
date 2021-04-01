"""
This function contains placeholder code demonstrating the bidscoin plugin API, both for bidsmapper.py and for
bidscoiner.py. Enter the name of this module (default location is the plugins-folder; otherwise the full path
must be provided) in the bidsmap dictionary file to import the plugin functions in this module, e.g. "README.py"
or "myplugin.py". The functions in this module should be named "bidsmapper_plugin" for bidsmapper.py and
"bidscoiner_plugin" for bidscoiner.py
"""

import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
    """
    All the logic to map the Philips PAR/XML fields onto bids labels go into this function

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The study bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param template:    The template bidsmap with the default heuristics
    :param store:       The paths of the source- and target-folder
    :return:
    """

    LOGGER.debug(f'This is a bidsmapper demo-plugin working on: {session}')
    return


def bidscoiner_plugin(session: Path, bidsmap: dict, bidsfolder: Path, personals: dict, subprefix: str, sesprefix: str) -> None:
    """
    The plugin to cast the series into the bids folder

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :param subprefix:   The prefix common for all source subject-folders
    :param sesprefix:   The prefix common for all source session-folders
    :return:            Nothing
    """

    LOGGER.debug(f'This is a bidscoiner demo-plugin working on: {session} -> {bidsfolder}')
