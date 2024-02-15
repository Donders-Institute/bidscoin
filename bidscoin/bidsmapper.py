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
from bidscoin.bids import Bidsmap

_, uptodate, versionmessage = check_version()


def bidsmapper(rawfolder: str, bidsfolder: str, bidsmapfile: str, templatefile: str, plugins: list, subprefix: str, sesprefix: str, unzip: str, store: bool=False, noeditor: bool=False, force: bool=False, noupdate: bool=False) -> dict:
    """
    Main function that processes all the subjects and session in the sourcefolder and that generates a fully filled-in bidsmap.yaml
    file in bidsfolder/code/bidscoin. Folders in sourcefolder are assumed to contain a single dataset.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param bidsmapfile:     The name of the bidsmap YAML-file
    :param templatefile:    The name of the bidsmap template YAML-file
    :param plugins:         Optional list of plugins that should be used (overrules the list in the study/template bidsmaps)
    :param subprefix:       The prefix common for all source subject-folders
    :param sesprefix:       The prefix common for all source session-folders
    :param unzip:           Wildcard pattern to select tar/zip-files in the session folder. Leave empty to use the bidsmap value
    :param store:           If True, the provenance samples will be stored
    :param noeditor:        The bidseditor will not be launched if True
    :param noupdate:        Do not update any sub/sesprefixes in or prepend the rawfolder name to the <<filepath:regex>> expression
    :param force:           If True, the previous bidsmap and logfiles will be deleted
    :return:                The new bidsmap
    """

    # Input checking
    rawfolder      = Path(rawfolder).resolve()
    bidsfolder     = Path(bidsfolder).resolve()
    bidsmapfile    = Path(bidsmapfile)
    templatefile   = Path(templatefile)
    bidscoinfolder = bidsfolder/'code'/'bidscoin'
    if [char for char in subprefix or '' if char in ('^', '$', '+', '{', '}', '[', ']', '\\', '|', '(', ')')]:
        LOGGER.debug(f"Regular expression metacharacters found in {subprefix}, this may cause errors later on...")
    if [char for char in sesprefix or '' if char in ('^', '$', '+', '{', '}', '[', ']', '\\', '|', '(', ')')]:
        LOGGER.debug(f"Regular expression metacharacters found in {sesprefix}, this may cause errors later on...")
    if not rawfolder.is_dir():
        print(f"Rawfolder '{rawfolder}' not found")
        return {}

    # Start logging
    if force:
        try:
            (bidscoinfolder/'bidsmapper.log').unlink(missing_ok=True)
        except (IOError, OSError) as unlinkerr:
            LOGGER.debug(f"Could not delete: {bidscoinfolder/'bidsmapper.log'}\n{unlinkerr}")
    bcoin.setup_logging(bidscoinfolder/'bidsmapper.log')
    LOGGER.info('')
    LOGGER.info('-------------- START BIDSmapper ------------')
    LOGGER.info(f">>> bidsmapper sourcefolder={rawfolder} bidsfolder={bidsfolder} bidsmap={bidsmapfile} "
                f"template={templatefile} plugins={plugins} subprefix={subprefix} sesprefix={sesprefix} store={store} force={force}")

    # Get the heuristics for filling the new bidsmap (NB: plugins are stored in the bidsmaps)
    bidsmap_old, bidsmapfile = bids.load_bidsmap(bidsmapfile,  bidscoinfolder, plugins)
    template, _              = bids.load_bidsmap(templatefile, plugins=plugins, checks=(True, True, False))
    bids.check_template(template)

    # Create the new bidsmap as a copy / bidsmap skeleton with no data type entries (i.e. bidsmap with empty lists)
    if force and bidsmapfile.is_file():
        LOGGER.info(f"Deleting previous bidsmap: {bidsmapfile}")
        bidsmapfile.unlink()
        bidsmap_old = {}
    if bidsmap_old:
        bidsmap_new = copy.deepcopy(bidsmap_old)
    else:
        bidsmap_new = copy.deepcopy(template)
    template['Options'] = bidsmap_new['Options']                # Always use the options of the new bidsmap
    if unzip:
        bidsmap_new['Options']['bidscoin']['unzip'] = unzip
    else:
        unzip = bidsmap_new['Options']['bidscoin'].get('unzip','')
    for dataformat in bidsmap_new:
        if dataformat in ('$schema', 'Options'): continue
        for datatype in bidsmap_new[dataformat]:
            if datatype not in ('subject', 'session'):
                bidsmap_new[dataformat][datatype] = []

    # Store/retrieve the empty or user-defined sub-/ses-prefix
    subprefix, sesprefix = setprefix(bidsmap_new, subprefix, sesprefix, rawfolder, update = not noupdate)

    # Start with an empty skeleton if we didn't have an old bidsmap
    if not bidsmap_old:
        bidsmap_old = copy.deepcopy(bidsmap_new)

    # Import the data scanning plugins
    plugins = [bcoin.import_plugin(plugin, ('bidsmapper_plugin',)) for plugin in bidsmap_new['Options']['plugins']]
    plugins = [plugin for plugin in plugins if plugin]          # Filter the empty items from the list
    if not plugins:
        LOGGER.warning(f"The plugins listed in your bidsmap['Options'] did not have a usable `bidsmapper_plugin` function, nothing to do")
        LOGGER.info('-------------- FINISHED! ------------')
        LOGGER.info('')
        return {}

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
                        store = {'source': sesfolder.parent.parent.parent.parent if unpacked else rawfolder.parent,
                                 'target': bidscoinfolder/'provenance'}
                    else:
                        store = {}

                    # Run the bidsmapper plugins
                    for module in plugins:
                        LOGGER.verbose(f"Executing plugin: {Path(module.__file__).stem} -> {sesfolder}")
                        trackusage(Path(module.__file__).stem)
                        module.bidsmapper_plugin(sesfolder, bidsmap_new, bidsmap_old, template, store)

                    # Clean-up the temporary unpacked data
                    if unpacked:
                        shutil.rmtree(sesfolder)

    # Save the new study bidsmap in the bidscoinfolder or launch the bidseditor UI_MainWindow
    if noeditor:
        bids.save_bidsmap(bidsmapfile, bidsmap_new)

    else:
        LOGGER.info('Opening the bidseditor')
        from PyQt6 import QtCore, QtGui
        from PyQt6.QtWidgets import QApplication, QMessageBox
        try:
            from bidscoin import bidseditor
        except ImportError:
            import bidseditor       # This should work if bidscoin was not pip-installed
        app = QApplication(sys.argv)
        app.setApplicationName(f"{bidsmapfile} - BIDS editor {__version__}")

        mainwin = bidseditor.MainWindow(bidsfolder, bidsmap_new, template)
        mainwin.show()

        if not bidsmapfile.is_file() or not uptodate:
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


def setprefix(bidsmap: Bidsmap, subprefix: str, sesprefix: str, rawfolder: Path, update: bool=True) -> tuple:
    """
    Set the prefix in the Options, subject, session and in all the run['datasource'] objects

    :param bidsmap:     The bidsmap with the data
    :param subprefix:   The subprefix (take value from bidsmap if empty)
    :param sesprefix:   The sesprefix (take value from bidsmap if empty)
    :param rawfolder:   The root folder-name of the sub/ses/data/file tree containing the source data files
    :param update:      Update the prefixes in and prepend the rawfolder.name in the subject/session regex: <<filepath:>> to <<filepath:/{rawfolder.name}>>
    :return:            A (subprefix, sesprefix) tuple
    """

    # Get/set the sub-/ses-prefixes in the 'Options'
    oldsubprefix = bidsmap['Options']['bidscoin'].get('subprefix','')
    oldsesprefix = bidsmap['Options']['bidscoin'].get('sesprefix','')
    if not subprefix:
        subprefix = oldsubprefix                                # Use the default value from the bidsmap
    if not sesprefix:
        sesprefix = oldsesprefix                                # Use the default value from the bidsmap
    bidsmap['Options']['bidscoin']['subprefix'] = subprefix
    bidsmap['Options']['bidscoin']['sesprefix'] = sesprefix

    # Update the bidsmap dataformat sections
    reprefix = lambda prefix: '' if prefix=='*' else re.escape(prefix).replace(r'\-','-')
    for dataformat in bidsmap:
        if not bidsmap[dataformat] or dataformat in ('$schema','Options'): continue

        # Update the run-DataSources
        for datatype in bidsmap[dataformat]:
            if not isinstance(bidsmap[dataformat][datatype], list): continue  # E.g. 'subject' and 'session'
            for run in bidsmap[dataformat][datatype]:
                run['datasource'].subprefix = subprefix
                run['datasource'].sesprefix = sesprefix

        # Replace the sub-/ses-prefixes in the dynamic filepath values of bidsmap[dataformat]['subject'] and ['session']
        if update and bidsmap[dataformat]['subject'].startswith('<<filepath:'):
            if oldsubprefix:
                bidsmap[dataformat]['subject'] = bidsmap[dataformat]['subject'].replace(reprefix(oldsubprefix), reprefix(subprefix))    # TODO: Not very robust for short prefixes :-(
            else:
                LOGGER.warning(f"Could not update the bidsmap subject label expression: {bidsmap[dataformat]['subject']}")
            if not bidsmap[dataformat]['subject'].startswith(f"<<filepath:/{rawfolder.name}"):    # NB: Don't prepend the fullpath of rawfolder because of potential data unpacking in /tmp
                bidsmap[dataformat]['subject'] = bidsmap[dataformat]['subject'].replace('<<filepath:', f"<<filepath:/{rawfolder.name}")
        if update and bidsmap[dataformat]['session'].startswith('<<filepath:'):
            if oldsesprefix:
                bidsmap[dataformat]['session'] = bidsmap[dataformat]['session'].replace(reprefix(oldsubprefix), reprefix(subprefix)).replace(reprefix(oldsesprefix), reprefix(sesprefix))       # TODO: Not very robust for short prefixes :-(
            else:
                LOGGER.warning(f"Could not update the bidsmap session label expression: {bidsmap[dataformat]['session']}")
            if not bidsmap[dataformat]['session'].startswith(f"<<filepath:/{rawfolder.name}"):
                bidsmap[dataformat]['session'] = bidsmap[dataformat]['session'].replace('<<filepath:', f"<<filepath:/{rawfolder.name}")

    return subprefix, sesprefix


def main():
    """Console script entry point"""

    from bidscoin.cli._bidsmapper import get_parser

    # Parse the input arguments and run bidsmapper(args)
    args = get_parser().parse_args()

    trackusage('bidsmapper')
    try:
        bidsmapper(rawfolder    = args.sourcefolder,
                   bidsfolder   = args.bidsfolder,
                   bidsmapfile  = args.bidsmap,
                   templatefile = args.template,
                   plugins      = args.plugins,
                   subprefix    = args.subprefix,
                   sesprefix    = args.sesprefix,
                   unzip        = args.unzip,
                   store        = args.store,
                   noeditor     = args.automated,
                   force        = args.force,
                   noupdate     = args.no_update)

    except Exception:
        trackusage('bidsmapper_exception')
        raise


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
