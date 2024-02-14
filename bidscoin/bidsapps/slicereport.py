#!/usr/bin/env python3
"""A wrapper around the 'slicer' imaging tool (See also cli/_slicereport.py)"""

# NB: Set os.environ['DUECREDIT'] values as early as possible to capture all credits
import os
import sys
if __name__ == "__main__" and os.getenv('DUECREDIT_ENABLE','').lower() not in ('1', 'yes', 'true') and len(sys.argv) > 1:    # Ideally the due state (`self.__active=True`) should also be checked (but that's impossible)
    os.environ['DUECREDIT_ENABLE'] = 'yes'
    os.environ['DUECREDIT_FILE']   = os.path.join(sys.argv[1], 'code', 'bidscoin', '.duecredit_slicereport.p')   # NB: argv[1] = bidsfolder

import logging
import subprocess
import csv
import json
import tempfile
import nibabel as nib
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from copy import copy
from pathlib import Path
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    sys.path.append(str(Path(__file__).parents[2]))
from bidscoin import bcoin, bids, lsdirs, bidsversion, trackusage, __version__, DEBUG

html_head = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Slice report</title>
    <link rel="stylesheet" href="style.css">
</head>

<body>

"""
html_style = """\
body     { color: #D1D1D1; background-color: #181818; font-family: Arial; margin-left: 15px }
h1       { color: Orange; font-size: 18px; display: inline-block; border: 1px solid orange;
           padding: 10px 20px; border-radius: 10px; }
a        { color: inherit; text-decoration: none; }
a:hover  { color: Orange; }
a:active { color: Yellow; }
"""


def parse_options(options: list) -> str:
    """Check the OPTIONS arguments and return them to a string that can be passed to slicer"""
    for n, option in enumerate(options):
        if options[n-1] == 'l': continue                  # Skip checking the LUT string
        if not (option in ('L','l','i','e','t','n','u','s','c') or option.replace('.','').replace('-','').isdecimal()):
            print(f"Invalid OPTIONS: {' '.join(options)}"); sys.exit(2)
        if option.isalpha():
            options[n] = '-' + options[n]

    return  f"{' '.join(options)}"


def parse_outputs(outputargs: list, name: str) -> tuple:
    """
    Check the OUTPUT arguments and construct slicer and pngappend input arguments

    :return: (slicer_outputopts: str, pngappend_slices: str)
    """
    outputs  = ''       # These are input arguments for slicer (i.e. the slicer output images)
    slices   = ''       # These are input arguments for pngappend (i.e. the slicer output images)
    isnumber = lambda arg: arg.replace('.','').replace('-','').isdecimal()
    for n, outputarg in enumerate(outputargs):
        if not (outputarg in ('x', 'y', 'z', 'a', 'A', 'S', 'LF') or isnumber(outputarg)):
            print(f"Invalid {name}: '{outputarg}' in '{' '.join(outputargs)}'"); sys.exit(2)
        if outputarg.isalpha() and outputarg != 'LF':
            slices += f"{'' if n==0 else '-' if outputargs[n-1]=='LF' else '+'} slice_tmp{n}.png "
            if outputarg == 'a':
                outputs += f"-{outputarg} slice_tmp{n}.png "
            elif outputarg in ('x', 'y', 'z', 'A'):
                if not isnumber(outputargs[n+1]):
                    print(f"Invalid {name}: '{outputargs[n+1]}' in '{' '.join(outputargs)}'"); sys.exit(2)
                outputs += f"-{outputarg} {outputargs[n+1]} slice_tmp{n}.png "
            elif outputarg == 'S':
                if not (isnumber(outputargs[n+1]) and isnumber(outputargs[n+2])):
                    print(f"Invalid {name}: {outputarg} >> '{' '.join(outputargs)}'"); sys.exit(2)
                outputs += f"-{outputarg} {outputargs[n+1]} {outputargs[n+2]} slice_tmp{n}.png "

    return outputs, slices


def slicer_append(inputimage: Path, operations: str, outlineimage: Path, mainopts: str, outputopts: str, sliceroutput: str, montage: Path, cluster: str):
    """Run fslmaths, slicer and pngappend (locally or on the cluster) to create a montage of the sliced images"""

    # Create a workdir and the shell command
    workdir  = montage.parent/next(tempfile._get_candidate_names())
    workdir.mkdir()
    inputdim = nib.load(inputimage).header['dim'][0]
    mathsimg = f"fslmaths {inputimage} {operations} mathsimg\n" if not (inputdim==3 and operations.strip()=='-Tmean') else ''
    command  = f"cd {workdir}\n" \
               f"{mathsimg}" \
               f"slicer {'mathsimg' if mathsimg else inputimage} {outlineimage} {mainopts} {outputopts}\n" \
               f"pngappend {sliceroutput} {montage.name}\n" \
               f"mv {montage.name} {montage.parent}\n" \
               + (f"rm -r {workdir}" if not DEBUG else '')

    # Wrap the shell command with a cluster submit command
    mem     = '8' if inputimage.stat().st_size > 50 * 1024**2 else '1'  # Ask for more resources if we have a large (e.g. 4D) input image
    outpath = workdir if DEBUG else tempfile.gettempdir()
    if cluster == 'torque':
        command = f"qsub -l walltime=0:02:00,mem={mem}gb -N slicereport -j oe -o {outpath} << EOF\n#!/bin/bash\n{command}\nEOF"
    elif cluster == 'slurm':
        command = f"sbatch --time=0:02:00 --mem={mem}G --job-name slicereport -o {outpath}/slurm-%x-%j.out << EOF\n#!/bin/bash\n{command}\nEOF"
    elif cluster:
        LOGGER.error(f"Invalid cluster manager `{cluster}`")
        exit(1)

    # Run the command
    LOGGER.bcdebug(f"Command: {command}")
    process = subprocess.run(command, shell=True, capture_output=True, text=True)
    if process.stderr or process.returncode != 0:
        LOGGER.warning(f"{command}\nErrorcode {process.returncode}:\n{process.stdout}\n{process.stderr}")
    if process.returncode != 0:
        sys.exit(process.returncode)


def slicereport(bidsdir: str, pattern: str, outlinepattern: str, outlineimage: str, subjects: list, reportdir: str, crossdirs: str, qccols: list, cluster: str, operations: str, suboperations: str, options: list, outputs: list, suboptions: list, suboutputs: list):
    """
    :param bidsdir:         The bids-directory with the subject data
    :param pattern:         Globlike search pattern to select the images in bidsdir to be reported, e.g. 'anat/*_T1w*'
    :param outlinepattern:  Globlike search pattern to select red-outline images that are projected on top of the reported images. Prepend `outlinedir:` if your outline images are in `outlinedir` instead of `bidsdir`
    :param outlineimage:    A common red-outline image that is projected on top of all images
    :param subjects:        Space separated list of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed
    :param reportdir:       The folder where the report is saved
    :param crossdirs:       A (list of) folder(s) with cross-linked sub-reports
    :param qccols:          Column names for creating an accompanying tsv-file to store QC-rating scores
    :param cluster:         Use `torque` or `slurm` to submit the slicer jobs to a high-performance compute (HPC) cluster. Leave empty to run slicer on your local computer
    :param operations:      The fslmath operations performed on the input image: fslmaths inputimage OPERATIONS reportimage
    :param suboperations:   The fslmath operations performed on the input image: fslmaths inputimage SUBOPERATIONS subreportimage
    :param options:         Slicer main options
    :param outputs:         Slicer output options
    :param suboptions:      Slicer main options for creating the sub-reports (same as OPTIONS)
    :param suboutputs:      Slicer output options for creating the sub-reports (same as OUTPUTS)
    :return:
    """

    # Input checking
    bidsdir = Path(bidsdir).resolve()
    if not bidsdir.is_dir():
        print(f"Could not find the bids folder: {bidsdir}"); return
    if not reportdir:
        reportdir = bidsdir/'derivatives/slicereport'
    else:
        reportdir = Path(reportdir).resolve()
    if isinstance(crossdirs, str):
        crossdirs = [crossdirs]
    elif crossdirs is None:
        crossdirs = []
    for crossdir in crossdirs:
        if not Path(crossdir).is_dir():
            print(f"Could not find: {crossdir}"); return
    if outlineimage:
        if outlinepattern:
            print('The "--outlineimage" and "--outlinepattern" arguments are mutually exclusive, please specify one or the other'); return
        outlineimage = Path(outlineimage).resolve()
        if not outlineimage.is_file():
            print(f"Could not find the common outline image: {outlineimage}"); return
    if outlinepattern and ':' in outlinepattern:
        outlinedir, outlinepattern = outlinepattern.split(':',1)
        outlinedir = Path(outlinedir).resolve()
        if not outlinedir.is_dir():
            print(f"Could not find the outline folder: {outlinedir}"); return
    else:
        outlinedir = bidsdir
    if not suboptions:
        suboptions = copy(options)

    # Format the slicer main and output options and sliced images
    options                     = parse_options(options)
    outputs, sliceroutput       = parse_outputs(outputs, 'OUTPUTS')
    suboptions                  = parse_options(suboptions)
    suboutputs, subsliceroutput = parse_outputs(suboutputs, 'SUBOUTPUTS')

    # Get the list of subjects
    if not subjects:
        subjects = lsdirs(bidsdir, 'sub-*')
        if not subjects:
            print(f"No subjects found in: {bidsdir/'sub-*'}"); return
    else:
        subjects = ['sub-' + subject.replace('sub-', '') for subject in subjects]               # Make sure there is a "sub-" prefix
        subjects = [bidsdir/subject for subject in subjects if (bidsdir/subject).is_dir()]

    # Start logging
    reportdir.mkdir(parents=True, exist_ok=True)
    (reportdir/'slicereport.log').unlink(missing_ok=True)
    bcoin.setup_logging(reportdir/'slicereport.log')
    LOGGER.info(f"Command: slicereport {' '.join(sys.argv[1:])}")

    # Create the report index file
    report = reportdir/'index.html'
    report.write_text(f'{html_head}<h1>Command:<span style="color: White"> slicereport {" ".join(sys.argv[1:])}</span></h1>\n')
    style  = reportdir/'style.css'
    style.write_text(html_style)

    # Create a QC tsv-file
    qcfile = reportdir/'qcscores.tsv'
    if qccols:
        with open(qcfile, 'wt') as fid:
            tsv_writer = csv.writer(fid, delimiter='\t')
            tsv_writer.writerow(['subject/session'] + qccols)

    # Loop over the subject/session-directories
    with logging_redirect_tqdm():
        for subject in tqdm(subjects, unit='subject', colour='green', leave=False):
            sessions  = lsdirs(subject, 'ses-*')
            style_rel = '../../style.css'
            if not sessions:
                sessions  = [subject]
                style_rel = '../style.css'
            for session in sessions:

                # Write a row in the QC tsv-file
                if qccols:
                    with open(qcfile, 'a') as fid:
                        tsv_writer = csv.writer(fid, delimiter='\t')
                        tsv_writer.writerow([str(session.relative_to(bidsdir))] + len(qccols) * ['n/a'])

                # Search for the image(s) to report
                LOGGER.info(f"Processing images in: {session.relative_to(bidsdir)}")
                images = sorted([match for match in session.glob(pattern) if '.nii' in match.suffixes])
                if not images:
                    LOGGER.warning(f"Could not find images using: {session.relative_to(bidsdir)}/{pattern}")
                    continue
                outlineimages = [''] * len(images)
                if outlinepattern:
                    outlinesession = outlinedir/session.relative_to(bidsdir)
                    outlineimages  = sorted([match.with_suffix('').with_suffix('') for match in outlinesession.glob(outlinepattern) if '.nii' in match.suffixes])
                    if len(outlineimages) != len(images):
                        LOGGER.error(f"Nr of outline images ({len(outlineimages)}) in {outlinesession.relative_to(bidsdir)} should be the same as the number of underlying images ({len(images)})")
                        outlineimages = [''] * len(images)

                # Generate a report row and a sub-report for each session
                reportses = reportdir/session.relative_to(bidsdir)
                reportses.mkdir(parents=True, exist_ok=True)
                for n, image in enumerate(images):

                    # Generate the sliced image montage
                    outline = outlineimages[n] if outlinepattern else outlineimage
                    montage = reportses/image.with_suffix('').with_suffix('.png').name
                    slicer_append(image, operations, outline, options, outputs, sliceroutput, montage, cluster)

                    # Add the montage as a (sub-report linked) row to the report
                    caption   = f"{image.relative_to(bidsdir)}{'&nbsp;&nbsp;&nbsp;( ../'+str(outline.relative_to(outlinesession))+' )' if outlinepattern and outline else ''}"
                    subreport = reportses/f"{bids.insert_bidskeyval(image, 'desc', 'subreport', False).with_suffix('').stem}.html"
                    with report.open('a') as fid:
                        fid.write(f'\n<p><a href="{subreport.relative_to(reportdir).as_posix()}"><img src="{montage.relative_to(reportdir).as_posix()}"><br>\n{caption}</a></p>\n')

                    # Add the sub-report
                    if suboutputs:
                        montage = subreport.with_suffix('.png')
                        slicer_append(image, suboperations, outline, suboptions, suboutputs, subsliceroutput, montage, cluster)
                    crossreports = ''
                    for crossdir in crossdirs:          # Include niprep reports
                        for crossreport in sorted(Path(crossdir).glob(f"{subject.name.split('_')[0]}*.html")) + sorted((Path(crossdir)/session.relative_to(bidsdir)).glob('*.html')):
                            crossreports += f'\n<br><a href="{crossreport.resolve()}">&#8618; {crossreport}</a>'
                    if subreport.with_suffix('.json').is_file():
                        with open(subreport.with_suffix('.json'), 'r') as meta_fid:
                            metadata = f"\n\n<p>{json.load(meta_fid)}</p>"
                    elif image.with_suffix('').with_suffix('.json').is_file():
                        with open(image.with_suffix('').with_suffix('.json'), 'r') as meta_fid:
                            metadata = f"\n\n<p>{json.load(meta_fid)}</p>"
                    else:
                        metadata = ''
                    subreport.write_text(f'{html_head.replace("style.css", style_rel)}<h1>{caption}</h1>\n{crossreports}\n<p><img src="{montage.name}"></p>{metadata}\n\n</body></html>')

    # Create a dataset description file if it does not exist
    dataset = reportdir/'dataset_description.json'
    if not dataset.is_file():
        description = {"Name": "Slicereport - A visual inspection report",
                       "BIDSVersion": bidsversion(),
                       "DatasetType": "derivative",
                       "GeneratedBy": [{"Name":"BIDScoin", "Version":__version__, "CodeURL":"https://github.com/Donders-Institute/bidscoin"}]}
        with dataset.open('w') as fid:
            json.dump(description, fid, indent=4)

    # Finish off
    errors = bcoin.reporterrors().replace('\n', '<br>\n')
    if errors:
        footer = '<h3 style="color: Red">The following errors and warnings were reported:</h3>\n'
    else:
        footer = '<h3 style="color: LimeGreen">No errors or warnings were reported</h3>\n'
    with report.open('a') as fid:
        fid.write(f'\n<br>{footer}<p>\n{errors}</p>\n\n</body></html>')
    if qccols:
        LOGGER.info(' ')
        LOGGER.info('To store QC ratings, open:')
        LOGGER.info(qcfile)
    LOGGER.info(' ')
    LOGGER.info('To view the slice report, point your web browser at:')
    LOGGER.info(f"{report}\n ")
    if cluster:
        LOGGER.info('But first wait for your `slicereport`-jobs to finish... Use e.g.:\n\nqstat $(qselect -s RQ) | grep slicereport\n')


def main():
    """Console script entry point"""

    from bidscoin.cli._slicereport import get_parser

    args = get_parser().parse_args()

    trackusage('slicereport')
    try:
        slicereport(bidsdir        = args.bidsfolder,
                    pattern        = args.pattern,
                    outlinepattern = args.outlinepattern,
                    outlineimage   = args.outlineimage,
                    subjects       = args.participant_label,
                    reportdir      = args.reportfolder,
                    crossdirs      = args.xlinkfolder,
                    qccols         = args.qcscores,
                    cluster        = args.cluster,
                    operations     = args.operations,
                    suboperations  = args.suboperations,
                    options        = args.options,
                    outputs        = args.outputs,
                    suboptions     = args.suboptions,
                    suboutputs     = args.suboutputs)

    except Exception:
        trackusage('slicereport_exception')
        raise


if __name__ == '__main__':
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
