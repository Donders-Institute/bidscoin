#!/usr/bin/env python3
"""A BIDScoin application to create a study bidsmap (See also cli/_bidsmapper.py)"""

# NB: Set os.environ['DUECREDIT'] values as early as possible to capture all credits
import os
import sys
if __name__ == "__main__" and os.getenv('DUECREDIT_ENABLE','').lower() not in ('1', 'yes', 'true') and len(sys.argv) > 2:    # Ideally the due state (`self.__active=True`) should also be checked (but that's impossible)
    os.environ['DUECREDIT_ENABLE'] = 'yes'
    os.environ['DUECREDIT_FILE']   = os.path.join(sys.argv[2], 'code', 'bidscoin', '.duecredit_bidsmapper.p')   # NB: argv[2] = bidsfolder

import copy
import logging
import shutil
import re
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    sys.path.append(str(Path(__file__).parents[1]))
from bidscoin import bcoin, bids, lsdirs, trackusage, check_version, __version__
from bidscoin.bids import BidsMap

_, uptodate, versionmessage = check_version()


def bidsmapper(sourcefolder: str, bidsfolder: str, bidsmap: str, template: str, plugins: list, subprefix: str, sesprefix: str, unzip: str, store: bool=False, automated: bool=False, force: bool=False, no_update: bool=False) -> BidsMap:
    """
    Main function that processes all the subjects and session in the sourcefolder and that generates a fully filled-in bidsmap.yaml
    file in bidsfolder/code/bidscoin. Folders in sourcefolder are assumed to contain a single dataset.

    :param sourcefolder: The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:   The name of the BIDS root folder
    :param bidsmap:      The name of the bidsmap YAML-file
    :param template:     The name of the bidsmap template YAML-file
    :param plugins:      Optional list of plugins that should be used (overrules the list in the study/template bidsmaps)
    :param subprefix:    The prefix common for all source subject-folders
    :param sesprefix:    The prefix common for all source session-folders
    :param unzip:        Wildcard pattern to select tar/zip-files in the session folder. Leave empty to use the bidsmap value
    :param store:        If True, the provenance samples will be stored
    :param automated:    The bidseditor will not be launched if True
    :param no_update:    Do not update any sub/sesprefixes in or prepend the sourcefolder name to the <<filepath:regex>> expression
    :param force:        If True, the previous bidsmap and logfiles will be deleted
    :return:             The new bidsmap
    """

    # Input checking
    rawfolder      = Path(sourcefolder).resolve()
    bidsfolder     = Path(bidsfolder).resolve()
    bidsmapfile    = Path(bidsmap)
    templatefile   = Path(template)
    bidscoinfolder = bidsfolder/'code'/'bidscoin'
    if [char for char in subprefix or '' if char in ('^', '$', '+', '{', '}', '[', ']', '\\', '|', '(', ')')]:
        LOGGER.bcdebug(f"Regular expression metacharacters found in {subprefix}, this may cause errors later on...")
    if [char for char in sesprefix or '' if char in ('^', '$', '+', '{', '}', '[', ']', '\\', '|', '(', ')')]:
        LOGGER.bcdebug(f"Regular expression metacharacters found in {sesprefix}, this may cause errors later on...")
    if not rawfolder.is_dir():
        raise SystemExit(f"\n[ERROR] Exiting the program because your sourcefolder argument '{sourcefolder}' was not found")
    if not templatefile.is_file():
        raise SystemExit(f"\n[ERROR] Exiting the program because your template bidsmap '{templatefile}' was not found")

    # Start logging
    if force:
        try:
            (bidscoinfolder/'bidsmapper.log').unlink(missing_ok=True)
        except (IOError, OSError) as unlinkerr:
            LOGGER.bcdebug(f"Could not delete: {bidscoinfolder/'bidsmapper.log'}\n{unlinkerr}")
    bcoin.setup_logging(bidscoinfolder/'bidsmapper.log')
    LOGGER.info('')
    LOGGER.info('-------------- START BIDSmapper ------------')
    LOGGER.info(f">>> bidsmapper sourcefolder={rawfolder} bidsfolder={bidsfolder} bidsmap={bidsmapfile} "
                f"template={templatefile} plugins={plugins} subprefix={subprefix} sesprefix={sesprefix} store={store} force={force}")

    # Get the heuristics for filling the new bidsmap (NB: plugins are stored in the bidsmaps)
    bidsmap_old = BidsMap(bidsmapfile,  bidscoinfolder, plugins)
    template    = BidsMap(templatefile, plugins=plugins, checks=(True, True, False))
    template.check_template()

    # Create the new bidsmap as a copy / bidsmap skeleton with only data types without run-items (i.e. empty lists)
    if force and bidsmap_old.filepath.name:
        LOGGER.info(f"Deleting previous bidsmap: {bidsmap_old.filepath}")
        bidsmap_old.filepath.unlink()
        bidsmap_old.filepath = Path()
    bidsmap_new          = copy.deepcopy(bidsmap_old if bidsmap_old.filepath.name else template)
    bidsmap_new.delete_runs()
    bidsmap_new.filepath = bidsmapfile
    template.options     = bidsmap_new.options      # Always use the options of the new bidsmap
    template.plugins     = bidsmap_new.plugins      # Always use the plugins of the new bidsmap
    if unzip:
        bidsmap_new.options['unzip'] = unzip
    else:
        unzip = bidsmap_new.options.get('unzip','')

    # Store/retrieve the empty or user-defined sub-/ses-prefix. The new bidsmap is now ready to be populated
    subprefix, sesprefix = setprefix(bidsmap_new, subprefix, sesprefix, rawfolder, update = not no_update)

    # Start with an empty skeleton if we don't have an old bidsmap (due to loading failure or deletion by force)
    if not bidsmap_old.filepath.name:
        bidsmap_old = copy.deepcopy(bidsmap_new)

    # Import the data scanning plugins
    plugins = [bcoin.import_plugin(plugin, ('bidsmapper_plugin',)) for plugin in bidsmap_new.plugins]
    plugins = [plugin for plugin in plugins if plugin]          # Filter the empty items from the list
    if not plugins:
        LOGGER.warning(f"The plugins listed in your bidsmap['Options'] did not have a usable `bidsmapper_plugin` function, nothing to do")
        LOGGER.info('-------------- FINISHED! ------------')
        LOGGER.info('')
        return bidsmap_new

    # Loop over all subjects and sessions and built up the bidsmap entries
    subjects = lsdirs(rawfolder, ('' if subprefix=='*' else subprefix) + '*')
    if not subjects:
        LOGGER.warning(f'No subjects found in: {rawfolder/subprefix}*')
    with logging_redirect_tqdm():
        for n, subject in enumerate(tqdm(subjects, unit='subject', colour='green', leave=False), 1):

            sessions = lsdirs(subject, ('' if sesprefix=='*' else sesprefix) + '*')
            if not sessions or (subject/'DICOMDIR').is_file():
                sessions = [subject]
            for session in sessions:

                LOGGER.info(f"Mapping: {session} (subject {n}/{len(subjects)})")

                # Unpack the data in a temporary folder if it is tarballed/zipped and/or contains a DICOMDIR file
                sesfolders, unpacked = bids.unpack(session, unzip)
                for sesfolder in sesfolders:
                    if store:
                        bidsmap_new.store = {'source': sesfolder.parent.parent.parent.parent if unpacked else rawfolder.parent,
                                             'target': bidscoinfolder/'provenance'}

                    # Run the bidsmapper plugins
                    for module in plugins:
                        LOGGER.verbose(f"Executing plugin: {Path(module.__file__).stem} -> {sesfolder}")
                        trackusage(Path(module.__file__).stem)
                        module.bidsmapper_plugin(sesfolder, bidsmap_new, bidsmap_old, template)

                    # Clean-up the temporary unpacked data
                    if unpacked:
                        shutil.rmtree(sesfolder)

    # Save the new study bidsmap in the bidscoinfolder or launch the bidseditor UI_MainWindow
    if automated:
        bidsmap_new.save()

    else:
        LOGGER.info('Opening the bidseditor')
        from PyQt6 import QtCore, QtGui
        from PyQt6.QtWidgets import QApplication, QMessageBox
        try:
            from bidscoin import bidseditor
        except ImportError:
            import bidseditor       # This should work if bidscoin was not pip-installed
        app = QApplication(sys.argv)
        app.setApplicationName(f"{bidsmap_new.filepath} - BIDS editor {__version__}")

        mainwin = bidseditor.MainWindow(bidsfolder, bidsmap_new, template)
        mainwin.show()

        if not bidsmap_new.filepath.name or not uptodate:
            messagebox = QMessageBox(mainwin)
            messagebox.setText(f"The bidsmapper has finished scanning {rawfolder}\n\n"
                               f"Please carefully check all the different BIDS output names "
                               f"and BIDScoin options and (re)edit them to your needs.\n\n"
                               f"You can always redo this step later by re-running the "
                               f"bidsmapper or by just running the bidseditor tool\n\n"
                               f"{versionmessage}")
            messagebox.setWindowTitle('About the BIDS-mapping workflow')
            messagebox.setIconPixmap(QtGui.QPixmap(str(bidseditor.BIDSCOIN_LOGO)).scaled(150, 150, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))
            messagebox.setWindowFlags(messagebox.windowFlags() & ~QtCore.Qt.WindowType.WindowMinMaxButtonsHint)
            messagebox.show()

        app.exec()

    LOGGER.info('-------------- FINISHED! -------------------')
    LOGGER.info('')

    bcoin.reporterrors()

    return bidsmap_new


def setprefix(bidsmap: BidsMap, subprefix: str, sesprefix: str, rawfolder: Path, update: bool=True) -> tuple:
    """
    Set the prefix in the Options, subject, session

    :param bidsmap:     The bidsmap with the data
    :param subprefix:   The subprefix (take value from bidsmap if empty)
    :param sesprefix:   The sesprefix (take value from bidsmap if empty)
    :param rawfolder:   The root folder-name of the sub/ses/data/file tree containing the source data files
    :param update:      Update the prefixes in and prepend the rawfolder.name in the subject/session regex: <<filepath:>> to <<filepath:/{rawfolder.name}>>
    :return:            A (subprefix, sesprefix) tuple
    """

    # Get/set the sub-/ses-prefixes in the 'Options'
    oldsubprefix = bidsmap.options.get('subprefix','')
    oldsesprefix = bidsmap.options.get('sesprefix','')
    if not subprefix:
        subprefix = oldsubprefix                                # Use the default value from the bidsmap
    if not sesprefix:
        sesprefix = oldsesprefix                                # Use the default value from the bidsmap
    bidsmap.options['subprefix'] = subprefix
    bidsmap.options['sesprefix'] = sesprefix

    # Update the bidsmap dataformat sections
    reprefix = lambda prefix: '' if prefix=='*' else re.escape(prefix).replace(r'\-','-')
    for dataformat in bidsmap.dataformats:

        # Replace the sub-/ses-prefixes in the dynamic filepath values of bidsmap[dataformat]['subject'] and ['session']
        if update and dataformat.subject.startswith('<<filepath:'):
            if oldsubprefix:
                dataformat.subject = dataformat.subject.replace(reprefix(oldsubprefix), reprefix(subprefix))    # TODO: Not very robust for short prefixes :-(
            else:
                LOGGER.warning(f"Could not update the bidsmap subject label expression: {dataformat.subject}")
            if not dataformat.subject.startswith(f"<<filepath:/{rawfolder.name}"):    # NB: Don't prepend the fullpath of rawfolder because of potential data unpacking in /tmp
                dataformat.subject = dataformat.subject.replace('<<filepath:', f"<<filepath:/{rawfolder.name}")
        if update and dataformat.session.startswith('<<filepath:'):
            if oldsesprefix:
                dataformat.session = dataformat.session.replace(reprefix(oldsubprefix), reprefix(subprefix)).replace(reprefix(oldsesprefix), reprefix(sesprefix))       # TODO: Not very robust for short prefixes :-(
            else:
                LOGGER.warning(f"Could not update the bidsmap session label expression: {dataformat.session}")
            if not dataformat.session.startswith(f"<<filepath:/{rawfolder.name}"):
                dataformat.session = dataformat.session.replace('<<filepath:', f"<<filepath:/{rawfolder.name}")

    return subprefix, sesprefix


def main():
    """Console script entry point"""

    from bidscoin.cli._bidsmapper import get_parser

    # Parse the input arguments and run bidsmapper(args)
    args = get_parser().parse_args()

    trackusage('bidsmapper')
    try:
        bidsmapper(**vars(args))

    except Exception as error:
        trackusage('bidsmapper_exception')
        raise error


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
