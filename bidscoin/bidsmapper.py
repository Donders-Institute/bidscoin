#!/usr/bin/env python
"""
Creates a bidsmap.yaml YAML file in the bidsfolder/code/bidscoin that maps the information
from all raw source data to the BIDS labels. You can check and edit the bidsmap file with
the bidseditor (but also with any text-editor) before passing it to the bidscoiner. See the
bidseditor help for more information and useful tips for running the bidsmapper in interactive
mode (which is the default).

N.B.: Institute users may want to use a site-customized template bidsmap (see the
--template option). The bidsmap_dccn template from the Donders Institute can serve as
an example (or may even mostly work for other institutes out of the box).
"""

# Global imports (plugin modules may be imported when needed)
import textwrap
import copy
import logging
import sys
import shutil
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QMessageBox
try:
    from bidscoin import bids, bidseditor
except ImportError:
    import bids, bidseditor         # This should work if bidscoin was not pip-installed


LOGGER = logging.getLogger('bidscoin')


def build_bidsmap(dataformat: str, sourcefile: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict, gui: object) -> dict:
    """
    All the logic to map the Philips PAR/XML fields onto bids labels go into this function

    :param dataformat:  The information source in the bidsmap that is used, e.g. 'DICOM'
    :param sourcefile:  The full-path name of the source file
    :param bidsmap_new: The bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param template:    The bidsmap template with the default heuristics
    :param gui:         If not None, the user will not be asked for help if an unknown run is encountered
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not sourcefile.name or (not template[dataformat] and not bidsmap_old[dataformat]):
        LOGGER.info(f"No {dataformat} source information found in the bidsmap and template")
        return bidsmap_new

    # See if we can find a matching run in the old bidsmap
    run, modality, index = bids.get_matching_run(sourcefile, bidsmap_old, dataformat)

    # If not, see if we can find a matching run in the template
    if index is None:
        run, modality, _ = bids.get_matching_run(sourcefile, template, dataformat)

    # See if we have collected the run in our new bidsmap
    if not bids.exist_run(bidsmap_new, dataformat, '', run):

        # Now work from the provenance store
        if store:
            targetfile        = store['target']/sourcefile.relative_to(store['source'])
            targetfile.parent.mkdir(parents=True, exist_ok=True)
            sourcefile        = Path(shutil.copy2(sourcefile, targetfile))
            run['provenance'] = str(sourcefile.resolve())

        # Communicate with the user if the run was not present in bidsmap_old or in template, i.e. that we found a new sample
        LOGGER.info(f"Found '{modality}' {dataformat} sample: {sourcefile}")

        # Copy the filled-in run over to the new bidsmap
        bidsmap_new = bids.append_run(bidsmap_new, dataformat, modality, run)

        # Launch a GUI to ask the user for help if the new run comes from the template (i.e. was not yet in the old bidsmap)
        if gui and gui.interactive==2 and index is None:

            # Open the interactive edit window to get the new mapping
            dialog_edit = bidseditor.EditDialog(dataformat, sourcefile, modality, bidsmap_new, template, gui.subprefix, gui.sesprefix)
            dialog_edit.exec()

            # Get the result
            if dialog_edit.result() == 1:           # The user has finished the edit
                bidsmap_new = dialog_edit.target_bidsmap
            elif dialog_edit.result() in [0, 2]:    # The user has canceled / aborted the edit
                answer = QMessageBox.question(None, 'BIDSmapper', 'Do you want to abort and quit the bidsmapper?',
                                              QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if answer==QMessageBox.No:
                    pass
                if answer==QMessageBox.Yes:
                    LOGGER.info('User has quit the bidsmapper')
                    sys.exit()

            else:
                LOGGER.debug(f'Unexpected result {dialog_edit.result()} from the edit dialog')

    return bidsmap_new


def build_niftimap(session: Path, bidsmap_new: dict, bidsmap_old: dict) -> dict:
    """
    All the logic to map nifti-info onto bids labels go into this function

    :param session:     The full-path name of the source folder containing nifti-files
    :param bidsmap_new: The bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not session or not bidsmap_old['Nifti']:
        return bidsmap_new

    # TODO: Loop through all bidsmodalities and runs

    return bidsmap_new


def build_filesystemmap(session: Path, bidsmap_new: dict, bidsmap_old: dict) -> dict:
    """
    All the logic to map filesystem-info onto bids labels go into this function

    :param session:     The full-path name of the source folder
    :param bidsmap_new: The bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not session or not bidsmap_old['FileSystem']:
        return bidsmap_new

    # TODO: Loop through all bidsmodalities and runs

    return bidsmap_new


def build_pluginmap(session: Path, bidsmap_new: dict, bidsmap_old: dict) -> dict:
    """
    Call the plugin to map info onto bids labels

    :param session:     The full-path name of the source folder
    :param bidsmap_new: The bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not session or not bidsmap_new['PlugIns']:
        return bidsmap_new

    for plugin in bidsmap_new['PlugIns']:

        # Load and run the plugin-module
        module = bids.import_plugin(plugin)
        if 'bidsmapper_plugin' in dir(module):
            LOGGER.debug(f"Running plug-in: {plugin}.bidsmapper_plugin('{session}', bidsmap_new, bidsmap_old)")
            bidsmap_new = module.bidsmapper_plugin(session, bidsmap_new, bidsmap_old)

    return bidsmap_new


def bidsmapper(rawfolder: str, bidsfolder: str, bidsmapfile: str, templatefile: str, subprefix: str='sub-', sesprefix: str='ses-', store: bool=False, interactive: bool=True) -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder
    and that generates a maximally filled-in bidsmap.yaml file in bidsfolder/code/bidscoin.
    Folders in sourcefolder are assumed to contain a single dataset.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param bidsmapfile:     The name of the bidsmap YAML-file
    :param templatefile:    The name of the bidsmap template YAML-file
    :param subprefix:       The prefix common for all source subject-folders
    :param sesprefix:       The prefix common for all source session-folders
    :param store:           If True, the provenance samples will be stored
    :param interactive:     If True, the user will be asked for help if an unknown run is encountered
    :return:bidsmapfile:    The name of the mapped bidsmap YAML-file
    """

    # Input checking
    rawfolder      = Path(rawfolder).resolve()
    bidsfolder     = Path(bidsfolder).resolve()
    bidsmapfile    = Path(bidsmapfile)
    templatefile   = Path(templatefile)
    bidscoinfolder = bidsfolder/'code'/'bidscoin'
    if store:
        store = dict(source=rawfolder, target=bidscoinfolder/'provenance')
    else:
        store = dict()

    # Start logging
    bids.setup_logging(bidscoinfolder/'bidsmapper.log')
    LOGGER.info('')
    LOGGER.info('-------------- START BIDSmapper ------------')
    LOGGER.info(f">>> bidsmapper sourcefolder={rawfolder} bidsfolder={bidsfolder} bidsmap={bidsmapfile} "
                f" template={templatefile} subprefix={subprefix} sesprefix={sesprefix} store={store} interactive={interactive}")

    # Get the heuristics for filling the new bidsmap
    bidsmap_old, _ = bids.load_bidsmap(bidsmapfile,  bidscoinfolder)
    template, _    = bids.load_bidsmap(templatefile, bidscoinfolder)

    # Create the new bidsmap as a copy / bidsmap skeleton with no modality entries (i.e. bidsmap with empty lists)
    if bidsmap_old:
        bidsmap_new = copy.deepcopy(bidsmap_old)
    else:
        bidsmap_new = copy.deepcopy(template)
    for logic in ('DICOM', 'PAR', 'P7', 'Nifti', 'FileSystem'):
        for modality in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):
            if bidsmap_new[logic] and modality in bidsmap_new[logic]:
                bidsmap_new[logic][modality] = None

    # Start with an empty skeleton if we didn't have an old bidsmap
    if not bidsmap_old:
        bidsmap_old = copy.deepcopy(bidsmap_new)

    # Start the Qt-application
    gui = interactive
    if gui:
        app = QApplication(sys.argv)
        app.setApplicationName('BIDS editor')
        mainwin = bidseditor.MainWindow()
        gui = bidseditor.Ui_MainWindow()
        gui.interactive = interactive
        gui.subprefix = subprefix
        gui.sesprefix = sesprefix

        if gui.interactive == 2:
            QMessageBox.information(mainwin, 'BIDS mapping workflow',
                                    f"The bidsmapper will now scan {bidsfolder} and whenever "
                                    f"it detects a new type of scan it will ask you to identify it.\n\n"
                                    f"It is important that you choose the correct BIDS modality "
                                    f"(e.g. 'anat', 'dwi' or 'func') and suffix (e.g. 'bold' or 'sbref').\n\n"
                                    f"At the end you will be shown an overview of all the "
                                    f"different scan types and BIDScoin options (as in the "
                                    f"bidseditor) that you can then (re)edit to your needs")

    # Loop over all subjects and sessions and built up the bidsmap entries
    dataformat = ''
    subjects   = bids.lsdirs(rawfolder, subprefix + '*')
    if not subjects:
        LOGGER.warning(f'No subjects found in: {rawfolder/subprefix}*')
        gui = None
    for n, subject in enumerate(subjects,1):

        sessions = bids.lsdirs(subject, sesprefix + '*')
        if not sessions:
            sessions = [subject]
        for session in sessions:

            # Unpack the data in a temporary folder if it is tarballed/zipped and/or contains a DICOMDIR file
            session, unpacked = bids.unpack(session, subprefix, sesprefix, '*')
            if unpacked:
                store = dict(source=unpacked, target=bidscoinfolder/'provenance')

            # Loop of the different DICOM runs (series) and collect source files
            sourcefiles = []
            dataformat  = bids.get_dataformat(session)
            if not dataformat:
                LOGGER.info(f"Skipping: {session} (subject {n}/{len(subjects)})")
                continue

            LOGGER.info(f"Parsing: {session} (subject {n}/{len(subjects)})")

            if dataformat=='DICOM':
                for sourcedir in bids.lsdirs(session):
                    sourcefile = bids.get_dicomfile(sourcedir)
                    if sourcefile.name:
                        sourcefiles.append(sourcefile)

            if dataformat=='PAR':
                sourcefiles = bids.get_parfiles(session)

            if dataformat=='P7':
                sourcefiles = bids.get_p7file(session)

            # Update the bidsmap with the info from the source files
            for sourcefile in sourcefiles:
                bidsmap_new = build_bidsmap(dataformat, sourcefile, bidsmap_new, bidsmap_old, template, store, gui)

            # Update / append the nifti mapping
            if dataformat=='Nifti':
                bidsmap_new = build_niftimap(session, bidsmap_new, bidsmap_old)

            # Update / append the file-system mapping
            if dataformat=='FileSystem':
                bidsmap_new = build_filesystemmap(session, bidsmap_new, bidsmap_old)

            # Update / append the plugin mapping
            if bidsmap_old['PlugIns']:
                bidsmap_new = build_pluginmap(session, bidsmap_new, bidsmap_old)

            # Clean-up the temporary unpacked data
            if unpacked:
                shutil.rmtree(session)

    # Save the bidsmap in the bidscoinfolder
    bidsmapfile = bidscoinfolder/'bidsmap.yaml'
    bids.save_bidsmap(bidsmapfile, bidsmap_new)

    # (Re)launch the bidseditor UI_MainWindow
    if not dataformat:
        LOGGER.warning('Could not determine the dataformat of the source data')
    if gui:
        if not dataformat:
            QMessageBox.information(mainwin, 'BIDS mapping workflow',
                                    'Could not determine the dataformat of the source data.\n'
                                    'You can try running the bidseditor tool yourself')
        else:
            QMessageBox.information(mainwin, 'BIDS mapping workflow',
                                    f"The bidsmapper has finished scanning {rawfolder}\n\n"
                                    f"Please carefully check all the different BIDS output names "
                                    f"and BIDScoin options and (re)edit them to your needs.\n\n"
                                    f"You can always redo this step later by re-running the "
                                    f"bidsmapper or by just running the bidseditor tool")

            LOGGER.info('Opening the bidseditor')
            gui.setupUi(mainwin, bidsfolder, bidsmapfile, bidsmap_new, copy.deepcopy(bidsmap_new), template, dataformat, subprefix=subprefix, sesprefix=sesprefix)
            mainwin.show()
            app.exec()

    LOGGER.info('-------------- FINISHED! -------------------')
    LOGGER.info('')

    bids.reporterrors()


def main():
    """Console script usage"""

    # Parse the input arguments and run bidsmapper(args)
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidsmapper /project/foo/raw /project/foo/bids\n'
                                            '  bidsmapper /project/foo/raw /project/foo/bids -t bidsmap_dccn\n ')
    parser.add_argument('sourcefolder',       help='The study root folder containing the raw data in sub-#/[ses-#/]data subfolders (or specify --subprefix and --sesprefix for different prefixes)')
    parser.add_argument('bidsfolder',         help='The destination folder with the (future) bids data and the bidsfolder/code/bidscoin/bidsmap.yaml output file')
    parser.add_argument('-b','--bidsmap',     help='The bidsmap YAML-file with the study heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-t','--template',    help='The bidsmap template with the default heuristics (this could be provided by your institute). If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap_template.yaml', default='bidsmap_template.yaml')
    parser.add_argument('-n','--subprefix',   help="The prefix common for all the source subject-folders. Default: 'sub-'", default='sub-')
    parser.add_argument('-m','--sesprefix',   help="The prefix common for all the source session-folders. Default: 'ses-'", default='ses-')
    parser.add_argument('-s','--store',       help="Flag to store the provenance data samples in the bidsfolder/'code'/'provenance' folder", action='store_true')
    parser.add_argument('-i','--interactive', help='{0}: The sourcefolder is scanned for different kinds of scans without any user interaction. {1}: The sourcefolder is scanned for different kinds of scans and, when finished, the resulting bidsmap is opened using the bidseditor. {2}: As {1}, except that already during scanning the user is asked for help if a new and unknown run is encountered. This option is most useful when re-running the bidsmapper (e.g. when the scan protocol was changed since last running the bidsmapper). Default: 1', type=int, choices=[0,1,2], default=1)
    parser.add_argument('-v','--version',     help='Show the BIDS and BIDScoin version', action='version', version=f'BIDS-version:\t\t{bids.bidsversion()}\nBIDScoin-version:\t{bids.version()}')
    args = parser.parse_args()

    bidsmapper(rawfolder    = args.sourcefolder,
               bidsfolder   = args.bidsfolder,
               bidsmapfile  = args.bidsmap,
               templatefile = args.template,
               subprefix    = args.subprefix,
               sesprefix    = args.sesprefix,
               store        = args.store,
               interactive  = args.interactive)


if __name__ == "__main__":
    main()
