"""The 'dcm2niix2bids' plugin is a wrapper around the well-known pydicom, nibabel and (in particular) dcm2niix
(https://github.com/rordenlab/dcm2niix) tools to interact with and convert DICOM and Philips PAR/REC source data.
Pydicom is used to read DICOM attributes, nibabel is used to read PAR attribute values and dcm2niix is used to
convert the DICOM and PAR source data to NIfTI and create BIDS sidecar files. Personal data from the source header
(e.g. Age, Sex) is added to the BIDS participants.tsv file."""

import logging
import dateutil.parser
import pandas as pd
import json
import shutil
from bids_validator import BIDSValidator
from typing import Union
from pathlib import Path
from bidscoin import bcoin, bids, lsdirs, due, Doi
from bidscoin.utilities import physio
try:
    from nibabel.testing import data_path
except ImportError:
    try:
        from importlib.resources import files
        data_path = files('nibabel')/'tests'/'data'
    except ImportError:           # PY38. Alternative: from importlib_resources import files
        import nibabel as nib
        data_path = (Path(nib.__file__).parent/'tests'/'data')

LOGGER = logging.getLogger(__name__)

# The default options that are set when installing the plugin
OPTIONS = {'command': 'dcm2niix',                   # Command to run dcm2niix, e.g. "module add dcm2niix/1.0.20180622; dcm2niix" or "PATH=/opt/dcm2niix/bin:$PATH; dcm2niix" or /opt/dcm2niix/bin/dcm2niix or 'C:\"Program Files"\dcm2niix\dcm2niix.exe' (use quotes to deal with whitespaces in the path)
           'args': '-b y -z y -i n',                # Argument string that is passed to dcm2niix. Tip: SPM users may want to use '-z n' (which produces unzipped NIfTI's, see dcm2niix -h for more information)
           'anon': 'y',                             # Set this anonymization flag to 'y' to round off age and discard acquisition date from the metadata
           'meta': ['.json', '.tsv', '.tsv.gz']}    # The file extensions of the equally named metadata sourcefiles that are copied over as BIDS sidecar files


def test(options: dict=OPTIONS) -> int:
    """
    Performs shell tests of dcm2niix

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins']['dcm2niix2bids']
    :return:        The errorcode (e.g 0 if the tool generated the expected result, > 0 if there was a tool error)
    """

    LOGGER.info('Testing the dcm2niix2bids installation:')

    if 'readphysio' not in dir(physio) or 'physio2tsv' not in dir(physio):
        LOGGER.error("Could not import the expected 'readphysio' and/or 'physio2tsv' from the physio.py utility")
        return 1
    if 'command' not in {**OPTIONS, **options}:
        LOGGER.error(f"The expected 'command' key is not defined in the dcm2niix2bids options")
        return 1
    if 'args' not in {**OPTIONS, **options}:
        LOGGER.warning(f"The expected 'args' key is not defined in the dcm2niix2bids options")

    # Test the dcm2niix installation
    errorcode = bcoin.run_command(f"{options.get('command', OPTIONS['command'])} -v", (0,3))

    # Test reading an attribute from a PAR-file
    parfile = Path(data_path)/'phantom_EPI_asc_CLEAR_2_1.PAR'
    try:
        assert is_sourcefile(parfile) == 'PAR'
        assert get_attribute('PAR', parfile, 'exam_name', options) == 'Konvertertest'
    except Exception as pluginerror:
        LOGGER.error(f"Could not read attribute(s) from {parfile}:\n{pluginerror}")
        return 1

    return errorcode if errorcode != 3 else 0


def is_sourcefile(file: Path) -> str:
    """
    This plugin function supports assessing whether the file is a valid sourcefile

    :param file:    The file that is assessed
    :return:        The valid dataformat of the file for this plugin
    """

    if bids.is_dicomfile(file):     # To support pet2bids add: and bids.get_dicomfield('Modality', file) != 'PT'
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
    All the logic to map the DICOM/PAR source fields onto bids labels go into this function

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The new study bidsmap that we are building
    :param bidsmap_old: The previous study bidsmap that has precedence over the template bidsmap
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
        for sourcedir in lsdirs(session, '**/*'):
            for n in range(1):      # Option: Use range(2) to scan two files and catch e.g. magnitude1/2 fieldmap files that are stored in one Series folder (but bidscoiner sees only the first file anyhow and it makes bidsmapper 2x slower :-()
                sourcefile = bids.get_dicomfile(sourcedir, n)
                if sourcefile.name and is_sourcefile(sourcefile):
                    sourcefiles.append(sourcefile)
    elif dataformat == 'PAR':
        sourcefiles = bids.get_parfiles(session)
    else:
        LOGGER.exception(f"Unsupported dataformat '{dataformat}'")

    # Extra bidsmap check
    if not template[dataformat] and not bidsmap_old[dataformat]:
        LOGGER.error(f"No {dataformat} source information found in the study and template bidsmap")
        return

    # Update the bidsmap with the info from the source files
    for sourcefile in sourcefiles:

        # Check if the source files all have approximately the same size (difference < 50kB)
        if dataformat == 'DICOM':
            for file in sourcefile.parent.iterdir():
                if abs(file.stat().st_size - sourcefile.stat().st_size) > 1024 * 50 and file.suffix == sourcefile.suffix:
                    LOGGER.warning(f"Not all {file.suffix}-files in '{sourcefile.parent}' have the same size. This may be ok but can also be indicative of a truncated acquisition or file corruption(s)")
                    break

        # See if we can find a matching run in the old bidsmap
        datasource = bids.DataSource(sourcefile, plugin, dataformat)
        run, match = bids.get_matching_run(datasource, bidsmap_old)

        # If not, see if we can find a matching run in the template
        if not match:
            run, _ = bids.get_matching_run(datasource, template)

        # See if we have collected the run somewhere in our new bidsmap
        if not bids.exist_run(bidsmap_new, '', run):

            # Communicate with the user if the run was not present in bidsmap_old or in template, i.e. that we found a new sample
            if not match:
                LOGGER.info(f"Discovered '{datasource.datatype}' {dataformat} sample: {sourcefile}")

            # Now work from the provenance store
            if store:
                targetfile             = store['target']/sourcefile.relative_to(store['source'])
                targetfile.parent.mkdir(parents=True, exist_ok=True)
                LOGGER.verbose(f"Storing the discovered {dataformat} sample as: {targetfile}")
                run['provenance']      = str(shutil.copyfile(sourcefile, targetfile))
                run['datasource'].path = targetfile

            # Copy the filled-in run over to the new bidsmap
            bids.append_run(bidsmap_new, run)


@due.dcite(Doi('10.1016/j.jneumeth.2016.03.001'), description='dcm2niix: DICOM to NIfTI converter', tags=['reference-implementation'])
def bidscoiner_plugin(session: Path, bidsmap: dict, bidsses: Path) -> Union[None, dict]:
    """
    The bidscoiner plugin to convert the session DICOM and PAR/REC source-files into BIDS-valid NIfTI-files in the
    corresponding bids session-folder and extract personals (e.g. Age, Sex) from the source header

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsses:     The full-path name of the BIDS output `sub-/ses-` folder
    :return:            A dictionary with personal data for the participants.tsv file (such as sex or age)
    """

    # Get the subject identifiers and the BIDS root folder from the bidsses folder
    if bidsses.name.startswith('ses-'):
        bidsfolder = bidsses.parent.parent
        subid      = bidsses.parent.name
        sesid      = bidsses.name
    else:
        bidsfolder = bidsses.parent
        subid      = bidsses.name
        sesid      = ''

    # Get started and see what dataformat we have
    options    = bidsmap['Options']['plugins']['dcm2niix2bids']
    datasource = bids.get_datasource(session, {'dcm2niix2bids': options})
    dataformat = datasource.dataformat
    if not dataformat:
        LOGGER.info(f"--> No {__name__} sourcedata found in: {session}")
        return

    # Make a list of all the data sources / runs
    manufacturer = 'UNKNOWN'
    sources      = []
    if dataformat == 'DICOM':
        sources      = lsdirs(session, '**/*')
        manufacturer = datasource.attributes('Manufacturer')
    elif dataformat == 'PAR':
        sources      = bids.get_parfiles(session)
        manufacturer = 'Philips Medical Systems'
    else:
        LOGGER.exception(f"Unsupported dataformat '{dataformat}'")

    # Read or create a scans_table and tsv-file
    scans_tsv = bidsses/f"{subid}{'_'+sesid if sesid else ''}_scans.tsv"
    if scans_tsv.is_file():
        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
    else:
        scans_table = pd.DataFrame(columns=['acq_time'], dtype='str')
        scans_table.index.name = 'filename'

    # Process all the source files or run subfolders
    sourcefile = Path()
    for source in sources:

        # Get a sourcefile
        if dataformat == 'DICOM':
            sourcefile = bids.get_dicomfile(source)
        elif dataformat == 'PAR':
            sourcefile = source
        if not sourcefile.name or not is_sourcefile(sourcefile):
            continue

        # Get a matching run from the bidsmap
        datasource = bids.DataSource(sourcefile, {'dcm2niix2bids': options}, dataformat)
        run, match = bids.get_matching_run(datasource, bidsmap, runtime=True)

        # Check if we should ignore this run
        if datasource.datatype in bidsmap['Options']['bidscoin']['ignoretypes']:
            LOGGER.info(f"--> Leaving out: {source}")
            continue

        # Check if we already know this run
        if not match:
            LOGGER.error(f"--> Skipping unknown '{datasource.datatype}' run: {sourcefile}\n-> Re-run the bidsmapper and delete {bidsses} to solve this warning")
            continue

        LOGGER.info(f"--> Coining: {source}")

        # Create the BIDS session/datatype output folder
        suffix = datasource.dynamicvalue(run['bids']['suffix'], True, True)
        if suffix in bids.get_derivatives(datasource.datatype):
            outfolder = bidsfolder/'derivatives'/manufacturer.replace(' ','')/subid/sesid/datasource.datatype
        else:
            outfolder = bidsses/datasource.datatype
        outfolder.mkdir(parents=True, exist_ok=True)

        # Compose the BIDS filename using the matched run
        bidsignore = bids.check_ignore(datasource.datatype, bidsmap['Options']['bidscoin']['bidsignore'])
        bidsname   = bids.get_bidsname(subid, sesid, run, not bidsignore, runtime=True)
        bidsignore = bidsignore or bids.check_ignore(bidsname+'.json', bidsmap['Options']['bidscoin']['bidsignore'], 'file')
        bidsname   = bids.increment_runindex(outfolder, bidsname, run, scans_table)
        jsonfiles  = set()  # Set -> Collect the associated json-files (for updating them later) -- possibly > 1

        # Check if the bidsname is valid
        bidstest = (Path('/')/subid/sesid/datasource.datatype/bidsname).with_suffix('.json').as_posix()
        isbids   = BIDSValidator().is_bids(bidstest)
        if not isbids and not bidsignore:
            LOGGER.warning(f"The '{bidstest}' ouput name did not pass the bids-validator test")

        # Check if the output file already exists (-> e.g. when a static runindex is used)
        if (outfolder/bidsname).with_suffix('.json').is_file():
            LOGGER.warning(f"{outfolder/bidsname}.* already exists and will be deleted -- check your results carefully!")
            for ext in ('.nii.gz', '.nii', '.json', '.tsv', '.tsv.gz', '.bval', '.bvec'):
                (outfolder/bidsname).with_suffix(ext).unlink(missing_ok=True)

        # Check if the source files all have approximately the same size (difference < 50kB)
        for file in source.iterdir() if source.is_dir() else []:
            if abs(file.stat().st_size - sourcefile.stat().st_size) > 1024 * 50 and file.suffix == sourcefile.suffix:
                LOGGER.warning(f"Not all {file.suffix}-files in '{source}' have the same size. This may be ok but can also be indicative of a truncated acquisition or file corruption(s)")
                break

        # Convert physiological log files (dcm2niix can't handle these)
        if suffix == 'physio':
            if bids.get_dicomfile(source, 2).name:                  # TODO: issue warning or support PAR
                LOGGER.warning(f"Found > 1 DICOM file in {source}, using: {sourcefile}")
            try:
                physiodata = physio.readphysio(sourcefile)
                physio.physio2tsv(physiodata, outfolder/bidsname)
                jsonfiles.update(outfolder.glob(f"{bidsname}.json"))  # add existing created json files: bidsname.json
            except Exception as physioerror:
                LOGGER.error(f"Could not read/convert physiological file: {sourcefile}\n{physioerror}")
                continue

        # Convert the source-files in the run folder to NIfTI's in the BIDS-folder
        else:
            command = '{command} {args} -f "{filename}" -o "{outfolder}" "{source}"'.format(
                command   = options['command'],
                args      = options.get('args',''),
                filename  = bidsname,
                outfolder = outfolder,
                source    = source)
            if bcoin.run_command(command):
                if not list(outfolder.glob(f"{bidsname}.*nii*")): continue

            jsonfiles.update(outfolder.glob(f"{bidsname}.json"))  # add existing created json files: bidsname.json

            # Handle the ABCD GE pepolar sequence
            extrafile = list(outfolder.glob(f"{bidsname}a.nii*"))
            if extrafile:
                # Load the json meta-data to see if it's a pepolar sequence
                with extrafile[0].with_suffix('').with_suffix('.json').open('r') as json_fid:
                    jsondata = json.load(json_fid)
                if 'PhaseEncodingPolarityGE' in jsondata:
                    ext     = ''.join(extrafile[0].suffixes)
                    invfile = bids.get_bidsvalue(outfolder/(bidsname+ext), 'dir', bids.get_bidsvalue(bidsname,'dir') + jsondata['PhaseEncodingPolarityGE'])
                    LOGGER.verbose(f"Renaming GE reversed polarity image: {extrafile[0]} -> {invfile}")
                    extrafile[0].replace(invfile)
                    extrafile[0].with_suffix('').with_suffix('.json').replace(invfile.with_suffix('').with_suffix('.json'))
                    jsonfiles.add(invfile.with_suffix('').with_suffix('.json'))
                else:
                    LOGGER.warning(f"Unexpected variants of {outfolder/bidsname}* were produced by dcm2niix. Possibly this can be remedied by using the dcm2niix -i option (to ignore derived, localizer and 2D images) or by clearing the BIDS folder before running bidscoiner")

            # Replace uncropped output image with the cropped one
            if '-x y' in options.get('args',''):
                for dcm2niixfile in sorted(outfolder.glob(bidsname + '*_Crop_*')):                              # e.g. *_Crop_1.nii.gz
                    ext         = ''.join(dcm2niixfile.suffixes)
                    newbidsfile = str(dcm2niixfile).rsplit(ext,1)[0].rsplit('_Crop_',1)[0] + ext
                    LOGGER.verbose(f"Found dcm2niix _Crop_ postfix, replacing original file\n{dcm2niixfile} ->\n{newbidsfile}")
                    dcm2niixfile.replace(newbidsfile)

            # Rename all files that got additional postfixes from dcm2niix. See: https://github.com/rordenlab/dcm2niix/blob/master/FILENAMING.md
            dcm2niixpostfixes = ('_c', '_i', '_Eq', '_real', '_imaginary', '_MoCo', '_t', '_Tilt', '_e', '_ph', '_ADC', '_fieldmaphz')      #_c%d, _e%d and _ph (and any combination of these in that order) are for multi-coil data, multi-echo data and phase data
            dcm2niixfiles     = sorted(set([dcm2niixfile for dcm2niixpostfix in dcm2niixpostfixes for dcm2niixfile in outfolder.glob(f"{bidsname}*{dcm2niixpostfix}*.nii*")]))

            for dcm2niixfile in dcm2niixfiles:

                # Strip each dcm2niix postfix and assign it to bids entities in a newly constructed bidsname
                ext         = ''.join(dcm2niixfile.suffixes)
                postfixes   = dcm2niixfile.name.split(bidsname)[1].rsplit(ext)[0].split('_')[1:]
                newbidsname = dcm2niixfile.name
                for postfix in postfixes:

                    # Patch the echo entity in the newbidsname with the dcm2niix echo info                      # NB: We can't rely on the bids-entity info here because manufacturers can e.g. put multiple echos in one series / run-folder
                    if 'echo' in run['bids'] and postfix.startswith('e'):
                        echonr = f"_{postfix}".replace('_e','')                                                 # E.g. postfix='e1'
                        if not echonr:
                            echonr = '1'
                        if echonr.isdecimal():
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'echo', echonr.lstrip('0'), bidsignore)       # In contrast to other labels, run and echo labels MUST be integers. Those labels MAY include zero padding, but this is NOT RECOMMENDED to maintain their uniqueness
                        elif echonr[0:-1].isdecimal():
                            LOGGER.verbose(f"Splitting off echo-number {echonr[0:-1]} from the '{postfix}' postfix")
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'echo', echonr[0:-1].lstrip('0'), bidsignore) # Strip of the 'a', 'b', etc. from `e1a`, `e1b`, etc
                            newbidsname = bids.get_bidsvalue(newbidsname, 'dummy', echonr[-1])                  # Append the 'a' to the acq-label
                        else:
                            LOGGER.error(f"Unexpected postix '{postfix}' found in {dcm2niixfile}")
                            newbidsname = bids.get_bidsvalue(newbidsname, 'dummy', postfix)                     # Append the unknown postfix to the acq-label

                    # Patch the phase entity in the newbidsname with the dcm2niix mag/phase info
                    elif 'part' in run['bids'] and postfix in ('ph','real','imaginary'):                        # e.g. part: ['', 'mag', 'phase', 'real', 'imag', 0]
                        if postfix == 'ph':
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'part', 'phase', bidsignore)
                        if postfix == 'real':
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'part', 'real', bidsignore)
                        if postfix == 'imaginary':
                            newbidsname = bids.insert_bidskeyval(newbidsname, 'part', 'imag', bidsignore)

                    # Patch fieldmap images (NB: datatype=='fmap' is too broad, see the fmap.yaml file)
                    elif suffix in bids.datatyperules['fmap']['fieldmaps']['suffixes']:                         # i.e. in ('magnitude','magnitude1','magnitude2','phase1','phase2','phasediff','fieldmap')
                        if len(dcm2niixfiles) not in (1, 2, 3, 4):                                              # Phase / echo data may be stored in the same data source / run folder
                            LOGGER.verbose(f"Unknown fieldmap {outfolder/bidsname} for '{postfix}'")
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
                            newbidsname = newbidsname.replace('_magnitude_fieldmaphz', '_fieldmap')
                            newbidsname = newbidsname.replace('_fieldmap_fieldmaphz',  '_fieldmap')
                        newbidsname = newbidsname.replace('_fieldmap_e1',    '_fieldmap')                       # Case 3
                        newbidsname = newbidsname.replace('_magnitude_ph',   '_fieldmap')                       # Case 3: One magnitude + one fieldmap image in one folder / datasource
                        newbidsname = newbidsname.replace('_fieldmap_ph',    '_fieldmap')                       # Case 3

                    # Append the dcm2niix info to acq-label, may need to be improved / elaborated for future BIDS standards, supporting multi-coil data
                    else:
                        newbidsname = bids.get_bidsvalue(newbidsname, 'dummy', postfix)

                    # Remove the added postfix from the new bidsname
                    newbidsname = newbidsname.replace(f"_{postfix}_",'_')                                       # If it is not last
                    newbidsname = newbidsname.replace(f"_{postfix}.",'.')                                       # If it is last

                    # The ADC images are not BIDS compliant
                    if postfix == 'ADC':
                        LOGGER.warning(f"The {newbidsname} image is a derivate / not BIDS-compliant -- you can probably delete it safely and update {scans_tsv}")

                # Save the NIfTI file with the newly constructed name
                newbidsname = bids.increment_runindex(outfolder, newbidsname, run, scans_table)                 # Update the runindex now that the acq-label has changed
                newbidsfile = outfolder/newbidsname
                LOGGER.verbose(f"Found dcm2niix {postfixes} postfixes, renaming\n{dcm2niixfile} ->\n{newbidsfile}")
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
                        jsonfiles.add(newjsonfile)
                for oldfile in outfolder.glob(dcm2niixfile.with_suffix('').stem + '.*'):
                    oldfile.replace(newjsonfile.with_suffix(''.join(oldfile.suffixes)))

        # Loop over all the newly produced json sidecar-files and adapt the data (NB: assumes every NIfTI-file comes with a json-file)
        for jsonfile in sorted(jsonfiles):

            # Load / copy over the source meta-data
            metadata = bids.updatemetadata(sourcefile, jsonfile, run['meta'], options['meta'], datasource)

            # Remove the bval/bvec files of sbref- and inv-images (produced by dcm2niix but not allowed by the BIDS specifications)
            if (datasource.datatype=='dwi' and suffix=='sbref') or (datasource.datatype=='fmap' and suffix=='epi'):
                for ext in ('.bval', '.bvec'):
                    bfile = jsonfile.with_suffix(ext)
                    if bfile.is_file():
                        bdata = pd.read_csv(bfile, header=None)
                        if bdata.any(axis=None):
                            LOGGER.warning(f"Found unexpected non-zero b-values in: {bfile} -> .bidsignore")
                            bidsmap['Options']['bidscoin']['bidsignore'] += [f"**/{datasource.datatype}/sub*{suffix}{ext}"]
                        else:
                            LOGGER.verbose(f"Removing BIDS-invalid b0-file: {bfile} -> {jsonfile}")
                            metadata[ext[1:]] = bdata.values.tolist()
                            bfile.unlink()

            # Save the meta-data to the json sidecar-file
            with jsonfile.open('w') as json_fid:
                json.dump(metadata, json_fid, indent=4)

            # Parse the acquisition time from the source header or else from the json file (NB: assuming the source file represents the first acquisition)
            outputfile = [file for file in jsonfile.parent.glob(jsonfile.stem + '.*') if file.suffix in ('.nii','.gz')]     # Find the corresponding NIfTI/tsv.gz file (there should be only one, let's not make assumptions about the .gz extension)
            if not outputfile:
                LOGGER.exception(f"No data-file found with {jsonfile} when updating {scans_tsv}")
            elif not bidsignore and not suffix in bids.get_derivatives(datasource.datatype):
                acq_time = ''
                if dataformat == 'DICOM':
                    acq_time = f"{datasource.attributes('AcquisitionDate')}T{datasource.attributes('AcquisitionTime')}"
                elif dataformat == 'PAR':
                    acq_time = datasource.attributes('exam_date')
                if not acq_time or acq_time == 'T':
                    acq_time = f"1925-01-01T{metadata.get('AcquisitionTime','')}"
                try:
                    acq_time = dateutil.parser.parse(acq_time)
                    if options.get('anon','y') in ('y','yes'):
                        acq_time = acq_time.replace(year=1925, month=1, day=1)      # Privacy protection (see BIDS specification)
                    acq_time = acq_time.isoformat()
                except Exception as jsonerror:
                    LOGGER.warning(f"Could not parse the acquisition time from: {sourcefile}\n{jsonerror}")
                    acq_time = 'n/a'
                scanpath = outputfile[0].relative_to(bidsses)
                scans_table.loc[scanpath.as_posix(), 'acq_time'] = acq_time

    # Write the scans_table to disk
    LOGGER.verbose(f"Writing acquisition time data to: {scans_tsv}")
    scans_table.sort_values(by=['acq_time','filename'], inplace=True)
    scans_table.replace('','n/a').to_csv(scans_tsv, sep='\t', encoding='utf-8', na_rep='n/a')

    # Collect personal data for the participants.tsv file
    if dataformat == 'DICOM':                               # PAR does not contain personal info
        personals = {}
        age       = datasource.attributes('PatientAge')     # A string of characters with one of the following formats: nnnD, nnnW, nnnM, nnnY
        if   age.endswith('D'): age = float(age.rstrip('D')) / 365.2524
        elif age.endswith('W'): age = float(age.rstrip('W')) / 52.1775
        elif age.endswith('M'): age = float(age.rstrip('M')) / 12
        elif age.endswith('Y'): age = float(age.rstrip('Y'))
        if age and options.get('anon','y') in ('y','yes'):
            age = int(float(age))
        personals['age']    = str(age)
        personals['sex']    = datasource.attributes('PatientSex')
        personals['size']   = datasource.attributes('PatientSize')
        personals['weight'] = datasource.attributes('PatientWeight')

        return personals
