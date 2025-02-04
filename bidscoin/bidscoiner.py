#!/usr/bin/env python3
"""A BIDScoin application to convert source data to BIDS (See also cli/_bidscoiner.py)"""

# NB: Set os.environ['DUECREDIT'] values as early as possible to capture all credits
import os
import sys
if __name__ == "__main__" and os.getenv('DUECREDIT_ENABLE','').lower() not in ('1', 'yes', 'true') and len(sys.argv) > 2:    # Ideally the due state (`self.__active=True`) should also be checked (but that's impossible)
    os.environ['DUECREDIT_ENABLE'] = 'yes'
    os.environ['DUECREDIT_FILE']   = os.path.join(sys.argv[2], 'code', 'bidscoin', '.duecredit_bidscoiner.p')   # NB: argv[2] = bidsfolder

import re
import pandas as pd
import json
import logging
import shutil
import urllib.request, urllib.error
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    sys.path.append(str(Path(__file__).parents[1]))
from bidscoin import bcoin, bids, lsdirs, bidsversion, trackusage, __version__, DEBUG
from bidscoin.utilities import unpack


def bidscoiner(sourcefolder: str, bidsfolder: str, participant: list=(), force: bool=False, bidsmap: str= 'bidsmap.yaml', cluster: str= '') -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder and uses the
    bidsmap.yaml file in bidsfolder/code/bidscoin to cast the data into the BIDS folder.

    :param sourcefolder: The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:   The name of the BIDS root folder
    :param participant:  List of selected subjects/participants (i.e. sub-# names/folders) to be processed (the sub-prefix can be omitted). Otherwise, all subjects in the sourcefolder will be processed
    :param force:        If True, participant will be processed, regardless of existing folders in the bidsfolder. Otherwise, existing folders will be skipped
    :param bidsmap:      The name of the bidsmap YAML-file. If the bidsmap pathname is just the base name (i.e. no "/" in the name) then it is assumed to be located in the current directory or in bidsfolder/code/bidscoin
    :param cluster:      Use the DRMAA library to submit the bidscoiner jobs to a high-performance compute (HPC) cluster with DRMAA native specifications for submitting bidscoiner jobs to the HPC cluster. See cli/_bidscoiner() for default
    :return:             Nothing
    """

    # Input checking & defaults
    rawfolder      = Path(sourcefolder).resolve()
    bidsfolder     = Path(bidsfolder).resolve()
    bidsmapfile    = Path(bidsmap)
    bidscoinfolder = bidsfolder/'code'/'bidscoin'
    bidscoinfolder.mkdir(parents=True, exist_ok=True)
    if not rawfolder.is_dir():
        raise SystemExit(f"\n[ERROR] Exiting the program because your sourcefolder argument '{sourcefolder}' was not found")

    # Start logging
    bcoin.setup_logging(bidscoinfolder/'bidscoiner.log')
    LOGGER.info('')
    LOGGER.info(f"-------------- START BIDScoiner {__version__}: BIDS {bidsversion()} ------------")
    LOGGER.info(f">>> bidscoiner sourcefolder={rawfolder} bidsfolder={bidsfolder} participant={participant} force={force} bidsmap={bidsmapfile}")

    # Create a dataset description file if it does not exist
    dataset_file = bidsfolder/'dataset_description.json'
    generatedby  = [{"Name":"BIDScoin", 'Version':__version__, 'Description:':'A flexible GUI application suite that converts source datasets to BIDS', 'CodeURL':'https://github.com/Donders-Institute/bidscoin'}]
    if not dataset_file.is_file():
        LOGGER.info(f"Creating dataset description file: {dataset_file}")
        dataset_description = {'Name':                  'REQUIRED. Name of the dataset',
                               'GeneratedBy':           generatedby,
                               'BIDSVersion':           str(bidsversion()),
                               'DatasetType':           'raw',
                               'License':               'RECOMMENDED. The license for the dataset. The use of license name abbreviations is RECOMMENDED for specifying a license. The corresponding full license text MAY be specified in an additional LICENSE file',
                               'Authors':               ['OPTIONAL. List of individuals who contributed to the creation/curation of the dataset'],
                               'Acknowledgements':      'OPTIONAL. Text acknowledging contributions of individuals or institutions beyond those listed in Authors or Funding',
                               'HowToAcknowledge':      'OPTIONAL. Instructions how researchers using this dataset should acknowledge the original authors. This field can also be used to define a publication that should be cited in publications that use the dataset',
                               'Funding':               ['OPTIONAL. List of sources of funding (grant numbers)'],
                               'EthicsApprovals':    	['OPTIONAL. List of ethics committee approvals of the research protocols and/or protocol identifiers'],
                               'ReferencesAndLinks':    ['OPTIONAL. List of references to publication that contain information on the dataset, or links', 'https://github.com/Donders-Institute/bidscoin'],
                               'DatasetDOI':            'OPTIONAL. The Document Object Identifier of the dataset (not the corresponding paper)'}
    else:
        with dataset_file.open('r') as fid:
            dataset_description = json.load(fid)
        if 'BIDScoin' not in [generatedby_['Name'] for generatedby_ in dataset_description.get('GeneratedBy',[])]:
            LOGGER.verbose(f"Adding {generatedby} to {dataset_file}")
            dataset_description['GeneratedBy'] = dataset_description.get('GeneratedBy',[]) + generatedby
    with dataset_file.open('w') as fid:
        json.dump(dataset_description, fid, indent=4)

    # Create a README file if it does not exist
    readme_file = bidsfolder/'README'
    if not (readme_file.is_file() or next(bidsfolder.glob('README.*'), None)):
        LOGGER.info(f"Creating a template README file (adjust it to your needs): {readme_file}")
        try:
            urllib.request.urlretrieve('https://raw.githubusercontent.com/bids-standard/bids-starter-kit/main/templates/README.MD', readme_file)
        except urllib.error.URLError:
            readme_file.write_text(f"A free form text ( README ) describing the dataset in more details that SHOULD be provided. For an example, see e.g.:\n"
                                   f"https://github.com/bids-standard/bids-starter-kit/blob/main/templates/README.MD\n\n"
                                   f"The raw BIDS data was created using BIDScoin {__version__}\n"
                                   f"All provenance information and settings can be found in ./code/bidscoin\n"
                                   f"For more information see: https://github.com/Donders-Institute/bidscoin\n")

    # Get the bidsmap heuristics from the bidsmap YAML-file
    bidsmap = bids.BidsMap(bidsmapfile, bidscoinfolder)
    if not bidsmap.filepath.is_file():
        LOGGER.error(f"No bidsmap file found in {bidsfolder}. Please run the bidsmapper first and/or use the correct bidsfolder")
        return

    # Load the data conversion plugins
    plugins = [plugin for name in bidsmap.plugins if (plugin := bcoin.import_plugin(name))]
    if not plugins:
        LOGGER.warning(f"The {bidsmap.plugins.keys()} plugins listed in your bidsmap['Options'] did not have a usable `bidscoiner` interface, nothing to do")
        LOGGER.info('-------------- FINISHED! ------------')
        LOGGER.info('')
        return

    # Append options to the .bidsignore file
    bidsignore_items = bidsmap.options['bidsignore']
    bidsignore_file  = bidsfolder/'.bidsignore'
    if bidsignore_items:
        LOGGER.verbose(f"Writing {bidsignore_items} entries to {bidsignore_file}")
        if bidsignore_file.is_file():
            bidsignore_items += bidsignore_file.read_text().splitlines()
        with bidsignore_file.open('w') as bidsignore:
            for item in set(bidsignore_items):
                bidsignore.write(item + '\n')

    # Get the list of subjects
    subprefix = bidsmap.options['subprefix'].replace('*','')
    sesprefix = bidsmap.options['sesprefix'].replace('*','')
    if not participant:
        subjects = lsdirs(rawfolder, (subprefix if subprefix!='*' else '') + '*')
        if not subjects:
            LOGGER.warning(f"No subjects found in: {rawfolder/subprefix}*")
    else:
        subjects = [rawfolder/(subprefix + re.sub(f"^{'' if subprefix=='*' else re.escape(subprefix)}",'',subject)) for subject in participant]   # Make sure there is a sub-prefix

    # Recursively call bidscoiner to run individual subjects on the HPC
    if cluster:

        from drmaa import Session as drmaasession           # NB: Importing drmaa for non-HPC users may cause import errors
        from bidscoin.bcoin import drmaa_nativespec

        LOGGER.info('')
        LOGGER.info('============== HPC START ==============')
        LOGGER.info('')
        with drmaasession() as pbatch:
            jt                     = pbatch.createJobTemplate()
            environ                = os.environ.copy()
            environ.update({'BIDSCOIN_JOB': 'TRUE'})
            jt.jobEnvironment      = environ
            jt.remoteCommand       = shutil.which('bidscoiner') or __file__
            jt.nativeSpecification = drmaa_nativespec(cluster, pbatch)
            jt.joinFiles           = True
            jobids                 = []

            # Run individual subject jobs in temporary bids subfolders
            for subject in subjects:

                # Check if we should skip the subject-folder
                datasource = bids.get_datasource(subject, bidsmap.plugins)
                subid,_    = datasource.subid_sesid(bidsmap.dataformat(datasource.dataformat).subject, bidsmap.dataformat(datasource.dataformat).session)
                if not force and (bidsfolder/subid).is_dir() and next((bidsfolder/subid).iterdir(), None):
                    LOGGER.info(f">>> Skipping already processed subject: {bidsfolder/subid} (you can use the -f option to overrule)")
                    continue

                # Create the job arguments and add it to the batch
                bidsfolder_tmp = bidsfolder/'HPC_work'/f"bids_{subid}"      # NB: f"bids_{subid}" is used later, don't change
                bidsfolder_tmp.mkdir(parents=True, exist_ok=True)
                jt.args        = [rawfolder, bidsfolder_tmp, '-p', subject.name, '-b', bidsmap.filepath] + (['-f'] if force else [])
                jt.jobName     = f"bidscoiner_{subject.name}"
                jt.outputPath  = f"{os.getenv('HOSTNAME')}:{bidsfolder_tmp}/{jt.jobName}.out"
                jobids.append(pbatch.runJob(jt))
                LOGGER.info(f"Your {jt.jobName} job has been submitted with ID: {jobids[-1]}")

            pbatch.deleteJobTemplate(jt)

            LOGGER.info('')
            if not jobids:
                LOGGER.info('============== HPC FINISH =============')
                LOGGER.info('')
                return

            LOGGER.info('Waiting for the bidscoiner jobs to finish...')
            bcoin.synchronize(pbatch, jobids, 'bidscoiner')

        # Merge the bids subfolders
        errors             = ''
        provdata           = bids.bidsprov(bidsfolder)
        participants_table = bids.addparticipant(bidsfolder/'participants.tsv')
        participants_meta  = bids.addparticipant_meta(bidsfolder/'participants.json')
        for bidsfolder_tmp in sorted((bidsfolder/'HPC_work').glob('bids_*')):

            subid = bidsfolder_tmp.name[5:]         # Uses name = f"bids_{subid}" (as defined above)

            # Copy over the logfiles content
            for logfile_tmp in (bidsfolder_tmp/'code'/'bidscoin').glob('bidscoiner.*'):
                logfile = bidscoinfolder/f"{logfile_tmp.name}"
                if logfile_tmp.suffix == '.tsv':
                    provdata_tmp = pd.read_csv(logfile_tmp, sep='\t', index_col='source')
                    provdata     = pd.concat([provdata, provdata_tmp])
                else:
                    logfile.write_text(f"{logfile.read_text()}\n{logfile_tmp.read_text()}")
                if logfile_tmp.suffix == '.errors' and logfile_tmp.stat().st_size:
                    errors += f"{logfile_tmp.read_text()}\n"

            # Check if data was produced or if it already exists (-> unpacked data)
            if not (bidsfolder_tmp/subid).is_dir():
                LOGGER.info(f"No HPC data found for: {subid}")
                continue
            if (bidsfolder/subid).is_dir():
                LOGGER.verbose(f"Processed data already exists: {bidsfolder/subid}")
                continue

            # Move the subject + derived data
            LOGGER.verbose(f"Moving: {subid} -> {bidsfolder}")
            shutil.move(bidsfolder_tmp/subid, bidsfolder)
            if (bidsfolder_tmp/'derivatives').is_dir():
                for derivative in (bidsfolder_tmp/'derivatives').iterdir():
                    for item in derivative.iterdir():
                        if (bidsfolder/item.relative_to(bidsfolder_tmp)).exists():
                            LOGGER.verbose(f"Processed data already exists: {item.relative_to(bidsfolder_tmp)}")
                            continue
                        (bidsfolder/'derivatives'/derivative.name).mkdir(parents=True, exist_ok=True)
                        LOGGER.verbose(f"Moving: {item} -> {bidsfolder}")
                        shutil.move(item, bidsfolder/item.relative_to(bidsfolder_tmp))

            # Update the participants table + dictionary
            if subid not in participants_table.index:
                LOGGER.verbose(f"Merging: participants.tsv -> {bidsfolder/'participants.tsv'}")
                participant_table  = bids.addparticipant(bidsfolder_tmp/'participants.tsv')
                participants_table = pd.concat([participants_table, participant_table])
                participant_meta   = bids.addparticipant_meta(bidsfolder_tmp/'participants.json')
                participants_meta.update(participant_meta)

        # Save the provenance and participants data to disk
        provdata.sort_index().to_csv(bidscoinfolder/'bidscoiner.tsv', sep='\t')
        participants_table.replace('', 'n/a').to_csv(bidsfolder/'participants.tsv', sep='\t', encoding='utf-8', na_rep='n/a')
        with (bidsfolder/'participants.json').open('w') as fid:
            json.dump(participants_meta, fid, indent=4)

        if not DEBUG:
            shutil.rmtree(bidsfolder/'HPC_work', ignore_errors=True)

        LOGGER.info('')
        LOGGER.info('============== HPC FINISH =============')
        LOGGER.info('')

        if errors:
            LOGGER.info(f"The following BIDScoin errors and warnings were reported:\n\n{40 * '>'}\n{errors}{40 * '<'}\n")

        return

    # Loop over all subjects and sessions and convert them using the bidsmap entries
    with logging_redirect_tqdm():
        for n, subject in enumerate(tqdm(subjects, unit='subject', colour='green', leave=False), 1):

            LOGGER.info(f"------------------- Subject {n}/{len(subjects)} -------------------")
            if not subject.is_dir():
                LOGGER.error(f"The '{subject}' subject folder does not exist")
                continue

            sessions = lsdirs(subject, (sesprefix if sesprefix!='*' else '') + '*')
            if not sessions or (subject/'DICOMDIR').is_file():
                sessions = [subject]
            for session in sessions:

                # Unpack the data in a temporary folder if it is tarballed/zipped and/or contains a DICOMDIR file
                sesfolders, unpacked = unpack(session, bidsmap.options.get('unzip',''))
                for sesfolder in sesfolders:

                    # Run the bidscoiner plugins
                    for plugin in plugins:

                        # Check if we should skip the sesfolder
                        name       = Path(plugin.__file__).stem
                        datasource = bids.get_datasource(sesfolder, {name: bidsmap.plugins[name]})
                        if not datasource.dataformat:
                            LOGGER.info(f">>> No {name} datasources found in '{sesfolder}'")
                            continue
                        subid        = bidsmap.dataformat(datasource.dataformat).subject
                        sesid        = bidsmap.dataformat(datasource.dataformat).session
                        subid, sesid = datasource.subid_sesid(subid, sesid or '')
                        bidssession  = bidsfolder/subid/sesid       # TODO: Support DICOMDIR with multiple subjects (as in PYDICOMDIR)
                        if not force and bidssession.is_dir():
                            datatypes = set()
                            for datatype in [dtype for dtype in lsdirs(bidssession) if next(dtype.iterdir(), None)]:    # See what non-empty datatypes we already have in the bids session-folder
                                if datatype.name in bidsmap.dataformat(datasource.dataformat).datatypes:                # See if the plugin may add data for this datatype
                                    datatypes.add(datatype.name)
                            if datatypes:
                                LOGGER.info(f">>> Skipping {name} processing: {bidssession} already has {datatypes} data (you can carefully use the -f option to overrule)")
                                continue

                        LOGGER.info(f">>> Coining {name} datasources in: {sesfolder}")
                        bidssession.mkdir(parents=True, exist_ok=True)
                        trackusage(name)
                        plugin.Interface().bidscoiner(sesfolder, bidsmap, bidssession)
                        personals = plugin.Interface().personals(bidsmap, datasource)

                        # Add a subject row to the participants table (if there is any data)
                        if next(bidssession.rglob('*.json'), None):
                            bids.addparticipant(bidsfolder/'participants.tsv', subid, sesid, personals)

                    # Add the special field map metadata (IntendedFor, TE, etc)
                    bids.addmetadata(bidssession)

                    # Check/repair the run-indices using acq_time info in the scans_table
                    bids.check_runindices(bidssession)

                    # Clean-up the temporary unpacked data
                    if unpacked:
                        shutil.rmtree(sesfolder)

    # Add the participants sidecar file
    bids.addparticipant_meta(bidsfolder/'participants.json', bidsmap)

    LOGGER.info('-------------- FINISHED! ------------')
    LOGGER.info('')

    bcoin.reporterrors()


def main():
    """Console script entry point"""

    from bidscoin.cli._bidscoiner import get_parser

    # Parse the input arguments and run bidscoiner(args)
    args = get_parser().parse_args()

    trackusage('bidscoiner')
    try:
        bidscoiner(**vars(args))

    except Exception as error:
        trackusage('bidscoiner_exception')
        raise error


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
