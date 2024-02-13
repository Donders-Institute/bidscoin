#!/usr/bin/env python3
"""A bidsapp that combines echos and wraps around FreeSurfer's 'synthstrip' skull stripping tool (See also cli/_skullstrip.py)"""

# NB: Set os.environ['DUECREDIT'] values as early as possible to capture all credits
import os
import sys
if __name__ == "__main__" and os.getenv('DUECREDIT_ENABLE','').lower() not in ('1', 'yes', 'true') and len(sys.argv) > 1:    # Ideally the due state (`self.__active=True`) should also be checked (but that's impossible)
    os.environ['DUECREDIT_ENABLE'] = 'yes'
    os.environ['DUECREDIT_FILE']   = os.path.join(sys.argv[1], 'code', 'bidscoin', '.duecredit_skullstrip.p')   # NB: argv[1] = bidsfolder

import shutil
import json
import logging
import pandas as pd
import nibabel as nib
import tempfile
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    sys.path.append(str(Path(__file__).parents[2]))
from bidscoin import bcoin, bids, lsdirs, trackusage, DEBUG
from bidscoin.due import due, Doi


@due.dcite(Doi('10.1016/j.neuroimage.2022.119474'), description='Robust, universal skull-stripping for brain images of any type', tags=['reference-implementation'])
def skullstrip(bidsdir: str, pattern: str, subjects: list, masked: str, output: list, force: bool, args: str, cluster: bool, nativespec: str):
    """
    :param bidsdir:     The bids-directory with the subject data
    :param pattern:     Globlike search pattern (relative to the subject/session folder) to select the images that need to be skullstripped, e.g. 'anat/*_T1w*'
    :param subjects:    List of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed
    :param force:       If True then images will be processed, regardless if images have already been skullstripped (i.e. if {"SkullStripped": True} in the json sidecar file)
    :param masked:      Globlike search pattern (relative to the subject/session folder) to select additional images that need to be masked with the same mask, e.g. 'fmap/*_phasediff')
    :param output:      One or two output strings that determine where the skullstripped + additional masked images are saved. Each output string can be the name of a BIDS datatype folder, such as 'anat', or of the derivatives folder, i.e. 'derivatives' (default). If the output string is the same as the datatype then the original images are replaced by the skullstripped images
    :param args:        Additional arguments that are passed to synthstrip. See examples for usage
    :param cluster:     Flag to submit the skullstrip-jobs to the high-performance compute (HPC) cluster using the drmaa library
    :param nativespec:  DRMAA native specifications for submitting skullstrip jobs to the HPC cluster
    :return:
    """

    # Input checking
    bidsdir = Path(bidsdir).resolve()
    if not bidsdir.is_dir():
        print(f"Could not find the bids folder: {bidsdir}")
        return
    if not output or len(output) == 0:
        output = ['derivatives']
    if len(output) == 1:
        output += output
    if len(output) != 2:
        print(f"The 'output' argument should be one or strings, not {len(output)} ({output})")
        return
    if not shutil.which('mri_synthstrip'):
        print("Could not find 'mri_synthstrip', skullstrip requires FreeSurfer v7.3.2 or higher")
        return
    if cluster and masked:
        print("The `--cluster` option cannot be used in combination with `--masked`")
        return

    # Start logging
    bcoin.setup_logging(bidsdir/'code'/'bidscoin'/'skullstrip.log')
    LOGGER.info('')
    LOGGER.info('------------ START skullstrip ------------')
    LOGGER.info(f">>> skullstrip bidsfolder={bidsdir} pattern={pattern} subjects={subjects} masked={masked} output={output} force={force} {args}")

    # Get the list of subjects
    if not subjects:
        subjects = lsdirs(bidsdir, 'sub-*')
        if not subjects:
            LOGGER.warning(f"No subjects found in: {bidsdir/'sub-*'}")
    else:
        subjects = ['sub-' + subject.replace('sub-', '') for subject in subjects]               # Make sure there is a "sub-" prefix
        subjects = [bidsdir/subject for subject in subjects if (bidsdir/subject).is_dir()]

    # Prepare the HPC job submission
    if cluster:
        from drmaa import Session as drmaasession
    else:
        from contextlib import nullcontext as drmaasession                                      # Use a dummy context manager
    with drmaasession() as pbatch:
        jobids = []
        if cluster:
            jt                     = pbatch.createJobTemplate()
            jt.jobEnvironment      = os.environ
            jt.remoteCommand       = shutil.which('mri_synthstrip')
            jt.nativeSpecification = nativespec
            jt.joinFiles           = True

        # Loop over bids subject/session-directories
        with logging_redirect_tqdm():
            for n, subject in enumerate(tqdm(subjects, unit='subject', colour='green', leave=False), 1):

                subid    = subject.name
                sessions = lsdirs(subject, 'ses-*')
                if not sessions:
                    sessions = [subject]
                for session in sessions:

                    LOGGER.info('--------------------------------------')
                    LOGGER.info(f"Processing ({n}/{len(subjects)}): {session}")

                    # Search for images that need to be skullstripped
                    sesid   = session.name if session.name.startswith('ses-') else ''
                    srcimgs = sorted([match for match in session.glob(pattern) if '.nii' in match.suffixes])
                    addimgs = sorted([match for match in session.glob(masked)  if '.nii' in match.suffixes]) if masked else []
                    if not srcimgs:
                        LOGGER.info(f"No images found for {pattern} in: {session}")
                    if masked and not addimgs:
                        LOGGER.info(f"No images found for {masked} in: {session}")
                    if addimgs and len(srcimgs) > 1:
                        LOGGER.error(f"{len(srcimgs)} matches found for {session/pattern}, which is ambiguous (the {masked} masked option requires a single match)")
                        addimgs = []
                    for srcimg in srcimgs:

                        # Construct the output filename and relative path names (for updating the IntendedFor list and scans.tsv file)
                        srcent, suffix = srcimg.with_suffix('').stem.rsplit('_',1)  # Name without suffix, suffix
                        derent         = 'space-orig_desc-brain'
                        ext            = ''.join(srcimg.suffixes)                   # Account for e.g. '.nii.gz'
                        if output[0] == 'derivatives':
                            outputimg = bidsdir/'derivatives'/'skullstrip'/subid/sesid/srcimg.parent.name/f"{srcent}_{derent}_{suffix}{ext}"
                        else:
                            outputimg = session/output[0]/srcimg.name               # NB: Overwrite the original image
                        outputimg.parent.mkdir(parents=True, exist_ok=True)

                        # Check the json "SkullStripped" field to see if it has already been skullstripped
                        outputjson = outputimg.with_suffix('').with_suffix('.json')
                        if not force and outputjson.is_file():
                            with outputjson.open('r') as sidecar:
                                metadata = json.load(sidecar)
                            if metadata.get('SkullStripped'):
                                LOGGER.info(f"Skipping already skullstripped image: {outputimg}")
                                continue

                        # Skullstrip the image
                        maskimg = bidsdir/'derivatives'/'skullstrip'/subid/sesid/srcimg.parent.name/f"{srcent}_{derent}_mask{ext}"
                        maskimg.parent.mkdir(parents=True, exist_ok=True)
                        if cluster:
                            jt.args       = ['-i', srcimg, '-o', outputimg, '-m', maskimg] + args.split()
                            jt.jobName    = f"skullstrip_{subid}_{sesid}"
                            jt.outputPath = f"{os.getenv('HOSTNAME')}:{Path.cwd() if DEBUG else tempfile.gettempdir()}/{jt.jobName}.out"
                            jobids.append(pbatch.runJob(jt))
                            LOGGER.info(f"Your skullstrip job has been submitted with ID: {jobids[-1]}")
                        elif bcoin.run_command(f"mri_synthstrip -i {srcimg} -o {outputimg} -m {maskimg} {args}"):
                            continue

                        # Add a json sidecar-file with the "SkullStripped" field
                        srcjson = srcimg.with_suffix('').with_suffix('.json')
                        if srcjson.is_file():
                            with srcjson.open('r') as sidecar:
                                metadata = json.load(sidecar)
                        else:
                            metadata = {}
                        metadata['SkullStripped'] = True
                        with outputjson.open('w') as sidecar:
                            json.dump(metadata, sidecar, indent=4)
                        metadata['Type'] = 'Brain'
                        with maskimg.with_suffix('').with_suffix('.json').open('w') as sidecar:
                            json.dump(metadata, sidecar, indent=4)

                        # Apply the mask to the additional images and save it as output
                        maskobj    = nib.load(maskimg)   if addimgs else []
                        maskvol    = maskobj.get_fdata() if addimgs else []
                        addoutimgs = []                # To be used for updating the IntendedFor list and the scans.tsv file
                        for addimg in addimgs:

                            # Define the output image
                            if output[1] == 'derivatives':
                                srcent, suffix = addimg.name.rsplit('_', 1)     # NB: suffix = suffix.ext
                                addoutimg      = bidsdir/'derivatives'/'skullstrip'/subid/sesid/addimg.parent.name/f"{srcent}_{derent}_{suffix}"
                            else:
                                addoutimg = session/output[1]/addimg.name       # NB: Could be the same as the original image
                            addoutimgs.append(addoutimg)
                            outputjson = addoutimg.with_suffix('').with_suffix('.json')
                            if not force and outputjson.is_file():
                                with outputjson.open('r') as sidecar:
                                    metadata = json.load(sidecar)
                                if metadata.get('SkullStripped'):
                                    LOGGER.info(f"Skipping already skullstripped image: {addoutimg}")
                                    continue

                            # Load the volume data, multiply it with the mask and save it to the output image
                            addoutimg.parent.mkdir(parents=True, exist_ok=True)
                            addobj = nib.load(addimg)
                            if addobj.header.get_data_shape()[0:3] == maskobj.header.get_data_shape():
                                LOGGER.info(f"Applying skullstrip-mask to: {addoutimg}")
                                addmsk = nib.Nifti1Image(addobj.get_fdata() * maskvol, addobj.affine, addobj.header)
                                addmsk.to_filename(addoutimg)
                            else:
                                LOGGER.error(f"Cannot apply skullstrip-mask to: {addoutimg}\nIt's dimensions are {addobj.header.get_data_shape()} but the mask is {maskobj.header.get_data_shape()}")
                                continue

                            # Add a json sidecar-file to the output image
                            if addimg.with_suffix('').with_suffix('.json').is_file():
                                with addimg.with_suffix('').with_suffix('.json').open('r') as sidecar:
                                    metadata = json.load(sidecar)
                            else:
                                metadata = {}
                            metadata['SkullStripped'] = True
                            with outputjson.open('w') as sidecar:
                                json.dump(metadata, sidecar, indent=4)

                        # Update the scans.tsv file
                        scans_tsv = session/f"{subid}{'_'+sesid if sesid else ''}_scans.tsv"
                        if scans_tsv.is_file():

                            # Add the new images to the scans table
                            scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
                            bidsignore  = (bidsdir/'.bidsignore').read_text().splitlines() if (bidsdir/'.bidsignore').is_file() else ['extra_data/']
                            for original, stripped in zip([srcimg] + addimgs, [outputimg] + addoutimgs):
                                if not stripped.name or 'derivatives' in stripped.parts or bids.check_ignore(stripped.parent.name, bidsignore):
                                    continue
                                original_rel = original.relative_to(session).as_posix()
                                stripped_rel = stripped.relative_to(session).as_posix()
                                datatype     = stripped_rel.split('/')[0]
                                if original_rel in scans_table.index and stripped_rel not in scans_table.index and datatype in bids.datatyperules:
                                    LOGGER.info(f"Adding '{stripped_rel}' to '{scans_tsv}'")
                                    scans_table.loc[stripped_rel] = scans_table.loc[original_rel]

                            # Save the data
                            scans_table.sort_values(by=['acq_time','filename'], inplace=True)
                            scans_table.replace('','n/a').to_csv(scans_tsv, sep='\t', encoding='utf-8', na_rep='n/a')
                            for scan in scans_table.index:
                                if not (session/scan).is_file():
                                    LOGGER.warning(f"Found non-existent file '{scan}' in '{scans_tsv}'")

        if cluster and jobids:
            LOGGER.info('')
            LOGGER.info('Waiting for the skullstrip jobs to finish...')
            bcoin.synchronize(pbatch, jobids, wait=0)
            pbatch.deleteJobTemplate(jt)

    LOGGER.info('-------------- FINISHED! -------------')
    LOGGER.info('')


def main():
    """Console script entry point"""

    from bidscoin.cli._skullstrip import get_parser

    args = get_parser().parse_args()

    trackusage('skullstrip')
    try:
        skullstrip(bidsdir    = args.bidsfolder,
                   pattern    = args.pattern,
                   subjects   = args.participant_label,
                   masked     = args.masked,
                   output     = args.output,
                   force      = args.force,
                   args       = args.args,
                   cluster    = args.cluster,
                   nativespec = args.nativespec)

    except Exception:
        trackusage('skullstrip_exception')
        raise


if __name__ == '__main__':
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
