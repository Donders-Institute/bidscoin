#!/usr/bin/env python3
"""A BIDScoin application to convert source data to BIDS (See also cli/_bidscoiner.py)"""

# NB: Set os.environ['DUECREDIT'] values as early as possible to capture all credits
import os
import sys
if __name__ == "__main__" and os.getenv('DUECREDIT_ENABLE','').lower() not in ('1', 'yes', 'true') and len(sys.argv) > 2:    # Ideally the due state (`self.__active=True`) should also be checked (but that's impossible)
    os.environ['DUECREDIT_ENABLE'] = 'yes'
    os.environ['DUECREDIT_FILE']   = os.path.join(sys.argv[2], 'code', 'bidscoin', '.duecredit_bidscoiner.p')   # NB: argv[2] = bidsfolder

import dateutil.parser
import re
import pandas as pd
import json
import logging
import shutil
import urllib.request, urllib.error
from typing import List, Set
from fnmatch import fnmatch
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    sys.path.append(str(Path(__file__).parents[1]))
from bidscoin import bcoin, bids, lsdirs, bidsversion, trackusage, __version__, DEBUG


def bidscoiner(rawfolder: str, bidsfolder: str, subjects: list=(), force: bool=False, bidsmapfile: str='bidsmap.yaml', cluster: bool=False, nativespec: str='') -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder and uses the
    bidsmap.yaml file in bidsfolder/code/bidscoin to cast the data into the BIDS folder.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param subjects:        List of selected subjects / participants (i.e. sub-# names / folders) to be processed (the sub-prefix can be removed). Otherwise, all subjects in the sourcefolder will be selected
    :param force:           If True, subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise, existing folders will be skipped
    :param bidsmapfile:     The name of the bidsmap YAML-file. If the bidsmap pathname is just the basename (i.e. no "/" in the name) then it is assumed to be located in the current directory or in bidsfolder/code/bidscoin
    :param cluster:         Use the DRMAA library to submit the bidscoiner jobs to a high-performance compute (HPC) cluster
    :param nativespec:      DRMAA native specifications for submitting bidscoiner jobs to the HPC cluster. See cli/_bidscoiner() for default
    :return:                Nothing
    """

    # Input checking & defaults
    rawfolder      = Path(rawfolder).resolve()
    bidsfolder     = Path(bidsfolder).resolve()
    bidsmapfile    = Path(bidsmapfile)
    bidscoinfolder = bidsfolder/'code'/'bidscoin'
    bidscoinfolder.mkdir(parents=True, exist_ok=True)
    if not rawfolder.is_dir():
        print(f"Rawfolder '{rawfolder}' not found")
        return

    # Start logging
    bcoin.setup_logging(bidscoinfolder/'bidscoiner.log')
    LOGGER.info('')
    LOGGER.info(f"-------------- START BIDScoiner {__version__}: BIDS {bidsversion()} ------------")
    LOGGER.info(f">>> bidscoiner sourcefolder={rawfolder} bidsfolder={bidsfolder} subjects={subjects} force={force} bidsmap={bidsmapfile}")

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
    if not readme_file.is_file():
        LOGGER.info(f"Creating a template README file (adjust it to your needs): {readme_file}")
        try:
            urllib.request.urlretrieve('https://raw.githubusercontent.com/bids-standard/bids-starter-kit/main/templates/README.MD', readme_file)
        except urllib.error.URLError:
            readme_file.write_text(
                f"A free form text ( README ) describing the dataset in more details that SHOULD be provided. For an example, see e.g.:\n"
                f"https://github.com/bids-standard/bids-starter-kit/blob/main/templates/README.MD\n\n"
                f"The raw BIDS data was created using BIDScoin {__version__}\n"
                f"All provenance information and settings can be found in ./code/bidscoin\n"
                f"For more information see: https://github.com/Donders-Institute/bidscoin\n")

    # Get the bidsmap heuristics from the bidsmap YAML-file
    bidsmap, bidsmapfile = bids.load_bidsmap(bidsmapfile, bidscoinfolder)
    dataformats          = [dataformat for dataformat in bidsmap if dataformat and dataformat not in ('$schema','Options')]
    if not bidsmap:
        LOGGER.error(f"No bidsmap file found in {bidsfolder}. Please run the bidsmapper first and/or use the correct bidsfolder")
        return

    # Load the data conversion plugins
    plugins = [bcoin.import_plugin(plugin, ('bidscoiner_plugin',)) for plugin,options in bidsmap['Options']['plugins'].items()]
    plugins = [plugin for plugin in plugins if plugin]          # Filter the empty items from the list
    if not plugins:
        LOGGER.warning(f"The plugins listed in your bidsmap['Options'] did not have a usable `bidscoiner_plugin` function, nothing to do")
        LOGGER.info('-------------- FINISHED! ------------')
        LOGGER.info('')
        return

    # Append options to the .bidsignore file
    bidsignore_items = bidsmap['Options']['bidscoin']['bidsignore']
    bidsignore_file  = bidsfolder/'.bidsignore'
    if bidsignore_items:
        LOGGER.verbose(f"Writing {bidsignore_items} entries to {bidsignore_file}")
        if bidsignore_file.is_file():
            bidsignore_items += bidsignore_file.read_text().splitlines()
        with bidsignore_file.open('w') as bidsignore:
            for item in set(bidsignore_items):
                bidsignore.write(item + '\n')

    # Get the list of subjects
    subprefix = bidsmap['Options']['bidscoin']['subprefix'].replace('*','')
    sesprefix = bidsmap['Options']['bidscoin']['sesprefix'].replace('*','')
    if not subjects:
        subjects = lsdirs(rawfolder, (subprefix if subprefix!='*' else '') + '*')
        if not subjects:
            LOGGER.warning(f"No subjects found in: {rawfolder/subprefix}*")
    else:
        subjects = [rawfolder/(subprefix + re.sub(f"^{'' if subprefix=='*' else re.escape(subprefix)}",'',subject)) for subject in subjects]   # Make sure there is a sub-prefix

    # Recursively call bidscoiner to run individual subjects on the HPC
    if cluster:

        from drmaa import Session as drmaasession           # NB: Importing drmaa for non-HPC users may cause import errors

        LOGGER.info('')
        LOGGER.info('============== HPC START ==============')
        LOGGER.info('')
        with drmaasession() as pbatch:
            jt                     = pbatch.createJobTemplate()
            jt.jobEnvironment      = os.environ
            jt.remoteCommand       = shutil.which('bidscoiner') or __file__
            jt.nativeSpecification = nativespec
            jt.joinFiles           = True
            jobids                 = []

            # Run individual subject jobs in temporary bids subfolders
            for subject in subjects:

                # Check if we should skip the session-folder
                datasource = bids.get_datasource(subject, bidsmap['Options']['plugins'])
                subid,_    = datasource.subid_sesid(bidsmap[datasource.dataformat]['subject'], bidsmap[datasource.dataformat]['session'])
                if (bidsfolder/subid).is_dir() and not force:
                    LOGGER.info(f">>> Skipping already processed subject: {bidsfolder/subid} (you can use the -f option to overrule)")
                    continue

                # Create the job arguments and add it to the batch
                bidsfolder_tmp = bidsfolder/'HPC_work'/f"bids_{subid}"      # NB: f"bids_{subid}" is used later, don't change
                bidsfolder_tmp.mkdir(parents=True, exist_ok=True)
                jt.args        = [rawfolder, bidsfolder_tmp, '-p', subject.name, '-b', bidsmapfile] + (['-f'] if force else [])
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
            bcoin.synchronize(pbatch, jobids)

        # Merge the bids subfolders
        errors                                = ''
        provdata                              = bids.bidsprov(bidsfolder/'dummy', Path())
        participants_table, participants_dict = bids.addparticipant(bidsfolder/'participants.tsv')
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
                participant_table, participant_dict = bids.addparticipant(bidsfolder_tmp/'participants.tsv')
                participants_table                  = pd.concat([participants_table, participant_table])
                participants_dict.update(participant_dict)

        # Save the provenance and participants data to disk
        provdata.sort_index().to_csv(bidscoinfolder/'bidscoiner.tsv', sep='\t')
        participants_table.replace('', 'n/a').to_csv(bidsfolder/'participants.tsv', sep='\t', encoding='utf-8', na_rep='n/a')
        with (bidsfolder/'participants.json').open('w') as fid:
            json.dump(participants_dict, fid, indent=4)

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
                sesfolders, unpacked = bids.unpack(session, bidsmap['Options']['bidscoin'].get('unzip',''))
                for sesfolder in sesfolders:

                    # Check if we should skip the session-folder
                    datasource = bids.get_datasource(sesfolder, bidsmap['Options']['plugins'])
                    if not datasource.dataformat:
                        LOGGER.info(f">>> No datasources found in '{sesfolder}'")
                        continue
                    subid        = bidsmap[datasource.dataformat]['subject']
                    sesid        = bidsmap[datasource.dataformat]['session']
                    subid, sesid = datasource.subid_sesid(subid, sesid or '')
                    bidssession  = bidsfolder/subid/sesid       # TODO: Support DICOMDIR with multiple subjects (as in PYDICOMDIR)
                    if not force and bidssession.is_dir():
                        datatypes = []
                        for dataformat in dataformats:
                            for datatype in lsdirs(bidssession):                               # See what datatypes we already have in the bids session-folder
                                if list(datatype.iterdir()) and bidsmap[dataformat].get(datatype.name): # See if we are going to add data for this datatype
                                    datatypes.append(datatype.name)
                        if datatypes:
                            LOGGER.info(f">>> Skipping processed session: {bidssession} already has {datatypes} data (you can carefully use the -f option to overrule)")
                            continue

                    LOGGER.info(f">>> Coining datasources in: {sesfolder}")
                    if bidssession.is_dir():
                        LOGGER.warning(f"Existing BIDS output-directory found, which may result in duplicate data (with increased run-index). Make sure {bidssession} was cleaned-up from old data before (re)running the bidscoiner")
                    bidssession.mkdir(parents=True, exist_ok=True)

                    # Run the bidscoiner plugins
                    for module in plugins:
                        LOGGER.verbose(f"Executing plugin: {Path(module.__file__).stem}")
                        trackusage(Path(module.__file__).stem)
                        personals = module.bidscoiner_plugin(sesfolder, bidsmap, bidssession)

                        # Add a subject row to the participants table (if there is any data)
                        if next(bidssession.rglob('*.json'), None):
                            bids.addparticipant(bidsfolder/'participants.tsv', subid, sesid, personals)

                    # Add the special fieldmap metadata (IntendedFor, TE, etc)
                    addmetadata(bidssession, subid, sesid)

                    # Check / repair the run-indices using acq_time info in the scans_table
                    bids.check_runindices(bidssession)

                    # Clean-up the temporary unpacked data
                    if unpacked:
                        shutil.rmtree(sesfolder)

    LOGGER.info('-------------- FINISHED! ------------')
    LOGGER.info('')

    bcoin.reporterrors()


def limitmatches(fmap: str, matches: List[str], limits: str, niifiles: Set[str], scans_table: pd.DataFrame):
    """
    Helper function for addmetadata() to check if there are multiple fieldmap runs and get the lower- and upperbound from
    the AcquisitionTime to bound the grand list of matches to adjacent runs. The resulting list is appended to niifiles

    :param fmap:        The fieldmap (relative to the session folder)
    :param matches:     The images (relative to the session folder) associated with the fieldmap
    :param limits:      The bounding limits from the dynamic value: '[lowerlimit:upperlimit]'
    :param niifiles:    The list to which the bounded results are appended
    :param scans_table: The scans table with the acquisition times
    :return:
    """

    # Check the input
    if limits == '[]':
        limits = '[:]'

    # Set fallback upper and lower bounds if parsing the scans-table is not possible
    fmaptime   = dateutil.parser.parse('1925-01-01')    # Use the BIDS stub acquisition time
    lowerbound = fmaptime.replace(year=1900)            # Use an ultra-wide lower limit for the search
    upperbound = fmaptime.replace(year=2100)            # Idem for the upper limit

    # There may be more fieldmaps, hence try to limit down the matches to the adjacent acquisitions
    try:
        fmaptime = dateutil.parser.parse(scans_table.loc[fmap, 'acq_time'])
        runindex = bids.get_bidsvalue(fmap, 'run')
        prevfmap = bids.get_bidsvalue(fmap, 'run', str(int(runindex) - 1))
        nextfmap = bids.get_bidsvalue(fmap, 'run', str(int(runindex) + 1))
        if prevfmap in scans_table.index:
            lowerbound = dateutil.parser.parse(scans_table.loc[prevfmap, 'acq_time'])  # Narrow the lower search limit down to the preceding fieldmap
        if nextfmap in scans_table.index:
            upperbound = dateutil.parser.parse(scans_table.loc[nextfmap, 'acq_time'])  # Narrow the upper search limit down to the succeeding fieldmap
    except (TypeError, ValueError, KeyError, dateutil.parser.ParserError) as acqtimeerror:
        pass  # Raise this only if there are limits and matches, i.e. below

    # Limit down the matches if the user added a range specifier/limits
    if limits and matches:
        try:
            limits     = limits[1:-1].split(':', 1)     # limits: '[lowerlimit:upperlimit]' -> ['lowerlimit', 'upperlimit']
            lowerlimit = int(limits[0]) if limits[0].strip() else float('-inf')
            upperlimit = int(limits[1]) if limits[1].strip() else float('inf')
            acqtimes   = []
            for match in set(matches):
                acqtimes.append((dateutil.parser.parse(scans_table.loc[match, 'acq_time']), match))  # Time + filepath relative to the session-folder
            acqtimes.sort(key=lambda acqtime: acqtime[0])
            offset = sum([acqtime[0] < fmaptime for acqtime in acqtimes])  # The nr of preceding runs
            for nr, acqtime in enumerate(acqtimes):
                if (lowerbound < acqtime[0] < upperbound) and (lowerlimit <= nr-offset <= upperlimit):
                    niifiles.add(acqtime[1])
        except Exception as matcherror:
            LOGGER.error(f"Could not bound the fieldmaps using <*:{limits}> as it requires a *_scans.tsv file with acq_time values for: {fmap}\n{matcherror}")
            niifiles.update(matches)
    else:
        niifiles.update(matches)


def addmetadata(bidsses: Path, subid: str, sesid: str) -> None:
    """
    Adds the special fieldmap metadata (IntendedFor, TE, etc.)

    :param bidsses: The session folder with the BIDS session data
    :param subid:   The subject 'sub-label' identifier
    :param sesid:   The session 'ses-label' identifier
    """

    # Add IntendedFor search results and TE1+TE2 meta-data to the fieldmap json-files. This has been postponed until all datatypes have been processed (i.e. so that all target images are indeed on disk)
    if (bidsses/'fmap').is_dir():

        scans_tsv = bidsses/f"{subid}{'_'+sesid if sesid else ''}_scans.tsv"
        if scans_tsv.is_file():
            scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
        else:
            scans_table = pd.DataFrame(columns=['acq_time'])

        for fmap in [fmap.relative_to(bidsses).as_posix() for fmap in sorted((bidsses/'fmap').glob('sub-*.nii*'))]:

            # Load the existing meta-data
            jsondata = {}
            jsonfile = (bidsses/fmap).with_suffix('').with_suffix('.json')
            if jsonfile.is_file():
                with jsonfile.open('r') as sidecar:
                    jsondata = json.load(sidecar)

            # Populate the dynamic IntendedFor values
            intendedfor = jsondata.get('IntendedFor')
            if intendedfor and isinstance(intendedfor, str):

                # Search with multiple patterns for matching NIfTI-files in all runs and store the relative paths to the session folder
                niifiles = set()
                if intendedfor.startswith('<') and intendedfor.endswith('>'):
                    intendedfor = intendedfor[2:-2].split('><')
                elif not isinstance(intendedfor, list):
                    intendedfor = [intendedfor]
                for part in intendedfor:
                    pattern = part.split(':',1)[0].strip()          # part = 'pattern: [lowerlimit:upperlimit]'
                    limits  = part.split(':',1)[1].strip() if ':' in part else ''
                    matches = [niifile.relative_to(bidsses).as_posix() for niifile in sorted(bidsses.rglob(f"*{pattern}*")) if pattern and '.nii' in niifile.suffixes]
                    limitmatches(fmap, matches, limits, niifiles, scans_table)

                # Add the IntendedFor data. NB: The BIDS URI paths need to use forward slashes and be relative to the bids root folder
                if niifiles:
                    LOGGER.verbose(f"Adding IntendedFor to: {jsonfile}")
                    jsondata['IntendedFor'] = [f"bids::{(Path(subid)/sesid/niifile).as_posix()}" for niifile in niifiles]
                else:
                    LOGGER.warning(f"Empty 'IntendedFor' fieldmap value in {jsonfile}: the search for {intendedfor} gave no results")
                    jsondata['IntendedFor'] = None

            elif not (jsondata.get('B0FieldSource') or jsondata.get('B0FieldIdentifier')):
                LOGGER.warning(f"Empty IntendedFor / B0FieldSource / B0FieldIdentifier fieldmap values in {jsonfile} (i.e. the fieldmap may not be used)")

            # Work-around because the bids-validator (v1.8) cannot handle `null` values / unused IntendedFor fields
            if not jsondata.get('IntendedFor'):
                jsondata.pop('IntendedFor', None)

            # Populate the dynamic B0FieldIdentifier/Source values with a run-index string if they contain a range specifier
            b0fieldtag = jsondata.get('B0FieldIdentifier')              # TODO: Refactor the code below to deal with B0FieldIdentifier lists (anywhere) instead of assuming it's a string (inside the fmap folder)
            if isinstance(b0fieldtag, str) and fnmatch(b0fieldtag, '*<<*:[[]*[]]>>*'):  # b0fieldtag = 'tag<<session:[lowerlimit:upperlimit]>>tag'

                # Search in all runs for the b0fieldtag and store the relative paths to the session folder
                niifiles = set()
                matches  = []
                dynamic  = b0fieldtag.split('<<')[1].split('>>')[0]         # dynamic = 'session:[lowerlimit:upperlimit]'
                limits   = dynamic.split(':',1)[1].strip()                  # limits = '[lowerlimit:upperlimit]'
                for match in bidsses.rglob(f"sub-*.nii*"):
                    if match.with_suffix('').with_suffix('.json').is_file():
                        with match.with_suffix('').with_suffix('.json').open('r') as sidecar:
                            metadata = json.load(sidecar)
                        for b0fieldkey in ('B0FieldSource', 'B0FieldIdentifier'):
                            b0fieldtags = metadata.get(b0fieldkey)
                            if b0fieldtag == b0fieldtags or (isinstance(b0fieldtags, list) and b0fieldtag in b0fieldtags):
                                matches.append(match.relative_to(bidsses).as_posix())
                limitmatches(fmap, matches, limits, niifiles, scans_table)

                # In the b0fieldtags, replace the limits with fieldmap runindex
                newb0fieldtag = b0fieldtag.replace(':'+limits, '_'+bids.get_bidsvalue(fmap,'run'))
                for niifile in niifiles:
                    metafile = (bidsses/niifile).with_suffix('').with_suffix('.json')
                    LOGGER.bcdebug(f"Updating the b0fieldtag ({b0fieldtag} -> {newb0fieldtag}) for: {metafile}")
                    if niifile == fmap:
                        metadata = jsondata
                    elif metafile.is_file():
                        with metafile.open('r') as sidecar:
                            metadata = json.load(sidecar)
                    else:
                        continue
                    for b0fieldkey in ('B0FieldSource', 'B0FieldIdentifier'):
                        b0fieldtags = metadata.get(b0fieldkey)
                        if b0fieldtag == b0fieldtags:
                            metadata[b0fieldkey] = newb0fieldtag
                        elif isinstance(b0fieldtags, list) and b0fieldtag in b0fieldtags:
                            metadata[b0fieldkey][b0fieldtags.index(b0fieldtag)] = newb0fieldtag
                    if niifile != fmap:
                        with metafile.open('w') as sidecar:
                            json.dump(metadata, sidecar, indent=4)

            # Extract the echo times from magnitude1 and magnitude2 and add them to the phasediff json-file
            if jsonfile.name.endswith('phasediff.json'):
                json_magnitude = [None, None]
                echotime       = [None, None]
                for n in (0,1):
                    json_magnitude[n] = jsonfile.parent/jsonfile.name.replace('_phasediff', f"_magnitude{n+1}")
                    if not json_magnitude[n].is_file():
                        LOGGER.error(f"Could not find expected magnitude{n+1} image associated with: {jsonfile}\nUse the bidseditor to verify that the fmap images that belong together have corresponding BIDS output names")
                    else:
                        with json_magnitude[n].open('r') as sidecar:
                            data = json.load(sidecar)
                        echotime[n] = data.get('EchoTime')
                jsondata['EchoTime1'] = jsondata['EchoTime2'] = None
                if None in echotime:
                    LOGGER.error(f"Cannot find and add valid EchoTime1={echotime[0]} and EchoTime2={echotime[1]} data to: {jsonfile}")
                elif echotime[0] > echotime[1]:
                    LOGGER.error(f"Found invalid EchoTime1={echotime[0]} > EchoTime2={echotime[1]} for: {jsonfile}")
                else:
                    jsondata['EchoTime1'] = echotime[0]
                    jsondata['EchoTime2'] = echotime[1]
                    LOGGER.verbose(f"Adding EchoTime1: {echotime[0]} and EchoTime2: {echotime[1]} to {jsonfile}")

            # Save the collected meta-data to disk
            if jsondata:
                with jsonfile.open('w') as sidecar:
                    json.dump(jsondata, sidecar, indent=4)


def main():
    """Console script entry point"""

    from bidscoin.cli._bidscoiner import get_parser

    # Parse the input arguments and run bidscoiner(args)
    args = get_parser().parse_args()

    trackusage('bidscoiner')
    try:
        bidscoiner(rawfolder   = args.sourcefolder,
                   bidsfolder  = args.bidsfolder,
                   subjects    = args.participant_label,
                   force       = args.force,
                   bidsmapfile = args.bidsmap,
                   cluster     = args.cluster,
                   nativespec  = args.nativespec)

    except Exception:
        trackusage('bidscoiner_exception')
        raise


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
