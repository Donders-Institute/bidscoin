#!/usr/bin/env python
"""
Converts ("coins") datasets in the rawfolder to nifti / json / tsv datasets in the
bidsfolder according to the BIDS standard. Check and edit the bidsmap.yaml file to
your needs before running this function. Provenance, warnings and error messages are
stored in the ../bidsfolder/code/bidscoiner.log file
"""

import os
import glob
import pandas as pd
import subprocess
import json
import dateutil
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed


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
        bids.printlog('WARNING: No series subfolder(s) found in: ' + session, LOG)
        return

    TE = [None, None]

    # Get a valid BIDS subject identifier from the (first) dicom-header or from the session source folder
    if bidsmap['DICOM']['participant_label'] and bidsmap['DICOM']['participant_label'].startswith('<<') and bidsmap['DICOM']['participant_label'].endswith('>>'):
        subid = bids.get_dicomfield(bidsmap['DICOM']['participant_label'][2:-2], bids.get_dicomfile(bids.lsdirs(session)[0]))
    elif bidsmap['DICOM']['participant_label']:
        subid = bidsmap['DICOM']['participant_label']
    else:
        subid = session.rsplit(os.sep + subprefix, 1)[1].split(os.sep + sesprefix, 1)[0]
    subid = 'sub-' + bids.cleanup_label(subid.lstrip(subprefix))
    if subid == subprefix:
        bids.printlog('Error: No valid subject identifier found for: ' + session, LOG)
        return

    # Get a valid or empty BIDS session identifier from the (first) dicom-header or from the session source folder
    if bidsmap['DICOM']['session_label'] and bidsmap['DICOM']['session_label'].startswith('<<') and bidsmap['DICOM']['session_label'].endswith('>>'):
        sesid = bids.get_dicomfield(bidsmap['DICOM']['session_label'][2:-2], bids.get_dicomfile(bids.lsdirs(session)[0]))
    elif bidsmap['DICOM']['session_label']:
        sesid = bidsmap['DICOM']['session_label']
    elif os.sep + sesprefix in session:
        sesid = session.rsplit(os.sep + sesprefix)[1]
    else:
        sesid = ''
    if sesid:
        sesid = 'ses-' + bids.cleanup_label(sesid.lstrip(sesprefix))

    # Create the BIDS session-folder and a scans.tsv file
    bidsses = os.path.join(bidsfolder, subid, sesid)         # NB: This gives a trailing '/' if ses=='', but that should be ok
    os.makedirs(bidsses, exist_ok=True)
    scans_tsv = os.path.join(bidsses, f'{subid}{bids.add_prefix("_",sesid)}_scans.tsv')
    if os.path.exists(scans_tsv):
        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
    else:
        scans_table = pd.DataFrame(columns=['acq_time'], dtype='str')
        scans_table.index.name = 'filename'

    # Process all the dicom series subfolders
    for series in bids.lsdirs(session):

        if series.startswith('.'):
            bids.printlog('Ignoring hidden dicom-folder: ' + series, LOG)
            continue
        else:
            bids.printlog('Processing dicom-folder: ' + series, LOG)

        # Get the cleaned-up bids labels from a dicom-file and bidsmap
        dicomfile = bids.get_dicomfile(series)
        if not dicomfile: continue
        result    = bids.get_matching_dicomseries(dicomfile, bidsmap)
        series_   = result['series']
        modality  = result['modality']

        # Create the BIDS session/modality folder
        bidsmodality = os.path.join(bidsses, modality)
        os.makedirs(bidsmodality, exist_ok=True)

        # Compose the BIDS filename using the bids labels and run-index
        runindex = series_['bids']['run_index']
        if runindex.startswith('<<') and runindex.endswith('>>'):
            bidsname = bids.get_bidsname(subid, sesid, modality, series_, runindex[2:-2])
            bidsname = bids.increment_runindex(bidsmodality, bidsname)
        else:
            bidsname = bids.get_bidsname(subid, sesid, modality, series_, runindex)

        # Convert the dicom-files in the series folder to nifti's in the BIDS-folder
        command = '{path}dcm2niix {args} -f "{filename}" -o "{outfolder}" "{infolder}"'.format(
            path      = bidsmap['Options']['dcm2niix']['path'],
            args      = bidsmap['Options']['dcm2niix']['args'],
            filename  = bidsname,
            outfolder = bidsmodality,
            infolder  = series)
        bids.printlog('$ ' + command, LOG)
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)         # TODO: investigate shell=False and capture_output=True
        bids.printlog(process.stdout.decode('utf-8'), LOG)
        if process.returncode != 0:
            errormsg = f'Error: Failed to process {series} (errorcode {process.returncode})'
            bids.printlog(errormsg, LOG)
            continue

        # Replace uncropped output image with the cropped one
        if '-x y' in bidsmap['Options']['dcm2niix']['args']:
            for filename in sorted(glob.glob(os.path.join(bidsmodality, bidsname + '*_Crop_*'))):
                basepath, ext1 = os.path.splitext(filename)
                basepath, ext2 = os.path.splitext(basepath)                                                    # Account for .nii.gz files
                basepath       = basepath.rsplit('_Crop_',1)[0]
                newfilename    = basepath + ext2 + ext1
                bids.printlog(f'Found dcm2niix _Crop_ suffix, replacing original file\n{filename} ->\n{newfilename}', LOG)
                os.replace(filename, newfilename)

        # Rename all files ending with _c%d, _e%d and _ph (and any combination of these): These are produced by dcm2niix for multi-coil data, multi-echo data and phase data, respectively
        jsonfiles = []                                                                                          # Collect the associated json-files (for updating them later) -- possibly > 1
        for suffix in ('_c', '_e', '_ph', '_i'):
            for filename in sorted(glob.glob(os.path.join(bidsmodality, bidsname + suffix + '*'))):
                basepath, ext1  = os.path.splitext(filename)
                basepath, ext2  = os.path.splitext(basepath)                                                    # Account for .nii.gz files
                basepath, index = basepath.rsplit(suffix,1)
                index           = index.split('_')[0].zfill(2)                                                  # Zero padd as specified in the BIDS-standard (assuming two digits is sufficient); strip following suffices (fieldmaps produce *_e2_ph files)

                # This is a special hack: dcm2niix does not always add a _c/_e suffix for the first(?) coil/echo image -> add it when we encounter a **_e2/_c2 file
                if suffix in ('_c','_e') and int(index)==2 and basepath.rsplit('_',1)[1] != 'magnitude1':       # For fieldmaps: *_magnitude1_e[index] -> *_magnitude[index] (This is handled below)
                    filename_ce = basepath + ext2 + ext1                                                        # The file without the _c1/_e1 suffix
                    if suffix=='_e' and bids.set_bidslabel(basepath, 'echo'):
                        newbasepath_ce = bids.set_bidslabel(basepath, 'echo', '1')
                    else:
                        newbasepath_ce = bids.set_bidslabel(basepath, 'dummy', suffix.upper() + '1'.zfill(len(index)))  # --> append to acq-label, may need to be elaborated for future BIDS standards, supporting multi-coil data
                    newfilename_ce = newbasepath_ce + ext2 + ext1                                               # The file as it should have been
                    if os.path.isfile(filename_ce):
                        if filename_ce != newfilename_ce:
                            bids.printlog(f'Found no dcm2niix {suffix} suffix for image instance 1, renaming\n{filename_ce} ->\n{newfilename_ce}', LOG)
                            os.rename(filename_ce, newfilename_ce)
                        if ext1=='.json':
                            jsonfiles.append(newbasepath_ce + '.json')

                # Patch the basepath with the suffix info
                if suffix=='_e' and bids.set_bidslabel(basepath, 'echo') and index:
                    basepath = bids.set_bidslabel(basepath, 'echo', str(int(index)))                            # In contrast to other labels, run and echo labels MUST be integers. Those labels MAY include zero padding, but this is NOT RECOMMENDED to maintain their uniqueness

                elif suffix=='_e' and basepath.rsplit('_',1)[1] in ('magnitude1','magnitude2') and index:       # i.e. modality == 'fmap'
                    basepath = basepath[0:-1] + str(int(index))                                                 # basepath: *_magnitude1_e[index] -> *_magnitude[index]
                    # Read the echo times that need to be added to the json-file (see below)
                    if os.path.splitext(filename)[1] == '.json':
                        with open(filename, 'r') as json_fid:
                            data = json.load(json_fid)
                        TE[int(index)-1] = data['EchoTime']
                        bids.printlog(f"Reading EchoTime{index} = {data['EchoTime']} from: {filename}", LOG)
                elif suffix=='_e' and basepath.rsplit('_',1)[1]=='phasediff' and index:                         # i.e. modality == 'fmap'
                    pass

                elif suffix=='_ph' and basepath.rsplit('_',1)[1] in ['phase1','phase2'] and index:              # i.e. modality == 'fmap' (TODO: untested)
                    basepath = basepath[0:-1] + str(int(index))                                                 # basepath: *_phase1_e[index] -> *_phase[index]
                    bids.printlog('WARNING: Untested dcm2niix "_ph"-filetype: ' + basepath, LOG)

                else:
                    basepath = bids.set_bidslabel(basepath, 'dummy', suffix.upper() + index)                    # --> append to acq-label, may need to be elaborated for future BIDS standards, supporting multi-coil data

                # Save the file with a new name
                if runindex.startswith('<<') and runindex.endswith('>>'):
                    newbidsname = bids.increment_runindex(bidsmodality, os.path.basename(basepath), ext2 + ext1)  # Update the runindex now that the acq-label has changed
                else:
                    newbidsname = os.path.basename(basepath)
                newfilename = os.path.join(bidsmodality, newbidsname + ext2 + ext1)
                bids.printlog(f'Found dcm2niix {suffix} suffix, renaming\n{filename} ->\n{newfilename}', LOG)
                os.rename(filename, newfilename)
                if ext1 == '.json':
                    jsonfiles.append(os.path.join(bidsmodality, newbidsname + '.json'))

        # Loop over and adapt all the newly produced json files and write to the scans.tsv file (every nifti-file comes with a json-file)
        if not jsonfiles:
            jsonfiles = [os.path.join(bidsmodality, bidsname + '.json')]
        for jsonfile in set(jsonfiles):

            # Check if dcm2niix behaved as expected
            if not os.path.isfile(jsonfile):
                bids.printlog(f'WARNING: Unexpected file conversion result: {jsonfile} not found', LOG)
                continue

            # Add a dummy b0 bval- and bvec-file for any file without a bval/bvec file (e.g. sbref, b0 scans)
            if modality == 'dwi':
                bvecfile = os.path.splitext(jsonfile)[0] + '.bvec'
                bvalfile = os.path.splitext(jsonfile)[0] + '.bval'
                if not os.path.isfile(bvecfile):
                    bids.printlog('Adding dummy bvec file: ' + bvecfile, LOG)
                    with open(bvecfile, 'w') as bvec_fid:
                        bvec_fid.write('0\n0\n0\n')
                if not os.path.isfile(bvalfile):
                    bids.printlog('Adding dummy bval file: ' + bvalfile, LOG)
                    with open(bvalfile, 'w') as bval_fid:
                        bval_fid.write('0\n')

            # Add the TaskName to the func json-file
            elif modality == 'func':
                with open(jsonfile, 'r') as json_fid:
                    data = json.load(json_fid)
                if not 'TaskName' in data:
                    bids.printlog('Adding TaskName to: ' + jsonfile, LOG)
                    data['TaskName'] = series_['bids']['task_label']
                    with open(jsonfile, 'w') as json_fid:
                        json.dump(data, json_fid, indent=4)

            # Add the EchoTime(s) used to create the difference image to the fmap json-file. NB: This assumes the magnitude series have already been parsed (i.e. their nifti's had an _e suffix) -- This is normally the case for Siemens (phase-series being saved after the magnitude series
            elif modality == 'fmap':
                if series_['bids']['suffix'] == 'phasediff':
                    bids.printlog('Adding EchoTime1 and EchoTime2 to: ' + jsonfile, LOG)
                    with open(jsonfile, 'r') as json_fid:
                        data = json.load(json_fid)
                    data['EchoTime1'] = TE[0]
                    data['EchoTime2'] = TE[1]
                    with open(jsonfile, 'w') as json_fid:
                        json.dump(data, json_fid, indent=4)
                    if TE[0]>TE[1]:
                        bids.printlog('WARNING: EchoTime1 > EchoTime2 in: ' + jsonfile, LOG)

            # Parse the acquisition time from the json file
            with open(jsonfile, 'r') as json_fid:
                data = json.load(json_fid)
            acq_time = dateutil.parser.parse(data['AcquisitionTime'])
            niipath  = glob.glob(os.path.splitext(jsonfile)[0] + '.nii*')[0]    # Find the corresponding nifti file (there should be only one, let's not make assumptions about the .gz extension)
            niipath  = niipath.replace(bidsses+os.sep,'')                       # Use a relative path. Somehow .strip(bidsses) instead of replace(bidsses,'') does not work properly
            scans_table.loc[niipath, 'acq_time'] = '1900-01-01T' + acq_time.strftime('%H:%M:%S')

    # Write the scans_table to disk
    bids.printlog('Writing acquisition time data to: ' + scans_tsv, LOG)
    scans_table.to_csv(scans_tsv, sep='\t', encoding='utf-8')

    # Search for the IntendedFor images and add them to the json-files. This has been postponed untill all modalities have been processed (i.e. so that all target images are indeed on disk)
    if bidsmap['DICOM']['fmap'] is not None:
        for fieldmap in bidsmap['DICOM']['fmap']:
            if 'IntendedFor' in fieldmap['bids'] and fieldmap['bids']['IntendedFor']:
                bidsname = bids.get_bidsname(subid, sesid, 'fmap', fieldmap, '1')
                acqlabel = bids.set_bidslabel(bidsname, 'acq')
                for jsonfile in glob.glob(os.path.join(bidsses, 'fmap', bidsname.replace('_run-1_','_run-[0-9]*_').replace(acqlabel,acqlabel+'[CE][0-9]*') + '.json')):     # Account for multiple runs and dcm2niix suffixes inserted into the acquisition label

                    intendedfor = fieldmap['bids']['IntendedFor']
                    if intendedfor.startswith('<<') and intendedfor.endswith('>>'):
                        intendedfor = intendedfor[2:-2].split('><')
                    else:
                        intendedfor = [intendedfor]

                    niifiles = []
                    for selector in intendedfor:
                        niifiles.extend([niifile.split(os.sep+subid+os.sep, 1)[1].replace('\\','/') for niifile in sorted(glob.glob(os.path.join(bidsses, f'**{os.sep}*{selector}*.nii*')))])     # Search in all series using a relative path

                    with open(jsonfile, 'r') as json_fid:
                        data = json.load(json_fid)
                    data['IntendedFor'] = niifiles
                    bids.printlog('Adding IntendedFor to: ' + jsonfile, LOG)
                    with open(jsonfile, 'w') as json_fid:
                        json.dump(data, json_fid, indent=4)

                # Catch magnitude2 files produced by dcm2niix (i.e. magnitude1 & magnitude2 both in the same seriesfolder)
                if jsonfile.endswith('magnitude1.json'):
                    jsonfile2 = jsonfile.rsplit('1.json',1)[0] + '2.json'
                    if os.path.isfile(jsonfile2):

                        with open(jsonfile2, 'r') as json_fid:
                            data = json.load(json_fid)
                        if 'IntendedFor' not in data:
                            data['IntendedFor'] = niifiles
                            bids.printlog('Adding IntendedFor to: ' + jsonfile2, LOG)
                            with open(jsonfile2, 'w') as json_fid:
                                json.dump(data, json_fid, indent=4)

    # Collect personal data from the DICOM header
    dicomfile                   = bids.get_dicomfile(series)
    personals['participant_id'] = subid
    if sesid:
        personals['session_id'] = sesid
    personals['age']            = bids.get_dicomfield('PatientAge',    dicomfile)
    personals['sex']            = bids.get_dicomfield('PatientSex',    dicomfile)
    personals['size']           = bids.get_dicomfield('PatientSize',   dicomfile)
    personals['weight']         = bids.get_dicomfield('PatientWeight', dicomfile)


def coin_par(session: str, bidsmap: dict, bidsfolder: str, personals: dict) -> None:
    """

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    bids.printlog('coin_par is WIP!!!', LOG)


def coin_p7(session: str, bidsmap: dict, bidsfolder: str, personals: dict) -> None:
    """

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    bids.printlog('coin_p7 is WIP!!!', LOG)


def coin_nifti(session: str, bidsmap: dict, bidsfolder: str, personals: dict) -> None:
    """

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    bids.printlog('coin_nifti is WIP!!!', LOG)


def coin_filesystem(session: str, bidsmap: dict, bidsfolder: str, personals: dict) -> None:
    """

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    bids.printlog('coin_filesystem is WIP!!!', LOG)


def coin_plugin(session: str, bidsmap: dict, bidsfolder: str, personals: dict) -> None:
    """
    Run the plugin coiner to cast the series into the bids folder

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :return:            Nothing
    """

    # Import and run the plugin modules
    from importlib import util

    for plugin in bidsmap['PlugIn']:

        # Get the full path to the plugin-module
        if os.path.basename(plugin)==plugin:
            plugin = os.path.join(os.path.dirname(__file__), 'plugins', plugin)
        else:
            plugin = plugin
        plugin = os.path.abspath(os.path.expanduser(plugin))
        if not os.path.isfile(plugin):
            bids.printlog('WARNING: Could not find: ' + plugin, LOG)
            continue

        # Load and run the plugin-module
        spec   = util.spec_from_file_location('bidscoin_plugin', plugin)
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if 'bidscoiner_plugin' in dir(module):
            bids.printlog(f'Running: {plugin}.bidscoiner_plugin({session}, bidsmap, {bidsfolder}, personals)', LOG)
            module.bidscoiner_plugin(session, bidsmap, bidsfolder, personals, LOG)


def bidscoiner(rawfolder: str, bidsfolder: str, subjects: tuple=(), force: bool=False, participants: bool=False, bidsmapfile: str='code'+os.sep+'bidsmap.yaml', subprefix: str='sub-', sesprefix: str='ses-') -> None:
    """
    Main function that processes all the subjects and session in the rawfolder and uses the
    bidsmap.yaml file in bidsfolder/code to cast the data into the BIDS folder.

    :param rawfolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param subjects:        List of selected subjects / participants (i.e. sub-# names / folders) to be processed (the sub- prefix can be removed). Otherwise all subjects in the rawfolder will be selected
    :param force:           If True, subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped
    :param participants:    If True, subjects in particpants.tsv will not be processed (this could be used e.g. to protect these subjects from being reprocessed), also when force=True
    :param bidsmapfile:     The name of the bidsmap YAML-file. If the bidsmap pathname is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/
    :param subprefix:       The prefix common for all source subject-folders
    :param sesprefix:       The prefix common for all source session-folders
    :return:                Nothing
    """

    # Input checking & defaults
    global LOG
    rawfolder  = os.path.abspath(os.path.expanduser(rawfolder))
    bidsfolder = os.path.abspath(os.path.expanduser(bidsfolder))
    LOG        = os.path.join(bidsfolder, 'code', 'bidscoiner.log')

    # Create a code subfolder
    os.makedirs(os.path.join(bidsfolder,'code'), exist_ok=True)
    if not os.path.isfile(os.path.join(bidsfolder,'.bidsignore')):
        with open(os.path.join(bidsfolder,'.bidsignore'), 'w') as bidsignore:
            bidsignore.write(bids.unknownmodality + os.sep)

    # Start logging
    bids.printlog(f'------------ START BIDScoiner {bids.version()}: BIDS {bids.bidsversion()} ------------\n'
                  f'>>> bidscoiner rawfolder={rawfolder} bidsfolder={bidsfolder} subjects={subjects} force={force}'
                  f' participants={participants} bidsmap={bidsmapfile} subprefix={subprefix} sesprefix={sesprefix}', LOG)

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
        bids.printlog('Creating dataset description file: ' + dataset_file, LOG)
        with open(dataset_file, 'w') as fid:
            json.dump(dataset_description, fid, indent=4)

    # Create a README file if it does not exist
    readme_file = os.path.join(bidsfolder, 'README')
    if not os.path.isfile(readme_file):
        bids.printlog('Creating README file: ' + readme_file, LOG)
        with open(readme_file, 'w') as fid:
            fid.write('A free form text ( README ) describing the dataset in more details that SHOULD be provided')

    # Get the bidsmap heuristics from the bidsmap YAML-file
    bidsmap = bids.get_heuristics(bidsmapfile, os.path.join(bidsfolder,'code'), LOG)

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
            print(f'\n{"-" * 30}\nSkipping subject: {subject} ({n}/{len(subjects)})')
            continue

        print(f'\n{"-"*30}\nCoining subject: {subject} ({n}/{len(subjects)})')

        personals = dict()
        sessions  = bids.lsdirs(subject, sesprefix + '*')
        if not sessions:
            sessions = [subject]
        for session in sessions:

            # Check if we should skip the session-folder
            if not force and os.path.isdir(session.replace(rawfolder, bidsfolder)):
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
            if bidsmap['PlugIn']:
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
    bids.printlog('Writing subject data to: ' + participants_tsv, LOG)
    participants_table.to_csv(participants_tsv, sep='\t', encoding='utf-8', na_rep='n/a')

    bids.printlog('Writing subject data dictionary to: ' + participants_json, LOG)
    with open(participants_json, 'w') as json_fid:
        json.dump(participants_dict, json_fid, indent=4)

    bids.printlog('------------ FINISHED! ------------', LOG)


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run bidscoiner(args)
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidscoiner.py /project/raw /project/bids\n'
                                            '  bidscoiner.py -f /project/raw /project/bids -p sub-009 sub-030\n ')
    parser.add_argument('sourcefolder',             help='The source folder containing the raw data in sub-#/ses-#/series format')
    parser.add_argument('bidsfolder',               help='The destination folder with the bids data structure')
    parser.add_argument('-p','--participant_label', help='Space seperated list of selected sub-# names / folders to be processed (the sub- prefix can be removed). Otherwise all subjects in the sourcefolder will be selected', nargs='+')
    parser.add_argument('-f','--force',             help='If this flag is given subjects will be processed, regardless of existing folders in the bidsfolder. Otherwise existing folders will be skipped', action='store_true')
    parser.add_argument('-s','--skip_participants', help='If this flag is given those subjects that are in particpants.tsv will not be processed (also when the --force flag is given). Otherwise the participants.tsv table is ignored', action='store_true')
    parser.add_argument('-b','--bidsmap',           help='The bidsmap YAML-file with the study heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-n','--subprefix',         help="The prefix common for all the source subject-folders. Default: 'sub-'", default='sub-')
    parser.add_argument('-m','--sesprefix',         help="The prefix common for all the source session-folders. Default: 'ses-'", default='ses-')
    parser.add_argument('-v','--version',           help="Show the BIDS and BIDScoin version", action='version', version=f'BIDS-version:\t\t{bids.bidsversion()}\nBIDScoin-version:\t{bids.version()}')
    args = parser.parse_args()

    bidscoiner(rawfolder    = args.sourcefolder,
               bidsfolder   = args.bidsfolder,
               subjects     = args.participant_label,
               force        = args.force,
               participants = args.skip_participants,
               bidsmapfile  = args.bidsmap,
               subprefix    = args.subprefix,
               sesprefix    = args.sesprefix)
