#!/usr/bin/env python
"""
Creates a bidsmap.yaml YAML file in the bidsfolde/code that maps the information from
all raw source data to the BIDS labels. You can check and edit the bidsmap file with
the bidseditor (but also with any text-editor) before passing it to the bidscoiner
N.B.: Institute users may want to use a site-customized template bidsmap (see the
--template option).
"""

# Global imports (specific modules may be imported when needed)
import os.path
import textwrap
import copy
import logging
import sys
from ruamel.yaml import YAML
yaml = YAML()
try:
    from bidscoin import bids
    from bidscoin import bidseditor
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed
    import bidseditor

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox

LOGGER = logging.getLogger('bidscoin')


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        actionQuit = QtWidgets.QAction("Quit", self)
        actionQuit.triggered.connect(self.closeEvent)

    def closeEvent(self, event):
        """Handle exit. """
        LOGGER.info('User-editing done')
        QApplication.quit()


class View_Ui_MainWindow(bidseditor.Ui_MainWindow):

    def setupUi(self, *args, **kwargs):
        """Make sure the user cannot edit a list item"""
        super().setupUi(*args, **kwargs)

    def set_tab_options(self):
        """Sets a view-only version of the Options tab"""
        super().set_tab_options()

    def set_tab_bidsmap(self):
        """Sets a view-only version of the BIDS-map tab"""
        super().set_tab_bidsmap()

    def update_list(self, *args, **kwargs):
        """User has finished editting (clicked OK)"""
        super().update_list(*args, **kwargs)


def built_dicommap(dicomfile: str, bidsmap: dict, heuristics: dict, gui: object) -> dict:
    """
    All the logic to map dicom-attributes (fields/tags) onto bids-labels go into this function

    :param dicomfile:   The full-path name of the source dicom-file
    :param bidsmap:     The bidsmap as we had it
    :param heuristics:  Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param gui:         If not None, the user will not be asked for help if an unknown series is encountered
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not dicomfile or not heuristics['DICOM']:
        return bidsmap

    # Get the matching series
    series, modality, index = bids.get_matching_dicomseries(dicomfile, heuristics)

    # Copy the filled-in attributes series over to the output bidsmap
    if not bids.exist_series(bidsmap, 'DICOM', modality, series):
        bidsmap = bids.append_series(bidsmap, 'DICOM', modality, series)

    # Check if we know this series
    if modality == bids.unknownmodality:
        LOGGER.info('Unknown modality found: ' + dicomfile)

        # If not, launch a GUI to ask the user for help
        if gui:

            # Update the index after the bids.append_series()
            series, modality, index = bids.get_matching_dicomseries(dicomfile, bidsmap)

            # Open a view-only version of the main window
            if gui.interactive == 2:
                gui.MainWindow.show()
                gui.setupUi(gui.MainWindow, gui.bidsfolder, gui.sourcefolder, gui.bidsmap_filename, bidsmap, bidsmap, gui.template_bidsmap)

            # Open the edit window to get the mapping
            gui.has_edit_dialog_open = True
            dialog_edit = bidseditor.EditDialog(index, modality, bidsmap, gui.template_bidsmap)
            dialog_edit.exec()

            if dialog_edit.result() == 0:
                LOGGER.info(f'The user has canceled the edit')
                exit()
            elif dialog_edit.result() == 1:
                LOGGER.info(f'The user has finished the edit')
                bidsmap = dialog_edit.bidsmap
            elif dialog_edit.result() == 2:
                LOGGER.info(f'The user has aborted the edit')

    return bidsmap


def built_parmap(parfile: str, bidsmap: dict, heuristics: dict) -> dict:
    """
    All the logic to map PAR/REC fields onto bids labels go into this function

    :param parfile:     The full-path name of the source PAR-file
    :param bidsmap:     The bidsmap as we had it
    :param heuristics:  Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not parfile or not heuristics['PAR']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_p7map(p7file: str, bidsmap: dict, heuristics: dict) -> dict:
    """
    All the logic to map P*.7-fields onto bids labels go into this function

    :param p7file:      The full-path name of the source P7-file
    :param bidsmap:     The bidsmap as we had it
    :param heuristics:  Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not p7file or not heuristics['P7']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_niftimap(niftifile: str, bidsmap: dict, heuristics: dict) -> dict:
    """
    All the logic to map nifti-info onto bids labels go into this function

    :param niftifile:   The full-path name of the source nifti-file
    :param bidsmap:     The bidsmap as we had it
    :param heuristics:  Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param automatic:   If True, the user will not be asked for help if an unknown series is encountered
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not niftifile or not heuristics['Nifti']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_filesystemmap(seriesfolder: str, bidsmap: dict, heuristics: dict) -> dict:
    """
    All the logic to map filesystem-info onto bids labels go into this function

    :param seriesfolder:    The full-path name of the source folder
    :param bidsmap:         The bidsmap as we had it
    :param heuristics:      Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param automatic:       If True, the user will not be asked for help if an unknown series is encountered
    :return:                The bidsmap with new entries in it
    """

    # Input checks
    if not seriesfolder or not heuristics['FileSystem']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_pluginmap(seriesfolder: str, bidsmap: dict, heuristics: dict) -> dict:
    """
    Call the plugin to map info onto bids labels

    :param seriesfolder:    The full-path name of the source folder
    :param bidsmap:         The bidsmap as we had it
    :param heuristics:      Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmap with new entries in it
    """

    # Input checks
    if not seriesfolder or not bidsmap['PlugIn']:
        return bidsmap

    # Import and run the plugin modules
    from importlib import util

    for plugin in bidsmap['PlugIn']:

        # Get the full path to the plugin-module
        if os.path.basename(plugin)==plugin:
            plugin = os.path.join(os.path.dirname(__file__),'plugins', plugin)
        else:
            plugin = plugin
        plugin = os.path.abspath(os.path.expanduser(plugin))
        if not os.path.isfile(plugin):
            LOGGER.warning('Could not find: ' + plugin)
            continue

        # Load and run the plugin-module
        spec   = util.spec_from_file_location('bidscoin_plugin', plugin)
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if 'bidsmapper_plugin' in dir(module):
            LOGGER.info(f'Running: {plugin}.bidsmapper_plugin({seriesfolder}, {bidsmap}, {heuristics})')
            bidsmap = module.bidsmapper_plugin(seriesfolder, bidsmap, heuristics)

    return bidsmap


def bidsmapper(rawfolder: str, bidsfolder: str, bidsmapfile: str, subprefix: str='sub-', sesprefix: str='ses-', interactive: bool=True) -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder
    and that generates a maximally filled-in bidsmap.yaml file in bidsfolder/code.
    Folders in sourcefolder are assumed to contain a single dataset.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param bidsmapfile:     The name of the bidsmap YAML-file
    :param subprefix:       The prefix common for all source subject-folders
    :param sesprefix:       The prefix common for all source session-folders
    :param interactive:     If True, the user will be asked for help if an unknown series is encountered
    :return:bidsmapfile:    The name of the mapped bidsmap YAML-file
    """

    # Input checking
    rawfolder  = os.path.abspath(os.path.expanduser(rawfolder))
    bidsfolder = os.path.abspath(os.path.expanduser(bidsfolder))

    # Start logging
    bids.setup_logging(os.path.join(bidsfolder, 'code', 'bidsmapper.log'))
    LOGGER.info('------------ START BIDSmapper ------------')

    # Get the heuristics for creating the bidsmap
    heuristics, bidsmapfile = bids.load_bidsmap(bidsmapfile, os.path.join(bidsfolder,'code'))
    template, _             = bids.load_bidsmap()  # TODO: make this a user input

    # Create a copy / bidsmap skeleton with no modality entries (i.e. bidsmap with empty lists)
    bidsmap = copy.deepcopy(heuristics)
    for logic in ('DICOM', 'PAR', 'P7', 'Nifti', 'FileSystem'):
        for modality in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):

            if bidsmap[logic] and modality in bidsmap[logic]:
                bidsmap[logic][modality] = None

    # Start the Qt-application
    gui = interactive
    if gui:
        app = QApplication(sys.argv)
        app.setApplicationName("BIDS editor")
        mainwin = MainWindow()
        gui = View_Ui_MainWindow()
        gui.interactive = interactive
        gui.MainWindow = mainwin
        gui.setupUi(mainwin, bidsfolder, rawfolder, bidsmapfile, bidsmap, bidsmap, template)
        QMessageBox.information(mainwin, 'bidsmapper workflow',
                                f"The bidsmapper will now scan {bidsfolder} and whenever it detects a new type of scan it will "
                                f"ask you to identify it.\n\nIt is important that you choose the correct BIDS modality (e.g. "
                                f"'anat', 'dwi' or 'func').\n\nAt the end you will be shown an overview of all identified scan "
                                f"types and BIDScoin options that you can then (re)edit to your needs")

    # Loop over all subjects and sessions and built up the bidsmap entries
    subjects = bids.lsdirs(rawfolder, subprefix + '*')
    for n, subject in enumerate(subjects,1):

        sessions = bids.lsdirs(subject, sesprefix + '*')
        if not sessions: sessions = [subject]
        for session in sessions:

            LOGGER.info(f'Parsing: {session} (subject {n}/{len(subjects)})')

            for series in bids.lsdirs(session):

                # Update / append the dicom mapping
                if heuristics['DICOM']:
                    dicomfile = bids.get_dicomfile(series)
                    bidsmap   = built_dicommap(dicomfile, bidsmap, heuristics, gui)

                # Update / append the PAR/REC mapping
                if heuristics['PAR']:
                    parfile   = bids.get_parfile(series)
                    bidsmap   = built_parmap(parfile, bidsmap, heuristics)

                # Update / append the P7 mapping
                if heuristics['P7']:
                    p7file    = bids.get_p7file(series)
                    bidsmap   = built_p7map(p7file, bidsmap, heuristics)

                # Update / append the nifti mapping
                if heuristics['Nifti']:
                    niftifile = bids.get_niftifile(series)
                    bidsmap   = built_niftimap(niftifile, bidsmap, heuristics)

                # Update / append the file-system mapping
                if heuristics['FileSystem']:
                    bidsmap   = built_filesystemmap(series, bidsmap, heuristics)

                # Update / append the plugin mapping
                if heuristics['PlugIn']:
                    bidsmap   = built_pluginmap(series, bidsmap, heuristics)

    # Create the bidsmap YAML-file in bidsfolder/code
    os.makedirs(os.path.join(bidsfolder,'code'), exist_ok=True)
    bidsmapfile = os.path.join(bidsfolder,'code','bidsmap.yaml')

    # Save the bidsmap to the bidsmap YAML-file
    bids.save_bidsmap(bidsmapfile, bidsmap)

    LOGGER.info('------------ FINISHED! ------------')

    if gui:
        sys.exit(app.exec_())


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run bidsmapper(args)
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidsmapper.py /project/foo/raw /project/foo/bids\n'
                                            '  bidsmapper.py /project/foo/raw /project/foo/bids -t bidsmap_dccn\n ')
    parser.add_argument('sourcefolder',       help='The source folder containing the raw data in sub-#/ses-#/series format (or specify --subprefix and --sesprefix for different prefixes)')
    parser.add_argument('bidsfolder',         help='The destination folder with the (future) bids data and the default bidsfolder/code/bidsmap.yaml file')
    parser.add_argument('-t','--template',    help='The non-default / site-specific bidsmap template file with the BIDS heuristics')
    parser.add_argument('-n','--subprefix',   help="The prefix common for all the source subject-folders. Default: 'sub-'", default='sub-')
    parser.add_argument('-m','--sesprefix',   help="The prefix common for all the source session-folders. Default: 'ses-'", default='ses-')
    parser.add_argument('-i','--interactive', help='If not zero, then the user will be asked for help if an unknown series is encountered. Default: 1', type=int, choices=[0,1,2], default=1)
    args = parser.parse_args()

    bidsmapper(rawfolder   = args.sourcefolder,
               bidsfolder  = args.bidsfolder,
               bidsmapfile = args.template,
               subprefix   = args.subprefix,
               sesprefix   = args.sesprefix,
               interactive = args.interactive)
