"""
A bidsapp that can change or add meta data in BIDS data repositories. The fixmeta app supports the use
of special bidsmap features, such as dynamic values to use source data attributes or properties, or to
populate `IntendedFor` and `B0FieldIdentifier`/`B0FieldSource` values
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse
import json


def get_parser():
    """Build an argument parser with input arguments for fixmeta.py"""

    class CustomFormatter(argparse.RawDescriptionHelpFormatter): pass

    parser = argparse.ArgumentParser(prog='fixmeta',
                                     formatter_class=CustomFormatter,
                                     description=__doc__,
                                     epilog='examples:\n'
                                            '  fixmeta myproject/bids func/*task-reward1* \'{"TaskName": "Monetary reward paradigm 1"}\'\n'
                                            '  fixmeta myproject/bids *acq-reward1* \'{"B0FieldIdentifier": ["<<", "_", ">>", ""], "B0FieldSource": ["<<", "_", ">>", ""]}\'\n'
                                            '  fixmeta myproject/bids fmap/*run-2* \'{"IntendedFor": "<<task/*run-2*_bold*>>"}\' -p 001 003\n ')
    parser.add_argument('bidsfolder',         help='The BIDS root directory that needs fixing (in place)')
    parser.add_argument('pattern',            help="Globlike recursive search pattern (relative to the subject/session folder) to select the json sidecar targets that need to be fixed, e.g. '*task-*echo-1*'")
    parser.add_argument('metadata',           help='Dictionary with key-value pairs of meta data that need to be fixed. If value is a string, then this meta data is written to the sidecars as is, but if it is a list of `old`/`new` strings, i.e. `[old1, new1, old2, new2, ..]`, then the existing meta data is re-written, with all occurrences of substring `old` replaced by `new`', type=json.loads)
    parser.add_argument('-p','--participant', help='Space separated list of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all participants will be processed', nargs='+', metavar='LABEL')
    parser.add_argument('-b','--bidsmap',     help='Selects a custom study bidsmap file for extracting source data properties and attributes. If the bidsmap filename is just the basename (i.e. no "/" in the name) then it is assumed to be located in the current directory or in bidsfolder/code/bidscoin. Default: bidsmap.yaml or else the template bidsmap', metavar='NAME')

    return parser
