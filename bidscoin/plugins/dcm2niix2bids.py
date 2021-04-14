"""
Contains the bidscoiner plugin to convert the session DICOM and PAR/REC source-files into BIDS-valid nifti-files in the
corresponding bidsfolder and extract personals (e.g. Age, Sex) from the source header
"""

import logging
import dateutil.parser
import pandas as pd
import json
from pathlib import Path
try:
    from bidscoin import bids, physio
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed
    import physio

LOGGER = logging.getLogger(__name__)


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
    if dataformat=='DICOM':
        sources = bids.lsdirs(session)
        for source in sources:
            sourcefile = bids.get_dicomfile(source)
            if sourcefile.name:
                manufacturer = bids.get_dicomfield('Manufacturer', sourcefile)
                break
        if not sourcefile.name:
            LOGGER.info(f"No data found in: {session}")
            return

    elif dataformat=='PAR':
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
        if dataformat=='DICOM':
            sourcefile = bids.get_dicomfile(source)
        elif dataformat=='PAR':
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
        bidsname  = bids.get_bidsname(subid, sesid, run)
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
                path      = bidsmap['Options']['dcm2niix']['path'],
                args      = bidsmap['Options']['dcm2niix']['args'],
                filename  = bidsname,
                outfolder = outfolder,
                source    = source)
            if not bids.run_command(command):
                continue

            # Replace uncropped output image with the cropped one
            if '-x y' in bidsmap['Options']['dcm2niix']['args']:
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
                    if 'echo' in run['bids'] and postfix.startswith(('e','ph')):
                        echonr = f"_{postfix}".replace('_e','').replace('_ph','')                               # E.g. postfix='e1' or postfix='pha'
                        if echonr.isalpha():
                            echonr = ord(echonr) - 95                                                           # dcm2niix adds an alphabetically ordered character if it outputs more than one image with the same name. Convert character to echo-number: '' -> 1, 'a'->2, etc
                        elif not echonr:
                            echonr = 1
                        newbidsname = bids.insert_bidskeyval(newbidsname, 'echo', str(echonr))                  # In contrast to other labels, run and echo labels MUST be integers. Those labels MAY include zero padding, but this is NOT RECOMMENDED to maintain their uniqueness

                    # Patch the phase entity in the newbidsname with the dcm2niix mag/phase info
                    elif 'part' in run['bids'] and postfix in ('ph','real','imaginary'):                        # e.g. part: ['', 'mag', 'phase', 'real', 'imag', 0]
                        if postfix=='ph':
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'part', 'phase')
                        if postfix=='real':
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'part', 'real')
                        if postfix=='imaginary':
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'part', 'imag')

                    # Patch fieldmap images (NB: datatype=='fmap' is too broad, see the fmap.yaml file)
                    elif run['bids']['suffix'] in ('magnitude','magnitude1','magnitude2','phase1','phase2','phasediff','fieldmap'):
                        if len(dcm2niixfiles) not in (0, 1, 2, 4, 6, 8):                                        # Phase / echo data may be stored in the same data source / run folder
                            LOGGER.debug(f"Unknown fieldmap {outfolder/bidsname} for '{postfix}'")
                        newbidsname = newbidsname.replace('_fieldmap_ph',    '_fieldmap')
                        newbidsname = newbidsname.replace('_magnitude_e1',   '_magnitude')
                        newbidsname = newbidsname.replace('_magnitude_ph',   '_fieldmap')
                        newbidsname = newbidsname.replace('_magnitude1_e1',  '_magnitude1')
                        newbidsname = newbidsname.replace('_magnitude2_e1',  '_magnitude1')                     # This can happen when the e2 image is stored in the same directory as the e1 image, but with the e2 listed first
                        newbidsname = newbidsname.replace('_magnitude1_e2',  '_magnitude2')
                        if len(dcm2niixfiles) == 8:
                            newbidsname = newbidsname.replace('_magnitude1_ph', '_phase1')                      # Two magnitude + 2 phase images in one folder / datasource
                        else:
                            newbidsname = newbidsname.replace('_magnitude1_ph', '_phasediff')                   # One or two magnitude + 1 phasediff image
                        newbidsname = newbidsname.replace('_magnitude1a',    '_magnitude2')
                        newbidsname = newbidsname.replace('_magnitude1_pha', '_phase2')
                        newbidsname = newbidsname.replace('_magnitude2_e2',  '_magnitude2')
                        newbidsname = newbidsname.replace('_magnitude2_ph',  '_phase2')
                        newbidsname = newbidsname.replace('_phase1_e1',      '_phase1')
                        newbidsname = newbidsname.replace('_phase2_e1',      '_phase1')                         # This can happen when the e2 image is stored in the same directory as the e1 image, but with the e2 listed first
                        newbidsname = newbidsname.replace('_phase1_ph',      '_phase1')
                        newbidsname = newbidsname.replace('_phase1_e2',      '_phase2')
                        newbidsname = newbidsname.replace('_phase2_e2',      '_phase2')
                        newbidsname = newbidsname.replace('_phase2_ph',      '_phase2')

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

            # Add the IntendedFor search data to the json-file (to be updated only after all session data is converted)
            if datatype == 'fmap':
                with jsonfile.open('r') as json_fid:
                    data = json.load(json_fid)
                data['IntendedFor'] = run['bids'].get('IntendedFor')
                with jsonfile.open('w') as json_fid:
                    json.dump(data, json_fid, indent=4)

            # Add a dummy b0 bval- and bvec-file for any file without a bval/bvec file (e.g. sbref, b0 scans)
            elif datatype == 'dwi':
                bvecfile = jsonfile.with_suffix('.bvec')
                bvalfile = jsonfile.with_suffix('.bval')
                if not bvecfile.is_file():
                    LOGGER.info(f"Adding dummy bvec file: {bvecfile}")
                    with bvecfile.open('w') as bvec_fid:
                        bvec_fid.write('0\n0\n0\n')
                if not bvalfile.is_file():
                    LOGGER.info(f"Adding dummy bval file: {bvalfile}")
                    with bvalfile.open('w') as bval_fid:
                        bval_fid.write('0\n')

            # Add the TaskName to the func json-file
            elif datatype == 'func':
                with jsonfile.open('r') as json_fid:
                    data = json.load(json_fid)
                if not 'TaskName' in data:
                    LOGGER.info(f"Adding TaskName to: {jsonfile}")
                    data['TaskName'] = run['bids']['task']
                    with jsonfile.open('w') as json_fid:
                        json.dump(data, json_fid, indent=4)

            # Parse the acquisition time from the json file or else from the source header (NB: assuming the source file represents the first acquisition)
            niifile = list(jsonfile.parent.glob(jsonfile.stem + '.nii*'))       # Find the corresponding nifti file (there should be only one, let's not make assumptions about the .gz extension)
            if niifile and datatype not in bidsmap['Options']['bidscoin']['bidsignore'] and not run['bids']['suffix'] in bids.get_derivatives(datatype):
                with jsonfile.open('r') as json_fid:
                    data = json.load(json_fid)
                if 'AcquisitionTime' not in data or not data['AcquisitionTime']:
                    data['AcquisitionTime'] = bids.get_sourcefield('AcquisitionTime', sourcefile)       # DICOM
                if not data['AcquisitionTime']:
                    data['AcquisitionTime'] = bids.get_sourcefield('exam_date', sourcefile)             # PAR/XML
                try:
                    acq_time = dateutil.parser.parse(data['AcquisitionTime'])
                except Exception as jsonerror:
                    LOGGER.warning(f"Could not parse the acquisition time from: '{data['AcquisitionTime']}' in {sourcefile}\n{jsonerror}")
                    acq_time = dateutil.parser.parse('00:00:00')
                scanpath = niifile[0].relative_to(bidsses)
                scans_table.loc[scanpath.as_posix(), 'acq_time'] = '1925-01-01T' + acq_time.strftime('%H:%M:%S')

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
            jsondata.pop('IntendedFor', None)
            if intendedfor:
                # Search with multiple patterns in all runs and store the relative path to the subject folder
                if intendedfor.startswith('<<') and intendedfor.endswith('>>'):
                    intendedfor = intendedfor[2:-2].split('><')
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
            else:
                LOGGER.warning(f"Empty 'IntendedFor' fieldmap value in {jsonfile}: the IntendedFor value of the bidsmap entry was empty")

            # Extract the echo times from magnitude1 and magnitude2 and add them to the phasediff json-file
            if jsonfile.name.endswith('phasediff.json'):
                json_magnitude = [None, None]
                TE             = [None, None]
                for n in (0,1):
                    json_magnitude[n] = jsonfile.parent/jsonfile.name.replace('_phasediff', f"_magnitude{n+1}")
                    if not json_magnitude[n].is_file():
                        LOGGER.error(f"Could not find expected magnitude{n+1} image associated with: {jsonfile}")
                    else:
                        with json_magnitude[n].open('r') as json_fid:
                            data = json.load(json_fid)
                        TE[n] = data['EchoTime']
                if None in TE:
                    LOGGER.error(f"Cannot find and add valid EchoTime1={TE[0]} and EchoTime2={TE[1]} data to: {jsonfile}")
                elif TE[0] > TE[1]:
                    LOGGER.error(f"Found invalid EchoTime1={TE[0]} > EchoTime2={TE[1]} for: {jsonfile}")
                else:
                    jsondata['EchoTime1'] = TE[0]
                    jsondata['EchoTime2'] = TE[1]
                    LOGGER.info(f"Adding EchoTime1: {TE[0]} and EchoTime2: {TE[1]} to {jsonfile}")

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
