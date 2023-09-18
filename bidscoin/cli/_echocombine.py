"""
A wrapper around the 'mecombine' multi-echo combination tool
(https://github.com/Donders-Institute/multiecho).

Except for BIDS inheritances, this wrapper is BIDS-aware (a 'bidsapp') and writes BIDS
compliant output
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse


def get_parser():
    """Build an argument parser with input arguments for echocombine.py"""

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass

    parser = argparse.ArgumentParser(prog='echocombine',
                                     formatter_class=CustomFormatter,
                                     description=__doc__,
                                     epilog='examples:\n'
                                            '  echocombine myproject/bids func/*task-stroop*echo-1*\n'
                                            '  echocombine myproject/bids *task-stroop*echo-1* -p 001 003\n'
                                            '  echocombine myproject/bids func/*task-*echo-1* -o func\n'
                                            '  echocombine myproject/bids func/*task-*echo-1* -o derivatives -w 13 26 39 52\n'
                                            '  echocombine myproject/bids func/*task-*echo-1* -a PAID\n ')
    parser.add_argument('bidsfolder',               help='The bids-directory with the (multi-echo) subject data')
    parser.add_argument('pattern',                  help="Globlike recursive search pattern (relative to the subject/session folder) to select the first echo of the images that need to be combined, e.g. '*task-*echo-1*'")
    parser.add_argument('-p','--participant_label', help='Space separated list of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed', nargs='+')
    parser.add_argument('-o','--output',            help=f"A string that determines where the output is saved. It can be the name of a BIDS datatype folder, such as 'func', or of the derivatives folder, i.e. 'derivatives'. If output = [the name of the input datatype folder] then the original echo images are replaced by one combined image. If output is left empty then the combined image is saved in the input datatype folder and the original echo images are moved to the 'extra_data' folder", default='')
    parser.add_argument('-a','--algorithm',         help='Combination algorithm', choices=['PAID', 'TE', 'average'], default='TE')
    parser.add_argument('-w','--weights',           help='Weights for each echo', nargs='*', default=None, type=list)
    parser.add_argument('-f','--force',             help='Process all images, regardless whether target images already exist. Otherwise the echo-combination will be skipped', action='store_true')

    return parser
