"""
This module contains the interface with dcm2niix to convert the session DICOM and PAR/REC source-files into BIDS-valid
nifti-files in the corresponding bidsfolder and extract personals (e.g. Age, Sex) from the source header.

NB: dcm2niix sometimes lead to appended suffixes to the filenames, which are automatically casted to the correct BIDS entities
or, if that fails, appended to the `acq` entity (e.g. "sub-01_acq-MEMPRAGE_T1w_E1.nii" becoming "sub-01_acq-MEMPRAGEe1_T1w.nii")

See also:
- https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage
"""

import logging
import dateutil.parser
import pandas as pd
import json
from typing import Union
from pathlib import Path
import shutil
try:
    from bidscoin import bidscoin, bids, physio
except ImportError:
    import bidscoin, bids, physio     # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger(__name__)


def test(options) -> bool:
    """
    Performs shell tests of dcm2niix

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']['dcm2niix2bids']
    :return:        True if the tool generated the expected result, False if there was a tool error
    """

    LOGGER.info('Testing the dcm2niix2bids installation:')

    if 'args' not in options:
        LOGGER.warning(f"The expected 'args' key is not defined in the dcm2niix2bids options")

    # Test the dcm2niix installation
    return bidscoin.run_command(f"{options.get('command','dcm2niix')} -u; {options.get('command','dcm2niix')}")


def is_sourcefile(file: Path) -> str:
    """
    This plugin function supports assessing whether the file is a valid sourcefile

    :param file:    The file that is assessed
    :return:        The valid dataformat of the file for this plugin
    """

    if bids.is_dicomfile(file):
        return 'DICOM'

    if bids.is_parfile(file):
        return 'PAR'

    return ''


def get_attribute(dataformat: str, sourcefile: Path, attribute: str, options: dict) -> Union[str, int]:
    """
    This plugin supports reading attributes from DICOM and PAR dataformats

    :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which the attribute value should be read
    :param attribute:   The attribute key for which the value should be read
    :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
    :return:            The attribute value
    """
    if dataformat == 'DICOM':
        return bids.get_dicomfield(attribute, sourcefile)

    if dataformat == 'PAR':
        return bids.get_parfield(attribute, sourcefile)


def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
    """
    All the logic to map the Philips PAR/XML fields onto bids labels go into this function

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The study bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param template:    The template bidsmap with the default heuristics
    :param store:       The paths of the source- and target-folder
    :return:
    """

    # Get started
    plugin     = {'dcm2niix2bids': bidsmap_new['Options']['plugins']['dcm2niix2bids']}
    datasource = bids.get_datasource(session, plugin)
    dataformat = datasource.dataformat
    if not dataformat:
        return

    # Collect the different DICOM/PAR source files for all runs in the session
    sourcefiles = []
    if dataformat == 'DICOM':
        for sourcedir in bidscoin.lsdirs(session):
            sourcefile = bids.get_dicomfile(sourcedir)
            if sourcefile.name:
                sourcefiles.append(sourcefile)
    elif dataformat == 'PAR':
        sourcefiles = bids.get_parfiles(session)
    else:
        LOGGER.exception(f"Unsupported dataformat '{dataformat}'")

    # Update the bidsmap with the info from the source files
    for sourcefile in sourcefiles:

        # Input checks
        if not sourcefile.name or (not template[dataformat] and not bidsmap_old[dataformat]):
            LOGGER.error(f"No {dataformat} source information found in the bidsmap and template for: {sourcefile}")
            return

        datasource = bids.DataSource(sourcefile, plugin, dataformat)

        # See if we can find a matching run in the old bidsmap
        run, index = bids.get_matching_run(datasource, bidsmap_old)

        # If not, see if we can find a matching run in the template
        if index is None:
            run, _ = bids.get_matching_run(datasource, template)

        # See if we have collected the run somewhere in our new bidsmap
        if not bids.exist_run(bidsmap_new, '', run):

            # Communicate with the user if the run was not present in bidsmap_old or in template, i.e. that we found a new sample
            LOGGER.info(f"Found '{run['datasource'].datatype}' {dataformat} sample: {sourcefile}")

            # Now work from the provenance store
            if store:
                targetfile             = store['target']/sourcefile.relative_to(store['source'])
                targetfile.parent.mkdir(parents=True, exist_ok=True)
                run['provenance']      = str(shutil.copy2(sourcefile, targetfile))
                run['datasource'].path = targetfile

            # Copy the filled-in run over to the new bidsmap
            bids.append_run(bidsmap_new, run)

        else:
            # Communicate with the user if the run was already present in bidsmap_old or in template
            LOGGER.debug(f"Known '{run['datasource'].datatype}' {dataformat} sample: {sourcefile}")


def bidscoiner_plugin(session: Path, bidsmap: dict, bidsfolder: Path) -> None:
    """
    The bidscoiner plugin to convert the session DICOM and PAR/REC source-files into BIDS-valid nifti-files in the
    corresponding bidsfolder and extract personals (e.g. Age, Sex) from the source header

    :param session:     The full-path name of the subject/session source file/folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsfolder:  The full-path name of the BIDS root-folder
    :return:            Nothing
    """

    # Get started and see what dataformat we have
    plugin     = {'dcm2niix2bids': bidsmap['Options']['plugins']['dcm2niix2bids']}
    datasource = bids.get_datasource(session, plugin)
    dataformat = datasource.dataformat
    if not dataformat:
        LOGGER.info(f"No {__name__} sourcedata found in: {session}")
        return

    # Make a list of all the data sources / runs
    manufacturer = 'UNKNOWN'
    sources      = []
    if dataformat == 'DICOM':
        sources      = bidscoin.lsdirs(session)
        manufacturer = datasource.attributes('Manufacturer')
    elif dataformat == 'PAR':
        sources      = bids.get_parfiles(session)
        manufacturer = 'Philips Medical Systems'
    else:
        LOGGER.exception(f"Unsupported dataformat '{dataformat}'")

    # Get valid BIDS subject/session identifiers from the (first) DICOM- or PAR/XML source file
    subid, sesid = datasource.subid_sesid(bidsmap[dataformat]['subject'], bidsmap[dataformat]['session'])
    if not subid:
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
    sourcefile = Path()
    for source in sources:

        # Get a data source
        if dataformat == 'DICOM':
            sourcefile = bids.get_dicomfile(source)
        elif dataformat == 'PAR':
            sourcefile = source
        if not sourcefile.name:
            continue

        # Get a matching run from the bidsmap and update its run['datasource'] object
        datasource          = bids.DataSource(sourcefile, plugin, dataformat)
        run, index          = bids.get_matching_run(datasource, bidsmap, runtime=True)
        datasource          = run['datasource']
        datasource.path     = sourcefile
        datasource.plugins  = plugin
        datatype            = datasource.datatype

        # Check if we should ignore this run
        if datatype in bidsmap['Options']['bidscoin']['ignoretypes']:
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
        jsonfiles = [(outfolder/bidsname).with_suffix('.json')]     # List -> Collect the associated json-files (for updating them later) -- possibly > 1

        # Check if file already exists (-> e.g. when a static runindex is used)
        if (outfolder/bidsname).with_suffix('.json').is_file():
            LOGGER.warning(f"{outfolder/bidsname}.* already exists and will be deleted -- check your results carefully!")
            for ext in ('.nii.gz', '.nii', '.json', '.bval', '.bvec', '.tsv.gz'):
                (outfolder/bidsname).with_suffix(ext).unlink(missing_ok=True)

        # Convert physiological log files (dcm2niix can't handle these)
        if run['bids']['suffix'] == 'physio':
            if bids.get_dicomfile(source, 2).name:                  # TODO: issue warning or support PAR
                LOGGER.warning(f"Found > 1 DICOM file in {source}, using: {sourcefile}")
            physiodata = physio.readphysio(sourcefile)
            physio.physio2tsv(physiodata, outfolder/bidsname)

        # Convert the source-files in the run folder to nifti's in the BIDS-folder
        else:
            command = '{command} {args} -f "{filename}" -o "{outfolder}" "{source}"'.format(
                command   = plugin['dcm2niix2bids'].get('command','dcm2niix'),
                args      = plugin['dcm2niix2bids'].get('args',''),
                filename  = bidsname,
                outfolder = outfolder,
                source    = source)
            if not bidscoin.run_command(command):
                continue

            # Replace uncropped output image with the cropped one
            if '-x y' in plugin['dcm2niix2bids'].get('args',''):
                for dcm2niixfile in sorted(outfolder.glob(bidsname + '*_Crop_*')):                              # e.g. *_Crop_1.nii.gz
                    ext         = ''.join(dcm2niixfile.suffixes)
                    newbidsfile = str(dcm2niixfile).rsplit(ext,1)[0].rsplit('_Crop_',1)[0] + ext
                    LOGGER.info(f"Found dcm2niix _Crop_ postfix, replacing original file\n{dcm2niixfile} ->\n{newbidsfile}")
                    dcm2niixfile.replace(newbidsfile)

            # Rename all files that got additional postfixes from dcm2niix. See: https://github.com/rordenlab/dcm2niix/blob/master/FILENAMING.md
            dcm2niixpostfixes = ('_c', '_i', '_Eq', '_real', '_imaginary', '_MoCo', '_t', '_Tilt', '_e', '_ph')
            dcm2niixfiles     = sorted(set([dcm2niixfile for dcm2niixpostfix in dcm2niixpostfixes for dcm2niixfile in outfolder.glob(f"{bidsname}*{dcm2niixpostfix}*.nii*")]))
            if not jsonfiles[0].is_file() and dcm2niixfiles:                                                    # Possibly renamed by dcm2niix, e.g. with multi-echo data (but not always for the first echo)
                jsonfiles.pop(0)
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

        # Loop over and adapt all the newly produced json sidecar-files and write to the scans.tsv file (NB: assumes every nifti-file comes with a json-file)
        for jsonfile in sorted(set(jsonfiles)):

            # Load the json meta-data
            with jsonfile.open('r') as json_fid:
                jsondata = json.load(json_fid)

            # Add the TaskName to the meta-data
            if datatype in ('func','pet') and 'TaskName' not in jsondata:
                jsondata['TaskName'] = run['bids']['task']

            # Add the TracerName and TaskName to the meta-data
            elif datatype == 'pet' and 'TracerName' not in jsondata:
                jsondata['TracerName'] = run['bids']['trc']

            # Add all the meta data to the meta-data. NB: the dynamic `IntendedFor` value is handled separately later
            for metakey, metaval in run['meta'].items():
                if metakey != 'IntendedFor':
                    metaval = datasource.dynamicvalue(metaval, cleanup=False, runtime=True)
                    LOGGER.info(f"Adding '{metakey}: {metaval}' to: {jsonfile}")
                jsondata[metakey] = metaval

            # Save the meta-data to the json sidecar-file
            with jsonfile.open('w') as json_fid:
                json.dump(jsondata, json_fid, indent=4)

            # Parse the acquisition time from the source header or else from the json file (NB: assuming the source file represents the first acquisition)
            outputfile = [file for file in jsonfile.parent.glob(jsonfile.stem + '.*') if file.suffix in ('.nii','.gz')]     # Find the corresponding nifti/tsv.gz file (there should be only one, let's not make assumptions about the .gz extension)
            if not outputfile:
                LOGGER.exception(f"No data-file found with {jsonfile} when updating {scans_tsv}")
            elif datatype not in bidsmap['Options']['bidscoin']['bidsignore'] and not run['bids']['suffix'] in bids.get_derivatives(datatype):
                acq_time = ''
                if dataformat == 'DICOM':
                    acq_time = f"{datasource.attributes('AcquisitionDate')}T{datasource.attributes('AcquisitionTime')}"
                elif dataformat == 'PAR':
                    acq_time = datasource.attributes('exam_date')
                if not acq_time or acq_time == 'T':
                    acq_time = f"1925-01-01T{jsondata.get('AcquisitionTime','')}"
                try:
                    acq_time = dateutil.parser.parse(acq_time)
                    if plugin['dcm2niix2bids'].get('anon','y') in ('y','yes'):
                        acq_time = acq_time.replace(year=1925, month=1, day=1)      # Privacy protection (see BIDS specification)
                    acq_time = acq_time.isoformat()
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
                    jsondata['IntendedFor'] = None
            else:
                LOGGER.warning(f"Empty 'IntendedFor' fieldmap value in {jsonfile}: the IntendedFor value of the bidsmap entry was empty")
            if not jsondata.get('IntendedFor'):     # Work-around because the bids-validator (v1.8) cannot handle `null` values
                jsondata.pop('IntendedFor', None)

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
    personals = {}
    if sesid and 'session_id' not in personals:
        personals['session_id'] = sesid
    personals['age'] = ''
    if dataformat == 'DICOM':
        age = datasource.attributes('PatientAge')                   # A string of characters with one of the following formats: nnnD, nnnW, nnnM, nnnY
        if age.endswith('D'):   age = float(age.rstrip('D')) / 365.2524
        elif age.endswith('W'): age = float(age.rstrip('W')) / 52.1775
        elif age.endswith('M'): age = float(age.rstrip('M')) / 12
        elif age.endswith('Y'): age = float(age.rstrip('Y'))
        if age:
            if plugin['dcm2niix2bids'].get('anon', 'y') in ('y','yes'):
                age = int(float(age))
            personals['age'] = str(age)
        personals['sex']     = datasource.attributes('PatientSex')
        personals['size']    = datasource.attributes('PatientSize')
        personals['weight']  = datasource.attributes('PatientWeight')

    # Store the collected personals in the participants_table
    participants_tsv = bidsfolder/'participants.tsv'
    if participants_tsv.is_file():
        participants_table = pd.read_csv(participants_tsv, sep='\t', dtype=str)
        participants_table.set_index(['participant_id'], verify_integrity=True, inplace=True)
    else:
        participants_table = pd.DataFrame()
        participants_table.index.name = 'participant_id'
    if subid in participants_table.index and 'session_id' in participants_table.keys() and participants_table.loc[subid, 'session_id']:
        return                                          # Only take data from the first session -> BIDS specification
    for key in personals:           # TODO: Check that only values that are consistent over sessions go in the participants.tsv file, otherwise put them in a sessions.tsv file
        if key not in participants_table or participants_table[key].isnull().get(subid, True) or participants_table[key].get(subid) == 'n/a':
            participants_table.loc[subid, key] = personals[key]

    # Write the collected data to the participants tsv-file
    LOGGER.info(f"Writing {subid} subject data to: {participants_tsv}")
    participants_table.replace('','n/a').to_csv(participants_tsv, sep='\t', encoding='utf-8', na_rep='n/a')
