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


def bidscoiner(rawfolder: str, bidsfolder: str, subjects: list=(), force: bool=False, participants: bool=False, bidsmapfile: str='bidsmap.yaml') -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder and uses the
    bidsmap.yaml file in bidsfolder/code/bidscoin to cast the data into the BIDS folder.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param subjects:        List of selected subjects / participants (i.e. sub-# names / folders) to be processed (the sub- prefix can be removed). Otherwise all subjects in the sourcefolder will be selected
    :param force:           If True, subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped
    :param participants:    If True, subjects in particpants.tsv will not be processed (this could be used e.g. to protect these subjects from being reprocessed), also when force=True
    :param bidsmapfile:     The name of the bidsmap YAML-file. If the bidsmap pathname is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin
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
    LOGGER.info(f">>> bidscoiner sourcefolder={rawfolder} bidsfolder={bidsfolder} subjects={subjects} force={force} participants={participants} bidsmap={bidsmapfile}")

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
    dataformats = [dataformat for dataformat in bidsmap if dataformat and dataformat not in ('Options','PlugIns')]     # Handle legacy bidsmaps (-> 'PlugIns')
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
    participants_tsv = bidsfolder/'participants.tsv'
    if participants_tsv.is_file():
        participants_table = pd.read_csv(participants_tsv, sep='\t')
        participants_table.set_index(['participant_id'], verify_integrity=True, inplace=True)
    else:
        participants_table = pd.DataFrame()
        participants_table.index.name = 'participant_id'

    # Get the list of subjects
    subprefix = bidsmap['Options']['bidscoin']['subprefix']
    sesprefix = bidsmap['Options']['bidscoin']['sesprefix']
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

        sessions = bidscoin.lsdirs(subject, sesprefix + '*')
        if not sessions:
            sessions = [subject]
        for session in sessions:

            # Unpack the data in a temporary folder if it is tarballed/zipped and/or contains a DICOMDIR file
            session, unpacked = bids.unpack(session, subprefix, sesprefix)

            # Check if we should skip the session-folder
            datasource = bids.get_datasource(session, bidsmap['Options']['plugins'])
            if not datasource.dataformat:
                LOGGER.info(f"No coinable datasources found in '{session}'")
                continue
            if not force:
                subid, sesid = datasource.subid_sesid(bidsmap[datasource.dataformat]['subject'], bidsmap[datasource.dataformat]['session'])
                bidssession  = bidsfolder/subid/sesid
                datatypes    = []
                for dataformat in dataformats:
                    if sesid and not bidsmap[dataformat].get('session'):
                        bidssession = bidssession.parent
                    for datatype in bidscoin.lsdirs(bidssession):                           # See what datatypes we already have in the bids session-folder
                        if datatype.glob('*') and bidsmap[dataformat].get(datatype.name):   # See if we are going to add data for this datatype
                            datatypes.append(datatype.name)
                if datatypes:
                    LOGGER.info(f"Skipping processed session: {bidssession} already has {datatypes} data (you can carefully use the -f option to overrule)")
                    continue

            LOGGER.info(f"Coining datasources in: {session}")

            # Run the bidscoiner plugins
            for module in plugins:
                LOGGER.info(f"Executing plugin: {Path(module.__file__).name}")
                module.bidscoiner_plugin(session, bidsmap, bidsfolder)

            # Clean-up the temporary unpacked data
            if unpacked:
                shutil.rmtree(session)

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
    parser.add_argument('-v','--version',           help='Show the installed version and check for updates', action='version', version=f"BIDS-version:\t\t{bidscoin.bidsversion()}\nBIDScoin-version:\t{localversion}, {versionmessage}")
    args = parser.parse_args()

    bidscoiner(rawfolder    = args.sourcefolder,
               bidsfolder   = args.bidsfolder,
               subjects     = args.participant_label,
               force        = args.force,
               participants = args.skip_participants,
               bidsmapfile  = args.bidsmap)


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
