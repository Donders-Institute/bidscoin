"""
A wrapper around the 'slicer' imaging tool (https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Miscvis)
to generate a web page with a row of image slices for each subject in the BIDS repository, as
well as individual sub-pages displaying more detailed information. The input images are
selectable using wildcards, and the output images are configurable via various user options,
allowing you to quickly create a custom 'slicer' report to do visual quality control on any
3D/4D imagetype in your repository.

Requires an existing installation of FSL

Set the environment variable BIDSCOIN_DEBUG=TRUE to save intermediate data
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse


def get_parser():
    """Build an argument parser with input arguments for slicereport.py"""

    epilogue = """
OPTIONS:
  L                  : Label slices with slice number.
  l [LUT]            : Use a different colour map from that specified in the header.
  i [MIN] [MAX]      : Specify intensity min and max for display range.
  e [THR]            : Use the specified threshold for edges (if > 0 use this proportion of max-min,
                       if < 0, use the absolute value)
  t                  : Produce semi-transparent (dithered) edges.
  n                  : Use nearest-neighbour interpolation for output.
  u                  : Do not put left-right labels in output.
  s                  : Size scaling factor
  c                  : Add a red dot marker to top right of image

OUTPUTS:
  x/y/z [SLICE] [..] : Output sagittal, coronal or axial slice (if SLICE > 0 it is a fraction of
                       image dimension, if < 0, it is an absolute slice number)
  a                  : Output mid-sagittal, -coronal and -axial slices into one image
  A [WIDTH]          : Output _all_ axial slices into one image of _max_ width WIDTH
  S [SAMPLE] [WIDTH] : As `A` but only include every SAMPLE'th slice
  LF                 : Start a new line (i.e. works like a row break)

examples:
  slicereport bids anat/*_T1w*
  slicereport bids anat/*_T2w* -r QC/slicereport_T2 -x QC/slicereport_T1
  slicereport bids fmap/*_phasediff* -o fmap/*_magnitude1*
  slicereport bids/derivatives/fmriprep func/*desc-preproc_bold* --suboperations " -Tstd"
  slicereport bids/derivatives/fmriprep anat/*desc-preproc_T1w* -o anat/*label-GM* -x bids/derivatives/fmriprep
  slicereport bids/derivatives/deface anat/*_T1w* -o bids:anat/*_T1w* --options L e 0.05
  slicereport bids anat/*_T1w* --outputs x 0.3 x 0.4 x 0.5 x 0.6 x 0.7 LF z 0.3 z 0.4 z 0.5 z 0.6 z 0.7\n """

    parser = argparse.ArgumentParser(prog='slicereport',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=__doc__, epilog=epilogue)
    parser.add_argument('bidsfolder',               help='The bids-directory with the subject data')
    parser.add_argument('pattern',                  help="Globlike search pattern to select the images in bidsfolder to be reported, e.g. 'anat/*_T2starw*'")
    parser.add_argument('-o','--outlinepattern',    help="Globlike search pattern to select red outline images that are projected on top of the reported images (i.e. 'outlinepattern' must yield the same number of images as 'pattern'. Prepend `outlinedir:` if your outline images are in `outlinedir` instead of `bidsdir` (see examples below)`")
    parser.add_argument('-i','--outlineimage',      help='A common red-outline image that is projected on top of all images', default='')
    parser.add_argument('-p','--participant_label', help='Space separated list of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed', nargs='+')
    parser.add_argument('-r','--reportfolder',      help="The folder where the report is saved (default: bidsfolder/derivatives/slicereport)")
    parser.add_argument('-x','--xlinkfolder',       help="A (list of) QC report folder(s) with cross-linkable sub-reports, e.g. bidsfolder/derivatives/mriqc", nargs='+')
    parser.add_argument('-q','--qcscores',          help="Column names for creating an accompanying tsv-file to store QC-rating scores (default: rating_overall)", default=['rating_overall'], nargs='+')
    parser.add_argument('-c','--cluster',           help='Use `torque` or `slurm` to submit the slicereport jobs to a high-performance compute (HPC) cluster', choices=['torque','slurm'])
    parser.add_argument('--operations',             help='One or more fslmaths operations that are performed on the input image (before slicing it for the report). OPERATIONS is opaquely passed as is: `fslmaths inputimage OPERATIONS reportimage`. NB: Use quotes and include at least one space character to prevent overearly parsing, e.g. " -Tmean" or "-Tstd -s 3" (default: -Tmean)', default='-Tmean')
    parser.add_argument('--suboperations',          help='The same as OPERATIONS but then for the sub-report instead of the main report: `fslmaths inputimage SUBOPERATIONS subreportimage` (default: -Tmean)', default='-Tmean')
    parser.add_argument('--options',                help='Main options of slicer (see below). (default: "s 1")', default=['s','1'], nargs='+')
    parser.add_argument('--outputs',                help='Output options of slicer (see below). (default: "x 0.4 x 0.5 x 0.6 y 0.4 y 0.5 y 0.6 z 0.4 z 0.5 z 0.6")', default=['x','0.4','x','0.5','x','0.6','y','0.4','y','0.5','y','0.6','z','0.4','z','0.5','z','0.6'], nargs='+')
    parser.add_argument('--suboptions',             help='Main options of slicer for creating the sub-reports (same as OPTIONS, see below). (default: OPTIONS)', nargs='+')
    parser.add_argument('--suboutputs',             help='Output options of slicer for creating the sub-reports (same as OUTPUTS, see below). (default: "S 4 1600")', default=['S','4','1600'], nargs='+')

    return parser
