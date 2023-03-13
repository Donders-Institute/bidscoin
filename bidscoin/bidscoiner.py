#!/usr/bin/env python3
"""
Converts ("coins") your source datasets to NIfTI/json/tsv BIDS datasets using the mapping
information from the bidsmap.yaml file. Edit this bidsmap to your needs using the bidseditor
tool before running this function or (re-)run the bidsmapper whenever you encounter unexpected
data. You can run bidscoiner after all data has been collected, or run / re-run it whenever
new data has been added to your source folder (presuming the scan protocol hasn't changed).
Also, if you delete a subject/session folder from the bidsfolder, it will simply be re-created
from the sourcefolder the next time you run the bidscoiner.

The bidscoiner uses plugins, as stored in the bidsmap['Options'], to do the actual work

Provenance information, warnings and error messages are stored in the
bidsfolder/code/bidscoin/bidscoiner.log file.
"""

import argparse
import dateutil.parser
import textwrap
import re
import pandas as pd
import json
import logging
import shutil
import urllib.request
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
try:
    from bidscoin import bidscoin as bcoin
    from bidscoin import bids
except ImportError:
    import bidscoin as bcoin        # This should work if bidscoin was not pip-installed
    import bids

localversion, _ = bcoin.version(check=True)


def bidscoiner(rawfolder: str, bidsfolder: str, subjects: list=(), force: bool=False, bidsmapfile: str='bidsmap.yaml') -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder and uses the
    bidsmap.yaml file in bidsfolder/code/bidscoin to cast the data into the BIDS folder.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param subjects:        List of selected subjects / participants (i.e. sub-# names / folders) to be processed (the sub-prefix can be removed). Otherwise, all subjects in the sourcefolder will be selected
    :param force:           If True, subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise, existing folders will be skipped
    :param bidsmapfile:     The name of the bidsmap YAML-file. If the bidsmap pathname is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin
    :return:                Nothing
    """

    # Input checking & defaults
    rawfolder   = Path(rawfolder).resolve()
    bidsfolder  = Path(bidsfolder).resolve()
    bidsmapfile = Path(bidsmapfile)

    # Start logging
    bcoin.setup_logging(bidsfolder/'code'/'bidscoin'/'bidscoiner.log')
    LOGGER.info('')
    LOGGER.info(f"-------------- START BIDScoiner {localversion}: BIDS {bcoin.bidsversion()} ------------")
    LOGGER.info(f">>> bidscoiner sourcefolder={rawfolder} bidsfolder={bidsfolder} subjects={subjects} force={force} bidsmap={bidsmapfile}")

    # Create a code/bidscoin subfolder
    (bidsfolder/'code'/'bidscoin').mkdir(parents=True, exist_ok=True)

    # Create a dataset description file if it does not exist
    dataset_file = bidsfolder/'dataset_description.json'
    generatedby  = [{"Name":"BIDScoin", "Version":localversion, "CodeURL":"https://github.com/Donders-Institute/bidscoin"}]
    if not dataset_file.is_file():
        LOGGER.info(f"Creating dataset description file: {dataset_file}")
        dataset_description = {"Name":                  "REQUIRED. Name of the dataset",
                               "GeneratedBy":           generatedby,
                               "BIDSVersion":           str(bcoin.bidsversion()),
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
    plugins = [bcoin.import_plugin(plugin, ('bidscoiner_plugin',)) for plugin,options in bidsmap['Options']['plugins'].items()]
    plugins = [plugin for plugin in plugins if plugin]          # Filter the empty items from the list
    if not plugins:
        LOGGER.warning(f"The plugins listed in your bidsmap['Options'] did not have a usable `bidscoiner_plugin` function, nothing to do")
        LOGGER.info('-------------- FINISHED! ------------')
        LOGGER.info('')
        return

    # Append options to the .bidsignore file
    bidsignore_items = [item.strip() for item in bidsmap['Options']['bidscoin']['bidsignore'].split(';')]
    bidsignore_file  = bidsfolder/'.bidsignore'
    if bidsignore_items:
        LOGGER.verbose(f"Writing {bidsignore_items} entries to {bidsignore_file}")
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
    subprefix = bidsmap['Options']['bidscoin']['subprefix'].replace('*','')
    sesprefix = bidsmap['Options']['bidscoin']['sesprefix'].replace('*','')
    if not subjects:
        subjects = bcoin.lsdirs(rawfolder, (subprefix if subprefix!='*' else '') + '*')
        if not subjects:
            LOGGER.warning(f"No subjects found in: {rawfolder/subprefix}*")
    else:
        subjects = [rawfolder/(subprefix + re.sub(f"^{'' if subprefix=='*' else re.escape(subprefix)}",'',subject)) for subject in subjects]   # Make sure there is a sub-prefix

    # Loop over all subjects and sessions and convert them using the bidsmap entries
    with logging_redirect_tqdm():
        for n, subject in enumerate(tqdm(subjects, unit='subject', leave=False), 1):

            LOGGER.info(f"------------------- Subject {n}/{len(subjects)} -------------------")
            if not subject.is_dir():
                LOGGER.error(f"The '{subject}' subject folder does not exist")
                continue

            sessions = bcoin.lsdirs(subject, (sesprefix if sesprefix!='*' else '') + '*')
            if not sessions or (subject/'DICOMDIR').is_file():
                sessions = [subject]
            for session in sessions:

                # Unpack the data in a temporary folder if it is tarballed/zipped and/or contains a DICOMDIR file
                sesfolders, unpacked = bids.unpack(session, bidsmap['Options']['bidscoin'].get('unzip',''))
                for sesfolder in sesfolders:

                    # Check if we should skip the session-folder
                    datasource = bids.get_datasource(sesfolder, bidsmap['Options']['plugins'])
                    if not datasource.dataformat:
                        LOGGER.info(f">>> No coinable datasources found in '{sesfolder}'")
                        continue
                    subid        = bidsmap[datasource.dataformat]['subject']
                    sesid        = bidsmap[datasource.dataformat]['session']
                    subid, sesid = datasource.subid_sesid(subid, sesid if sesid else '')
                    bidssession  = bidsfolder/subid/sesid       # TODO: Support DICOMDIR with multiple subjects (as in PYDICOMDIR)
                    if not force and bidssession.is_dir():
                        datatypes = []
                        for dataformat in dataformats:
                            for datatype in bcoin.lsdirs(bidssession):                               # See what datatypes we already have in the bids session-folder
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
                        LOGGER.verbose(f"Executing plugin: {Path(module.__file__).name}")
                        module.bidscoiner_plugin(sesfolder, bidsmap, bidssession)

                    # Add the special fieldmap metadata (IntendedFor, B0FieldIdentifier, TE, etc)
                    addmetadata(bidssession, subid, sesid)

                    # Clean-up the temporary unpacked data
                    if unpacked:
                        shutil.rmtree(sesfolder)

    # Re-read the participants_table (the plugins may have changed it) and store the collected personals in the json sidecar-file
    if participants_tsv.is_file():
        participants_table = pd.read_csv(participants_tsv, sep='\t')
        participants_table.set_index(['participant_id'], verify_integrity=True, inplace=True)
    participants_json = participants_tsv.with_suffix('.json')
    participants_dict = {}
    if participants_json.is_file():
        with participants_json.open('r') as json_fid:
            participants_dict = json.load(json_fid)
    if not participants_dict.get('participant_id'):
        participants_dict['participant_id'] = {'Description': 'Unique participant identifier'}
    if not participants_dict.get('session_id') and 'session_id' in participants_table.columns:
        participants_dict['session_id'] = {'Description': 'Session identifier'}
    newkey = False
    for col in participants_table.columns:
        if col not in participants_dict:
            newkey = True
            participants_dict[col] = dict(LongName    = 'Long (unabbreviated) name of the column',
                                          Description = 'Description of the the column',
                                          Levels      = dict(Key='Value (This is for categorical variables: a dictionary of possible values (keys) and their descriptions (values))'),
                                          Units       = 'Measurement units. [<prefix symbol>]<unit symbol> format following the SI standard is RECOMMENDED')

    # Write the collected data to the participant files
    if newkey:
        LOGGER.info(f"Writing subject meta data to: {participants_json}")
        with participants_json.open('w') as json_fid:
            json.dump(participants_dict, json_fid, indent=4)

    LOGGER.info('-------------- FINISHED! ------------')
    LOGGER.info('')

    bcoin.reporterrors()


def addmetadata(bidsses: Path, subid: str, sesid: str) -> None:
    """
    Adds the special fieldmap metadata (IntendedFor, B0FieldIdentifier, TE, etc.)

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

        fmaps = [fmap.relative_to(bidsses).as_posix() for fmap in sorted((bidsses/'fmap').glob('sub-*.nii*'))]
        for fmap in fmaps:

            # Load the existing meta-data
            jsonfile = bidsses/Path(fmap).with_suffix('').with_suffix('.json')
            with jsonfile.open('r') as sidecar:
                jsondata = json.load(sidecar)

            # Search for the imaging files that match the IntendedFor search criteria
            intendedfor = jsondata.get('IntendedFor')
            if intendedfor and isinstance(intendedfor, str):

                # Check if there are multiple runs and get the lower- and upperbound from the AcquisitionTime to limit down the IntendedFor search
                fmaptime   = dateutil.parser.parse('1925-01-01')                                    # If nothing, use the BIDS stub acquisition time
                lowerbound = fmaptime.replace(year=1900)                                            # If nothing, use an ultra-wide lower limit for the IntendedFor search
                upperbound = fmaptime.replace(year=2100)                                            # Idem for the upper limit
                try:                                                                                # There may be more fieldmaps, hence try to limit down the search to the adjacently acquired data
                    fmaptime = dateutil.parser.parse(scans_table.loc[fmap, 'acq_time'])
                    runindex = bids.get_bidsvalue(fmap, 'run')
                    prevfmap = bids.get_bidsvalue(fmap, 'run', str(int(runindex) - 1))
                    nextfmap = bids.get_bidsvalue(fmap, 'run', str(int(runindex) + 1))
                    if prevfmap in fmaps:
                        lowerbound = dateutil.parser.parse(scans_table.loc[prevfmap, 'acq_time'])   # Narrow the lower search limit down to the preceding fieldmap
                    if nextfmap in fmaps:
                        upperbound = dateutil.parser.parse(scans_table.loc[nextfmap, 'acq_time'])   # Narrow the upper search limit down to the succeeding fieldmap
                except (TypeError, ValueError, KeyError, dateutil.parser.ParserError) as acqtimeerror:
                    pass                                                                            # Raise this only if there are limits and matches, i.e. below

                # Search with multiple patterns for matching NIfTI-files in all runs and store the relative path to the session folder
                niifiles = []
                if intendedfor.startswith('<') and intendedfor.endswith('>'):
                    intendedfor = intendedfor[2:-2].split('><')
                elif not isinstance(intendedfor, list):
                    intendedfor = [intendedfor]
                for part in intendedfor:
                    limits  = part.split(':',1)[1].strip() if ':' in part else ''   # part = 'pattern: [lowerlimit:upperlimit]'
                    pattern = part.split(':',1)[0].strip()
                    matches = [niifile.relative_to(bidsses).as_posix() for niifile in sorted(bidsses.rglob(f"*{pattern}*.nii*")) if pattern]
                    if limits and matches:
                        try:
                            limits     = limits[1:-1].split(':',1)                  # limits: '[lowerlimit:upperlimit]' -> ['lowerlimit', 'upperlimit']
                            lowerlimit = int(limits[0]) if limits[0].strip() else float('-inf')
                            upperlimit = int(limits[1]) if limits[1].strip() else float('inf')
                            acqtimes   = []
                            for match in matches:
                                acqtimes.append((dateutil.parser.parse(scans_table.loc[match,'acq_time']), match))      # Time + filepath relative to the session-folder
                            acqtimes.sort(key = lambda acqtime: acqtime[0])
                            offset = sum([acqtime[0] < fmaptime for acqtime in acqtimes])  # The nr of preceding series
                            for n, acqtime in enumerate(acqtimes):
                                if lowerbound < acqtime[0] < upperbound and lowerlimit <= n-offset < upperlimit:
                                    niifiles.append(acqtime[1])
                        except Exception as intendedforerror:
                            LOGGER.error(f"Could not bound the <{part}> IntendedFor search as it requires a *_scans.tsv file with acq_time values for: {fmap}\n{intendedforerror}")
                            niifiles.extend(matches)
                    else:
                        niifiles.extend(matches)

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
            with jsonfile.open('w') as sidecar:
                json.dump(jsondata, sidecar, indent=4)


def main():
    """Console script usage"""

    # Parse the input arguments and run bidscoiner(args)
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidscoiner myproject/raw myproject/bids\n'
                                            '  bidscoiner -f myproject/raw myproject/bids -p sub-009 sub-030\n ')
    parser.add_argument('sourcefolder',             help='The study root folder containing the raw source data')
    parser.add_argument('bidsfolder',               help='The destination / output folder with the bids data')
    parser.add_argument('-p','--participant_label', help='Space separated list of selected sub-# names / folders to be processed (the sub-prefix can be removed). Otherwise all subjects in the sourcefolder will be selected', nargs='+')
    parser.add_argument('-b','--bidsmap',           help='The study bidsmap file with the mapping heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-f','--force',             help='Process all subjects, regardless of existing subject folders in the bidsfolder. Otherwise these subject folders will be skipped', action='store_true')
    args = parser.parse_args()

    bidscoiner(rawfolder    = args.sourcefolder,
               bidsfolder   = args.bidsfolder,
               subjects     = args.participant_label,
               force        = args.force,
               bidsmapfile  = args.bidsmap)


if __name__ == "__main__":
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
