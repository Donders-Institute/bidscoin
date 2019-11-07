#!/usr/bin/env python3
"""A wrapper around the 'mecombine' multi-echo combination utility (https://github.com/Donders-Institute/multiecho).

This wrapper is fully BIDS-aware (a 'bidsapp') and writes BIDS compliant output
"""

import shutil
import argparse
import multiecho as me
import json
import re
import logging
from pathlib import Path
try:
    from bidscoin import bids
except ImportError:
    import bids             # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger('echocombine')


def echocombine(bidsdir: str, subjects: list, pattern: str, output: str, algorithm: str, weights: list):

    # Input checking
    bidsdir = Path(bidsdir)

    # Start logging
    bids.setup_logging(bidsdir/'code'/'bidscoin'/'mecombine.log')
    LOGGER.info('')
    LOGGER.info('------------ START echocombine ------------')

    # Get the list of subjects
    if not subjects:
        subjects = bids.lsdirs(bidsdir, 'sub-*')
        if not subjects:
            LOGGER.warning(f"No subjects found in: {bidsdir/'sub-*'}")
    else:
        subjects = ['sub-' + re.sub('^sub-','',subject) for subject in subjects]            # Make sure there is a "sub-" prefix
        subjects = [bidsdir/subject for subject in subjects if (bidsdir/subject).is_dir()]

    # Loop over bids subject/session-directories
    for n, subject in enumerate(subjects, 1):

        LOGGER.info('-------------------------------------')
        LOGGER.info(f'Combining echos for ({n}/{len(subjects)}): {subject}')

        sessions = bids.lsdirs(subject, 'ses-*')
        if not sessions:
            sessions = [subject]
        for session in sessions:

            sub_id, ses_id = bids.get_subid_sesid(session)

            # Search for matches
            for match in sorted((bidsdir/sub_id/ses_id).glob(pattern)):

                # Check if it is normal/BIDS multi-echo data
                echonr    = bids.get_bidsvalue(match, 'echo')
                mepattern = bids.get_bidsvalue(match, 'echo', '*')
                echos     = match.parent.glob(mepattern.name)
                if not echonr:
                    LOGGER.warning(f"No 'echo' key-value pair found in the filename, skipping: {match}")
                    continue
                if len(echos) == 1:
                    LOGGER.warning(f"Only one echo image found, nothing to do for: {match}")
                    continue

                # Create the multi-echo output filename and check if that file already exists
                mename = match.name.replace(f"_echo-{echonr}", '')
                if not output:
                    mefile = bidsdir/sub_id/ses_id/match.parent.name/mename
                elif output=='derivatives':
                    mefile = bidsdir/'derivatives'/'multi-echo'/sub_id/ses_id/match.parent.name/mename
                else:
                    mefile = bidsdir/sub_id/ses_id/output/mename
                mefile.parent.mkdir(parents=True, exist_ok=True)
                if mefile.is_file():
                    LOGGER.warning(f"Outputfile {mefile} already exists, skipping: {match}")
                    continue

                # Combine the echo images
                me.me_combine(mepattern, mefile, algorithm, weights, saveweights=False)

                # Add a multi-echo json sidecar-file
                mejson = mefile.with_suffix('').with_suffix('.json')
                LOGGER.info(f"Adding a json sidecar-file: {mejson}")
                shutil.copyfile(echos[0].with_suffix('').with_suffix('.json'), mejson)
                with mejson.open('w') as json_fid:
                    data               = json.load(json_fid)
                    data['EchoTime']   = 'n/a'
                    data['EchoNumber'] = 1
                    json.dump(data, json_fid, indent=4)

                # (Re)move the original echo images
                if not output:
                    for echo in echos:
                        newecho = echo.parents[1]/bids.unknownmodality/echo.name
                        LOGGER.info(f'Moving original echo image: {echo} -> {newecho}')
                        echo.replace(newecho)
                        echo.with_suffix('').with_suffix('.json').replace(newecho.with_suffix('').with_suffix('.json'))
                elif output == match.parent.name:
                    for echo in echos:
                        LOGGER.info(f'Removing original echo image: {echo}')
                        echo.unlink()
                        echo.with_suffix('').with_suffix('.json').unlink()


def main():
    """Console script usage"""

    parser = argparse.ArgumentParser(description=__doc__,
                                     epilog='examples:\n'
                                            '  echocombine /project/3017065.01/bids\n'
                                            '  echocombine /project/3017065.01/bids -o /project/3017065.01/bids/derivatives/mecombine\n'
                                            '  echocombine /project/3017065.01/bids -a PAID -s\n\n')
    parser.add_argument('bidsfolder', type=str,
                        help='The bids-directory with the (multi-echo) subject data')
    parser.add_argument('pattern', type=str, choices=bids.bidsmodalities + (bids.unknownmodality, 'derivatives'),
                        help="Globlike search pattern (relative to the subject/session folder) to select the first echo of the images that need to be combined, e.g. 'func/*task-stroop*echo-1*'")
    parser.add_argument('-p','--participant_label', type=str, nargs='+',
                        help='Space seperated list of sub-# identifiers to be processed (the sub- prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed')
    parser.add_argument('-o','--output', type=str, choices=bids.bidsmodalities + (bids.unknownmodality, 'derivatives'),
                        help=f"A string that determines where the output is saved. It can be the name of a BIDS modality folder, such as 'func', or of the derivatives folder, i.e. 'derivatives'. If output = [the name of the input modality folder] then the original echo images are replaced by one combined image. If output is left empty then the combined image is saved in the input modality folder and the original echo images are moved to the {bids.unknownmodality} folder (= default)")
    parser.add_argument('-a','--algorithm', choices=['PAID', 'TE', 'average'], default='TE',
                        help='Combination algorithm. Default: TE')
    parser.add_argument('-w','--weights', nargs='*', default=[], type=list,
                        help='Weights for each echo')
    args = parser.parse_args()

    echocombine(bidsdir   = args.bidsfolder,
                subjects  = args.participant_label,
                pattern   = args.pattern,
                output    = args.output,
                algorithm = args.algorithm,
                weights   = args.weights)


if __name__ == '__main__':
    main()
