#!/usr/bin/env python
"""
Converts ("coins") datasets in the sourcefolder to nifti / json / tsv datasets in the
bidsfolder according to the BIDS standard. Check and edit the bidsmap.yaml file to
your needs using the bidseditor.py tool before running this function. You can run
bidscoiner.py after all data is collected, or whenever new data has been added to the
source folder (presuming the scan protocol hasn't changed).

Provenance information, warnings and error messages are stored in the
bidsfolder/code/bidscoin/bidscoiner.log file.
"""

import os
import glob
import pandas as pd
import json
import dateutil.parser
import logging
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger('bidscoin')


def coin_dicom(session: str, bidsmap: dict, bidsfolder: str, personals: dict, subprefix: str, sesprefix: str) -> None:
    """
    Converts the session dicom-files into BIDS-valid nifti-files in the corresponding bidsfolder and
    extracts personals (e.g. Age, Sex) from the dicom header

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :param subprefix:   The prefix common for all source subject-folders
    :param sesprefix:   The prefix common for all source session-folders
    :return:            Nothing
    """

    if not bids.lsdirs(session):
        LOGGER.warning('No run subfolder(s) found in: ' + session)
        return

    TE = [None, None]

    # Get a valid BIDS subject identifier from the (first) dicom-header or from the session source folder
    if bidsmap['DICOM']['participant'] and bidsmap['DICOM']['participant'].startswith('<<') and bidsmap['DICOM']['participant'].endswith('>>'):
        subid = bids.get_dicomfield(bidsmap['DICOM']['participant'][2:-2], bids.get_dicomfile(bids.lsdirs(session)[0]))
    elif bidsmap['DICOM']['participant']:
        subid = bidsmap['DICOM']['participant']
    else:
        subid = session.rsplit(os.sep + subprefix, 1)[1].split(os.sep + sesprefix, 1)[0]
    subid = 'sub-' + bids.cleanup_value(subid.lstrip(subprefix))
    if subid == subprefix:
        LOGGER.error('No valid subject identifier found for: ' + session)
        return

    # Get a valid or empty BIDS session identifier from the (first) dicom-header or from the session source folder
    if bidsmap['DICOM']['session'] and bidsmap['DICOM']['session'].startswith('<<') and bidsmap['DICOM']['session'].endswith('>>'):
        sesid = bids.get_dicomfield(bidsmap['DICOM']['session'][2:-2], bids.get_dicomfile(bids.lsdirs(session)[0]))
    elif bidsmap['DICOM']['session']:
        sesid = bidsmap['DICOM']['session']
    elif os.sep + sesprefix in session:
        sesid = session.rsplit(os.sep + sesprefix)[1]
    else:
        sesid = ''
    if sesid:
        sesid = 'ses-' + bids.cleanup_value(sesid.lstrip(sesprefix))

    # Create the BIDS session-folder and a scans.tsv file
    bidsses = os.path.join(bidsfolder, subid, sesid)         # NB: This gives a trailing '/' if ses=='', but that should be ok
    os.makedirs(bidsses, exist_ok=True)
    scans_tsv = os.path.join(bidsses, f'{subid}{bids.add_prefix("_",sesid)}_scans.tsv')
    if os.path.exists(scans_tsv):
        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
    else:
        scans_table = pd.DataFrame(columns=['acq_time'], dtype='str')
        scans_table.index.name = 'filename'

    # Process all the dicom run subfolders
    for runfolder in bids.lsdirs(session):

        if runfolder.startswith('.'):
            LOGGER.info('Ignoring hidden dicom-folder: ' + runfolder)
            continue
        else:
            LOGGER.info('Processing dicom-folder: ' + runfolder)

        # Get the cleaned-up bids labels from a dicom-file and bidsmap
        dicomfile = bids.get_dicomfile(runfolder)
        if not dicomfile: continue
        run, modality, index = bids.get_matching_dicomrun(dicomfile, bidsmap)

        # Check if we should ignore this run
        if modality == bids.ignoremodality:
            LOGGER.info(f'Leaving out: {runfolder}')
            continue

        # Check if we already know this run
        if index is None:
            LOGGER.warning(f"Skipping unknown '{modality}': {dicomfile}")
            continue

        # Create the BIDS session/modality folder
        bidsmodality = os.path.join(bidsses, modality)
        os.makedirs(bidsmodality, exist_ok=True)

        # Compose the BIDS filename using the bids labels and run-index
        runindex = run['bids']['run']
        if runindex.startswith('<<') and runindex.endswith('>>'):
            bidsname = bids.get_bidsname(subid, sesid, modality, run, runindex[2:-2])
            bidsname = bids.increment_runindex(bidsmodality, bidsname)
        else:
            bidsname = bids.get_bidsname(subid, sesid, modality, run, runindex)

        # Check if file already exists
        if os.path.isfile(os.path.join(bidsmodality, bidsname + '.json')):
            LOGGER.warning(os.path.join(bidsmodality, bidsname) + '.* already exists -- check your results carefully!')

        # Convert the dicom-files in the run folder to nifti's in the BIDS-folder
        command = '{path}dcm2niix {args} -f "{filename}" -o "{outfolder}" "{infolder}"'.format(
            path      = bidsmap['Options']['dcm2niix']['path'],
            args      = bidsmap['Options']['dcm2niix']['args'],
            filename  = bidsname,
            outfolder = bidsmodality,
            infolder  = runfolder)
        if not bids.run_command(command):
            continue

        # Replace uncropped output image with the cropped one
        if '-x y' in bidsmap['Options']['dcm2niix']['args']:
            for filename in sorted(glob.glob(os.path.join(bidsmodality, bidsname + '*_Crop_*'))):               # e.g. *_Crop_1.nii.gz
                basepath, ext1 = os.path.splitext(filename)
                basepath, ext2 = os.path.splitext(basepath)                                                     # Account for .nii.gz files
                basepath       = basepath.rsplit('_Crop_',1)[0]
                newfilename    = basepath + ext2 + ext1
                LOGGER.info(f'Found dcm2niix _Crop_ suffix, replacing original file\n{filename} ->\n{newfilename}')
                os.replace(filename, newfilename)

        # Rename all files ending with _c%d, _e%d and _ph (and any combination of these): These are produced by dcm2niix for multi-coil data, multi-echo data and phase data, respectively
        jsonfiles = []                                                                                          # Collect the associated json-files (for updating them later) -- possibly > 1
        for dcm2niisuffix in ('_c', '_e', '_ph', '_i'):
            for filename in sorted(glob.glob(os.path.join(bidsmodality, bidsname + dcm2niisuffix + '[0-9]*'))):
                basepath, ext1  = os.path.splitext(filename)
                basepath, ext2  = os.path.splitext(basepath)                                                    # Account for .nii.gz files
                basepath, index = basepath.rsplit(dcm2niisuffix,1)
                index           = index.split('_')[0].zfill(2)                                                  # Zero padd as specified in the BIDS-standard (assuming two digits is sufficient); strip following suffices (fieldmaps produce *_e2_ph files)

                # This is a special hack: dcm2niix does not always add a _c/_e suffix for the first(?) coil/echo image -> add it when we encounter a **_e2/_c2 file
                if dcm2niisuffix in ('_c','_e') and int(index)==2 and basepath.rsplit('_',1)[1] != 'magnitude1':    # For fieldmaps: *_magnitude1_e[index] -> *_magnitude[index] (This is handled below)
                    filename_ce = basepath + ext2 + ext1                                                        # The file without the _c1/_e1 suffix
                    if dcm2niisuffix=='_e' and bids.set_bidsvalue(basepath, 'echo'):
                        newbasepath_ce = bids.set_bidsvalue(basepath, 'echo', '1')
                    else:
                        newbasepath_ce = bids.set_bidsvalue(basepath, 'dummy', dcm2niisuffix.upper() + '1'.zfill(len(index)))  # --> append to acq-label, may need to be elaborated for future BIDS standards, supporting multi-coil data
                    newfilename_ce = newbasepath_ce + ext2 + ext1                                               # The file as it should have been
                    if os.path.isfile(filename_ce):
                        if filename_ce != newfilename_ce:
                            LOGGER.info(f'Found no dcm2niix {dcm2niisuffix} suffix for image instance 1, renaming\n{filename_ce} ->\n{newfilename_ce}')
                            os.rename(filename_ce, newfilename_ce)
                        if ext1=='.json':
                            jsonfiles.append(newbasepath_ce + '.json')

                # Patch the basepath with the dcm2niix suffix info (we can't rely on the basepath info here because Siemens can e.g. put multiple echos in one series / run-folder)
                basesuffix = basepath.rsplit('_',1)[1]                                                          # Example basepath: *_magnitude1
                if dcm2niisuffix=='_e' and bids.set_bidsvalue(basepath, 'echo') and index:
                    basepath = bids.set_bidsvalue(basepath, 'echo', str(int(index)))                            # In contrast to other labels, run and echo labels MUST be integers. Those labels MAY include zero padding, but this is NOT RECOMMENDED to maintain their uniqueness

                elif dcm2niisuffix=='_e' and basesuffix in ('magnitude1','magnitude2') and index:               # i.e. modality == 'fmap'
                    basepath = basepath[0:-1] + str(int(index))                                                 # basepath: *_magnitude1_e[index] -> *_magnitude[index]
                    # Collect the echo times that need to be added to the json-file (see below)
                    if os.path.splitext(filename)[1] == '.json':
                        with open(filename, 'r') as json_fid:
                            data = json.load(json_fid)
                        TE[int(index)-1] = data['EchoTime']
                        LOGGER.info(f"Collected EchoTime{index} = {data['EchoTime']} from: {filename}")
                elif dcm2niisuffix=='_e' and basesuffix=='phasediff' and index:                                 # i.e. modality == 'fmap'
                    pass

                elif dcm2niisuffix=='_ph' and basepath.rsplit('_',1)[1] in ['phase1','phase2'] and index:       # i.e. modality == 'fmap' (TODO: untested)
                    basepath = basepath[0:-1] + str(int(index))                                                 # basepath: *_phase1_e[index] -> *_phase[index]
                    LOGGER.warning('Untested dcm2niix "_ph"-filetype: ' + basepath)

                else:
                    basepath = bids.set_bidsvalue(basepath, 'dummy', dcm2niisuffix.upper() + index)             # --> append to acq-label, may need to be elaborated for future BIDS standards, supporting multi-coil data

                # Save the file with a new name
                if runindex.startswith('<<') and runindex.endswith('>>'):
                    newbidsname = bids.increment_runindex(bidsmodality, os.path.basename(basepath), ext2 + ext1)  # Update the runindex now that the acq-label has changed
                else:
                    newbidsname = os.path.basename(basepath)
                newfilename = os.path.join(bidsmodality, newbidsname + ext2 + ext1)
                LOGGER.info(f'Found dcm2niix {dcm2niisuffix} suffix, renaming\n{filename} ->\n{newfilename}')
                os.rename(filename, newfilename)
                if ext1 == '.json':
                    jsonfiles.append(os.path.join(bidsmodality, newbidsname + '.json'))

        # Loop over and adapt all the newly produced json files and write to the scans.tsv file (every nifti-file comes with a json-file)
        if not jsonfiles:
            jsonfiles = [os.path.join(bidsmodality, bidsname + '.json')]
        for jsonfile in set(jsonfiles):

            # Check if dcm2niix behaved as expected
            if not os.path.isfile(jsonfile):
                LOGGER.warning(f'Unexpected file conversion result: {jsonfile} not found')
                continue

            # Add a dummy b0 bval- and bvec-file for any file without a bval/bvec file (e.g. sbref, b0 scans)
            if modality == 'dwi':
                bvecfile = os.path.splitext(jsonfile)[0] + '.bvec'
                bvalfile = os.path.splitext(jsonfile)[0] + '.bval'
                if not os.path.isfile(bvecfile):
                    LOGGER.info('Adding dummy bvec file: ' + bvecfile)
                    with open(bvecfile, 'w') as bvec_fid:
                        bvec_fid.write('0\n0\n0\n')
                if not os.path.isfile(bvalfile):
                    LOGGER.info('Adding dummy bval file: ' + bvalfile)
                    with open(bvalfile, 'w') as bval_fid:
                        bval_fid.write('0\n')

            # Add the TaskName to the func json-file
            elif modality == 'func':
                with open(jsonfile, 'r') as json_fid:
                    data = json.load(json_fid)
                if not 'TaskName' in data:
                    LOGGER.info('Adding TaskName to: ' + jsonfile)
                    data['TaskName'] = run['bids']['task']
                    with open(jsonfile, 'w') as json_fid:
                        json.dump(data, json_fid, indent=4)

            # Add the EchoTime(s) used to create the difference image to the fmap json-file. NB: This assumes the magnitude runs have already been parsed (i.e. their nifti's had an _e suffix) -- This is normally the case for Siemens (phase-runs being saved after the magnitude runs
            elif modality == 'fmap':
                if run['bids']['suffix'] == 'phasediff':
                    LOGGER.info(f'Adding EchoTime1: {TE[0]} and EchoTime2: {TE[1]} to {jsonfile}')
                    if TE[0] is None or TE[1] is None:
                        LOGGER.warning('Missing Echo-Time data for: ' + jsonfile)
                    elif TE[0]>TE[1]:
                        LOGGER.warning('EchoTime1 > EchoTime2 for: ' + jsonfile)
                    with open(jsonfile, 'r') as json_fid:
                        data = json.load(json_fid)
                    data['EchoTime1'] = TE[0]
                    data['EchoTime2'] = TE[1]
                    with open(jsonfile, 'w') as json_fid:
                        json.dump(data, json_fid, indent=4)

            # Parse the acquisition time from the json file
            with open(jsonfile, 'r') as json_fid:
                data = json.load(json_fid)
            if 'AcquisitionTime' not in data:
                data['AcquisitionTime'] = bids.get_dicomfield('AcquisitionTime', dicomfile)
            acq_time = dateutil.parser.parse(data['AcquisitionTime'])
            niipath  = glob.glob(os.path.splitext(jsonfile)[0] + '.nii*')[0]    # Find the corresponding nifti file (there should be only one, let's not make assumptions about the .gz extension)
            niipath  = niipath.replace(bidsses+os.sep,'')                       # Use a relative path. Somehow .strip(bidsses) instead of replace(bidsses,'') does not work properly
            scans_table.loc[niipath, 'acq_time'] = '1900-01-01T' + acq_time.strftime('%H:%M:%S')

    # Write the scans_table to disk
    LOGGER.info('Writing acquisition time data to: ' + scans_tsv)
    scans_table.to_csv(scans_tsv, sep='\t', encoding='utf-8')

    # Search for the IntendedFor images and add them to the json-files. This has been postponed untill all modalities have been processed (i.e. so that all target images are indeed on disk)
    if bidsmap['DICOM']['fmap'] is not None:
        for fieldmap in bidsmap['DICOM']['fmap']:
            if fieldmap['bids']['IntendedFor']:

                # Search for the imaging files that match the IntendedFor search criteria
                bidsname    = bids.get_bidsname(subid, sesid, 'fmap', fieldmap, '1')
                acqlabel    = bids.set_bidsvalue(bidsname, 'acq')
                intendedfor = fieldmap['bids']['IntendedFor']
                if intendedfor.startswith('<<') and intendedfor.endswith('>>'):
                    intendedfor = intendedfor[2:-2].split('><')
                elif not isinstance(intendedfor, list):
                    intendedfor = [intendedfor]
                niifiles = []
                for selector in intendedfor:
                    niifiles.extend([niifile.split(os.sep+subid+os.sep, 1)[1].replace('\\','/')                                                # The path needs to use forward slashes instead of backward slashes
                                     for niifile in sorted(glob.glob(os.path.join(bidsses, f'**{os.sep}*{selector}*.nii*'))) if selector])     # Search in all runs using a relative path

                # Save the IntendedFor data in the json-files (account for multiple runs and dcm2niix suffixes inserted into the acquisition label)
                for jsonfile in glob.glob(os.path.join(bidsses, 'fmap', bidsname.replace('_run-1_', '_run-[0-9]*_') + '.json')) + \
                                glob.glob(os.path.join(bidsses, 'fmap', bidsname.replace('_run-1_', '_run-[0-9]*_').replace(acqlabel, acqlabel+'[CE][0-9]*') + '.json')):
                    with open(jsonfile, 'r') as json_fid:
                        data = json.load(json_fid)
                    data['IntendedFor'] = niifiles
                    LOGGER.info('Adding IntendedFor to: ' + jsonfile)
                    with open(jsonfile, 'w') as json_fid:
                        json.dump(data, json_fid, indent=4)

                # Catch magnitude2 files produced by dcm2niix (i.e. magnitude1 & magnitude2 both in the same runfolder)
                if jsonfile.endswith('magnitude1.json'):
                    jsonfile2 = jsonfile.rsplit('1.json',1)[0] + '2.json'
                    if os.path.isfile(jsonfile2):
                        with open(jsonfile2, 'r') as json_fid:
                            data = json.load(json_fid)
                        if 'IntendedFor' not in data:
                            data['IntendedFor'] = niifiles
                            LOGGER.info('Adding IntendedFor to: ' + jsonfile2)
                            with open(jsonfile2, 'w') as json_fid:
                                json.dump(data, json_fid, indent=4)

    # Collect personal data from the DICOM header
    dicomfile = bids.get_dicomfile(runfolder)
    personals['participant_id'] = subid
    if sesid:
        personals['session_id'] = sesid
    personals['age']    = bids.get_dicomfield('PatientAge',    dicomfile)
    personals['sex']    = bids.get_dicomfield('PatientSex',    dicomfile)
    personals['size']   = bids.get_dicomfield('PatientSize',   dicomfile)
    personals['weight'] = bids.get_dicomfield('PatientWeight', dicomfile)


def coin_par(session: str, bidsmap: dict, bidsfolder: str, personals: dict) -> None:
    """

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    pass


def coin_p7(session: str, bidsmap: dict, bidsfolder: str, personals: dict) -> None:
    """

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    pass


def coin_nifti(session: str, bidsmap: dict, bidsfolder: str, personals: dict) -> None:
    """

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    pass


def coin_filesystem(session: str, bidsmap: dict, bidsfolder: str, personals: dict) -> None:
    """

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    pass


def coin_plugin(session: str, bidsmap: dict, bidsfolder: str, personals: dict) -> None:
    """
    Run the plugin coiner to cast the run into the bids folder

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    # Input checks
    if not bidsmap['PlugIns']:
        return

    for plugin in bidsmap['PlugIns']:

        # Load and run the plugin-module
        module = bids.import_plugin(plugin)
        if 'bidscoiner_plugin' in dir(module):
            LOGGER.debug(f'Running: {plugin}.bidscoiner_plugin({session}, bidsmap, {bidsfolder}, personals)')
            module.bidscoiner_plugin(session, bidsmap, bidsfolder, personals)


def bidscoiner(rawfolder: str, bidsfolder: str, subjects: tuple=(), force: bool=False, participants: bool=False, bidsmapfile: str='bidsmap.yaml', subprefix: str='sub-', sesprefix: str='ses-') -> None:
    """
    Main function that processes all the subjects and session in the sourcefolder and uses the
    bidsmap.yaml file in bidsfolder/code/bidscoin to cast the data into the BIDS folder.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param subjects:        List of selected subjects / participants (i.e. sub-# names / folders) to be processed (the sub- prefix can be removed). Otherwise all subjects in the sourcefolder will be selected
    :param force:           If True, subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped
    :param participants:    If True, subjects in particpants.tsv will not be processed (this could be used e.g. to protect these subjects from being reprocessed), also when force=True
    :param bidsmapfile:     The name of the bidsmap YAML-file. If the bidsmap pathname is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin
    :param subprefix:       The prefix common for all source subject-folders
    :param sesprefix:       The prefix common for all source session-folders
    :return:                Nothing
    """

    # Input checking & defaults
    rawfolder  = os.path.abspath(os.path.expanduser(rawfolder))
    bidsfolder = os.path.abspath(os.path.expanduser(bidsfolder))

    # Start logging
    bids.setup_logging(os.path.join(bidsfolder, 'code', 'bidscoin', 'bidscoiner.log'))
    LOGGER.info('')
    LOGGER.info(f'------------ START BIDScoiner {bids.version()}: BIDS {bids.bidsversion()} ------------')
    LOGGER.info(f'>>> bidscoiner sourcefolder={rawfolder} bidsfolder={bidsfolder} subjects={subjects} force={force}'
                f' participants={participants} bidsmap={bidsmapfile} subprefix={subprefix} sesprefix={sesprefix}')

    # Create a code/bidscoin subfolder
    os.makedirs(os.path.join(bidsfolder,'code','bidscoin'), exist_ok=True)

    # Create a dataset description file if it does not exist
    dataset_file = os.path.join(bidsfolder, 'dataset_description.json')
    if not os.path.isfile(dataset_file):
        dataset_description = {"Name":                  "REQUIRED. Name of the dataset",
                               "BIDSVersion":           bids.bidsversion(),
                               "License":               "RECOMMENDED. What license is this dataset distributed under?. The use of license name abbreviations is suggested for specifying a license",
                               "Authors":               ["OPTIONAL. List of individuals who contributed to the creation/curation of the dataset"],
                               "Acknowledgements":      "OPTIONAL. List of individuals who contributed to the creation/curation of the dataset",
                               "HowToAcknowledge":      "OPTIONAL. Instructions how researchers using this dataset should acknowledge the original authors. This field can also be used to define a publication that should be cited in publications that use the dataset",
                               "Funding":               ["OPTIONAL. List of sources of funding (grant numbers)"],
                               "ReferencesAndLinks":    ["OPTIONAL. List of references to publication that contain information on the dataset, or links"],
                               "DatasetDOI":            "OPTIONAL. The Document Object Identifier of the dataset (not the corresponding paper)"}
        LOGGER.info('Creating dataset description file: ' + dataset_file)
        with open(dataset_file, 'w') as fid:
            json.dump(dataset_description, fid, indent=4)

    # Create a README file if it does not exist
    readme_file = os.path.join(bidsfolder, 'README')
    if not os.path.isfile(readme_file):
        LOGGER.info('Creating README file: ' + readme_file)
        with open(readme_file, 'w') as fid:
            fid.write('A free form text ( README ) describing the dataset in more details that SHOULD be provided')

    # Get the bidsmap heuristics from the bidsmap YAML-file
    bidsmap, _ = bids.load_bidsmap(bidsmapfile, os.path.join(bidsfolder, 'code', 'bidscoin'))

    # Save options to the .bidsignore file
    bidsignore_items = [item.strip() for item in bidsmap['Options']['bidscoin']['bidsignore'].split(';')]
    LOGGER.info(f"Writing {bidsignore_items} entries to {bidsfolder}.bidsignore")
    with open(os.path.join(bidsfolder,'.bidsignore'), 'w') as bidsignore:
        for item in bidsignore_items:
            bidsignore.write(item + '\n')

    # Get the table & dictionary of the subjects that have been processed
    participants_tsv  = os.path.join(bidsfolder, 'participants.tsv')
    participants_json = os.path.splitext(participants_tsv)[0] + '.json'
    if os.path.exists(participants_tsv):
        participants_table = pd.read_csv(participants_tsv, sep='\t')
        participants_table.set_index(['participant_id'], verify_integrity=True, inplace=True)
    else:
        participants_table = pd.DataFrame()
        participants_table.index.name = 'participant_id'
    if os.path.exists(participants_json):
        with open(participants_json, 'r') as json_fid:
            participants_dict = json.load(json_fid)
    else:
        participants_dict = dict()

    # Get the list of subjects
    if not subjects:
        subjects = bids.lsdirs(rawfolder, subprefix + '*')
    else:
        subjects = [subprefix + subject.lstrip(subprefix) for subject in subjects]        # Make sure there is a "sub-" prefix
        subjects = [os.path.join(rawfolder,subject) for subject in subjects if os.path.isdir(os.path.join(rawfolder,subject))]

    # Loop over all subjects and sessions and convert them using the bidsmap entries
    for n, subject in enumerate(subjects, 1):

        if participants and subject in list(participants_table.index):
            LOGGER.info(f'Skipping subject: {subject} ({n}/{len(subjects)})')
            continue

        LOGGER.info(f'Coining subject ({n}/{len(subjects)}): {subject}')

        personals = dict()
        sessions  = bids.lsdirs(subject, sesprefix + '*')
        if not sessions:
            sessions = [subject]
        for session in sessions:

            # Check if we should skip the session-folder
            if not force and os.path.isdir(session.replace(rawfolder, bidsfolder)):
                LOGGER.info(f'Skipping processed session: {session}')
                continue

            # Update / append the dicom mapping
            if bidsmap['DICOM']:
                coin_dicom(session, bidsmap, bidsfolder, personals, subprefix, sesprefix)

            # Update / append the PAR/REC mapping
            if bidsmap['PAR']:
                coin_par(session, bidsmap, bidsfolder, personals)

            # Update / append the P7 mapping
            if bidsmap['P7']:
                coin_p7(session, bidsmap, bidsfolder, personals)

            # Update / append the nifti mapping
            if bidsmap['Nifti']:
                coin_nifti(session, bidsmap, bidsfolder, personals)

            # Update / append the file-system mapping
            if bidsmap['FileSystem']:
                coin_filesystem(session, bidsmap, bidsfolder, personals)

            # Update / append the plugin mapping
            if bidsmap['PlugIns']:
                coin_plugin(session, bidsmap, bidsfolder, personals)

        # Store the collected personals in the participant_table
        for key in personals:

            # participant_id is the index of the participants_table
            assert 'participant_id' in personals
            if key == 'participant_id':
                continue

            # TODO: Check that only values that are consistent over sessions go in the participants.tsv file, otherwise put them in a sessions.tsv file

            if key not in participants_dict:
                participants_dict[key]  = dict(LongName     = 'Long (unabbreviated) name of the column',
                                               Description  = 'Description of the the column',
                                               Levels       = dict(Key='Value (This is for categorical variables: a dictionary of possible values (keys) and their descriptions (values))'),
                                               Units        = 'Measurement units. [<prefix symbol>]<unit symbol> format following the SI standard is',
                                               TermURL      = 'URL pointing to a formal definition of this type of data in an ontology available on the web')
            participants_table.loc[personals['participant_id'], key] = personals[key]

    # Write the collected data to the participant files
    LOGGER.info('Writing subject data to: ' + participants_tsv)
    participants_table.to_csv(participants_tsv, sep='\t', encoding='utf-8', na_rep='n/a')

    LOGGER.info('Writing subject data dictionary to: ' + participants_json)
    with open(participants_json, 'w') as json_fid:
        json.dump(participants_dict, json_fid, indent=4)

    LOGGER.info('------------ FINISHED! ------------')
    LOGGER.info('')


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run bidscoiner(args)
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidscoiner.py /project/foo/raw /project/foo/bids\n'
                                            '  bidscoiner.py -f /project/foo/raw /project/foo/bids -p sub-009 sub-030\n ')
    parser.add_argument('sourcefolder',             help='The source folder containing the raw data in sub-#/[ses-#]/run format (or specify --subprefix and --sesprefix for different prefixes)')
    parser.add_argument('bidsfolder',               help='The destination / output folder with the bids data')
    parser.add_argument('-p','--participant_label', help='Space seperated list of selected sub-# names / folders to be processed (the sub- prefix can be removed). Otherwise all subjects in the sourcefolder will be selected', nargs='+')
    parser.add_argument('-f','--force',             help='If this flag is given subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped', action='store_true')
    parser.add_argument('-s','--skip_participants', help='If this flag is given those subjects that are in particpants.tsv will not be processed (also when the --force flag is given). Otherwise the participants.tsv table is ignored', action='store_true')
    parser.add_argument('-b','--bidsmap',           help='The bidsmap YAML-file with the study heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-n','--subprefix',         help="The prefix common for all the source subject-folders. Default: 'sub-'", default='sub-')
    parser.add_argument('-m','--sesprefix',         help="The prefix common for all the source session-folders. Default: 'ses-'", default='ses-')
    parser.add_argument('-v','--version',           help='Show the BIDS and BIDScoin version', action='version', version=f'BIDS-version:\t\t{bids.bidsversion()}\nBIDScoin-version:\t{bids.version()}')
    args = parser.parse_args()

    bidscoiner(rawfolder    = args.sourcefolder,
               bidsfolder   = args.bidsfolder,
               subjects     = args.participant_label,
               force        = args.force,
               participants = args.skip_participants,
               bidsmapfile  = args.bidsmap,
               subprefix    = args.subprefix,
               sesprefix    = args.sesprefix)
