#!/usr/bin/env python3
"""(Re)scans data sets in the source folder for subject metadata (See also cli/_bidsparticipants.py)"""

import logging
import shutil
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    import sys
    sys.path.append(str(Path(__file__).parents[2]))
from bidscoin import bcoin, bids, lsdirs, trackusage, __version__
from bidscoin.bids import BidsMap
from bidscoin.utilities import unpack


def bidsparticipants(sourcefolder: str, bidsfolder: str, keys: list, bidsmap: str= 'bidsmap.yaml', dryrun: bool=False) -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder to (re)generate the participants.tsv file in the BIDS folder.

    :param sourcefolder: The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:   The name of the BIDS root folder
    :param keys:         The keys that are extracted from the source data when populating the participants.tsv file
    :param bidsmap:      The name of the bidsmap YAML-file. If the bidsmap pathname is just the base name (i.e. no "/" in the name) then it is assumed to be located in the current directory or in bidsfolder/code/bidscoin
    :param dryrun:       Boolean to just display the participants info
    :return:             Nothing
    """

    # Input checking & defaults
    rawfolder  = Path(sourcefolder).resolve()
    bidsfolder = Path(bidsfolder).resolve()
    if not rawfolder.is_dir():
        raise SystemExit(f"\n[ERROR] Exiting the program because your sourcefolder argument '{sourcefolder}' was not found")
    if not bidsfolder.is_dir():
        raise SystemExit(f"\n[ERROR] Exiting the program because your bidsfolder argument '{bidsfolder}' was not found")

    # Start logging
    if dryrun:
        bcoin.setup_logging()
    else:
        bcoin.setup_logging(bidsfolder/'code'/'bidscoin'/'bidsparticipants.log')
    LOGGER.info('')
    LOGGER.info(f"-------------- START bidsparticipants {__version__} ------------")
    LOGGER.info(f">>> bidsparticipants sourcefolder={rawfolder} bidsfolder={bidsfolder} bidsmap={bidsmap}")

    # Get the bidsmap sub-/ses-prefix from the bidsmap YAML-file
    bidsmap = BidsMap(Path(bidsmap), bidsfolder/'code'/'bidscoin', checks=(False, False, False))
    if not bidsmap.filepath.is_file():
        LOGGER.info('Make sure to run "bidsmapper" first, exiting now')
        return
    subprefix = bidsmap.options['subprefix']
    sesprefix = bidsmap.options['sesprefix']

    # Get the table & dictionary of the subjects that have been processed
    participants_tsv   = bidsfolder/'participants.tsv'
    participants_table = bids.addparticipant(participants_tsv)

    # Get the list of subjects
    subjects = lsdirs(bidsfolder, 'sub-*')
    if not subjects:
        LOGGER.warning(f"No subjects found in: {bidsfolder}")

    # Remove obsolete participants from the participants table
    for participant in participants_table.index:
        if participant not in [sub.name for sub in subjects]:
            participants_table.drop(participant, inplace=True)

    # Import the plugins
    plugins = [plugin for name in bidsmap.plugins if (plugin := bcoin.import_plugin(name))]

    # Loop over all subjects in the bids-folder and add them to the participants table
    with logging_redirect_tqdm():
        for n, subject in enumerate(tqdm(subjects, unit='subject', colour='green', leave=False), 1):

            LOGGER.info(f"------------------- Subject {n}/{len(subjects)} -------------------")
            personals = {}
            subject   = rawfolder/subject.name.replace('sub-', subprefix.replace('*',''))     # TODO: This assumes e.g. that the subject-ids in the rawfolder did not contain BIDS-invalid characters (such as '_')
            sessions  = lsdirs(subject, ('' if sesprefix=='*' else sesprefix) + '*')
            if not subject.is_dir():
                LOGGER.error(f"Could not find source-folder: {subject}")
                continue
            if not sessions:
                sessions = [subject]
            for session in sessions:

                success      = False            # Only take data from the first session -> BIDS specification
                subid, sesid = bids.DataSource(session/'dum.my', bidsmap.plugins, '', bidsmap.options).subid_sesid()

                # Unpack the data in a temporary folder if it is tarballed/zipped and/or contains a DICOMDIR file
                sesfolders, unpacked = unpack(session, bidsmap.options.get('unzip',''))
                for sesfolder in sesfolders:

                    # Run the plugin.Interface().personals()
                    for plugin in plugins:

                        name       = Path(plugin.__file__).stem
                        datasource = bids.get_datasource(sesfolder, {name: bidsmap.plugins[name]})
                        if not datasource.dataformat:
                            LOGGER.info(f">>> No {name} datasources found in '{sesfolder}'")
                            continue

                        # Update/append the personal source data
                        LOGGER.info(f"Scanning session: {sesfolder}")
                        personaldata = plugin.Interface().personals(bidsmap, datasource)
                        if personaldata:
                            personals.update(personaldata)
                            success = True

                        # Clean-up the temporary unpacked data
                        if unpacked:
                            shutil.rmtree(sesfolder)

                        if success: break
                    if success: break
                if success: break

            # Store the collected personals in the participant_table. TODO: Check that only values that are consistent over sessions go in the participants.tsv file, otherwise put them in a sessions.tsv file
            if sessions:
                participants_table = bids.addparticipant(participants_tsv, subid, sesid, personals, dryrun)

    # Add the participants sidecar file
    bids.addparticipant_meta(bidsfolder/'participants.json', bidsmap)

    LOGGER.info('-------------- FINISHED! ------------')
    LOGGER.info('')

    bcoin.reporterrors()

    print(participants_table)


def main():
    """Console script entry point"""

    from bidscoin.cli._bidsparticipants import get_parser

    args = get_parser().parse_args()

    trackusage('bidsparticipants')
    try:
        bidsparticipants(**vars(args))

    except Exception as error:
        trackusage('bidsparticipants_exception', error)
        raise error


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
