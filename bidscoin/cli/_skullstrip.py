"""
A wrapper around FreeSurfer's 'synthstrip' skull stripping tool
(https://surfer.nmr.mgh.harvard.edu/docs/synthstrip). Except for BIDS inheritances,
this wrapper is BIDS-aware (a 'bidsapp') and writes BIDS compliant output

The corresponding brain mask is saved in the bids/derivatives/synthstrip folder

Assumes the installation of FreeSurfer v7.3.2 or higher
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse


def get_parser():
    """Build an argument parser with input arguments for skullstrip.py"""

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass

    parser = argparse.ArgumentParser(prog='skullstrip',
                                     formatter_class=CustomFormatter,
                                     description=__doc__,
                                     epilog='examples:\n'
                                            '  skullstrip myproject/bids anat/*_T1w*\n'
                                            '  skullstrip myproject/bids anat/*_T1w* -p 001 003 -a " --no-csf"\n'
                                            '  skullstrip myproject/bids fmap/*_magnitude1* -m fmap/*_phasediff* -o extra_data fmap\n'
                                            '  skullstrip myproject/bids fmap/*_acq-mylabel*_magnitude1* -m fmap/*_acq-mylabel_* -o fmap\n ')
    parser.add_argument('bidsfolder',               help="The bids-directory with the subject data", type=str)
    parser.add_argument('pattern',                  help="Globlike search pattern (relative to the subject/session folder) to select the (3D) images that need to be skullstripped, e.g. 'anat/*_T1w*'", type=str)
    parser.add_argument('-p','--participant_label', help="Space separated list of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed", type=str, nargs='+')
    parser.add_argument('-m','--masked',            help="Globlike search pattern (relative to the subject/session folder) to select additional (3D/4D) images from the same space that need to be masked with the same mask, e.g. 'fmap/*_phasediff'. NB: This option can only be used if pattern yields a single file per session", type=str)
    parser.add_argument('-o','--output',            help="One or two output strings that determine where the skullstripped + additional masked images are saved. Each output string can be the name of a BIDS datatype folder, such as 'anat', or of the derivatives folder, i.e. 'derivatives' (default). If the output string is the same as the datatype then the original images are replaced by the skullstripped images", nargs='+')
    parser.add_argument('-f','--force',             help="Process images, regardless whether images have already been skullstripped (i.e. if {'SkullStripped': True} in the json sidecar file)", action='store_true')
    parser.add_argument('-a','--args',              help="Additional arguments that are passed to synthstrip (NB: Use quotes and include at least one space character to prevent overearly parsing)", type=str, default='')
    parser.add_argument('-c','--cluster',           help='Use the DRMAA library to submit the skullstrip jobs to a high-performance compute (HPC) cluster', action='store_true')
    parser.add_argument('-n','--nativespec',        help='Opaque DRMAA argument with native specifications for submitting skullstrip jobs to the HPC cluster (NB: Use quotes and include at least one space character to prevent overearly parsing)', default='-l walltime=0:05:00,mem=8gb')

    return parser
