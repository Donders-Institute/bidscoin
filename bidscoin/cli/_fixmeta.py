"""
A wrapper around the 'fixmeta' editing tool

Except for BIDS inheritances, this wrapper is BIDS-aware (a 'bidsapp') and writes BIDS compliant output
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse
import json


def get_parser():
    """Build an argument parser with input arguments for fixmeta.py"""

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass

    parser = argparse.ArgumentParser(prog='fixmeta',
                                     formatter_class=CustomFormatter,
                                     description=__doc__,
                                     epilog='examples:\n'
                                            '  fixmeta myproject/bids func/*task-reward1* \'{"TaskName": "Monetary reward paradigm 1"}\'\n'
                                            '  fixmeta myproject/bids *acq-reward1* \'{"B0FieldIdentifier": ["<<", "_", ">>", ""]}\'\n'
                                            '  fixmeta myproject/bids fmap/*run-2* \'{"IntendedFor": "<<task/*run-2*_bold*>>", "Comment": "Subject went out of the scanner"}\' -p 001 003\n ')
    parser.add_argument('bidsfolder',               help='The bids-directory with the target data')
    parser.add_argument('pattern',                  help="Globlike recursive search pattern (relative to the subject/session folder) to select the targets that need to be fixed, e.g. '*task-*echo-1*'")
    parser.add_argument('metadata',                 help='Dictionary with key-value pairs of meta data that need to be fixed. If value is a string, then it is taken as is, but if it is a list of `old`/`new` strings, i.e. `[old1, new1, old2, new2, ..]`, the existing meta data is used, with all occurrences of substring `old` replaced by `new`', type=json.loads)
    parser.add_argument('-p','--participant_label', help='Space separated list of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed', nargs='+')
    parser.add_argument('-b','--bidsmap',           help='The study bidsmap file with the mapping heuristics. If the bidsmap filename is just the basename (i.e. no "/" in the name) then it is assumed to be located in the current directory or in bidsfolder/code/bidscoin. Default: bidsmap.yaml or else the template bidsmap')

    return parser
