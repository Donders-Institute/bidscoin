#!/usr/bin/env python3
"""
A wrapper around the 'mecombine' multi-echo combination tool (https://github.com/Donders-Institute/multiecho).

This wrapper is fully BIDS-aware (a 'bidsapp') and writes BIDS compliant output
"""

import shutil
import argparse
import json
import logging
import pandas as pd
import numpy as np
from multiecho import combination as me
from pathlib import Path
try:
    from bidscoin import bids
except ImportError:
    import bids             # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger('bidscoin')


def echocombine(bidsdir: str, pattern: str, subjects: list, output: str, algorithm: str, weights: list):
    """

    :param bidsdir:     The bids-directory with the (multi-echo) subject data
    :param pattern:     Globlike recursive search pattern (relative to the subject/session folder) to select the first echo of the images that need to be combined, e.g. '*task-*echo-1*'
    :param subjects:    List of sub-# identifiers to be processed (the sub- prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed
    :param output:      Determines where the output is saved. It can be the name of a BIDS modality folder, such as 'func', or of the derivatives folder, i.e. 'derivatives'. If output = [the name of the input modality folder] then the original echo images are replaced by one combined image. If output is left empty then the combined image is saved in the input modality folder and the original echo images are moved to the {bids.unknownmodality} folder
    :param algorithm:   Combination algorithm, either 'PAID', 'TE' or 'average'
    :param weights:     Weights for each echo
    :return:
    """

    # Input checking
    bidsdir = Path(bidsdir).resolve()

    # Start logging
    bids.setup_logging(bidsdir/'code'/'bidscoin'/'echocombine.log')
    LOGGER.info('')
    LOGGER.info(f"--------- START echocombine ---------")
    LOGGER.info(f">>> echocombine bidsfolder={bidsdir} pattern={pattern} subjects={subjects} output={output}"
                f" algorithm={algorithm} weights={weights}")

    if 'echo' not in pattern:
        LOGGER.warning(f"Missing 'echo-#' substring in glob-like search pattern, i.e. '{pattern}' does not seem to select the first echo")

    # Get the list of subjects
    if not subjects:
        subjects = bids.lsdirs(bidsdir, 'sub-*')
        if not subjects:
            LOGGER.warning(f"No subjects found in: {bidsdir/'sub-*'}")
    else:
        subjects = ['sub-' + subject.replace('^sub-', '') for subject in subjects]              # Make sure there is a "sub-" prefix
        subjects = [bidsdir/subject for subject in subjects if (bidsdir/subject).is_dir()]

    # Loop over bids subject/session-directories
    for n, subject in enumerate(subjects, 1):

        sessions = bids.lsdirs(subject, 'ses-*')
        if not sessions:
            sessions = [subject]
        for session in sessions:

            LOGGER.info('-------------------------------------')
            LOGGER.info(f"Combining echos for ({n}/{len(subjects)}): {session}")

            sub_id, ses_id = bids.get_subid_sesid(session/'dum.my')

            # Search for multi-echo matches
            for match in sorted([match for match in session.rglob(pattern) if '.nii' in match.suffixes]):

                # Check if it is normal/BIDS multi-echo data
                input     = match.parent.name
                echonr    = bids.get_bidsvalue(match, 'echo')
                mepattern = bids.get_bidsvalue(match, 'echo', '*')
                echos     = sorted(match.parent.glob(mepattern.name))
                newechos  = [echo.parents[1]/bids.unknownmodality/echo.name for echo in echos]
                if not echonr:
                    LOGGER.warning(f"No 'echo' key-value pair found in the filename, skipping: {match}")
                    continue
                if len(echos) == 1:
                    LOGGER.warning(f"Only one echo image found, nothing to do for: {match}")
                    continue

                # Construct the combined-echo output filename and check if that file already exists
                cename = match.name.replace(f"_echo-{echonr}", '')
                if not output:
                    cefile = session/input/cename
                elif output == 'derivatives':
                    cefile = bidsdir/'derivatives'/'multiecho'/sub_id/ses_id/input/cename
                else:
                    cefile = session/output/cename
                cefile.parent.mkdir(parents=True, exist_ok=True)
                if cefile.is_file():
                    LOGGER.warning(f"Outputfile {cefile} already exists, skipping: {match}")
                    continue

                # Combine the multi-echo images
                me.me_combine(mepattern, cefile, algorithm, weights, saveweights=False, logger=LOGGER.name)

                # Add a combined-echo json sidecar-file
                cejson  = cefile.with_suffix('').with_suffix('.json')
                sejsons = [echo.with_suffix('').with_suffix('.json') for echo in echos]
                if sejsons[0].is_file():
                    TEs = [json.load(sejson.open('r'))['EchoTime'] for sejson in sejsons]
                    LOGGER.info(f"Adding a json sidecar-file: {sejsons[0]} -> {cejson}")
                    shutil.copyfile(sejsons[0], cejson)
                    with cejson.open('r') as fmap_fid:
                        data = json.load(fmap_fid)
                    data['EchoTime']   = np.average(TEs, weights=weights)       # This seems to be the best we can do (the BIDS validator indicates there has to be a nr here, an empty value generates a warning)
                    data['EchoNumber'] = 1
                    with cejson.open('w') as fmap_fid:
                        json.dump(data, fmap_fid, indent=4)

                # (Re)move the original multi-echo images
                if not output:
                    for echo, newecho in zip(echos, newechos):
                        LOGGER.info(f"Moving original echo image: {echo} -> {newecho}")
                        echo.replace(newecho)
                        echo.with_suffix('').with_suffix('.json').replace(newecho.with_suffix('').with_suffix('.json'))
                elif output == input:
                    for echo in echos:
                        LOGGER.info(f"Removing original echo image: {echo}")
                        echo.unlink()
                        echo.with_suffix('').with_suffix('.json').unlink()

                # Construct relative path names as they are used in BIDS
                echos_rel    = [str(echo.relative_to(session)) for echo in echos]
                newechos_rel = [str(echo.relative_to(session)) for echo in newechos]
                if output != 'derivatives':
                    cefile_rel = str(cefile.relative_to(session))

                # Update the IntendedFor fields in the fieldmap sidecar files (i.e. remove the old echos, add the echo-combined image and, optionally, the new echos)
                if output != 'derivatives' and (session/'fmap').is_dir():
                    for fmap in (session/'fmap').glob('*.json'):
                        with fmap.open('r') as fmap_fid:
                            fmap_data = json.load(fmap_fid)
                        if 'IntendedFor' in fmap_data:
                            intendedfor = fmap_data['IntendedFor']
                            if type(intendedfor)==str:
                                intendedfor = [intendedfor]
                            if echos_rel[0] in intendedfor:
                                LOGGER.info(f"Updating 'IntendedFor' to {cefile_rel} in {fmap}")
                                if not output:
                                    intendedfor = [file for file in intendedfor if not file in echos_rel] + [cefile_rel] + [newecho for newecho in newechos_rel]
                                elif output == input:
                                    intendedfor = [file for file in intendedfor if not file in echos_rel] + [cefile_rel]
                                else:
                                    intendedfor = intendedfor + [cefile_rel]
                                fmap_data['IntendedFor'] = intendedfor
                                with fmap.open('w') as fmap_fid:
                                    json.dump(fmap_data, fmap_fid, indent=4)

                # Update the scans.tsv file
                scans_tsv = session/f"{sub_id}{bids.add_prefix('_',ses_id)}_scans.tsv"
                if output != 'derivatives' and scans_tsv.is_file():

                    LOGGER.info(f"Adding {cefile_rel} to {scans_tsv}")
                    scans_table                 = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
                    scans_table.loc[cefile_rel] = scans_table.loc[echos_rel[0]]

                    for echo, newecho in zip(echos_rel, newechos_rel):
                        if not output:
                            LOGGER.info(f"Updating {echo} -> {newecho} in {scans_tsv}")
                            scans_table.loc[newecho] = scans_table.loc[echo]
                            scans_table.drop(echo, inplace=True)
                        elif output == input:
                            LOGGER.info(f"Removing {echo} from {scans_tsv}")
                            scans_table.drop(echo, inplace=True)

                    scans_table.sort_values(by=['acq_time','filename'], inplace=True)
                    scans_table.to_csv(scans_tsv, sep='\t', encoding='utf-8')

    LOGGER.info('-------------- FINISHED! -------------')
    LOGGER.info('')


def main():
    """Console script usage"""

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(formatter_class=CustomFormatter,
                                     description=__doc__,
                                     epilog='examples:\n'
                                            '  echocombine /project/3017065.01/bids func/*task-stroop*echo-1*\n'
                                            '  echocombine /project/3017065.01/bids *task-stroop*echo-1* -p 001 003\n'
                                            '  echocombine /project/3017065.01/bids func/*task-*echo-1* -o func\n'
                                            '  echocombine /project/3017065.01/bids func/*task-*echo-1* -o derivatives -w 13 26 39 52\n'
                                            '  echocombine /project/3017065.01/bids func/*task-*echo-1* -a PAID\n ')
    parser.add_argument('bidsfolder', type=str,
                        help='The bids-directory with the (multi-echo) subject data')
    parser.add_argument('pattern', type=str,
                        help="Globlike recursive search pattern (relative to the subject/session folder) to select the first echo of the images that need to be combined, e.g. '*task-*echo-1*'")
    parser.add_argument('-p','--participant_label', type=str, nargs='+',
                        help='Space separated list of sub-# identifiers to be processed (the sub- prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed')
    parser.add_argument('-o','--output', type=str, choices=bids.bidsmodalities + (bids.unknownmodality, 'derivatives'),
                        help=f"A string that determines where the output is saved. It can be the name of a BIDS modality folder, such as 'func', or of the derivatives folder, i.e. 'derivatives'. If output = [the name of the input modality folder] then the original echo images are replaced by one combined image. If output is left empty then the combined image is saved in the input modality folder and the original echo images are moved to the {bids.unknownmodality} folder")
    parser.add_argument('-a','--algorithm', choices=['PAID', 'TE', 'average'], default='TE',
                        help='Combination algorithm')
    parser.add_argument('-w','--weights', nargs='*', default=None, type=list,
                        help='Weights for each echo')
    args = parser.parse_args()

    echocombine(bidsdir   = args.bidsfolder,
                pattern   = args.pattern,
                subjects  = args.participant_label,
                output    = args.output,
                algorithm = args.algorithm,
                weights   = args.weights)


if __name__ == '__main__':
    main()
