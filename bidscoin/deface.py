#!/usr/bin/env python3
"""
A wrapper around the 'pydeface' defacing tool (https://github.com/poldracklab/pydeface).

This wrapper is fully BIDS-aware (a 'bidsapp') and writes BIDS compliant output
"""

import shutil
import argparse
import json
import logging
import pandas as pd
import pydeface.utils as pdu
from pathlib import Path
try:
    from bidscoin import bids
except ImportError:
    import bids             # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger('bidscoin')


def deface(bidsdir: str, pattern: str, subjects: list, output: str, args: dict):

    # Input checking
    bidsdir = Path(bidsdir)

    # Start logging
    bids.setup_logging(bidsdir/'code'/'bidscoin'/'deface.log')
    LOGGER.info('')
    LOGGER.info('------------ START deface ------------')

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

        LOGGER.info('--------------------------------------')
        LOGGER.info(f'Defacing ({n}/{len(subjects)}): {subject}')

        sessions = bids.lsdirs(subject, 'ses-*')
        if not sessions:
            sessions = [subject]
        for session in sessions:

            sub_id, ses_id = bids.get_subid_sesid(session/'dum.my')

            # Search for images that need to be defaced
            for match in sorted([match for match in session.glob(pattern) if '.nii' in match.suffixes]):

                # Construct the output filename and check if that file already exists
                if not output:
                    outputfile = match
                elif output == 'derivatives':
                    outputfile = bidsdir/'derivatives'/'deface'/sub_id/ses_id/match.parent.name/match.name
                else:
                    outputfile = session/output/match.name
                outputfile.parent.mkdir(parents=True, exist_ok=True)

                # Deface the image
                pdu.deface_image(match, outputfile, force=True, forcecleanup=True, **args)

                # Add a json sidecar-file
                outputjson = outputfile.with_suffix('').with_suffix('.json')
                LOGGER.info(f"Adding a json sidecar-file: {outputjson}")
                shutil.copyfile(match.with_suffix('').with_suffix('.json'), outputjson)

                # Construct relative path names as they are used in BIDS
                match_rel      = str(     match.relative_to(session))
                outputfile_rel = str(outputfile.relative_to(session))

                # Update the IntendedFor fields in the fieldmap sidecar files
                if output and (match.parent/'fieldmap').is_dir():
                    for fmap in (match.parent/'fieldmap').glob('*.json'):
                        with fmap.open('r') as fmap_fid:
                            fmap_data = json.load(fmap_fid)
                        intendedfor = fmap_data['IntendedFor']
                        if match_rel in intendedfor:
                            LOGGER.info(f"Updating 'IntendedFor' to {outputfile_rel} in {fmap}")
                            fmap_data['IntendedFor'] = intendedfor + [outputfile_rel]
                            with fmap.open('w') as fmap_fid:
                                json.dump(fmap_data, fmap_fid, indent=4)

                # Update the scans.tsv file
                scans_tsv = session/f"{sub_id}{bids.add_prefix('_',ses_id)}_scans.tsv"
                if output and scans_tsv.is_file():
                    LOGGER.info(f"Adding {outputfile_rel} to {scans_tsv}")
                    scans_table                     = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
                    scans_table.loc[outputfile_rel] = scans_table.loc[match_rel]
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
                                            '  deface /project/3017065.01/bids anat/*_T1w*\n'
                                            '  deface /project/3017065.01/bids anat/*_T1w* -p 001 003 -o derivatives\n'
                                            '  deface /project/3017065.01/bids anat/*_T1w* -a \'{"cost": "corratio", "verbose": ""}\'\n ')
    parser.add_argument('bidsfolder', type=str,
                        help='The bids-directory with the (multi-echo) subject data')
    parser.add_argument('pattern', type=str,
                        help="Globlike search pattern (relative to the subject/session folder) to select the images that need to be defaced, e.g. 'anat/*_T1w*'")
    parser.add_argument('-p','--participant_label', type=str, nargs='+',
                        help='Space separated list of sub-# identifiers to be processed (the sub- prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed')
    parser.add_argument('-o','--output', type=str, choices=bids.bidsmodalities + (bids.unknownmodality, 'derivatives'),
                        help=f"A string that determines where the defaced images are saved. It can be the name of a BIDS modality folder, such as 'anat', or of the derivatives folder, i.e. 'derivatives'. If output is left empty then the original images are replaced by the defaced images")
    parser.add_argument('-a','--args',
                        help='Additional arguments (in dict/json-style) that are passed to pydeface. See examples for usage', type=json.loads, default={})
    args = parser.parse_args()

    deface(bidsdir  = args.bidsfolder,
           pattern  = args.pattern,
           subjects = args.participant_label,
           output   = args.output,
           args     = args.args)


if __name__ == '__main__':
    main()
