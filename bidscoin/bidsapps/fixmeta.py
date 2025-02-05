#!/usr/bin/env python3
"""A wrapper around the 'slicer' imaging tool (See also cli/_fixmeta.py)"""

# NB: Set os.environ['DUECREDIT'] values as early as possible to capture all credits
import os
import sys

if __name__ == "__main__" and os.getenv('DUECREDIT_ENABLE','').lower() not in ('1', 'yes', 'true') and len(sys.argv) > 1:    # Ideally the due state (`self.__active=True`) should also be checked (but that's impossible)
    os.environ['DUECREDIT_ENABLE'] = 'yes'
    os.environ['DUECREDIT_FILE']   = os.path.join(sys.argv[1], 'code', 'bidscoin', '.duecredit_fixmeta.p')   # NB: argv[1] = bidsfolder

import logging
import json
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    sys.path.append(str(Path(__file__).parents[2]))
from bidscoin import bcoin, bids, lsdirs, trackusage, bidsmap_template


def fixmeta(bidsfolder: str, pattern: str, metadata: dict, participant: list, bidsmap: str= ''):
    """
    :param bidsfolder:  The bids-directory with the subject data
    :param pattern:     Globlike search pattern to select the targets in bidsfolder to be fixed, e.g. 'anat/*_T1w*'
    :param metadata:    Dictionary with key-value pairs of metadata that need to be fixed. If value is a string, then it is taken as is, but if it is a list of `old`/`new` strings, i.e. `[old1, new1, old2, new2, etc]`, the existing metadata is used, with all occurrences of substring `old` replaced by `new`
    :param participant: Space separated list of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all participants will be processed
    :param bidsmap:     The name of the bidsmap YAML-file. If the bidsmap pathname is just the base name (i.e. no "/" in the name) then it is assumed to be located in the current directory or in bidsfolder/code/bidscoin. Default: 'bidsmap.yaml' or the template bidsmap
    :return:
    """

    # Input checking
    bidsdir = Path(bidsfolder).resolve()
    if not bidsdir.is_dir():
        print(f"Could not find the bids folder: {bidsdir}"); return
    for key, value in metadata.items():
        if isinstance(value, list) and len(value) % 2:
            print(f"Odd number of metadata values in {value}")
            return

    # Get the list of subjects
    if not participant:
        subjects = lsdirs(bidsdir, 'sub-*')
        if not subjects:
            print(f"No subjects found in: {bidsdir/'sub-*'}"); return
    else:
        subjects = ['sub-' + subject.replace('sub-', '') for subject in participant]               # Make sure there is a "sub-" prefix
        subjects = [bidsdir/subject for subject in subjects if (bidsdir/subject).is_dir()]

    # Start logging
    bcoin.setup_logging(bidsdir/'code'/'bidscoin'/'fixmeta.log')
    LOGGER.info(f"Command: fixmeta {' '.join(sys.argv[1:])}")

    # Load the bidsmap data (-> plugins)
    bidsmap = bids.BidsMap(Path(bidsmap or 'bidsmap.yaml'), bidsdir/'code'/'bidscoin', checks=(False, False, False))
    if not bidsmap.filepath.is_file():
        bidsmap = bids.BidsMap(bidsmap_template, checks=(False, False, False))
    plugins  = bidsmap.plugins
    provdata = bids.bidsprov(bidsdir)

    # Loop over the subject/session-directories
    with logging_redirect_tqdm():
        for subject in tqdm(subjects, unit='subject', colour='green', leave=False):
            sessions = lsdirs(subject, 'ses-*')
            if not sessions:
                sessions = [subject]
            for session in sessions:

                # Search for the image(s) to fix
                LOGGER.info(f"Fixing metadata in: {session.relative_to(bidsdir)}")
                targets = sorted([match for match in session.rglob(pattern) if match.suffixes[0] in ('.tsv','.nii')])
                if not targets:
                    LOGGER.warning(f"Could not find data files using: {session.relative_to(bidsdir)}/{pattern}")
                    continue

                # Fix the targets
                for target in targets:

                    # Lookup the source folder in the bidscoiner.tsv provenance logs and get a datasource from it
                    sourcedir = ''
                    for source, row in provdata.iterrows():
                        if isinstance(row['targets'], str) and target.name in row['targets']:
                            sourcedir = source
                    datasource = bids.get_datasource(Path(sourcedir), plugins)
                    LOGGER.bcdebug(f"Datasource provenance: '{target.name}' -> '{datasource}'")

                    # Load/copy over the source metadata
                    jsonfile = target.with_suffix('').with_suffix('.json')
                    jsondata = bids.poolmetadata(datasource, jsonfile, bids.Meta({}), ['.json'])
                    for key, value in metadata.items():
                        if isinstance(value, list):
                            for n in range(0, len(value), 2):
                                if isinstance(jsondata.get(key), str):
                                    jsondata[key] = jsondata[key].replace(value[n], value[n+1])
                        else:
                            jsondata[key] = value
                        LOGGER.verbose(f"Writing '{key}: {jsondata.get(key)}' to: {jsonfile}")

                    # Save the metadata to the json sidecar-file
                    if jsondata:
                        with jsonfile.open('w') as json_fid:
                            json.dump(jsondata, json_fid, indent=4)

                # Add the special field map metadata (IntendedFor, TE, etc)
                bids.addmetadata(session)


def main():
    """Console script entry point"""

    from bidscoin.cli._fixmeta import get_parser

    args = get_parser().parse_args()

    trackusage('fixmeta')
    try:
        fixmeta(**vars(args))

    except Exception as error:
        trackusage('fixmeta_exception', error)
        raise error


if __name__ == '__main__':
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
