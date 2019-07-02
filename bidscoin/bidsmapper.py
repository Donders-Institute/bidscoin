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


class MainWindow(bidseditor.MainWindow):

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


def build_dicommap(dicomfile: str, bidsmap_new: dict, bidsmap_old: dict, template: dict, gui: object) -> dict:
    """
    All the logic to map dicom-attributes (fields/tags) onto bids-labels go into this function

    :param dicomfile:   The full-path name of the source dicom-file
    :param bidsmap_new: The bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param template:    The bidsmap template with the default heuristics
    :param gui:         If not None, the user will not be asked for help if an unknown series is encountered
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not dicomfile or not template['DICOM'] or not bidsmap_old['DICOM']:
        return bidsmap_new

    # See if we can find a matching series in the old bidsmap
    series, modality, index = bids.get_matching_dicomseries(dicomfile, bidsmap_old)

    # If not, see if we can find a matching series in the template
    if modality == bids.unknownmodality:
        series, modality, index = bids.get_matching_dicomseries(dicomfile, template)

    # Copy the filled-in attributes series over to the output bidsmap
    if not bids.exist_series(bidsmap_new, 'DICOM', modality, series):
        bidsmap_new = bids.append_series(bidsmap_new, 'DICOM', modality, series)

    # If we haven't found a matching series, launch a GUI to ask the user for help
    if modality == bids.unknownmodality:
        LOGGER.info('Unknown modality found: ' + dicomfile)

        if gui:
            # Update the index after the bids.append_series()
            series, modality, index = bids.get_matching_dicomseries(dicomfile, bidsmap_new)

            # Open a view-only version of the main window
            if gui.interactive == 2:
                gui.MainWindow.show()
                gui.setupUi(gui.MainWindow, gui.bidsfolder, gui.sourcefolder, gui.bidsmap_filename, bidsmap_new, bidsmap_new, gui.template_bidsmap)
                gui.has_edit_dialog_open = True

            # Open the edit window to get the mapping
            dialog_edit = bidseditor.EditDialog(index, modality, bidsmap_new, gui.template_bidsmap, gui.subprefix, gui.sesprefix)
            dialog_edit.exec()

            if dialog_edit.result() == 0:
                LOGGER.info(f'The user has canceled the edit')
                exit()
            elif dialog_edit.result() == 1:
                LOGGER.info(f'The user has finished the edit')
                bidsmap_new = dialog_edit.bidsmap
            elif dialog_edit.result() == 2:
                LOGGER.info(f'The user has aborted the edit')

    return bidsmap_new


def build_parmap(parfile: str, bidsmap_new: dict, bidsmap_old: dict) -> dict:
    """
    All the logic to map PAR/REC fields onto bids labels go into this function

    :param parfile:     The full-path name of the source PAR-file
    :param bidsmap_new: The bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not parfile or not bidsmap_old['PAR']:
        return bidsmap_new

    # TODO: Loop through all bidsmodalities and series

    return bidsmap_new


def build_p7map(p7file: str, bidsmap_new: dict, bidsmap_old: dict) -> dict:
    """
    All the logic to map P*.7-fields onto bids labels go into this function

    :param p7file:      The full-path name of the source P7-file
    :param bidsmap_new: The bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not p7file or not bidsmap_old['P7']:
        return bidsmap_new

    # TODO: Loop through all bidsmodalities and series

    return bidsmap_new


def build_niftimap(niftifile: str, bidsmap_new: dict, bidsmap_old: dict) -> dict:
    """
    All the logic to map nifti-info onto bids labels go into this function

    :param niftifile:   The full-path name of the source nifti-file
    :param bidsmap_new: The bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param automatic:   If True, the user will not be asked for help if an unknown series is encountered
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not niftifile or not bidsmap_old['Nifti']:
        return bidsmap_new

    # TODO: Loop through all bidsmodalities and series

    return bidsmap_new


def build_filesystemmap(seriesfolder: str, bidsmap_new: dict, bidsmap_old: dict) -> dict:
    """
    All the logic to map filesystem-info onto bids labels go into this function

    :param seriesfolder:    The full-path name of the source folder
    :param bidsmap_new:     The bidsmap that we are building
    :param bidsmap_old:     Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param automatic:       If True, the user will not be asked for help if an unknown series is encountered
    :return:                The bidsmap with new entries in it
    """

    # Input checks
    if not seriesfolder or not bidsmap_old['FileSystem']:
        return bidsmap_new

    # TODO: Loop through all bidsmodalities and series

    return bidsmap_new


def build_pluginmap(seriesfolder: str, bidsmap_new: dict, bidsmap_old: dict) -> dict:
    """
    Call the plugin to map info onto bids labels

    :param seriesfolder:    The full-path name of the source folder
    :param bidsmap_new:     The bidsmap that we are building
    :param bidsmap_old:     Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmap with new entries in it
    """

    # Input checks
    if not seriesfolder or not bidsmap_new['PlugIn']:
        return bidsmap_new

    # Import and run the plugin modules
    from importlib import util

    for plugin in bidsmap_new['PlugIn']:

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
            LOGGER.info(f'Running: {plugin}.bidsmapper_plugin({seriesfolder}, {bidsmap_new}, {bidsmap_old})')
            bidsmap_new = module.bidsmapper_plugin(seriesfolder, bidsmap_new, bidsmap_old)

    return bidsmap_new


def bidsmapper(rawfolder: str, bidsfolder: str, bidsmapfile: str, templatefile: str, subprefix: str='sub-', sesprefix: str='ses-', interactive: bool=True) -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder
    and that generates a maximally filled-in bidsmap.yaml file in bidsfolder/code.
    Folders in sourcefolder are assumed to contain a single dataset.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param bidsmapfile:     The name of the bidsmap YAML-file
    :param templatefile:    The name of the bidsmap template YAML-file
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
    bidsmap_old, bidsmapfile = bids.load_bidsmap(bidsmapfile, os.path.join(bidsfolder,'code'))
    template, templatefile   = bids.load_bidsmap(templatefile, os.path.join(bidsfolder,'code'))

    # Create a copy / bidsmap skeleton with no modality entries (i.e. bidsmap with empty lists)
    bidsmap_new = copy.deepcopy(bidsmap_old)
    for logic in ('DICOM', 'PAR', 'P7', 'Nifti', 'FileSystem'):
        for modality in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):

            if bidsmap_new[logic] and modality in bidsmap_new[logic]:
                bidsmap_new[logic][modality] = None

    # Start the Qt-application
    gui = interactive
    if gui:
        app = QApplication(sys.argv)
        app.setApplicationName("BIDS editor")
        mainwin = MainWindow()
        gui = View_Ui_MainWindow()
        gui.interactive = interactive
        gui.subprefix = subprefix
        gui.sesprefix = sesprefix
        gui.MainWindow = mainwin
        gui.setupUi(mainwin, bidsfolder, rawfolder, bidsmapfile, bidsmap_new, bidsmap_new, template)
        QMessageBox.information(mainwin, 'bidsmapper workflow',
                                f"The bidsmapper will now scan {bidsfolder} and whenever it detects a new type of scan it will "
                                f"ask you to identify it.\n\nIt is important that you choose the correct BIDS modality (e.g. "
                                f"'anat', 'dwi' or 'func').\n\nAt the end you will be shown an overview of all the different scan "
                                f"types and BIDScoin options (i.e. the bidseditor) that you can then (re)edit to your needs")

    # Loop over all subjects and sessions and built up the bidsmap entries
    subjects = bids.lsdirs(rawfolder, subprefix + '*')
    for n, subject in enumerate(subjects,1):

        sessions = bids.lsdirs(subject, sesprefix + '*')
        if not sessions: sessions = [subject]
        for session in sessions:

            LOGGER.info(f'Parsing: {session} (subject {n}/{len(subjects)})')

            for series in bids.lsdirs(session):

                # Update / append the dicom mapping
                if bidsmap_old['DICOM']:
                    dicomfile   = bids.get_dicomfile(series)
                    bidsmap_new = build_dicommap(dicomfile, bidsmap_new, bidsmap_old, template, gui)

                # Update / append the PAR/REC mapping
                if bidsmap_old['PAR']:
                    parfile     = bids.get_parfile(series)
                    bidsmap_new = build_parmap(parfile, bidsmap_new, bidsmap_old)

                # Update / append the P7 mapping
                if bidsmap_old['P7']:
                    p7file      = bids.get_p7file(series)
                    bidsmap_new = build_p7map(p7file, bidsmap_new, bidsmap_old)

                # Update / append the nifti mapping
                if bidsmap_old['Nifti']:
                    niftifile   = bids.get_niftifile(series)
                    bidsmap_new = build_niftimap(niftifile, bidsmap_new, bidsmap_old)

                # Update / append the file-system mapping
                if bidsmap_old['FileSystem']:
                    bidsmap_new = build_filesystemmap(series, bidsmap_new, bidsmap_old)

                # Update / append the plugin mapping
                if bidsmap_old['PlugIn']:
                    bidsmap_new = build_pluginmap(series, bidsmap_new, bidsmap_old)

    # Create the bidsmap YAML-file in bidsfolder/code
    os.makedirs(os.path.join(bidsfolder,'code'), exist_ok=True)
    bidsmapfile = os.path.join(bidsfolder,'code','bidsmap.yaml')

    # Save the bidsmap to the bidsmap YAML-file
    bids.save_bidsmap(bidsmapfile, bidsmap_new)

    LOGGER.info('------------ FINISHED! ------------')

    if gui:
        # Close the GUI and launch the bidseditor
        sys.exit(app.exec_())
        bidseditor.bidseditor(bidsfolder, rawfolder, bidsmapfile=bidsmapfile, templatefile=templatefile, subprefix=subprefix, sesprefix=sesprefix)


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
    parser.add_argument('bidsfolder',         help='The destination folder with the (future) bids data and the default bidsfolder/code/bidsmap.yaml file. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-b','--bidsmap',     help='The bidsmap YAML-file with the study heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/')
    parser.add_argument('-t','--template',    help='The bidsmap template with the default heuristics (this could be provided by your institute). If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/. Default: bidsmap_template.yaml', default='bidsmap_template.yaml')
    parser.add_argument('-n','--subprefix',   help="The prefix common for all the source subject-folders. Default: 'sub-'", default='sub-')
    parser.add_argument('-m','--sesprefix',   help="The prefix common for all the source session-folders. Default: 'ses-'", default='ses-')
    parser.add_argument('-i','--interactive', help='If not zero, then the user will be asked for help if an unknown series is encountered. Default: 1', type=int, choices=[0,1,2], default=1)
    parser.add_argument('-v','--version',     help='Show the BIDS and BIDScoin version', action='version', version=f'BIDS-version:\t\t{bids.bidsversion()}\nBIDScoin-version:\t{bids.version()}')
    args = parser.parse_args()

    bidsmapper(rawfolder    = args.sourcefolder,
               bidsfolder   = args.bidsfolder,
               bidsmapfile  = args.bidsmap,
               templatefile = args.template,
               subprefix    = args.subprefix,
               sesprefix    = args.sesprefix,
               interactive  = args.interactive)
