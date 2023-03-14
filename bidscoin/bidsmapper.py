#!/usr/bin/env python3
"""
The bidsmapper scans your source data repository to identify different data types by matching
them against the run-items in the template bidsmap. Once a match is found, a mapping to BIDS
output data types is made and the run-item is added to the study bidsmap. You can check and
edit these generated bids-mappings to your needs with the (automatically launched) bidseditor.
Re-run the bidsmapper whenever something was changed in your data acquisition protocol and
edit the new data type to your needs (your existing bidsmap will be re-used).

The bidsmapper uses plugins, as stored in the bidsmap['Options'], to do the actual work
"""

# Global imports (plugin modules may be imported when needed)
import argparse
import textwrap
import copy
import logging
import sys
import shutil
import re
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QMessageBox
try:
    from bidscoin import bcoin, bids, bidseditor
except ImportError:
    import bcoin, bids, bidseditor      # This should work if bidscoin was not pip-installed

localversion, versionmessage = bcoin.version(check=True)


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
    :param noupdate:        Do not update any sub/sesprefixes in or prepend the rawfolder name to the <<filepath:regexp>> expression
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

    # Start logging
    if force:
        try:
            (bidscoinfolder/'bidsmapper.log').unlink(missing_ok=True)
        except IOError as unlinkerr:
            LOGGER.debug(f"Could not delete: {bidscoinfolder/'bidsmapper.log'}\n{unlinkerr}")
    bcoin.setup_logging(bidscoinfolder/'bidsmapper.log')
    LOGGER.info('')
    LOGGER.info('-------------- START BIDSmapper ------------')
    LOGGER.info(f">>> bidsmapper sourcefolder={rawfolder} bidsfolder={bidsfolder} bidsmap={bidsmapfile} "
                f"template={templatefile} plugins={plugins} subprefix={subprefix} sesprefix={sesprefix} store={store} force={force}")

    # Get the heuristics for filling the new bidsmap (NB: plugins are stored in the bidsmaps)
    bidsmap_old, bidsmapfile = bids.load_bidsmap(bidsmapfile,  bidscoinfolder, plugins)
    template, _              = bids.load_bidsmap(templatefile, bidscoinfolder, plugins, check=(True,True,False))

    # Create the new bidsmap as a copy / bidsmap skeleton with no datatype entries (i.e. bidsmap with empty lists)
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
        if dataformat == 'Options': continue
        for datatype in bidsmap_new[dataformat]:
            if datatype not in ('subject', 'session'):
                bidsmap_new[dataformat][datatype] = []

    # Store/retrieve the empty or user-defined sub-/ses-prefix
    subprefix, sesprefix = setprefix(bidsmap_new, subprefix, sesprefix, rawfolder, update = not noupdate)

    # Start with an empty skeleton if we didn't have an old bidsmap
    if not bidsmap_old:
        bidsmap_old = copy.deepcopy(bidsmap_new)
        bidsmapfile = bidscoinfolder/'bidsmap.yaml'

    # Import the data scanning plugins
    plugins = [bcoin.import_plugin(plugin, ('bidsmapper_plugin',)) for plugin in bidsmap_new['Options']['plugins']]
    plugins = [plugin for plugin in plugins if plugin]          # Filter the empty items from the list
    if not plugins:
        LOGGER.warning(f"The plugins listed in your bidsmap['Options'] did not have a usable `bidsmapper_plugin` function, nothing to do")
        LOGGER.info('-------------- FINISHED! ------------')
        LOGGER.info('')
        return {}

    # Loop over all subjects and sessions and built up the bidsmap entries
    subjects = bcoin.lsdirs(rawfolder, ('' if subprefix=='*' else subprefix) + '*')
    if not subjects:
        LOGGER.warning(f'No subjects found in: {rawfolder/subprefix}*')
    with logging_redirect_tqdm():
        for n, subject in enumerate(tqdm(subjects, unit='subject', leave=False), 1):

            sessions = bcoin.lsdirs(subject, ('' if sesprefix=='*' else sesprefix) + '*')
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
                        LOGGER.verbose(f"Executing plugin: {Path(module.__file__).name} -> {sesfolder}")
                        module.bidsmapper_plugin(sesfolder, bidsmap_new, bidsmap_old, template, store)

                    # Clean-up the temporary unpacked data
                    if unpacked:
                        shutil.rmtree(sesfolder)

    # Save the new study bidsmap in the bidscoinfolder or launch the bidseditor UI_MainWindow
    if noeditor:
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

    bcoin.reporterrors()

    return bidsmap_new


def setprefix(bidsmap: dict, subprefix: str, sesprefix: str, rawfolder: Path, update: bool=True) -> tuple:
    """
    Set the prefix in the Options, subject, session and in all the run['datasource'] objects

    :param bidsmap:     The bidsmap with the data
    :param subprefix:   The subprefix (take value from bidsmap if empty)
    :param sesprefix:   The sesprefix (take value from bidsmap if empty)
    :param rawfolder:   The root folder-name of the sub/ses/data/file tree containing the source data files
    :param update:      Update the prefixes in and prepend the rawfolder.name in the subject/session regexp: <<filepath:>> to <<filepath:/{rawfolder.name}>>
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
        if not bidsmap[dataformat] or dataformat=='Options': continue

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
    """Console script usage"""

    # Parse the input arguments and run bidsmapper(args)
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidsmapper myproject/raw myproject/bids\n'
                                            '  bidsmapper myproject/raw myproject/bids -t bidsmap_custom  # Uses a template bidsmap of choice\n'
                                            '  bidsmapper myproject/raw myproject/bids -p nibabel2bids    # Uses a plugin of choice\n'
                                            "  bidsmapper myproject/raw myproject/bids -u '*.tar.gz'      # Unzip tarball sourcefiles\n ")
    parser.add_argument('sourcefolder',       help='The study root folder containing the raw source data folders')
    parser.add_argument('bidsfolder',         help='The destination folder with the (future) bids data and the bidsfolder/code/bidscoin/bidsmap.yaml output file')
    parser.add_argument('-b','--bidsmap',     help="The study bidsmap file with the mapping heuristics. If the bidsmap filename is relative (i.e. no '/' in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap.yaml", default='bidsmap.yaml')
    parser.add_argument('-t','--template',    help=f"The bidsmap template file with the default heuristics (this could be provided by your institute). If the bidsmap filename is relative (i.e. no '/' in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: {bcoin.bidsmap_template.stem}", default=bcoin.bidsmap_template)
    parser.add_argument('-p','--plugins',     help='List of plugins to be used. Default: the plugin list of the study/template bidsmap)', nargs='+', default=[])
    parser.add_argument('-n','--subprefix',   help="The prefix common for all the source subject-folders (e.g. 'Pt' is the subprefix if subject folders are named 'Pt018', 'Pt019', ...). Use '*' when your subject folders do not have a prefix. Default: the value of the study/template bidsmap, e.g. 'sub-'")
    parser.add_argument('-m','--sesprefix',   help="The prefix common for all the source session-folders (e.g. 'M_' is the subprefix if session folders are named 'M_pre', 'M_post', ..). Use '*' when your session folders do not have a prefix. Default: the value of the study/template bidsmap, e.g. 'ses-'")
    parser.add_argument('-u','--unzip',       help='Wildcard pattern to unpack tarball/zip-files in the sub/ses sourcefolder that need to be unzipped (in a tempdir) to make the data readable. Default: the value of the study/template bidsmap')
    parser.add_argument('-s','--store',       help='Store provenance data samples in the bidsfolder/code/provenance folder (useful for inspecting e.g. zipped or transfered datasets)', action='store_true')
    parser.add_argument('-a','--automated',   help='Save the automatically generated bidsmap to disk and without interactively tweaking it with the bidseditor', action='store_true')
    parser.add_argument('-f','--force',       help='Discard the previously saved bidsmap and logfile', action='store_true')
    parser.add_argument('--no-update',        help="Do not update any sub/sesprefixes in or prepend the sourcefolder name to the <<filepath:regexp>> expression that extracts the subject/session labels. This is normally done to make the extraction more robust, but could case problems for certain use cases", action='store_true')
    args = parser.parse_args()

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


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
