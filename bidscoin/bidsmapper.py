#!/usr/bin/env python3
"""
The bidsmapper scans your source data repository to identify different data types by matching
them against the run-items in the template bidsmap. Once a match is found, a mapping to BIDS
output data types is made and the run-item is added to the study bidsmap. You can check and edit
these generated bids-mappings to your needs with the (automatically launched) bidseditor. Re-run
the bidsmapper whenever something was changed in your data acquisition protocol and edit the new
data type to your needs (your existing bidsmap will be re-used).

The bidsmapper uses plugins, as stored in the bidsmap['Options'], to do the actual work
"""

# Global imports (plugin modules may be imported when needed)
import argparse
import textwrap
import copy
import logging
import sys
import shutil
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QMessageBox
try:
    from bidscoin import bidscoin, bids, bidseditor
except ImportError:
    import bidscoin, bids, bidseditor         # This should work if bidscoin was not pip-installed


localversion, versionmessage = bidscoin.version(check=True)


def bidsmapper(rawfolder: str, bidsfolder: str, bidsmapfile: str, templatefile: str, plugins: list, subprefix: str, sesprefix: str, store: bool=False, noedit: bool=False, force: bool=False) -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder
    and that generates a maximally filled-in bidsmap.yaml file in bidsfolder/code/bidscoin.
    Folders in sourcefolder are assumed to contain a single dataset.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param bidsmapfile:     The name of the bidsmap YAML-file
    :param templatefile:    The name of the bidsmap template YAML-file
    :param plugins:         Optional list of plugins that should be used (overrules the list in the study/template bidsmaps)
    :param subprefix:       The prefix common for all source subject-folders
    :param sesprefix:       The prefix common for all source session-folders
    :param store:           If True, the provenance samples will be stored
    :param noedit:          The bidseditor will not be launched if True
    :param force:           If True, the previous bidsmap and logfiles will be deleted
    :return:
    """

    # Input checking
    rawfolder      = Path(rawfolder).resolve()
    bidsfolder     = Path(bidsfolder).resolve()
    bidsmapfile    = Path(bidsmapfile)
    templatefile   = Path(templatefile)
    bidscoinfolder = bidsfolder/'code'/'bidscoin'

    # Start logging
    if force:
        (bidscoinfolder/'bidsmapper.log').unlink(missing_ok=True)
    bidscoin.setup_logging(bidscoinfolder/'bidsmapper.log')
    LOGGER.info('')
    LOGGER.info('-------------- START BIDSmapper ------------')
    LOGGER.info(f">>> bidsmapper sourcefolder={rawfolder} bidsfolder={bidsfolder} bidsmap={bidsmapfile} "
                f" template={templatefile} subprefix={subprefix} sesprefix={sesprefix} store={store} automatic={noedit}")

    # Get the heuristics for filling the new bidsmap
    bidsmap_old, bidsmapfile = bids.load_bidsmap(bidsmapfile,  bidscoinfolder)
    template, _              = bids.load_bidsmap(templatefile, bidscoinfolder)

    # Create the new bidsmap as a copy / bidsmap skeleton with no datatype entries (i.e. bidsmap with empty lists)
    if force:
        bidsmapfile.unlink(missing_ok=True)
        bidsmap_old = {}
    if bidsmap_old:
        bidsmap_new = copy.deepcopy(bidsmap_old)
    else:
        bidsmap_new = copy.deepcopy(template)
    bidscoindatatypes = bidsmap_new['Options']['bidscoin'].get('datatypes',[])
    unknowndatatypes  = bidsmap_new['Options']['bidscoin'].get('unknowntypes',[])
    ignoredatatypes   = bidsmap_new['Options']['bidscoin'].get('ignoretypes',[])
    if plugins:
        bidsmap_new['Options']['plugins'] = {}
        for plugin in plugins:
            module = bidscoin.import_plugin(plugin)
            bidsmap_new['Options']['plugins'][plugin] = bidsmap_old.get('Options',{}).get('plugins',{}).get(plugin,
                                                           template.get('Options',{}).get('plugins',{}).get(plugin,
                                                           module.OPTIONS if 'OPTIONS' in dir(module) else {}))
    for dataformat in bidsmap_new:
        if dataformat in ('Options','PlugIns'): continue        # Handle legacy bidsmaps (-> 'PlugIns')
        for datatype in bidscoindatatypes + unknowndatatypes + ignoredatatypes:
            if bidsmap_new[dataformat].get(datatype):
                bidsmap_new[dataformat][datatype] = None

    # Store/retrieve the empty or user-defined sub-/ses-prefix
    setprefix(bidsmap_new, subprefix, sesprefix)
    subprefix = bidsmap_new['Options']['bidscoin']['subprefix']
    sesprefix = bidsmap_new['Options']['bidscoin']['sesprefix']

    # Start with an empty skeleton if we didn't have an old bidsmap
    if not bidsmap_old:
        bidsmap_old = copy.deepcopy(bidsmap_new)
        bidsmapfile = bidscoinfolder/'bidsmap.yaml'

    # Import the data scanning plugins
    plugins = [bidscoin.import_plugin(plugin, ('bidsmapper_plugin',)) for plugin in bidsmap_new['Options']['plugins']]
    plugins = [plugin for plugin in plugins if plugin]          # Filter the empty items from the list
    if not plugins:
        LOGGER.warning(f"The plugins listed in your bidsmap['Options'] did not have a usable `bidsmapper_plugin` function, nothing to do")
        LOGGER.info('-------------- FINISHED! ------------')
        LOGGER.info('')
        return

    # Loop over all subjects and sessions and built up the bidsmap entries
    subjects = bidscoin.lsdirs(rawfolder, subprefix + '*')
    if not subjects:
        LOGGER.warning(f'No subjects found in: {rawfolder/subprefix}*')
    with logging_redirect_tqdm():
        for n, subject in enumerate(tqdm(subjects, unit='subject', leave=False), 1):

            sessions = bidscoin.lsdirs(subject, sesprefix + '*')
            if not sessions:
                sessions = [subject]
            for session in sessions:

                LOGGER.info(f"Mapping: {session} (subject {n}/{len(subjects)})")

                # Unpack the data in a temporary folder if it is tarballed/zipped and/or contains a DICOMDIR file
                session, unpacked = bids.unpack(session, subprefix, sesprefix)
                if unpacked:
                    store = dict(source=unpacked, target=bidscoinfolder/'provenance')
                elif store:
                    store = dict(source=rawfolder, target=bidscoinfolder/'provenance')
                else:
                    store = dict()

                # Run the bidsmapper plugins
                for module in plugins:
                    LOGGER.info(f"Executing plugin: {Path(module.__file__).name}")
                    module.bidsmapper_plugin(session, bidsmap_new, bidsmap_old, template, store)

                # Clean-up the temporary unpacked data
                if unpacked:
                    shutil.rmtree(session)

    # Save the new study bidsmap in the bidscoinfolder or launch the bidseditor UI_MainWindow
    if noedit:
        bids.save_bidsmap(bidsmapfile, bidsmap_new)

    else:
        LOGGER.info('Opening the bidseditor')
        app = QApplication(sys.argv)
        app.setApplicationName(f"{bidsmapfile} - BIDS editor {localversion}")

        mainwin = bidseditor.MainWindow(bidsfolder, bidsmap_new, template)
        mainwin.show()

        messagebox = QMessageBox(mainwin)
        messagebox.setText(f"The bidsmapper has finished scanning {rawfolder}\n\n"
                           f"Please carefully check all the different BIDS output names "
                           f"and BIDScoin options and (re)edit them to your needs.\n\n"
                           f"You can always redo this step later by re-running the "
                           f"bidsmapper or by just running the bidseditor tool\n\n"
                           f"{versionmessage}")
        messagebox.setWindowTitle('About the BIDS-mapping workflow')
        messagebox.setIconPixmap(QtGui.QPixmap(str(bidseditor.BIDSCOIN_LOGO)).scaled(150, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        messagebox.setWindowFlags(messagebox.windowFlags() & ~QtCore.Qt.WindowMinMaxButtonsHint)
        messagebox.show()

        app.exec()

    LOGGER.info('-------------- FINISHED! -------------------')
    LOGGER.info('')

    bidscoin.reporterrors()


def setprefix(bidsmap, subprefix, sesprefix):
    """Set the prefix in the Options, subject, session and in all the run['datasource'] objects if the prefix is not empty"""

    oldsubprefix = bidsmap['Options']['bidscoin']['subprefix']
    oldsesprefix = bidsmap['Options']['bidscoin']['sesprefix']
    if subprefix:
        bidsmap['Options']['bidscoin']['subprefix'] = subprefix
    if sesprefix:
        bidsmap['Options']['bidscoin']['sesprefix'] = sesprefix
    for dataformat in bidsmap:
        if dataformat in ('Options','PlugIns'): continue        # Handle legacy bidsmaps (-> 'PlugIns')
        if not bidsmap[dataformat]:             continue
        for datatype in bidsmap[dataformat]:
            if subprefix:
                bidsmap[dataformat]['subject'] = bidsmap[dataformat]['subject'].replace(oldsubprefix, subprefix)  # This may not work for every template but it's the best we can do
            if sesprefix:
                bidsmap[dataformat]['session'] = bidsmap[dataformat]['session'].replace(oldsesprefix, sesprefix)
            if not isinstance(bidsmap[dataformat][datatype], list): continue
            for run in bidsmap[dataformat][datatype]:
                if subprefix:
                    run['datasource'].subprefix = subprefix
                if sesprefix:
                    run['datasource'].sesprefix = sesprefix


def main():
    """Console script usage"""

    # Parse the input arguments and run bidsmapper(args)
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidsmapper /project/foo/raw /project/foo/bids\n'
                                            '  bidsmapper /project/foo/raw /project/foo/bids -t bidsmap_dccn\n ')
    parser.add_argument('sourcefolder',       help='The study root folder containing the raw data in sub-#/[ses-#/]data subfolders (or specify --subprefix and --sesprefix for different prefixes)')
    parser.add_argument('bidsfolder',         help='The destination folder with the (future) bids data and the bidsfolder/code/bidscoin/bidsmap.yaml output file')
    parser.add_argument('-b','--bidsmap',     help='The study bidsmap file with the mapping heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-t','--template',    help='The bidsmap template file with the default heuristics (this could be provided by your institute). If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap_dccn.yaml', default=bidscoin.bidsmap_template)
    parser.add_argument('-p','--plugins',     help='List of plugins to be used (with default options, overrules the plugin list in the study/template bidsmaps)', nargs='+', default=[])
    parser.add_argument('-n','--subprefix',   help="The prefix common for all the source subject-folders (e.g. 'Pt' is the subprefix if subject folders are named 'Pt018', 'Pt019', ...). Default: 'sub-'")
    parser.add_argument('-m','--sesprefix',   help="The prefix common for all the source session-folders (e.g. 'M_' is the subprefix if session folders are named 'M_pre', 'M_post', ...). Default: 'ses-'")
    parser.add_argument('-s','--store',       help="Flag to store provenance data samples in the bidsfolder/'code'/'provenance' folder (useful for inspecting e.g. zipped or transfered datasets)", action='store_true')
    parser.add_argument('-a','--automated',   help="Flag to save the automatically generated bidsmap to disk and without interactively tweaking it with the bidseditor", action='store_true')
    parser.add_argument('-f','--force',       help='Flag to discard the previously saved bidsmap and logfile', action='store_true')
    parser.add_argument('-v','--version',     help='Show the installed version and check for updates', action='version', version=f'BIDS-version:\t\t{bidscoin.bidsversion()}\nBIDScoin-version:\t{localversion}, {versionmessage}')
    args = parser.parse_args()

    bidsmapper(rawfolder    = args.sourcefolder,
               bidsfolder   = args.bidsfolder,
               bidsmapfile  = args.bidsmap,
               templatefile = args.template,
               plugins      = args.plugins,
               subprefix    = args.subprefix,
               sesprefix    = args.sesprefix,
               store        = args.store,
               noedit       = args.automated,
               force        = args.force)


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
