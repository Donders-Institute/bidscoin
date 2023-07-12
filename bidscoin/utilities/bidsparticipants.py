#!/usr/bin/env python3
"""(Re)scans data sets in the source folder for subject metadata (See also cli/_bidsparticipants.py)"""

import pandas as pd
import json
import logging
import shutil
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    import sys
    sys.path.append(str(Path(__file__).parents[2]))
from bidscoin import bcoin, bids, __version__


def scanpersonals(bidsmap: dict, session: Path, personals: dict) -> bool:
    """
    Converts the session source-files into BIDS-valid NIfTI-files in the corresponding bidsfolder and
    extracts personals (e.g. Age, Sex) from the source header

    :param bidsmap:     The study bidsmap with the mapping heuristics
    :param session:     The full-path name of the subject/session source file/folder
    :param personals:   The dictionary with the personal information
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

    personals['sex']    = datasource.attributes('PatientSex')
    personals['size']   = datasource.attributes('PatientSize')
    personals['weight'] = datasource.attributes('PatientWeight')

    age = datasource.attributes('PatientAge')                   # A string of characters with one of the following formats: nnnD, nnnW, nnnM, nnnY
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
    :param bidsmapfile:     The name of the bidsmap YAML-file. If the bidsmap pathname is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin
    :param dryrun:          Boolean to just display the participants info
    :return:                Nothing
    """

    # Input checking & defaults
    rawfolder  = Path(rawfolder).resolve()
    bidsfolder = Path(bidsfolder).resolve()

    # Start logging
    if dryrun:
        bcoin.setup_logging()
    else:
        bcoin.setup_logging(bidsfolder/'code'/'bidscoin'/'bidsparticipants.log')
    LOGGER.info('')
    LOGGER.info(f"-------------- START bidsparticipants {__version__} ------------")
    LOGGER.info(f">>> bidsparticipants sourcefolder={rawfolder} bidsfolder={bidsfolder} bidsmap={bidsmapfile}")

    # Get the bidsmap sub-/ses-prefix from the bidsmap YAML-file
    bidsmap,_ = bids.load_bidsmap(Path(bidsmapfile), bidsfolder /'code' /'bidscoin', checks=(False, False, False))
    if not bidsmap:
        LOGGER.info('Make sure to run "bidsmapper" first, exiting now')
        return
    subprefix = bidsmap['Options']['bidscoin']['subprefix']
    sesprefix = bidsmap['Options']['bidscoin']['sesprefix']

    # Get the table & dictionary of the subjects that have been processed
    participants_tsv  = bidsfolder/'participants.tsv'
    participants_json = participants_tsv.with_suffix('.json')
    if participants_tsv.is_file():
        participants_table = pd.read_csv(participants_tsv, sep='\t')
        participants_table.set_index(['participant_id'], verify_integrity=True, inplace=True)
    else:
        participants_table = pd.DataFrame()
        participants_table.index.name = 'participant_id'
    if participants_json.is_file():
        with participants_json.open('r') as json_fid:
            participants_dict = json.load(json_fid)
    else:
        participants_dict = {'participant_id': {'Description': 'Unique participant identifier'}}

    # Get the list of subjects
    subjects = bcoin.lsdirs(bidsfolder, 'sub-*')
    if not subjects:
        LOGGER.warning(f"No subjects found in: {bidsfolder}")

    # Remove obsolete participants from the participants table
    for participant in participants_table.index:
        if participant not in [sub.name for sub in subjects]:
            participants_table.drop(participant, inplace=True)

    # Loop over all subjects in the bids-folder and add them to the participants table
    with logging_redirect_tqdm():
        for n, subject in enumerate(tqdm(subjects, unit='subject', leave=False), 1):

            LOGGER.info(f"------------------- Subject {n}/{len(subjects)} -------------------")
            personals = {}
            subject   = rawfolder/subject.name.replace('sub-', subprefix.replace('*',''))     # TODO: This assumes e.g. that the subject-ids in the rawfolder did not contain BIDS-invalid characters (such as '_')
            sessions  = bcoin.lsdirs(subject, ('' if sesprefix=='*' else sesprefix) + '*')
            if not subject.is_dir():
                LOGGER.error(f"Could not find source-folder: {subject}")
                continue
            if not sessions:
                sessions = [subject]
            for session in sessions:

                success      = False            # Only take data from the first session -> BIDS specification
                subid, sesid = bids.DataSource(session/'dum.my', subprefix=subprefix, sesprefix=sesprefix).subid_sesid()
                if sesid and 'session_id' not in personals:
                    personals['session_id']         = sesid
                    participants_dict['session_id'] = {'Description': 'Session identifier'}

                # Unpack the data in a temporary folder if it is tarballed/zipped and/or contains a DICOMDIR file
                sesfolders, unpacked = bids.unpack(session, bidsmap['Options']['bidscoin'].get('unzip',''))
                for sesfolder in sesfolders:

                    # Update / append the personal source data
                    LOGGER.info(f"Scanning session: {sesfolder}")
                    success = scanpersonals(bidsmap, sesfolder, personals)

                    # Clean-up the temporary unpacked data
                    if unpacked:
                        shutil.rmtree(sesfolder)

                    if success: break

                if success: break

            # Store the collected personals in the participant_table. TODO: Check that only values that are consistent over sessions go in the participants.tsv file, otherwise put them in a sessions.tsv file
            for key in keys:
                if key not in participants_dict:
                    participants_dict[key] = dict(LongName    = 'Long (unabbreviated) name of the column',
                                                  Description = 'Description of the the column',
                                                  Levels      = dict(Key='Value (This is for categorical variables: a dictionary of possible values (keys) and their descriptions (values))'),
                                                  Units       = 'Measurement units. [<prefix symbol>]<unit symbol> format following the SI standard is RECOMMENDED')

                participants_table.loc[subid, key] = personals.get(key)

    # Write the collected data to the participant files
    LOGGER.info(f"Writing subject data to: {participants_tsv}")
    if not dryrun:
        participants_table.replace('','n/a').to_csv(participants_tsv, sep='\t', encoding='utf-8', na_rep='n/a')

    LOGGER.info(f"Writing subject data dictionary to: {participants_json}")
    if not dryrun:
        with participants_json.open('w') as json_fid:
            json.dump(participants_dict, json_fid, indent=4)

    print(participants_table)

    LOGGER.info('-------------- FINISHED! ------------')
    LOGGER.info('')

    bcoin.reporterrors()


def main():
    """Console script entry point"""

    from bidscoin.cli._bidsparticipants import get_parser

    args = get_parser().parse_args()
    bidsparticipants(rawfolder   = args.sourcefolder,
                     bidsfolder  = args.bidsfolder,
                     keys        = args.keys,
                     bidsmapfile = args.bidsmap,
                     dryrun      = args.dryrun)


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
