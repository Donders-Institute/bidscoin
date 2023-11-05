"""
A wrapper around the 'pydeface' defacing tool (https://github.com/poldracklab/pydeface) that
computes a defacing mask on a (temporary) echo-combined image and then applies it to each
individual echo-image.

Except for BIDS inheritances and IntendedFor usage, this wrapper is BIDS-aware (a 'bidsapp')
and writes BIDS compliant output

Linux users can distribute the computations to their HPC compute cluster if the DRMAA
libraries are installed and the DRMAA_LIBRARY_PATH environment variable set

For single-echo data see `deface`
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse
import json


def get_parser():
    """Build an argument parser with input arguments for medeface.py"""

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass

    parser = argparse.ArgumentParser(prog='medeface',
                                     formatter_class=CustomFormatter,
                                     description=__doc__,
                                     epilog='examples:\n'
                                            '  medeface myproject/bids anat/*_T1w*\n'
                                            '  medeface myproject/bids anat/*_T1w* -p 001 003 -o derivatives\n'
                                            '  medeface myproject/bids anat/*_T1w* -c -n "-l walltime=00:60:00,mem=4gb"\n'
                                            '  medeface myproject/bids anat/*acq-GRE* -m anat/*acq-GRE*magnitude*"\n'
                                            '  medeface myproject/bids anat/*_FLAIR* -a \'{"cost": "corratio", "verbose": ""}\'\n ')
    parser.add_argument('bidsfolder',               help='The bids-directory with the (multi-echo) subject data')
    parser.add_argument('pattern',                  help="Globlike search pattern (relative to the subject/session folder) to select the images that need to be defaced, e.g. 'anat/*_T2starw*'")
    parser.add_argument('-m','--maskpattern',       help="Globlike search pattern (relative to the subject/session folder) to select the images from which the defacemask is computed, e.g. 'anat/*_part-mag_*_T2starw*'. If not given then 'pattern' is used")
    parser.add_argument('-p','--participant_label', help='Space separated list of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed', nargs='+')
    parser.add_argument('-o','--output',            help=f"A string that determines where the defaced images are saved. It can be the name of a BIDS datatype folder, such as 'anat', or of the derivatives folder, i.e. 'derivatives'. If output is left empty then the original images are replaced by the defaced images")
    parser.add_argument('-c','--cluster',           help='Use the DRMAA library to submit the deface jobs to a high-performance compute (HPC) cluster', action='store_true')
    parser.add_argument('-n','--nativespec',        help='Opaque DRMAA argument with native specifications for submitting deface jobs to the HPC cluster (NB: Use quotes and include at least one space character to prevent overearly parsing)', default='-l walltime=00:30:00,mem=2gb')
    parser.add_argument('-a','--args',              help='Additional arguments (in dict/json-style) that are passed to pydeface (NB: Use quotes). See examples for usage', type=json.loads, default={})
    parser.add_argument('-f','--force',             help='Process all images, regardless if images have already been defaced (i.e. if {"Defaced": True} in the json sidecar file)', action='store_true')

    return parser
