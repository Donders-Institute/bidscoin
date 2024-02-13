#!/usr/bin/env python3
"""A bidsapp that combines echos and wraps around the 'pydeface' defacing tool (See also cli/_medeface.py)"""

# NB: Set os.environ['DUECREDIT'] values as early as possible to capture all credits
import os
import sys
if __name__ == "__main__" and os.getenv('DUECREDIT_ENABLE','').lower() not in ('1', 'yes', 'true') and len(sys.argv) > 1:    # Ideally the due state (`self.__active=True`) should also be checked (but that's impossible)
    os.environ['DUECREDIT_ENABLE'] = 'yes'
    os.environ['DUECREDIT_FILE']   = os.path.join(sys.argv[1], 'code', 'bidscoin', '.duecredit_medeface.p')   # NB: argv[1] = bidsfolder

import shutil
import json
import logging
import pandas as pd
import pydeface.utils as pdu
import nibabel as nib
import numpy as np
import tempfile
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from pathlib import Path
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    sys.path.append(str(Path(__file__).parents[2]))
from bidscoin import bcoin, bids, lsdirs, trackusage, DEBUG
from bidscoin.due import due, Doi


@due.dcite(Doi('10.5281/zenodo.3524400'), description='A tool to remove facial structure from MRI images', tags=['reference-implementation'])
def medeface(bidsdir: str, pattern: str, maskpattern: str, subjects: list, force: bool, output: str, cluster: bool, nativespec: str, kwargs: dict):
    """
    :param bidsdir:     The bids-directory with the (multi-echo) subject data
    :param pattern:     Globlike search pattern (relative to the subject/session folder) to select the echo-images that need to be defaced, e.g. 'anat/*_T1w*'
    :param maskpattern: Globlike search pattern (relative to the subject/session folder) to select the images from which the defacemask is computed, e.g. 'anat/*_part-mag_*_T2starw*'. If not given then 'pattern' is used
    :param subjects:    List of sub-# identifiers to be processed (the sub-prefix can be left out). If not specified then all sub-folders in the bidsfolder will be processed
    :param force:       If True then images will be processed, regardless if images have already been defaced (i.e. if {"Defaced": True} in the json sidecar file)
    :param output:      Determines where the defaced images are saved. It can be the name of a BIDS datatype folder, such as 'anat', or of the derivatives folder, i.e. 'derivatives'. If output is left empty then the original images are replaced by the defaced images
    :param cluster:     Flag to submit the-deface jobs to the high-performance compute (HPC) cluster
    :param nativespec:  DRMAA native specifications for submitting deface jobs to the HPC cluster
    :param kwargs:      Additional arguments (in dict/json-style) that are passed to pydeface. See examples for usage
    :return:
    """

    # Input checking
    bidsdir = Path(bidsdir).resolve()
    if not bidsdir.is_dir():
        print(f"Could not find the bids folder: {bidsdir}")
        return
    if not maskpattern:
        maskpattern = pattern

    # Start logging
    bcoin.setup_logging(bidsdir/'code'/'bidscoin'/'medeface.log')
    LOGGER.info('')
    LOGGER.info('------------ START multi-echo deface ----------')
    LOGGER.info(f">>> medeface bidsfolder={bidsdir} pattern={pattern} maskpattern={maskpattern} subjects={subjects} output={output}"
                f" cluster={cluster} nativespec={nativespec} {kwargs}")

    # Get the list of subjects
    if not subjects:
        subjects = lsdirs(bidsdir, 'sub-*')
        if not subjects:
            LOGGER.warning(f"No subjects found in: {bidsdir/'sub-*'}")
    else:
        subjects = ['sub-' + subject.replace('sub-', '') for subject in subjects]               # Make sure there is a "sub-" prefix
        subjects = [bidsdir/subject for subject in subjects if (bidsdir/subject).is_dir()]

    # Prepare the HPC pydeface job submission
    tmp_combined = f"{next(tempfile._get_candidate_names())}_echocombined_deface.nii"
    if cluster:
        from drmaa import Session as drmaasession
    else:
        from contextlib import nullcontext as drmaasession                                      # Use a dummy context manager
    with drmaasession() as pbatch:
        jobids = []
        if cluster:
            jt                     = pbatch.createJobTemplate()
            jt.jobEnvironment      = os.environ
            jt.remoteCommand       = shutil.which('pydeface')
            jt.nativeSpecification = nativespec
            jt.joinFiles           = True

        # Loop over bids subject/session-directories to first get all the echo-combined deface masks
        with logging_redirect_tqdm():
            for n, subject in enumerate(tqdm(subjects, unit='subject', colour='yellow', leave=False), 1):

                subid    = subject.name
                sessions = lsdirs(subject, 'ses-*')
                if not sessions:
                    sessions = [subject]
                for session in sessions:

                    LOGGER.info('--------------------------------------')
                    LOGGER.info(f"Processing ({n}/{len(subjects)}): {session}")

                    # Read the echo-images that will be combined to compute the deface-mask
                    sesid     = session.name if session.name.startswith('ses-') else ''
                    echofiles = sorted([match for match in session.glob(maskpattern) if '.nii' in match.suffixes])
                    if not echofiles:
                        LOGGER.info(f'No mask files found for: {session}/{maskpattern}')
                        continue

                    # Check the json "Defaced" field to see if it has already been defaced
                    if not force and echofiles[0].with_suffix('').with_suffix('.json').is_file():
                        with echofiles[0].with_suffix('').with_suffix('.json').open('r') as fid:
                            jsondata = json.load(fid)
                        if jsondata.get('Defaced'):
                            LOGGER.info(f"Skipping already defaced images: {[str(echofile) for echofile in echofiles]}")
                            continue

                    LOGGER.info(f'Loading mask files: {[str(echofile) for echofile in echofiles]}')
                    echos = [nib.load(echofile) for echofile in echofiles]

                    # Create a temporary echo-combined image
                    tmpfile  = session/tmp_combined
                    combined = nib.Nifti1Image(np.mean([echo.get_fdata() for echo in echos], axis=0), echos[0].affine, echos[0].header)
                    combined.to_filename(tmpfile)

                    # Deface the echo-combined image
                    LOGGER.info(f"Creating a deface-mask from the echo-combined image: {tmpfile}")
                    if cluster:
                        jt.args       = [str(tmpfile), '--outfile', str(tmpfile), '--force'] + [item for pair in [[f"--{key}", val] for key,val in kwargs.items()] for item in pair]
                        jt.jobName    = f"medeface_{subid}_{sesid}"
                        jt.outputPath = f"{os.getenv('HOSTNAME')}:{Path.cwd() if DEBUG else tempfile.gettempdir()}/{jt.jobName}.out"
                        jobids.append(pbatch.runJob(jt))
                        LOGGER.info(f"Your deface job has been submitted with ID: {jobids[-1]}")
                    else:
                        pdu.deface_image(str(tmpfile), str(tmpfile), force=True, forcecleanup=True, **kwargs)

        if cluster and jobids:
            LOGGER.info('')
            LOGGER.info('Waiting for the deface jobs to finish...')
            bcoin.synchronize(pbatch, jobids)
            pbatch.deleteJobTemplate(jt)

    # Loop again over bids subject/session-directories to apply the deface-masks and write meta-data
    with logging_redirect_tqdm():
        for n, subject in enumerate(tqdm(subjects, unit='subject', colour='green', leave=False), 1):

            subid    = subject.name
            sessions = lsdirs(subject, 'ses-*')
            if not sessions:
                sessions = [subject]
            for session in sessions:

                LOGGER.info('--------------------------------------')
                LOGGER.info(f"Processing ({n}/{len(subjects)}): {session}")

                # Read the temporary defacemask
                sesid   = session.name if session.name.startswith('ses-') else ''
                tmpfile = session/tmp_combined
                if not tmpfile.is_file():
                    LOGGER.info(f'No {tmpfile} file found')
                    continue
                defacemask = nib.load(tmpfile).get_fdata() != 0     # The original defacemask is saved in a temporary folder, so it may be deleted -> use the defaced image to infer the mask
                tmpfile.unlink()

                # Process the echo-images that need to be defaced
                for echofile in sorted([match for match in session.glob(pattern) if '.nii' in match.suffixes]):

                    # Construct the output filename and relative path name (used in BIDS)
                    echofile_rel = echofile.relative_to(session).as_posix()
                    if not output:
                        outputfile     = echofile
                        outputfile_rel = echofile_rel
                    elif output == 'derivatives':
                        srcent, suffix = echofile.with_suffix('').stem.rsplit('_', 1)   # Name without suffix, suffix
                        ext = ''.join(echofile.suffixes)                                # Account for e.g. '.nii.gz'
                        outputfile     = bidsdir/'derivatives'/'deface'/subid/sesid/echofile.parent.name/f"{srcent}_space-orig_{suffix}{ext}"
                        outputfile_rel = outputfile.relative_to(bidsdir).as_posix()
                    else:
                        outputfile     = session/output/echofile.name
                        outputfile_rel = outputfile.relative_to(session).as_posix()
                    outputfile.parent.mkdir(parents=True, exist_ok=True)

                    # Apply the defacemask
                    LOGGER.info(f'Applying deface mask on: {echofile} -> {outputfile_rel}')
                    echoimg   = nib.load(echofile)
                    outputimg = nib.Nifti1Image(echoimg.get_fdata() * defacemask, echoimg.affine, echoimg.header)
                    outputimg.to_filename(outputfile)

                    # Add a json sidecar-file with the "Defaced" field
                    inputjson  = echofile.with_suffix('').with_suffix('.json')
                    outputjson = outputfile.with_suffix('').with_suffix('.json')
                    if inputjson.is_file():
                        with inputjson.open('r') as sidecar:
                            metadata = json.load(sidecar)
                    else:
                        metadata = {}
                    metadata['Defaced'] = True
                    with outputjson.open('w') as sidecar:
                        json.dump(metadata, sidecar, indent=4)

                    # Update the scans.tsv file
                    scans_tsv  = session/f"{subid}{'_'+sesid if sesid else ''}_scans.tsv"
                    bidsignore = (bidsdir/'.bidsignore').read_text().splitlines() if (bidsdir/'.bidsignore').is_file() else ['extra_data/']
                    if output and not bids.check_ignore(output, bidsignore) and scans_tsv.is_file():
                        LOGGER.info(f"Adding {outputfile_rel} to {scans_tsv}")
                        scans_table                     = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
                        scans_table.loc[outputfile_rel] = scans_table.loc[echofile_rel]
                        scans_table.sort_values(by=['acq_time','filename'], inplace=True)
                        scans_table.to_csv(scans_tsv, sep='\t', encoding='utf-8')

    LOGGER.info('-------------- FINISHED! -------------')
    LOGGER.info('')


def main():
    """Console script entry point"""

    from bidscoin.cli._medeface import get_parser

    args = get_parser().parse_args()

    trackusage('medeface')
    try:
        medeface(bidsdir     = args.bidsfolder,
                 pattern     = args.pattern,
                 maskpattern = args.maskpattern,
                 subjects    = args.participant_label,
                 force       = args.force,
                 output      = args.output,
                 cluster     = args.cluster,
                 nativespec  = args.nativespec,
                 kwargs      = args.args)

    except Exception:
        trackusage('medeface_exception')
        raise


if __name__ == '__main__':
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
