#!/usr/bin/env python3
"""
A wrapper around the 'slicer' reporting tool (https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Miscvis)
that generates a web page with a row of image slices for each subject in the BIDS repository.
In this way you can do a simple visual quality control of any datatype in your BIDS repository

Requires an existing installation of FSL/slicer
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
try:
    from bidscoin import bidscoin
except ImportError:
    sys.path.append(str(Path(__file__).parents[1]))             # This should work if bidscoin was not pip-installed
    import bidscoin


def slicereport(bidsdir: str, pattern: str, outlinepattern: str, outlineimage: str, mainopts: list, outputopts: list, reportdir: str):
    """
    :param bidsdir:         The bids-directory with the subject data
    :param pattern:         Globlike search pattern to select the images in bidsdir to be reported, e.g. 'anat/*_T1w*'
    :param outlinepattern:  Globlike search pattern to select red-outline images that are projected on top of the reported images. Prepend `outlinedir:` if your outline images are in `outlinedir` instead of `bidsdir`
    :param outlineimage:    A common red-outline image that is projected on top of all images
    :param mainopts:        Slicer main options
    :param outputopts:      Slicer output options
    :param reportdir:       The folder where the report is saved
    :return:
    """

    # Input checking
    bidsdir = Path(bidsdir).resolve()
    if not reportdir:
        reportdir = bidsdir/'derivatives/slicereport'
    else:
        reportdir = Path(reportdir).resolve()
    if not bidsdir.is_dir():
        print(f"Could not find the bids folder: {bidsdir}")
        return
    if outlineimage:
        if outlinepattern:
            print('The "--outlineimage" and "--outlinepattern" arguments are mutually exclusive, please specify one or the other')
            return
        outlineimage = Path(outlineimage).resolve()
        if not outlineimage.is_file():
            print(f"Could not find the common overlay image: {outlineimage}")
            return
    if outlinepattern and ':' in outlinepattern:
        outlinedir, outlinepattern = outlinepattern.split(':',1)
        outlinedir = Path(outlinedir).resolve()
        if not outlinedir.is_dir():
            print(f"Could not find the outline folder: {outlinedir}")
            return
    else:
        outlinedir = bidsdir
    if mainopts[0] not in ('L','l','i','e','t','n','u','s','c'):
        print(f"Invalid MAINOPTS: {' '.join(mainopts)}")
        return
    mainopts = f"-{' '.join(mainopts)}"
    for n, outputopt in enumerate(outputopts):
        if not (outputopt in ('x', 'y', 'z', 'a', 'A', 'S') or outputopt.replace('.','').replace('-','').isdecimal()):
            print(f"Invalid OUTPUTOPTS: {outputopts}")
            return

    # Format the slicer output images and options
    sliceimages = []
    outputopts_ = ''
    if outputopts[0] in ('x', 'y', 'z'):
        for n, outputopt in enumerate(outputopts):
            if not n % 2:
                sliceimages.append(f"slice_tmp{n}.png")
                outputopts_ += f"-{outputopt} {outputopts[n+1]} {sliceimages[-1]} "
    elif outputopts[0].upper() in ('A', 'S'):
        sliceimages = ['slice_tmp1.png']
        outputopts_ = f"-{' '.join(outputopts)} {sliceimages[0]}"

    # Start logging
    reportdir.mkdir(parents=True, exist_ok=True)
    (reportdir/'slicereport.log').unlink(missing_ok=True)
    bidscoin.setup_logging(reportdir/'slicereport.log')
    LOGGER.info(f"Command: {' '.join(sys.argv)}")

    # Create the report index file
    report = reportdir/'index.html'
    report.write_text(f'<HTML><TITLE>slicereport</TITLE><BODY BGCOLOR="#181818"><h3 style="color:#FFFFFF">Command: slicereport {" ".join(sys.argv[1:])}</h3><br>')

    # Get the list of subjects/sessions
    subjects = bidscoin.lsdirs(bidsdir, 'sub-*')
    for subject in subjects:
        sessions = bidscoin.lsdirs(subject, 'ses-*')
        if not sessions:
            sessions = [subject]
        for session in sessions:

            # Search for the image(s) to report
            LOGGER.info(f"Processing images in: {session.relative_to(bidsdir)}")
            images = sorted([str(match.with_suffix('').with_suffix('')) for match in session.glob(pattern) if '.nii' in match.suffixes])
            if not images:
                LOGGER.warning(f"Could not find images using: {session.relative_to(bidsdir)}/{pattern}")
                continue
            outlineimages = [''] * len(images)
            if outlinepattern:
                outlinesession = outlinedir/session.relative_to(bidsdir)
                outlineimages  = sorted([str(match.with_suffix('').with_suffix('')) for match in outlinesession.glob(outlinepattern) if '.nii' in match.suffixes])
                if len(outlineimages) != len(images):
                    LOGGER.error(f"Nr of outline images ({len(outlineimages)}) in {outlinesession.relative_to(bidsdir)} should be the same as the number of underlying images ({len(images)})")
                    outlineimages = [''] * len(images)

            # Generate the report row(s)
            for n, image in enumerate(images):

                # Generate the slice image
                outline = outlineimages[n] if outlinepattern else outlineimage
                command = f"slicer {image} {outline} {mainopts} {outputopts_}"
                process = subprocess.run(command, cwd=reportdir, shell=True, capture_output=True, text=True)
                if process.stderr or process.returncode != 0:
                    LOGGER.error(f"{command}\nErrorcode {process.returncode}:\n{process.stdout}\n{process.stderr}")
                    continue

                # Append the slice images to a slice row
                slicerow = f"{Path(image).name}.png"
                command  = f"pngappend {' + '.join(sliceimages)} {slicerow}"
                process  = subprocess.run(command, cwd=reportdir, shell=True, capture_output=True, text=True)
                for sliceimage in sliceimages:
                    (reportdir/sliceimage).unlink()
                if process.stderr or process.returncode != 0:
                    LOGGER.error(f"{command}\nErrorcode {process.returncode}:\n{process.stdout}\n{process.stderr}")
                    continue

                # Add a row to the report
                append_row(report, slicerow, f"{Path(image).relative_to(bidsdir)}{'&nbsp; &nbsp; &nbsp;['+str(Path(outline).relative_to(outlinedir))+']' if outline else ''}")

    # Finish off
    errors = bidscoin.reporterrors().replace('\n', '<br>')
    if errors:
        message = '<h3 style="color:#EE4B2B">The following errors and warnings were reported:</h3>'
    else:
        message = '<h3 style="color:#50C878">No errors or warnings were reported</h3>'
    with report.open('a') as fid:
        fid.write(f'<br>{message}<p style="color:#D1D1D1">{errors}</p></BODY></HTML>')
    LOGGER.info(' ')
    LOGGER.info(f"To view the report, point your web browser at:\n\n{report}\n ")


def append_row(report: Path, imagesrc: str, text: str):
   with report.open('a') as fid:
       fid.write(f'<p style="color:#D1D1D1"><image src="{imagesrc}"><br>{text}</p>')


def main():
    """Console script usage"""

    epilogue = """
MAINOPTS:
  L                  : Label slices with slice number.
  l [LUT]            : use a different colour map from that specified in the header.
  i [MIN] [MAX]      : specify intensity min and max for display range.
  e [THR]            : use the specified threshold for edges (if > 0 use this proportion of max-min,
                       if < 0, use the absolute value)
  t                  : produce semi-transparent (dithered) edges.
  n                  : use nearest-neighbour interpolation for output.
  u                  : do not put left-right labels in output.
  s                  : Scaling factor
  c                  : add a red dot marker to top right of image

OUTPUTOPTS:
  x/y/z [SLICE] [..] : output sagittal, coronal or axial slice (if [SLICE] > 0 it is a
                       fraction of image dimension, if < 0, it is an absolute slice number)
  a                  : output mid-sagittal, -coronal and -axial slices into one image
  A [WIDTH]          : output _all_ axial slices into one image of _max_ width [WIDTH]
  S [SAMPLE] [WIDTH] : as A but only include every [SAMPLE]'th slice

examples:
  slicereport myproject/bids anat/*_T1w*
  slicereport myproject/bids fmap/*_phasediff* -o fmap/*_magnitude1*
  slicereport myproject/bids/derivatives/fmriprep anat/*run-?_desc-preproc_T1w* -o anat/*run-?_label-GM*
  slicereport myproject/bids/derivatives/deface anat/*_T1w* -o myproject/bids:anat/*_T1w* --mainopts e 0.05\n """

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=__doc__, epilog=epilogue)
    parser.add_argument('bidsfolder',               help='The bids-directory with the subject data')
    parser.add_argument('pattern',                  help="Globlike search pattern to select the images in bidsdir to be reported, e.g. 'anat/*_T2starw*'")
    parser.add_argument('-o','--outlinepattern',    help="Globlike search pattern to select red outline images that are projected on top of the reported images (i.e. 'outlinepattern' must yield the same number of images as 'pattern'. Prepend `outlinedir:` if your outline images are in `outlinedir` instead of `bidsdir` (see examples below)`")
    parser.add_argument('-i','--outlineimage',      help='A common red-outline image that is projected on top of all images')
    parser.add_argument('-r','--reportfolder',      help="The folder where the report is saved (default: bidsfolder/derivatives/slicereport)")
    parser.add_argument('--mainopts',               help='Main options of slicer (see below). (default: "s 1")', default=['s','1'], nargs='+')
    parser.add_argument('--outputopts',             help='Output options of slicer (see below). (default: "x 0.4 x 0.5 x 0.6 y 0.4 y 0.5 y 0.6 z 0.4 z 0.5 z 0.6")', default=['x','0.4','x','0.5','x','0.6','y','0.4','y','0.5','y','0.6','z','0.4','z','0.5','z','0.6'], nargs='+')
    args = parser.parse_args()

    slicereport(bidsdir        = args.bidsfolder,
                pattern        = args.pattern,
                outlinepattern = args.outlinepattern,
                outlineimage   = args.outlineimage,
                mainopts       = args.mainopts,
                outputopts     = args.outputopts,
                reportdir      = args.reportfolder)


if __name__ == '__main__':
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
