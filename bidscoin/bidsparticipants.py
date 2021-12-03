#!/usr/bin/env python3
"""
(Re)scans data sets in the source folder for subject meta data to populate the participants.tsv file in the bids
directory, e.g. after you renamed (be careful there!), added or deleted data in the bids folder yourself.

Provenance information, warnings and error messages are stored in the
bidsfolder/code/bidscoin/bidsparticipants.log file.
"""

import pandas as pd
import json
import logging
import shutil
import dateutil.parser
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
try:
    from bidscoin import bidscoin, bids
except ImportError:
    import bidscoin, bids         # This should work if bidscoin was not pip-installed


def scanpersonals(bidsmap: dict, session: Path, personals: dict) -> bool:
    """
    Converts the session source-files into BIDS-valid nifti-files in the corresponding bidsfolder and
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
        LOGGER.info(f"No supported datasources found in '{session}'")
        return False

    # Collect personal data from a source header (PAR/XML does not contain personal info)
    if dataformat in ('DICOM', 'Twix'):
        personals['sex']    = datasource.attributes('PatientSex')
        personals['size']   = datasource.attributes('PatientSize')
        personals['weight'] = datasource.attributes('PatientWeight')
        age = str(datasource.attributes('PatientAge'))              # A string of characters with one of the following formats: nnnD, nnnW, nnnM, nnnY
    elif dataformat=='Pfile':
        sex = datasource.attributes('rhe_patsex')
        if sex=='0':   personals['sex'] = 'O'
        elif sex=='1': personals['sex'] = 'M'
        elif sex=='2': personals['sex'] = 'F'
        age = dateutil.parser.parse(datasource.attributes('rhr_rh_scan_date')) - dateutil.parser.parse(datasource.attributes('rhe_dateofbirth'))
        age = str(age.days) + 'D'
    else:
        return False

    if age.endswith('D'):   age = float(age.rstrip('D')) / 365.2524
    elif age.endswith('W'): age = float(age.rstrip('W')) / 52.1775
    elif age.endswith('M'): age = float(age.rstrip('M')) / 12
    elif age.endswith('Y'): age = float(age.rstrip('Y'))
    if age:
        if bidsmap['Options']['plugins']['dcm2niix2bids'].get('anon', 'y') in ('y','yes'):
            age = int(float(age))
        personals['age'] = str(age)

    return True


def bidsparticipants(rawfolder: str, bidsfolder: str, keys: str, bidsmapfile: str='bidsmap.yaml', dryrun: bool=False) -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder to (re)generate the particpants.tsv file in the BIDS folder.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param keys:            The keys that are extracted fro mthe source data when populating the participants.tsv file
    :param bidsmapfile:     The name of the bidsmap YAML-file. If the bidsmap pathname is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin
    :param dryrun:          Boolean to just display the participants info
    :return:                Nothing
    """

    # Input checking & defaults
    rawfolder  = Path(rawfolder).resolve()
    bidsfolder = Path(bidsfolder).resolve()

    # Start logging
    if dryrun:
        bidscoin.setup_logging()
    else:
        bidscoin.setup_logging(bidsfolder/'code'/'bidscoin'/'bidsparticipants.log')
    LOGGER.info('')
    LOGGER.info(f"-------------- START bidsparticipants {bidscoin.version()} ------------")
    LOGGER.info(f">>> bidsparticipants sourcefolder={rawfolder} bidsfolder={bidsfolder} bidsmap={bidsmapfile}")

    # Get the bidsmap sub-/ses-prefix from the bidsmap YAML-file
    bidsmap, _ = bids.load_bidsmap(Path(bidsmapfile), bidsfolder / 'code' / 'bidscoin')
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
    subjects = bidscoin.lsdirs(bidsfolder, 'sub-*')
    if not subjects:
        LOGGER.warning(f"No subjects found in: {bidsfolder}")

    # Remove obsolete participants from the participants table
    for participant in participants_table.index:
        if participant not in subjects:
            participants_table = participants_table.drop(participant)

    # Loop over all subjects in the bids-folder and add them to the participants table
    with logging_redirect_tqdm():
        for n, subject in enumerate(tqdm(subjects, unit='subject', leave=False), 1):

            LOGGER.info(f"------------------- Subject {n}/{len(subjects)} -------------------")
            personals = dict()
            subid, _  = bids.DataSource(subject/'dum.my').subid_sesid()
            subject   = rawfolder/subid.replace('sub-', subprefix)     # TODO: This assumes that the subject-ids in the rawfolder did not contain BIDS-invalid characters (such as '_')
            sessions  = bidscoin.lsdirs(subject, sesprefix + '*')
            if not subject.is_dir():
                LOGGER.error(f"Could not find source-folder: {subject}")
                continue
            if not sessions:
                sessions = [subject]
            for session in sessions:

                # Only take data from the first session -> BIDS specification
                subid, sesid = bids.DataSource(session/'dum.my').subid_sesid()
                if sesprefix and sesid and 'session_id' not in personals:
                    personals['session_id']         = sesid
                    participants_dict['session_id'] = {'Description': 'Session identifier'}

                # Unpack the data in a temporary folder if it is tarballed/zipped and/or contains a DICOMDIR file
                session, unpacked = bids.unpack(session, subprefix, sesprefix)

                LOGGER.info(f"Scanning session: {session}")

                # Update / append the personal source data
                success = scanpersonals(bidsmap, session, personals)

                # Clean-up the temporary unpacked data
                if unpacked:
                    shutil.rmtree(session)

                if success:
                    break

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

    bidscoin.reporterrors()


def main():
    """Console script usage"""

    # Parse the input arguments and run bidsparticipants(args)
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidsparticipants /project/foo/raw /project/foo/bids\n'
                                            '  bidsparticipants /project/foo/raw /project/foo/bids -k participant_id age sex\n ')
    parser.add_argument('sourcefolder',     help='The study root folder containing the raw data in sub-#/[ses-#/]data subfolders (or specify --subprefix and --sesprefix for different prefixes)')
    parser.add_argument('bidsfolder',       help='The destination / output folder with the bids data')
    parser.add_argument('-k','--keys',      help="Space separated list of the participants.tsv columns. Default: 'session_id' 'age' 'sex' 'size' 'weight'", nargs='+', default=['session_id', 'age', 'sex', 'size' ,'weight'])
    parser.add_argument('-n','--subprefix', help="The prefix common for all the source subject-folders. Default: 'sub-'", default='sub-')
    parser.add_argument('-m','--sesprefix', help="The prefix common for all the source session-folders. Default: 'ses-'", default='ses-')
    parser.add_argument('-d','--dryrun',    help='Add this flag to only print the participants info on screen', action='store_true')
    parser.add_argument('-b','--bidsmap',   help='The study bidsmap file with the mapping heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-v','--version',   help='Show the BIDS and BIDScoin version', action='version', version=f"BIDS-version:\t\t{bidscoin.bidsversion()}\nBIDScoin-version:\t{bidscoin.version()}")
    args = parser.parse_args()

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
