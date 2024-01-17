#!/usr/bin/env python3
"""A bidsapp that wraps around the multi-echo combination tool (See also cli/_echocombine.py)"""

# NB: Set os.environ['DUECREDIT'] values as early as possible to capture all credits
import os
import sys
if __name__ == "__main__" and os.getenv('DUECREDIT_ENABLE','').lower() not in ('1', 'yes', 'true') and len(sys.argv) > 1:    # Ideally the due state (`self.__active=True`) should also be checked (but that's impossible)
    os.environ['DUECREDIT_ENABLE'] = 'yes'
    os.environ['DUECREDIT_FILE']   = os.path.join(sys.argv[1], 'code', 'bidscoin', '.duecredit_echocombine.p')   # NB: argv[1] = bidsfolder

import json
import logging
import pandas as pd
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from multiecho import combination as me
from pathlib import Path
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    sys.path.append(str(Path(__file__).parents[2]))
from bidscoin import bcoin, bids, lsdirs, trackusage

unknowndatatype = 'extra_data'


def echocombine(bidsdir: str, pattern: str, subjects: list, output: str, algorithm: str, weights: list, force: bool=False):
    """
    :param bidsdir:     The bids-directory with the (multi-echo) subject data
    :param pattern:     Globlike recursive search pattern (relative to the subject/session folder) to select the first echo of the images that need to be combined, e.g. '*task-*echo-1*'
    :param subjects:    List of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed
    :param output:      Determines where the output is saved. It can be the name of a BIDS datatype folder, such as 'func', or of the derivatives folder, i.e. 'derivatives'. If output = [the name of the input datatype folder] then the original echo images are replaced by one combined image. If output is left empty then the combined image is saved in the input datatype folder and the original echo images are moved to the {unknowndatatype} folder
    :param algorithm:   Combination algorithm, either 'PAID', 'TE' or 'average'
    :param weights:     Weights for each echo
    :param force:       Boolean to overwrite existing ME target files
    :return:
    """

    # Input checking
    bidsdir = Path(bidsdir).resolve()
    if not bidsdir.is_dir():
        print(f"Could not find the bids folder: {bidsdir}")
        return

    # Start logging
    bcoin.setup_logging(bidsdir/'code'/'bidscoin'/'echocombine.log')
    LOGGER.info('')
    LOGGER.info(f"--------- START echocombine ---------")
    LOGGER.info(f">>> echocombine bidsfolder={bidsdir} pattern={pattern} subjects={subjects} output={output}"
                f" algorithm={algorithm} weights={weights}")

    # Get the list of subjects
    if not subjects:
        subjects = lsdirs(bidsdir, 'sub-*')
        if not subjects:
            LOGGER.warning(f"No subjects found in: {bidsdir/'sub-*'}")
    else:
        subjects = ['sub-' + subject.replace('sub-', '') for subject in subjects]              # Make sure there is a "sub-" prefix
        subjects = [bidsdir/subject for subject in subjects if (bidsdir/subject).is_dir()]

    # Loop over bids subject/session-directories
    with logging_redirect_tqdm():
        for n, subject in enumerate(tqdm(subjects, unit='subject', colour='green', leave=False), 1):

            subid    = subject.name
            sessions = lsdirs(subject, 'ses-*')
            if not sessions:
                sessions = [subject]
            for session in sessions:

                LOGGER.info('-------------------------------------')
                LOGGER.info(f"Combining echos for ({n}/{len(subjects)}): {session}")

                # Search for multi-echo matches
                sesid = session.name if session.name.startswith('ses-') else ''
                for match in sorted([match for match in session.rglob(pattern) if '.nii' in match.suffixes]):

                    # Check if it is normal/BIDS multi-echo data or that the echo-number is appended to the acquisition label (as done in BIDScoin)
                    if '_echo-' in match.name:
                        echonr      = bids.get_bidsvalue(match, 'echo')
                        mepattern   = bids.get_bidsvalue(match, 'echo', '*')                        # The pattern that selects all echos
                        cename      = match.name.replace(f"_echo-{echonr}", '')                     # The combined-echo output filename
                    elif '_acq-' in match.name and bids.get_bidsvalue(match, 'acq').split('e')[-1].isdecimal():
                        acq, echonr = bids.get_bidsvalue(match, 'acq').rsplit('e',1)
                        mepattern   = bids.get_bidsvalue(match, 'acq', acq + 'e*')                  # The pattern that selects all echos
                        cename      = match.name.replace(f"_acq-{acq}e{echonr}", f"_acq-{acq}")     # The combined-echo output filename
                        LOGGER.info(f"No 'echo' key-value pair found in the filename, using the 'acq-{acq}e{echonr}' pair instead (BIDScoin-style)")
                    else:
                        LOGGER.warning(f"No 'echo' encoding found in the filename, skipping: {match}")
                        continue
                    echos     = sorted(match.parent.glob(mepattern.name))
                    newechos  = [echo.parents[1]/unknowndatatype/echo.name for echo in echos]
                    if len(echos) == 1:
                        LOGGER.warning(f"Only one echo image found, nothing to do for: {match}")
                        continue

                    # Construct the combined-echo output filename and check if that file already exists
                    datatype = match.parent.name
                    if not output:
                        cefile = session/datatype/cename
                    elif output == 'derivatives':
                        cefile = bidsdir/'derivatives'/'multiecho'/subid/sesid/datatype/cename
                    else:
                        cefile = session/output/cename
                    cefile.parent.mkdir(parents=True, exist_ok=True)
                    if cefile.is_file() and not force:
                        LOGGER.warning(f"Outputfile {cefile} already exists, skipping: {match}")
                        continue

                    # Combine the multi-echo images
                    me.me_combine(mepattern, cefile, algorithm, weights, saveweights=False)

                    # (Re)move the original multi-echo images
                    if not output:
                        for echo, newecho in zip(echos, newechos):
                            LOGGER.info(f"Moving original echo image: {echo} -> {newecho}")
                            newecho.parent.mkdir(parents=True, exist_ok=True)
                            echo.replace(newecho)
                            echo.with_suffix('').with_suffix('.json').replace(newecho.with_suffix('').with_suffix('.json'))
                    elif output == datatype:
                        for echo in echos:
                            LOGGER.info(f"Removing original echo image: {echo}")
                            echo.unlink()
                            echo.with_suffix('').with_suffix('.json').unlink()

                    # Construct the path names relative to the session folder (used for updating the IntendedFor list and scans.tsv file)
                    oldechos_rel = [echo.relative_to(session).as_posix() for echo in echos]
                    newechos_rel = [echo.relative_to(session).as_posix() for echo in echos + newechos if echo.is_file()]
                    if output == 'derivatives':
                        cefile_rel = ''                 # A remote folder cannot be specified easily, it's too much hassle
                    else:
                        cefile_rel = cefile.relative_to(session).as_posix()

                    # Update the IntendedFor fields of the fieldmaps (i.e. remove the old echos, add the echo-combined image and, optionally, the new echos)
                    if output != 'derivatives' and (session/'fmap').is_dir():
                        for fmap in (session/'fmap').glob('*.json'):

                            # Load the IntendedFor data as a list
                            with fmap.open('r') as fmap_fid:
                                fmapdata = json.load(fmap_fid)
                            intendedfor = fmapdata.get('IntendedFor')
                            if not intendedfor or oldechos_rel[0] not in str(intendedfor):
                                continue
                            if isinstance(intendedfor, str):
                                intendedfor = [intendedfor]

                            # Filter out the old echo entries and add the new and echo-combined entries
                            LOGGER.info(f"Updating 'IntendedFor' in {fmap}")
                            newintendedfor = []
                            for item in intendedfor:
                                item_rel = item.split(f":{subid}/",1)[-1]     # NB: The BIDS v1.8 IntendedFor URI is relative to the bids folder (split it off)
                                if sesid:
                                    item_rel = item_rel.split(sesid+'/',1)[-1]
                                if item_rel not in oldechos_rel:
                                    newintendedfor.append(item)
                                else:
                                    uri = item.replace(item_rel,'')           # E.g. uri = 'bids::sub-01/ses-01/' or 'ses-01/' or ''
                            fmapdata['IntendedFor'] = newintendedfor + [f"{uri}{file}" for file in newechos_rel + [cefile_rel]]
                            with fmap.open('w') as fmap_fid:
                                json.dump(fmapdata, fmap_fid, indent=4)

                    # Update the scans.tsv file
                    scans_tsv = session/f"{subid}{'_'+sesid if sesid else ''}_scans.tsv"
                    if scans_tsv.is_file():

                        # Store the original echo data in a dummy row
                        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
                        if oldechos_rel[0] in scans_table.index:
                            scans_table.loc['dummyrow'] = scans_table.loc[oldechos_rel[0]]
                        elif 'acq_time' in scans_table:
                            with cefile.with_suffix('').with_suffix('.json').open('r') as fid:
                                metadata = json.load(fid)
                            date = scans_table.iloc[0]['acq_time'].split('T')[0]
                            scans_table.loc['dummyrow', 'acq_time'] = f"{date}T{metadata.get('AcquisitionTime')}"
                        else:
                            scans_table.loc['dummyrow'] = None

                        # Add the echo-combined image
                        bidsignore = (bidsdir/'.bidsignore').read_text().splitlines() if (bidsdir/'.bidsignore').is_file() else [unknowndatatype+'/']
                        if not bids.check_ignore(output, bidsignore) and cefile.parent.name in bids.datatyperules:
                            LOGGER.info(f"Adding '{cefile_rel}' to '{scans_tsv}'")
                            scans_table.loc[cefile_rel] = scans_table.loc['dummyrow']

                        # Remove the old echo images and add the new ones
                        for echo in oldechos_rel + newechos_rel:
                            if echo in scans_table.index and not (session/echo).is_file():
                                LOGGER.info(f"Removing '{echo}' from '{scans_tsv}'")
                                scans_table.drop(echo, inplace=True)
                            elif echo not in scans_table.index and (session/echo).is_file() and echo.split('/')[0] in bids.datatyperules:
                                LOGGER.info(f"Adding '{echo}' to '{scans_tsv}'")
                                scans_table.loc[echo] = scans_table.loc['dummyrow']       # NB: Assuming that the echo-rows are all identical

                        # Save the data
                        scans_table.drop('dummyrow', inplace=True)
                        scans_table.sort_values(by=['acq_time','filename'], inplace=True)
                        scans_table.replace('','n/a').to_csv(scans_tsv, sep='\t', encoding='utf-8', na_rep='n/a')
                        for scan in scans_table.index:
                            if not (session/scan).is_file():
                                LOGGER.warning(f"Found non-existent file '{scan}' in '{scans_tsv}'")

    LOGGER.info('-------------- FINISHED! -------------')
    LOGGER.info('')


def main():
    """Console script entry point"""

    from bidscoin.cli._echocombine import get_parser

    # Parse the input arguments and run bidscoiner(args)
    args = get_parser().parse_args()

    trackusage('echocombine')
    try:
        echocombine(bidsdir   = args.bidsfolder,
                    pattern   = args.pattern,
                    subjects  = args.participant_label,
                    output    = args.output,
                    algorithm = args.algorithm,
                    weights   = args.weights,
                    force     = args.force)

    except Exception:
        trackusage('echocombine_exception')
        raise


if __name__ == '__main__':
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
