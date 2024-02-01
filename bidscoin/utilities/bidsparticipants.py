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
from bidscoin.bids import Bidsmap


def scanpersonals(bidsmap: Bidsmap, session: Path, personals: dict, keys: list) -> bool:
    """
    Converts the session source-files into BIDS-valid NIfTI-files in the corresponding bidsfolder and
    extracts personals (e.g. Age, Sex) from the source header

    :param bidsmap:     The study bidsmap with the mapping heuristics
    :param session:     The full-path name of the subject/session source file/folder
    :param personals:   The dictionary with the personal information
    :param keys:        The keys that are extracted from the source data when populating the participants.tsv file
    :return:            True if successful
    """

    # Get valid BIDS subject/session identifiers from the (first) DICOM- or PAR/XML source file
    datasource = bids.get_datasource(session, bidsmap['Options']['plugins'])
    dataformat = datasource.dataformat
    if not datasource.dataformat:
        LOGGER.info(f"No supported datasource found in '{session}'")
        return False

    # Collect personal data from a source header (PAR/XML does not contain personal info)
    if dataformat not in ('DICOM', 'Twix'): return False

    if 'sex'    in keys: personals['sex']    = datasource.attributes('PatientSex')
    if 'size'   in keys: personals['size']   = datasource.attributes('PatientSize')
    if 'weight' in keys: personals['weight'] = datasource.attributes('PatientWeight')
    if 'age' in keys:
        age = datasource.attributes('PatientAge')       # A string of characters with one of the following formats: nnnD, nnnW, nnnM, nnnY
        if   age.endswith('D'): age = float(age.rstrip('D')) / 365.2524
        elif age.endswith('W'): age = float(age.rstrip('W')) / 52.1775
        elif age.endswith('M'): age = float(age.rstrip('M')) / 12
        elif age.endswith('Y'): age = float(age.rstrip('Y'))
        if age:
            if bidsmap['Options']['plugins']['dcm2niix2bids'].get('anon', 'y') in ('y','yes'):
                age = int(float(age))
            personals['age'] = str(age)

    return True


def bidsparticipants(rawfolder: str, bidsfolder: str, keys: list, bidsmapfile: str='bidsmap.yaml', dryrun: bool=False) -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder to (re)generate the particpants.tsv file in the BIDS folder.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param keys:            The keys that are extracted from the source data when populating the participants.tsv file
    :param bidsmapfile:     The name of the bidsmap YAML-file. If the bidsmap pathname is just the basename (i.e. no "/" in the name) then it is assumed to be located in the current directory or in bidsfolder/code/bidscoin
    :param dryrun:          Boolean to just display the participants info
    :return:                Nothing
    """

    # Input checking & defaults
    rawfolder  = Path(rawfolder).resolve()
    bidsfolder = Path(bidsfolder).resolve()
    if not rawfolder.is_dir():
        print(f"Rawfolder '{rawfolder}' not found")
        return
    if not bidsfolder.is_dir():
        print(f"Bidsfolder '{bidsfolder}' not found")
        return

    # Start logging
    if dryrun:
        bcoin.setup_logging()
    else:
        bcoin.setup_logging(bidsfolder/'code'/'bidscoin'/'bidsparticipants.log')
    LOGGER.info('')
    LOGGER.info(f"-------------- START bidsparticipants {__version__} ------------")
    LOGGER.info(f">>> bidsparticipants sourcefolder={rawfolder} bidsfolder={bidsfolder} bidsmap={bidsmapfile}")

    # Get the bidsmap sub-/ses-prefix from the bidsmap YAML-file
    bidsmap,_ = bids.load_bidsmap(Path(bidsmapfile), bidsfolder/'code'/'bidscoin', checks=(False, False, False))
    if not bidsmap:
        LOGGER.info('Make sure to run "bidsmapper" first, exiting now')
        return
    subprefix = bidsmap['Options']['bidscoin']['subprefix']
    sesprefix = bidsmap['Options']['bidscoin']['sesprefix']

    # Get the table & dictionary of the subjects that have been processed
    participants_tsv                      = bidsfolder/'participants.tsv'
    participants_table, participants_dict = bids.addparticipant(participants_tsv)

    # Get the list of subjects
    subjects = lsdirs(bidsfolder, 'sub-*')
    if not subjects:
        LOGGER.warning(f"No subjects found in: {bidsfolder}")

    # Remove obsolete participants from the participants table
    for participant in participants_table.index:
        if participant not in [sub.name for sub in subjects]:
            participants_table.drop(participant, inplace=True)

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
                subid, sesid = bids.DataSource(session/'dum.my', subprefix=subprefix, sesprefix=sesprefix).subid_sesid()

                # Unpack the data in a temporary folder if it is tarballed/zipped and/or contains a DICOMDIR file
                sesfolders, unpacked = bids.unpack(session, bidsmap['Options']['bidscoin'].get('unzip',''))
                for sesfolder in sesfolders:

                    # Update / append the personal source data
                    LOGGER.info(f"Scanning session: {sesfolder}")
                    success = scanpersonals(bidsmap, sesfolder, personals, keys)

                    # Clean-up the temporary unpacked data
                    if unpacked:
                        shutil.rmtree(sesfolder)

                    if success: break

                if success: break

            # Store the collected personals in the participant_table. TODO: Check that only values that are consistent over sessions go in the participants.tsv file, otherwise put them in a sessions.tsv file
            if sessions:
                participants_table,_ = bids.addparticipant(participants_tsv, subid, sesid, personals, dryrun)

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
        bidsparticipants(rawfolder   = args.sourcefolder,
                         bidsfolder  = args.bidsfolder,
                         keys        = args.keys,
                         bidsmapfile = args.bidsmap,
                         dryrun      = args.dryrun)

    except Exception:
        trackusage('bidsparticipants_exception')
        raise


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
