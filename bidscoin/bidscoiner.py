#!/usr/bin/env python3
"""
Converts ("coins") your source datasets to nifti / json / tsv BIDS datasets using
the information from the bidsmap.yaml file. Edit this bidsmap to your needs using the
bidseditor tool before running this function or (re-)run the bidsmapper whenever you
encounter unexpected data. You can run bidscoiner after all data has been collected,
or run / re-run it whenever new data has been added to your source folder (presuming
the scan protocol hasn't changed). Also, if you delete a subject/session folder from
the bidsfolder, it will simply be re-created from the sourcefolder the next time you
run the bidscoiner.

The bidscoiner uses plugins, as stored in the bidsmap['Options'], to do the actual work

Provenance information, warnings and error messages are stored in the
bidsfolder/code/bidscoin/bidscoiner.log file.
"""

import argparse
import textwrap
import re
import pandas as pd
import json
import logging
import shutil
from pathlib import Path
try:
    from bidscoin import bidscoin, bids
except ImportError:
    import bidscoin, bids         # This should work if bidscoin was not pip-installed

localversion, versionmessage = bidscoin.version(check=True)


def bidscoiner(rawfolder: str, bidsfolder: str, subjects: list=(), force: bool=False, participants: bool=False, bidsmapfile: str='bidsmap.yaml', subprefix: str='sub-', sesprefix: str='ses-') -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder and uses the
    bidsmap.yaml file in bidsfolder/code/bidscoin to cast the data into the BIDS folder.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param subjects:        List of selected subjects / participants (i.e. sub-# names / folders) to be processed (the sub- prefix can be removed). Otherwise all subjects in the sourcefolder will be selected
    :param force:           If True, subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped
    :param participants:    If True, subjects in particpants.tsv will not be processed (this could be used e.g. to protect these subjects from being reprocessed), also when force=True
    :param bidsmapfile:     The name of the bidsmap YAML-file. If the bidsmap pathname is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin
    :param subprefix:       The prefix common for all source subject-folders
    :param sesprefix:       The prefix common for all source session-folders
    :return:                Nothing
    """

    # Input checking & defaults
    rawfolder   = Path(rawfolder).resolve()
    bidsfolder  = Path(bidsfolder).resolve()
    bidsmapfile = Path(bidsmapfile)

    # Start logging
    bidscoin.setup_logging(bidsfolder/'code'/'bidscoin'/'bidscoiner.log')
    LOGGER.info('')
    LOGGER.info(f"-------------- START BIDScoiner {localversion}: BIDS {bidscoin.bidsversion()} ------------")
    LOGGER.info(f">>> bidscoiner sourcefolder={rawfolder} bidsfolder={bidsfolder} subjects={subjects} force={force}"
                f" participants={participants} bidsmap={bidsmapfile} subprefix={subprefix} sesprefix={sesprefix}")

    # Create a code/bidscoin subfolder
    (bidsfolder/'code'/'bidscoin').mkdir(parents=True, exist_ok=True)

    # Create a dataset description file if it does not exist
    dataset_file = bidsfolder/'dataset_description.json'
    generatedby  = [{"Name":"BIDScoin", "Version":localversion, "CodeURL":"https://github.com/Donders-Institute/bidscoin"}]
    if not dataset_file.is_file():
        LOGGER.info(f"Creating dataset description file: {dataset_file}")
        dataset_description = {"Name":                  "REQUIRED. Name of the dataset",
                               "GeneratedBy":           generatedby,
                               "BIDSVersion":           str(bidscoin.bidsversion()),
                               "DatasetType":           "raw",
                               "License":               "RECOMMENDED. The license for the dataset. The use of license name abbreviations is RECOMMENDED for specifying a license. The corresponding full license text MAY be specified in an additional LICENSE file",
                               "Authors":               ["OPTIONAL. List of individuals who contributed to the creation/curation of the dataset"],
                               "Acknowledgements":      "OPTIONAL. Text acknowledging contributions of individuals or institutions beyond those listed in Authors or Funding",
                               "HowToAcknowledge":      "OPTIONAL. Instructions how researchers using this dataset should acknowledge the original authors. This field can also be used to define a publication that should be cited in publications that use the dataset",
                               "Funding":               ["OPTIONAL. List of sources of funding (grant numbers)"],
                               "EthicsApprovals":    	["OPTIONAL. List of ethics committee approvals of the research protocols and/or protocol identifiers"],
                               "ReferencesAndLinks":    ["OPTIONAL. List of references to publication that contain information on the dataset, or links", "https://github.com/Donders-Institute/bidscoin"],
                               "DatasetDOI":            "OPTIONAL. The Document Object Identifier of the dataset (not the corresponding paper)"}
    else:
        with dataset_file.open('r') as fid:
            dataset_description = json.load(fid)
        if 'BIDScoin' not in [generatedby_['Name'] for generatedby_ in dataset_description.get('GeneratedBy',[])]:
            LOGGER.info(f"Adding {generatedby} to {dataset_file}")
            dataset_description['GeneratedBy'] = dataset_description.get('GeneratedBy',[]) + generatedby
    with dataset_file.open('w') as fid:
        json.dump(dataset_description, fid, indent=4)

    # Create a README file if it does not exist
    readme_file = bidsfolder/'README'
    if not readme_file.is_file():
        LOGGER.info(f"Creating README file: {readme_file}")
        readme_file.write_text(f"A free form text ( README ) describing the dataset in more details that SHOULD be provided\n\n"
                               f"The raw BIDS data was created using BIDScoin {localversion}\n"
                               f"All provenance information and settings can be found in ./code/bidscoin\n"
                               f"For more information see: https://github.com/Donders-Institute/bidscoin\n")

    # Get the bidsmap heuristics from the bidsmap YAML-file
    bidsmap, _  = bids.load_bidsmap(bidsmapfile, bidsfolder/'code'/'bidscoin')
    dataformats = [dataformat for dataformat in bidsmap if dataformat not in ('Options','PlugIns')]     # Handle legacy bidsmaps (-> 'PlugIns')
    if not bidsmap:
        LOGGER.error(f"No bidsmap file found in {bidsfolder}. Please run the bidsmapper first and/or use the correct bidsfolder")
        return

    # Load the data conversion plugins
    plugins = [bidscoin.import_plugin(plugin, ('bidscoiner_plugin',)) for plugin,options in bidsmap['Options']['plugins'].items()]
    plugins = [plugin for plugin in plugins if plugin]          # Filter the empty items from the list
    if not plugins:
        LOGGER.warning(f"No bidscoiner plugins found in {bidsmapfile}, nothing to do")
        LOGGER.info('-------------- FINISHED! ------------')
        LOGGER.info('')
        return

    # Append options to the .bidsignore file
    bidsignore_items = [item.strip() for item in bidsmap['Options']['bidscoin']['bidsignore'].split(';')]
    bidsignore_file  = bidsfolder/'.bidsignore'
    if bidsignore_items:
        LOGGER.info(f"Writing {bidsignore_items} entries to {bidsignore_file}")
        if bidsignore_file.is_file():
            bidsignore_items += bidsignore_file.read_text().splitlines()
        with bidsignore_file.open('w') as bidsignore:
            for item in set(bidsignore_items):
                bidsignore.write(item + '\n')

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
    if not subjects:
        subjects = bidscoin.lsdirs(rawfolder, subprefix + '*')
        if not subjects:
            LOGGER.warning(f"No subjects found in: {rawfolder/subprefix}*")
    else:
        subjects = [subprefix + re.sub(f"^{subprefix}", '', subject) for subject in subjects]   # Make sure there is a "sub-" prefix
        subjects = [rawfolder/subject for subject in subjects if (rawfolder/subject).is_dir()]

    # Loop over all subjects and sessions and convert them using the bidsmap entries
    for n, subject in enumerate(subjects, 1):

        LOGGER.info(f"------------------- Subject {n}/{len(subjects)} -------------------")
        if participants and subject.name in list(participants_table.index):
            LOGGER.info(f"Skipping subject: {subject} ({n}/{len(subjects)})")
            continue

        personals = dict()
        sessions  = bidscoin.lsdirs(subject, sesprefix + '*')
        if not sessions:
            sessions = [subject]
        for session in sessions:

            # Unpack the data in a temporary folder if it is tarballed/zipped and/or contains a DICOMDIR file
            session, unpacked = bids.unpack(session, subprefix, sesprefix)

            # Check if we should skip the session-folder
            if not force:
                subid, sesid = bids.get_subid_sesid(session/'dum.my', subprefix=subprefix, sesprefix=sesprefix)
                bidssession  = bidsfolder/subid/sesid
                datatypes    = []
                for dataformat in dataformats:
                    if not bidsmap[dataformat]['session']:
                        bidssession = bidssession.parent
                    for datatype in bidscoin.lsdirs(bidssession):                           # See what datatypes we already have in the bids session-folder
                        if datatype.glob('*') and bidsmap[dataformat].get(datatype.name):   # See if we are going to add data for this datatype
                            datatypes.append(datatype.name)
                if datatypes:
                    LOGGER.info(f"Skipping processed session: {bidssession} already has {datatypes} data (you can carefully use the -f option to overrule)")
                    continue

            LOGGER.info(f"Coining session: {session}")

            # Run the bidscoiner plugins
            for module in plugins:
                LOGGER.info(f"Executing plugin: {Path(module.__file__).name}")
                module.bidscoiner_plugin(session, bidsmap, bidsfolder, personals, subprefix, sesprefix)

            # Clean-up the temporary unpacked data
            if unpacked:
                shutil.rmtree(session)

        # Store the collected personals in the participant_table
        for key in personals:

            # participant_id is the index of the participants_table
            assert 'participant_id' in personals
            if key == 'participant_id':
                continue

            # TODO: Check that only values that are consistent over sessions go in the participants.tsv file, otherwise put them in a sessions.tsv file

            if key not in participants_dict:
                participants_dict[key] = dict(LongName     = 'Long (unabbreviated) name of the column',
                                              Description  = 'Description of the the column',
                                              Levels       = dict(Key='Value (This is for categorical variables: a dictionary of possible values (keys) and their descriptions (values))'),
                                              Units        = 'Measurement units. [<prefix symbol>]<unit symbol> format following the SI standard is RECOMMENDED')
            participants_table.loc[personals['participant_id'], key] = personals[key]

    # Write the collected data to the participant files
    LOGGER.info(f"Writing subject data to: {participants_tsv}")
    participants_table.replace('','n/a').to_csv(participants_tsv, sep='\t', encoding='utf-8', na_rep='n/a')

    LOGGER.info(f"Writing subject data dictionary to: {participants_json}")
    with participants_json.open('w') as json_fid:
        json.dump(participants_dict, json_fid, indent=4)

    LOGGER.info('-------------- FINISHED! ------------')
    LOGGER.info('')

    bidscoin.reporterrors()


def main():
    """Console script usage"""

    # Parse the input arguments and run bidscoiner(args)
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidscoiner /project/foo/raw /project/foo/bids\n'
                                            '  bidscoiner -f /project/foo/raw /project/foo/bids -p sub-009 sub-030\n ')
    parser.add_argument('sourcefolder',             help='The study root folder containing the raw data in sub-#/[ses-#/]data subfolders (or specify --subprefix and --sesprefix for different prefixes)')
    parser.add_argument('bidsfolder',               help='The destination / output folder with the bids data')
    parser.add_argument('-p','--participant_label', help='Space separated list of selected sub-# names / folders to be processed (the sub- prefix can be removed). Otherwise all subjects in the sourcefolder will be selected', nargs='+')
    parser.add_argument('-f','--force',             help='If this flag is given subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped', action='store_true')
    parser.add_argument('-s','--skip_participants', help='If this flag is given those subjects that are in participants.tsv will not be processed (also when the --force flag is given). Otherwise the participants.tsv table is ignored', action='store_true')
    parser.add_argument('-b','--bidsmap',           help='The study bidsmap file with the mapping heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-n','--subprefix',         help="The prefix common for all the source subject-folders. Default: 'sub-'", default='sub-')
    parser.add_argument('-m','--sesprefix',         help="The prefix common for all the source session-folders. Default: 'ses-'", default='ses-')
    parser.add_argument('-v','--version',           help='Show the installed version and check for updates', action='version', version=f"BIDS-version:\t\t{bidscoin.bidsversion()}\nBIDScoin-version:\t{localversion}, {versionmessage}")
    args = parser.parse_args()

    bidscoiner(rawfolder    = args.sourcefolder,
               bidsfolder   = args.bidsfolder,
               subjects     = args.participant_label,
               force        = args.force,
               participants = args.skip_participants,
               bidsmapfile  = args.bidsmap,
               subprefix    = args.subprefix,
               sesprefix    = args.sesprefix)


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
