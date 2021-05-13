"""
Contains the bidscoiner default plugin to convert the session DICOM and PAR/REC source-files into BIDS-valid nifti-files in the
corresponding bidsfolder and extract personals (e.g. Age, Sex) from the source header.

This plugin uses dcm2niix to do the conversion to nifti & json. This can sometimes lead to appended suffixes
to the filenames, which are automatically casted to the correct BIDS entities or, if that fails, appended
to the `acq` entity (e.g. "sub-01_acq-MEMPRAGE_T1w_E1.nii" becoming "sub-01_acq-MEMPRAGEe1_T1w.nii")
"""

import logging
import dateutil.parser
import pandas as pd
import json
from pathlib import Path
try:
    from bidscoin import bidscoin, bids, physio
except ImportError:
    import bidscoin, bids, physio     # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger(__name__)


def test(options) -> bool:
    """
    Performs shell tests dcm2niix

    :return:        True if the tool generated the expected result, False if there was a tool error, None if not tested
    """

    LOGGER.info('Testing the dcm2niix installation:')

    if 'path' not in options:
        LOGGER.error(f"The expected 'path' key is not defined in the dcm2niix2bids options")
    if 'args' not in options:
        LOGGER.error(f"The expected 'args' key is not defined in the dcm2niix2bids options")

    command = f"{options.get('path')}dcm2niix -u"

    return bidscoin.run_command(command)


def bidscoiner_plugin(session: Path, bidsmap: dict, bidsfolder: Path, personals: dict, subprefix: str, sesprefix: str) -> None:
    """
    The bidscoiner plugin to convert the session DICOM and PAR/REC source-files into BIDS-valid nifti-files in the
    corresponding bidsfolder and extract personals (e.g. Age, Sex) from the source header

    :param session:     The full-path name of the subject/session source file/folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :param personals:   The dictionary with the personal information
    :param subprefix:   The prefix common for all source subject-folders
    :param sesprefix:   The prefix common for all source session-folders
    :return:            Nothing
    """

    # See what dataformat we have
    dataformat = bids.get_dataformat(session)

    # Get valid BIDS subject/session identifiers from the (first) DICOM- or PAR/XML source file
    sourcefile   = Path()
    manufacturer = 'UNKNOWN'
    if dataformat == 'DICOM':
        sources = bidscoin.lsdirs(session)
        for source in sources:
            sourcefile = bids.get_dicomfile(source)
            if sourcefile.name:
                manufacturer = bids.get_dicomfield('Manufacturer', sourcefile)
                break
        if not sourcefile.name:
            LOGGER.info(f"No data found in: {session}")
            return

    elif dataformat == 'PAR':
        sources = bids.get_parfiles(session)
        if sources:
            sourcefile   = sources[0]
            manufacturer = 'Philips Medical Systems'
        else:
            LOGGER.info(f"No data found in: {session}")
            return

    else:
        LOGGER.info(f"Session {session} cannot be processed by {__name__}")
        return

    subid, sesid = bids.get_subid_sesid(sourcefile,
                                        bidsmap[dataformat]['subject'],
                                        bidsmap[dataformat]['session'],
                                        subprefix, sesprefix)

    if subid == subprefix:
        LOGGER.error(f"No valid subject identifier found for: {session}")
        return

    # Create the BIDS session-folder and a scans.tsv file
    bidsses = bidsfolder/subid/sesid
    if bidsses.is_dir():
        LOGGER.warning(f"Existing BIDS output-directory found, which may result in duplicate data (with increased run-index). Make sure {bidsses} was cleaned-up from old data before (re)running the bidscoiner")
    bidsses.mkdir(parents=True, exist_ok=True)
    scans_tsv = bidsses/f"{subid}{bids.add_prefix('_',sesid)}_scans.tsv"
    if scans_tsv.is_file():
        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
    else:
        scans_table = pd.DataFrame(columns=['acq_time'], dtype='str')
        scans_table.index.name = 'filename'

    # Process all the source files or run subfolders
    for source in sources:

        # Get a source-file
        if dataformat == 'DICOM':
            sourcefile = bids.get_dicomfile(source)
        elif dataformat == 'PAR':
            sourcefile = source
        if not sourcefile.name:
            continue

        # Get a matching run from the bidsmap
        run, datatype, index = bids.get_matching_run(sourcefile, bidsmap, dataformat)

        # Check if we should ignore this run
        if datatype == bids.ignoredatatype:
            LOGGER.info(f"Leaving out: {source}")
            continue

        # Check if we already know this run
        if index is None:
            LOGGER.error(f"Skipping unknown '{datatype}' run: {sourcefile}\n-> Re-run the bidsmapper and delete {bidsses} to solve this warning")
            continue

        LOGGER.info(f"Processing: {source}")

        # Create the BIDS session/datatype output folder
        if run['bids']['suffix'] in bids.get_derivatives(datatype):
            outfolder = bidsfolder/'derivatives'/manufacturer.replace(' ','')/subid/sesid/datatype
        else:
            outfolder = bidsses/datatype
        outfolder.mkdir(parents=True, exist_ok=True)

        # Compose the BIDS filename using the matched run
        bidsname  = bids.get_bidsname(subid, sesid, run, runtime=True)
        runindex  = run['bids'].get('run', '')
        if runindex.startswith('<<') and runindex.endswith('>>'):
            bidsname = bids.increment_runindex(outfolder, bidsname)
        jsonfiles = [(outfolder/bidsname).with_suffix('.json')]      # List -> Collect the associated json-files (for updating them later) -- possibly > 1

        # Check if file already exists (-> e.g. when a static runindex is used)
        if (outfolder/bidsname).with_suffix('.json').is_file():
            LOGGER.warning(f"{outfolder/bidsname}.* already exists and will be deleted -- check your results carefully!")
            for ext in ('.nii.gz', '.nii', '.json', '.bval', '.bvec', '.tsv.gz'):
                (outfolder/bidsname).with_suffix(ext).unlink(missing_ok=True)

        # Convert physiological log files (dcm2niix can't handle these)
        if run['bids']['suffix'] == 'physio':
            if bids.get_dicomfile(source, 2).name:
                LOGGER.warning(f"Found > 1 DICOM file in {source}, using: {sourcefile}")
            physiodata = physio.readphysio(sourcefile)
            physio.physio2tsv(physiodata, outfolder/bidsname)

        # Convert the source-files in the run folder to nifti's in the BIDS-folder
        else:
            command = '{path}dcm2niix {args} -f "{filename}" -o "{outfolder}" "{source}"'.format(
                path      = bidsmap['Options']['plugins']['dcm2niix2bids'].get('path',''),
                args      = bidsmap['Options']['plugins']['dcm2niix2bids'].get('args',''),
                filename  = bidsname,
                outfolder = outfolder,
                source    = source)
            if not bidscoin.run_command(command):
                continue

            # Replace uncropped output image with the cropped one
            if '-x y' in bidsmap['Options']['plugins']['dcm2niix2bids']['args']:
                for dcm2niixfile in sorted(outfolder.glob(bidsname + '*_Crop_*')):                              # e.g. *_Crop_1.nii.gz
                    ext         = ''.join(dcm2niixfile.suffixes)
                    newbidsfile = str(dcm2niixfile).rsplit(ext,1)[0].rsplit('_Crop_',1)[0] + ext
                    LOGGER.info(f"Found dcm2niix _Crop_ postfix, replacing original file\n{dcm2niixfile} ->\n{newbidsfile}")
                    dcm2niixfile.replace(newbidsfile)

            # Rename all files that got additional postfixes from dcm2niix. See: https://github.com/rordenlab/dcm2niix/blob/master/FILENAMING.md
            dcm2niixpostfixes = ('_c', '_i', '_Eq', '_real', '_imaginary', '_MoCo', '_t', '_Tilt', '_e', '_ph')
            dcm2niixfiles     = sorted(set([dcm2niixfile for dcm2niixpostfix in dcm2niixpostfixes for dcm2niixfile in outfolder.glob(f"{bidsname}*{dcm2niixpostfix}*.nii*")]))
            for dcm2niixfile in dcm2niixfiles:
                ext         = ''.join(dcm2niixfile.suffixes)
                postfixes   = str(dcm2niixfile).split(bidsname)[1].rsplit(ext)[0].split('_')[1:]
                newbidsname = dcm2niixfile.name                                                                 # Strip the additional postfixes and assign them to bids entities in the for-loop below
                for postfix in postfixes:                                                                       # dcm2niix postfixes _c%d, _e%d and _ph (and any combination of these in that order) are for multi-coil data, multi-echo data and phase data

                    # Patch the echo entity in the newbidsname with the dcm2niix echo info                      # NB: We can't rely on the bids-entity info here because manufacturers can e.g. put multiple echos in one series / run-folder
                    if 'echo' in run['bids'] and postfix.startswith('e'):
                        echonr = f"_{postfix}".replace('_e','')                                                 # E.g. postfix='e1'
                        if not echonr:
                            echonr = '1'
                        if echonr.isalpha():
                            LOGGER.error(f"Unexpected postix '{postfix}' found in {dcm2niixfile}")
                            newbidsname = bids.get_bidsvalue(newbidsname, 'dummy', postfix)                     # Append the unknown postfix to the acq-label
                        else:
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'echo', str(int(echonr)))         # In contrast to other labels, run and echo labels MUST be integers. Those labels MAY include zero padding, but this is NOT RECOMMENDED to maintain their uniqueness

                    # Patch the phase entity in the newbidsname with the dcm2niix mag/phase info
                    elif 'part' in run['bids'] and postfix in ('ph','real','imaginary'):                        # e.g. part: ['', 'mag', 'phase', 'real', 'imag', 0]
                        if postfix == 'ph':
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'part', 'phase')
                        if postfix == 'real':
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'part', 'real')
                        if postfix == 'imaginary':
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'part', 'imag')

                    # Patch fieldmap images (NB: datatype=='fmap' is too broad, see the fmap.yaml file)
                    elif run['bids']['suffix'] in bids.bidsdatatypes['fmap'][0]['suffixes']:                    # i.e. in ('magnitude','magnitude1','magnitude2','phase1','phase2','phasediff','fieldmap'). TODO: Make this robust for future BIDS versions
                        if len(dcm2niixfiles) not in (1, 2, 3, 4):                                              # Phase / echo data may be stored in the same data source / run folder
                            LOGGER.debug(f"Unknown fieldmap {outfolder/bidsname} for '{postfix}'")
                        newbidsname = newbidsname.replace('_magnitude1a',    '_magnitude2')                     # First catch this potential weird / rare case
                        newbidsname = newbidsname.replace('_magnitude1_pha', '_phase2')                         # First catch this potential weird / rare case
                        newbidsname = newbidsname.replace('_magnitude1_e1',  '_magnitude1')                     # Case 2 = Two phase and magnitude images
                        newbidsname = newbidsname.replace('_magnitude1_e2',  '_magnitude2')                     # Case 2: This can happen when the e2 image is stored in the same directory as the e1 image, but with the e2 listed first
                        newbidsname = newbidsname.replace('_magnitude2_e1',  '_magnitude1')                     # Case 2: This can happen when the e2 image is stored in the same directory as the e1 image, but with the e2 listed first
                        newbidsname = newbidsname.replace('_magnitude2_e2',  '_magnitude2')                     # Case 2
                        if len(dcm2niixfiles) in (2,3):                                                         # Case 1 = One or two magnitude + one phasediff image
                            newbidsname = newbidsname.replace('_magnitude1_ph', '_phasediff')
                            newbidsname = newbidsname.replace('_magnitude2_ph', '_phasediff')
                        newbidsname = newbidsname.replace('_phasediff_e1',   '_phasediff')                      # Case 1
                        newbidsname = newbidsname.replace('_phasediff_e2',   '_phasediff')                      # Case 1
                        newbidsname = newbidsname.replace('_phasediff_ph',   '_phasediff')                      # Case 1
                        newbidsname = newbidsname.replace('_magnitude1_ph',  '_phase1')                         # Case 2: One or two magnitude and phase images in one folder / datasource
                        newbidsname = newbidsname.replace('_magnitude2_ph',  '_phase2')                         # Case 2: Two magnitude + two phase images in one folder / datasource
                        newbidsname = newbidsname.replace('_phase1_e1',      '_phase1')                         # Case 2
                        newbidsname = newbidsname.replace('_phase1_e2',      '_phase2')                         # Case 2: This can happen when the e2 image is stored in the same directory as the e1 image, but with the e2 listed first
                        newbidsname = newbidsname.replace('_phase2_e1',      '_phase1')                         # Case 2: This can happen when the e2 image is stored in the same directory as the e1 image, but with the e2 listed first
                        newbidsname = newbidsname.replace('_phase2_e2',      '_phase2')                         # Case 2
                        newbidsname = newbidsname.replace('_phase1_ph',      '_phase1')                         # Case 2: One or two magnitude and phase images in one folder / datasource
                        newbidsname = newbidsname.replace('_phase2_ph',      '_phase2')                         # Case 2: Two magnitude + two phase images in one folder / datasource
                        newbidsname = newbidsname.replace('_magnitude_e1',   '_magnitude')                      # Case 3 = One magnitude + one fieldmap image
                        if len(dcm2niixfiles) == 2:
                            newbidsname = newbidsname.replace('_fieldmap_e1', '_magnitude')                     # Case 3: One magnitude + one fieldmap image in one folder / datasource
                        newbidsname = newbidsname.replace('_fieldmap_e1',    '_fieldmap')                       # Case 3
                        newbidsname = newbidsname.replace('_magnitude_ph',   '_fieldmap')                       # Case 3: One magnitude + one fieldmap image in one folder / datasource
                        newbidsname = newbidsname.replace('_fieldmap_ph',    '_fieldmap')                       # Case 3

                    # Append the dcm2niix info to acq-label, may need to be improved / elaborated for future BIDS standards, supporting multi-coil data
                    else:
                        newbidsname = bids.get_bidsvalue(newbidsname, 'dummy', postfix)

                    # Remove the added postfix from the new bidsname
                    newbidsname = newbidsname.replace(f"_{postfix}_",'_')                                       # If it is not last
                    newbidsname = newbidsname.replace(f"_{postfix}.",'.')                                       # If it is last

                # Save the nifti file with a new name
                if runindex.startswith('<<') and runindex.endswith('>>'):
                    newbidsname = bids.increment_runindex(outfolder, newbidsname, '')                           # Update the runindex now that the acq-label has changed
                newbidsfile = outfolder/newbidsname
                LOGGER.info(f"Found dcm2niix {postfixes} postfixes, renaming\n{dcm2niixfile} ->\n{newbidsfile}")
                if newbidsfile.is_file():
                    LOGGER.warning(f"Overwriting existing {newbidsfile} file -- check your results carefully!")
                dcm2niixfile.replace(newbidsfile)

                # Rename all associated files (i.e. the json-, bval- and bvec-files)
                oldjsonfile = dcm2niixfile.with_suffix('').with_suffix('.json')
                newjsonfile = newbidsfile.with_suffix('').with_suffix('.json')
                if not oldjsonfile.is_file():
                    LOGGER.warning(f"Unexpected file conversion result: {oldjsonfile} not found")
                else:
                    if oldjsonfile in jsonfiles:
                        jsonfiles.remove(oldjsonfile)
                    if newjsonfile not in jsonfiles:
                        jsonfiles.append(newjsonfile)
                for oldfile in outfolder.glob(dcm2niixfile.with_suffix('').stem + '.*'):
                    oldfile.replace(newjsonfile.with_suffix(''.join(oldfile.suffixes)))

        # Loop over and adapt all the newly produced json files and write to the scans.tsv file (NB: assumes every nifti-file comes with a json-file)
        for jsonfile in sorted(set(jsonfiles)):

            # Add a dummy b0 bval- and bvec-file for any file without a bval/bvec file (e.g. sbref, b0 scans)
            if datatype == 'dwi':
                bvecfile = jsonfile.with_suffix('.bvec')
                bvalfile = jsonfile.with_suffix('.bval')
                if not bvecfile.is_file():
                    LOGGER.info(f"Adding dummy bvec file: {bvecfile}")
                    bvecfile.write_text('0\n0\n0\n')
                if not bvalfile.is_file():
                    LOGGER.info(f"Adding dummy bval file: {bvalfile}")
                    bvalfile.write_text('0\n')

            # Load the json meta-data
            with jsonfile.open('r') as json_fid:
                jsondata = json.load(json_fid)

            # Add the TaskName to the meta-data
            if datatype == 'func' and 'TaskName' not in jsondata:
                jsondata['TaskName'] = run['bids']['task']

            # Add the TracerName and TaskName to the meta-data
            elif datatype == 'pet' and 'TracerName' not in jsondata:
                jsondata['TracerName'] = run['bids']['trc']

            # Add all the meta data to the json-file
            for metakey, metaval in run['meta'].items():
                metaval = bids.get_dynamicvalue(metaval, sourcefile, cleanup=False, runtime=True)
                LOGGER.info(f"Adding '{metakey}: {metaval}' to: {jsonfile}")
                jsondata[metakey] = metaval
            with jsonfile.open('w') as json_fid:
                json.dump(jsondata, json_fid, indent=4)

            # Parse the acquisition time from the json file or else from the source header (NB: assuming the source file represents the first acquisition)
            outputfile = [file for file in jsonfile.parent.glob(jsonfile.stem + '.*') if file.suffix in ('.nii','.gz')]     # Find the corresponding nifti/tsv.gz file (there should be only one, let's not make assumptions about the .gz extension)
            if not outputfile:
                LOGGER.exception(f"No data-file found with {jsonfile} when updating {scans_tsv}")
            elif datatype not in bidsmap['Options']['bidscoin']['bidsignore'] and not run['bids']['suffix'] in bids.get_derivatives(datatype):
                if 'AcquisitionTime' not in jsondata or not jsondata['AcquisitionTime']:
                    jsondata['AcquisitionTime'] = bids.get_sourcevalue('AcquisitionTime', sourcefile)       # DICOM
                if not jsondata['AcquisitionTime']:
                    jsondata['AcquisitionTime'] = bids.get_sourcevalue('exam_date', sourcefile)             # PAR/XML
                try:
                    acq_time = dateutil.parser.parse(jsondata['AcquisitionTime'])
                    acq_time = '1925-01-01T' + acq_time.strftime('%H:%M:%S')                                # Privacy protection (see BIDS specification)
                except Exception as jsonerror:
                    LOGGER.warning(f"Could not parse the acquisition time from: {sourcefile}\n{jsonerror}")
                    acq_time = 'n/a'
                scanpath = outputfile[0].relative_to(bidsses)
                scans_table.loc[scanpath.as_posix(), 'acq_time'] = acq_time

    # Write the scans_table to disk
    LOGGER.info(f"Writing acquisition time data to: {scans_tsv}")
    scans_table.sort_values(by=['acq_time','filename'], inplace=True)
    scans_table.to_csv(scans_tsv, sep='\t', encoding='utf-8')

    # Add IntendedFor search results and TE1+TE2 meta-data to the fieldmap json-files. This has been postponed until all datatypes have been processed (i.e. so that all target images are indeed on disk)
    if (bidsses/'fmap').is_dir():
        for jsonfile in sorted((bidsses/'fmap').glob('sub-*.json')):

            # Load the existing meta-data
            with jsonfile.open('r') as json_fid:
                jsondata = json.load(json_fid)

            # Search for the imaging files that match the IntendedFor search criteria
            niifiles    = []
            intendedfor = jsondata.get('IntendedFor')
            if intendedfor:
                # Search with multiple patterns in all runs and store the relative path to the subject folder
                if intendedfor.startswith('<') and intendedfor.endswith('>'):
                    intendedfor = intendedfor[1:-1].split('><')                 # NB: The outer <> brackets have been stripped of by get_dynamicvalue(runtime=True) above
                elif not isinstance(intendedfor, list):
                    intendedfor = [intendedfor]
                for selector in intendedfor:
                    niifiles.extend([Path(niifile).relative_to(bidsfolder/subid) for niifile in sorted(bidsses.rglob(f"*{selector}*.nii*")) if selector])

                # Add the IntendedFor data
                if niifiles:
                    LOGGER.info(f"Adding IntendedFor to: {jsonfile}")
                    jsondata['IntendedFor'] = [niifile.as_posix() for niifile in niifiles]  # The path needs to use forward slashes instead of backward slashes
                else:
                    LOGGER.warning(f"Empty 'IntendedFor' fieldmap value in {jsonfile}: the search for {intendedfor} gave no results")
                    jsondata['IntendedFor'] = ''
            else:
                LOGGER.warning(f"Empty 'IntendedFor' fieldmap value in {jsonfile}: the IntendedFor value of the bidsmap entry was empty")

            # Extract the echo times from magnitude1 and magnitude2 and add them to the phasediff json-file
            if jsonfile.name.endswith('phasediff.json'):
                json_magnitude = [None, None]
                echotime       = [None, None]
                for n in (0,1):
                    json_magnitude[n] = jsonfile.parent/jsonfile.name.replace('_phasediff', f"_magnitude{n+1}")
                    if not json_magnitude[n].is_file():
                        LOGGER.error(f"Could not find expected magnitude{n+1} image associated with: {jsonfile}")
                    else:
                        with json_magnitude[n].open('r') as json_fid:
                            data = json.load(json_fid)
                        echotime[n] = data['EchoTime']
                jsondata['EchoTime1'] = jsondata['EchoTime2'] = None
                if None in echotime:
                    LOGGER.error(f"Cannot find and add valid EchoTime1={echotime[0]} and EchoTime2={echotime[1]} data to: {jsonfile}")
                elif echotime[0] > echotime[1]:
                    LOGGER.error(f"Found invalid EchoTime1={echotime[0]} > EchoTime2={echotime[1]} for: {jsonfile}")
                else:
                    jsondata['EchoTime1'] = echotime[0]
                    jsondata['EchoTime2'] = echotime[1]
                    LOGGER.info(f"Adding EchoTime1: {echotime[0]} and EchoTime2: {echotime[1]} to {jsonfile}")

            # Save the collected meta-data to disk
            with jsonfile.open('w') as json_fid:
                json.dump(jsondata, json_fid, indent=4)

    # Collect personal data from a source header (PAR/XML does not contain personal info)
    if dataformat=='DICOM' and sourcefile.name:
        personals['participant_id'] = subid
        if sesid:
            if 'session_id' not in personals:
                personals['session_id'] = sesid
            else:
                return                                              # Only take data from the first session -> BIDS specification
        age = bids.get_dicomfield('PatientAge', sourcefile)         # A string of characters with one of the following formats: nnnD, nnnW, nnnM, nnnY
        if age.endswith('D'):
            personals['age'] = str(int(float(age.rstrip('D'))/365.2524))
        elif age.endswith('W'):
            personals['age'] = str(int(float(age.rstrip('W'))/52.1775))
        elif age.endswith('M'):
            personals['age'] = str(int(float(age.rstrip('M'))/12))
        elif age.endswith('Y'):
            personals['age'] = str(int(float(age.rstrip('Y'))))
        elif age:
            personals['age'] = age
        personals['sex']     = bids.get_dicomfield('PatientSex',    sourcefile)
        personals['size']    = bids.get_dicomfield('PatientSize',   sourcefile)
        personals['weight']  = bids.get_dicomfield('PatientWeight', sourcefile)
