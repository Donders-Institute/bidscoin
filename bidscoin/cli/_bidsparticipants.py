"""
(Re)scans data sets in the source folder for subject metadata to populate the participants.tsv
file in the bids directory, e.g. after you renamed (be careful there!), added or deleted data
in the bids folder yourself.

Provenance information, warnings and error messages are stored in the
bidsfolder/code/bidscoin/bidsparticipants.log file.
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse
import textwrap


def get_parser():
    """Build an argument parser with input arguments for bidsparticipants.py"""

    # Parse the input arguments and run bidsparticipants(args)
    parser = argparse.ArgumentParser(prog='bidsparticipants',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidsparticipants myproject/raw myproject/bids\n'
                                            '  bidsparticipants myproject/raw myproject/bids -k participant_id age sex\n ')
    parser.add_argument('sourcefolder',     help='The study root folder containing the raw source data folders')
    parser.add_argument('bidsfolder',       help='The destination / output folder with the bids data')
    parser.add_argument('-k','--keys',      help="Space separated list of the participants.tsv columns. Default: 'session_id' 'age' 'sex' 'size' 'weight'", nargs='+', default=['age', 'sex', 'size', 'weight'])    # NB: session_id is default
    parser.add_argument('-d','--dryrun',    help='Do not save anything, only print the participants info on screen', action='store_true')
    parser.add_argument('-b','--bidsmap',   help='The study bidsmap file with the mapping heuristics. If the bidsmap filename is just the basename (i.e. no "/" in the name) then it is assumed to be located in the current directory or in bidsfolder/code/bidscoin. Default: bidsmap.yaml', default='bidsmap.yaml')

    return parser
