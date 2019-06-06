#!/usr/bin/env python
"""
Module with helper functions

Derived from dac2bids.py from Daniel Gomez 29.08.2016
https://github.com/dangom/dac2bids/blob/master/dac2bids.py

@author: Marcel Zwiers
"""

# Global imports (specific modules may be imported when needed)
import os.path
import glob
import warnings
import re
import ruamel
import logging
from ruamel.yaml import YAML
yaml = YAML()

logger = logging.getLogger('bidscoin')

bidsmodalities  = ('anat', 'func', 'dwi', 'fmap', 'beh', 'pet')
unknownmodality = 'extra_data'
bidslabels      = ('acq_label', 'ce_label', 'rec_label', 'task_label', 'echo_index', 'dir_label', 'suffix')   # This is not really something from BIDS, but these are the BIDS-labels used in the bidsmap


def setup_logging(log_filename: str) -> logging.Logger:
    """
    Setup the logging

    :param log_filename:    Name of the logile
    :return:                Logger object
     """

    # Create the log dir if it does not exist
    os.makedirs(os.path.dirname(log_filename), exist_ok=True)

    # Set the format
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s %(message)s',
                                  '%Y-%m-%d %H:%M:%S')

    # Set the streamhandler
    streamhandler = logging.StreamHandler()
    streamhandler.setLevel(logging.INFO)
    streamhandler.setFormatter(formatter)

    # Set the filehandler
    filehandler = logging.FileHandler(log_filename)
    filehandler.setLevel(logging.INFO)
    filehandler.setFormatter(formatter)

    # Add the streamhandler and filehandler to the logger
    logger.addHandler(streamhandler)
    logger.addHandler(filehandler)

    return logger


def version() -> float:
    """
    Reads the BIDSCOIN version from the VERSION.TXT file

    :return:    The BIDSCOIN version number
    """

    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'version.txt')) as fid:
        version = fid.read().strip()

    return float(version)


def bidsversion() -> str:
    """
    Reads the BIDS version from the BIDSVERSION.TXT file

    :return:    The BIDS version number
    """

    with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'bidsversion.txt')) as fid:
        version = fid.read().strip()

    return str(version)


def lsdirs(folder: str, wildcard: str='*'):
    """
    Gets all directories in a folder, ignores files

    :param folder:      The full pathname of the folder
    :param wildcard:    Simple (glob.glob) shell-style wildcards. Foldernames starting with a dot are special cases that are not matched by '*' and '?' patterns.") wildcard
    :return:            An iterable filter object with all directories in a folder
    """

    if wildcard:
        folder = os.path.join(folder, wildcard)
    return [fname for fname in sorted(glob.glob(folder)) if os.path.isdir(fname)]


def is_dicomfile(file: str) -> bool:
    """
    Checks whether a file is a DICOM-file. It uses the feature that Dicoms have the string DICM hardcoded at offset 0x80.

    :param file:    The full pathname of the file
    :return:        Returns true if a file is a DICOM-file
    """

    if os.path.isfile(file):
        if os.path.basename(file).startswith('.'):
            logger.warning(f'DICOM file is hidden: {file}')
        with open(file, 'rb') as dcmfile:
            dcmfile.seek(0x80, 1)
            if dcmfile.read(4) == b'DICM':
                return True
            else:
                import pydicom
                dicomdict = pydicom.dcmread(file, force=True)       # The DICM tag may be missing for anonymized DICOM files
                return 'Modality' in dicomdict


def is_dicomfile_siemens(file: str) -> bool:
    """
    Checks whether a file is a *SIEMENS* DICOM-file. All Siemens Dicoms contain a dump of the
    MrProt structure. The dump is marked with a header starting with 'ASCCONV BEGIN'. Though
    this check is not foolproof, it is very unlikely to fail.

    :param file:    The full pathname of the file
    :return:        Returns true if a file is a Siemens DICOM-file
    """

    return b'ASCCONV BEGIN' in open(file, 'rb').read()


def is_parfile(file: str) -> bool:
    """
    Checks whether a file is a Philips PAR file

    WIP!!!!!!

    :param file:    The full pathname of the file
    :return:        Returns true if a file is a Philips PAR-file
    """

    # TODO: Returns true if filetype is PAR.
    if os.path.isfile(file):
        with open(file, 'r') as parfile:
            pass
        return False


def is_p7file(file: str) -> bool:
    """
    Checks whether a file is a GE P*.7 file

    WIP!!!!!!

    :param file:    The full pathname of the file
    :return:        Returns true if a file is a GE P7-file
    """

    # TODO: Returns true if filetype is P7.
    if os.path.isfile(file):
        with open(file, 'r') as p7file:
            pass
        return False


def is_niftifile(file: str) -> bool:
    """
    Checks whether a file is a nifti file

    WIP!!!!!!

    :param file:    The full pathname of the file
    :return:        Returns true if a file is a nifti-file
    """

    # TODO: Returns true if filetype is nifti.
    if os.path.isfile(file):
        with open(file, 'r') as niftifile:
            pass
        return False


def is_incomplete_acquisition(folder: str) -> bool:
    """
    If a scan was aborted in the middle of the experiment, it is likely that images will be saved
    anyway. We want to avoid converting these incomplete directories. This function checks the number
    of measurements specified in the protocol against the number of imaging files in the folder.

    :param folder:  The full pathname of the folder
    :return:        Returns true if the acquisition was incomplete
    """

    dicomfile = get_dicomfile(folder)
    nrep      = get_dicomfield('lRepetitions', dicomfile)
    nfiles    = len(os.listdir(folder))     # TODO: filter out non-imaging files

    if nrep and nrep > nfiles:
        logger.warning('Incomplete acquisition found in: {}'\
                       '\nExpected {}, found {} dicomfiles'.format(folder, nrep, nfiles))
        return True
    else:
        return False


def get_dicomfile(folder: str) -> str:
    """
    Gets a dicom-file from the folder

    :param folder:  The full pathname of the folder
    :return:        The filename of the first dicom-file in the folder.
    """

    for file in sorted(os.listdir(folder)):
        if os.path.basename(file).startswith('.'):
            logger.warning(f'Ignoring hidden DICOM file: {file}')
            continue
        if is_dicomfile(os.path.join(folder, file)):
            return os.path.join(folder, file)

    logger.warning('Cannot find dicom files in:' + folder)
    return None


def get_parfile(folder: str) -> str:
    """
    Gets a Philips PAR-file from the folder

    :param folder:  The full pathname of the folder
    :return:        The filename of the first PAR-file in the folder.
    """

    for file in sorted(os.listdir(folder)):
        if is_parfile(file):
            return os.path.join(folder, file)

    logger.warning('Cannot find PAR files in:' + folder)
    return None


def get_p7file(folder: str) -> str:
    """
    Gets a GE P*.7-file from the folder

    :param folder:  The full pathname of the folder
    :return:        The filename of the first P7-file in the folder.
    """

    for file in sorted(os.listdir(folder)):
        if is_p7file(file):
            return os.path.join(folder, file)

    logger.warning('Cannot find P7 files in:' + folder)
    return None


def get_niftifile(folder: str) -> str:
    """
    Gets a nifti-file from the folder

    :param folder:  The full pathname of the folder
    :return:        The filename of the first nifti-file in the folder.
    """

    for file in sorted(os.listdir(folder)):
        if is_niftifile(file):
            return os.path.join(folder, file)

    logger.warning('Cannot find nifti files in:' + folder)
    return None


def load_bidsmap(yamlfile: str='', folder: str='') -> ruamel.yaml:
    """
    Read the mapping heuristics from the bidsmap yaml-file

    :param yamlfile:    The full pathname or basename of the bidsmap yaml-file. If None, the default bidsmap_template.yaml file in the heuristics folder is used
    :param folder:      Only used when yamlfile=basename or None: yamlfile is then first searched for in folder and then falls back to the ./heuristics folder (useful for centrally managed template yaml-files)
    :return:            ruamel.yaml dict structure, with all options, BIDS mapping heuristics, labels and attributes, etc
    """

    # Input checking
    heuristics_folder = os.path.join(os.path.dirname(__file__),'..','heuristics')
    if not folder:
        folder = heuristics_folder
    if not yamlfile:
        yamlfile = os.path.join(folder,'bidsmap.yaml')
        if not os.path.isfile(yamlfile):
            yamlfile = os.path.join(heuristics_folder,'bidsmap_template.yaml')

    if not os.path.splitext(yamlfile)[1]:           # Add a standard file-extension if needed
        yamlfile = yamlfile + '.yaml'

    if os.path.basename(yamlfile) == yamlfile:      # Get the full path to the bidsmap yaml-file
        if os.path.isfile(os.path.join(folder, yamlfile)):
            yamlfile = os.path.join(folder, yamlfile)
        else:
            yamlfile = os.path.join(heuristics_folder, yamlfile)

    yamlfile = os.path.abspath(os.path.expanduser(yamlfile))
    logger.info('Using: ' + os.path.abspath(yamlfile))

    # Read the heuristics from the bidsmap file
    with open(yamlfile, 'r') as stream:
        bidsmap = yaml.load(stream)

    # Issue a warning if the version in the bidsmap YAML-file is not the same as the bidscoin version
    if 'version' not in bidsmap['Options']:
        bidsmapversion = 'Unknown'
    else:
        bidsmapversion = bidsmap['Options']['version']
    if bidsmapversion != version():
        logger.warning(f'BIDScoiner version conflict: {yamlfile} was created using version {bidsmapversion}, but this is version {version()}')

    return bidsmap


def save_bidsmap(filename: str, bidsmap: dict):
    """
    Save the BIDSmap as a YAML text file

    :param filename:
    :param bidsmap:
    :return:
    """

    logger.info('Writing bidsmap to: ' + filename)
    with open(filename, 'w') as stream:
        yaml.dump(bidsmap, stream)


def parse_x_protocol(pattern: str, dicomfile: str) -> str:
    """
    Siemens writes a protocol structure as text into each DICOM file.
    This structure is necessary to recreate a scanning protocol from a DICOM,
    since the DICOM information alone wouldn't be sufficient.

    :param pattern:     A regexp expression: '^' + pattern + '\t = \t(.*)\\n'
    :param dicomfile:   The full pathname of the dicom-file
    :return:            The string extracted values from the dicom-file according to the given pattern
    """

    if not is_dicomfile_siemens(dicomfile):
        logger.warning('Parsing {} may fail because {} does not seem to be a Siemens DICOM file'.format(pattern, dicomfile))

    regexp = '^' + pattern + '\t = \t(.*)\n'
    regex  = re.compile(regexp.encode('utf-8'))

    with open(dicomfile, 'rb') as openfile:
        for line in openfile:
            match = regex.match(line)
            if match:
                return match.group(1).decode('utf-8')

    logger.warning('Pattern: "' + regexp.encode('unicode_escape').decode() + '" not found in: ' + dicomfile)
    return None


# Profiling shows this is currently the most expensive function, so therefore the (primitive but effective) _DICOMDICT_CACHE optimization
_DICOMDICT_CACHE = None
_DICOMFILE_CACHE = None
def get_dicomfield(tagname: str, dicomfile: str):
    """
    Robustly extracts a DICOM field/tag from a dictionary or from vendor specific fields

    :param tagname:     Name of the DICOM field
    :param dicomfile:   The full pathname of the dicom-file
    :return:            Extracted tag-values from the dicom-file
    """

    import pydicom
    global _DICOMDICT_CACHE, _DICOMFILE_CACHE

    try:
        if dicomfile != _DICOMFILE_CACHE:
            dicomdict = pydicom.dcmread(dicomfile, force=True)      # The DICM tag may be missing for anonymized DICOM files
            if 'Modality' not in dicomdict:
                raise ValueError(f'Cannot read {dicomfile}')
            _DICOMDICT_CACHE = dicomdict
            _DICOMFILE_CACHE = dicomfile
        else:
            dicomdict = _DICOMDICT_CACHE

        value = dicomdict.get(tagname)

        # Try a recursive search
        if not value:
            for elem in dicomdict.iterall():
                if elem.name==tagname:
                    value = elem.value
                    continue

    except IOError:
        logger.warning(f'Cannot read {tagname} from {dicomfile}')
        value = None

    except Exception:
        try:
            value = parse_x_protocol(tagname, dicomfile)

        except Exception:
            logger.warning(f'Could not parse {tagname} from {dicomfile}')
            value = None

    # Cast the dicom datatype to standard to int or str (i.e. to something that yaml.dump can handle)
    if not value:
        return

    elif isinstance(value, int):
        return int(value)

    elif not isinstance(value, str):    # Assume it's a MultiValue type and flatten it
        return str(value)

    else:
        return str(value)


def add_prefix(prefix: str, tag: str) -> str:
    """
    Simple function to account for optional BIDS tags in the bids file names, i.e. it prefixes 'prefix' only when tag is not empty

    :param prefix:  The prefix (e.g. '_sub-')
    :param tag:     The tag (e.g. 'control01')
    :return:        The tag with the leading prefix (e.g. '_sub-control01') or just the empty tag ''
    """

    if tag:
        tag = prefix + tag
    else:
        tag = ''

    return tag


def strip_suffix(series: dict) -> dict:
    """
    Certain attributes such as SeriesDescriptions (but not ProtocolName!?) may get a suffix like '_SBRef' from the vendor,
    try to strip it off from the BIDS labels

    :param series:  The series with potentially added suffixes that are the same as the BIDS suffixes
    :return:        The series with these suffixes removed
    """

    # See if we have a suffix for this modality
    if 'suffix' in series['bids'] and series['bids']['suffix']:
        suffix = series['bids']['suffix'].lower()
    else:
        return series

    # See if any of the BIDS labels ends with the same suffix. If so, then remove it
    for key in series['bids']:
        if key == 'suffix':
            continue
        if series['bids'][key] and series['bids'][key].lower().endswith(suffix):
            series['bids'][key] = series['bids'][key][0:-len(suffix)]       # NB: This will leave the added '_' and '.' characters, but they will be taken out later (as they are not BIDS-valid)

    return series


def cleanup_label(label: str) -> str:
    """
    Converts a given label to a cleaned-up label that can be used as a BIDS label. Remove leading and trailing spaces;
    convert other spaces, special BIDS characters and anything that is not an alphanumeric to a ''. This will for
    example map "Joe's reward_task" to "Joesrewardtask"

    :param label:   The given label that potentially contains undesired characters
    :return:        The cleaned-up / BIDS-valid label
    """

    special_characters = (' ', '_', '-','.')

    for special in special_characters:
        label = str(label).strip().replace(special, '')

    return re.sub(r'(?u)[^-\w.]', '', label)


def exist_series(bidsmap: dict, source: str, modality: str, series: dict, matchbidslabels: bool=False) -> bool:
    """
    Checks if there is already an entry in serieslist with the same attributes and, optionally, labels as series

    :param bidsmap:         Full BIDS bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param source:          The information source in the bidsmap that is used, e.g. 'DICOM'
    :param modality:        The modality in the source that is used, e.g. 'anat'
    :param series:          The series (listitem) that is searched for in the modality
    :param matchbidslabels: If True, also matches the BIDS-labels, otherwise only series['attributes']
    :return:                True if the series exists in serieslist
    """

    if not bidsmap[source][modality]:
        return False

    for item in bidsmap[source][modality]:

        match = any([series['attributes'][key] is not None for key in series['attributes']])  # Make match False if all attributes are empty

        # Search for a case where all series items match with the series items
        for attrkey in series['attributes']:
            seriesvalue = series['attributes'][attrkey]
            itemvalue   = item['attributes'][attrkey]
            match = match and (seriesvalue==itemvalue)
            if not match:           # There is no point in searching further within the series now that we've found a mismatch
                break

        if matchbidslabels:         # This is probably not very useful, but maybe one day...
            try:
                for key in series['bids']:
                    seriesvalue = series['bids'][key]
                    itemvalue   = item['bids'][key]
                    match       = match and (seriesvalue == itemvalue)
                    if not match:   # There is no point in searching further within the series now that we've found a mismatch
                        break

            except KeyError:        # Errors may be evoked when matching bids-labels which exist in one modality but not in the other
                match = False

        # Stop searching if we found a matching series (i.e. which is the case if match is still True after all item tests)
        # TODO: maybe count how many instances, could perhaps be useful info
        if match:
            return True

    return False


def delete_series(bidsmap: dict, source: str, modality: str, index: int) -> dict:
    """
    Delete a series from the BIDS map

    :param bidsmap:     Full BIDS bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param source:      The information source in the bidsmap that is used, e.g. 'DICOM'
    :param modality:    The modality in the source that is used, e.g. 'anat'
    :param index:       The index number of the series (listitem) that is deleted from the modality
    :return:            The new bidsmap
    """

    if not modality in bidsmodalities + (unknownmodality,):
        raise ValueError(f"invalid modality '{modality}'")

    bidsmap_dicom = bidsmap.get(source, {})
    bidsmap_dicom_modality = bidsmap_dicom.get(modality, None)

    if bidsmap_dicom_modality is not None:
        num_series = len(bidsmap_dicom_modality)
    else:
        num_series = 0
    if index > num_series:
        raise IndexError(f"invalid index {index} ({num_series+1} items found)")

    if bidsmap_dicom_modality is not None:
        del bidsmap[source][modality][index]
    else:
        logger.warning(f'modality not found {modality}')

    return bidsmap


def append_series(bidsmap: dict, source: str, modality: str, series: dict) -> dict:
    """
    Append a series to the BIDS map

    :param bidsmap:     Full BIDS bidsmap data structure, with all options, BIDS labels and attributes, etc
    :param source:      The information source in the bidsmap that is used, e.g. 'DICOM'
    :param modality:    The modality in the source that is used, e.g. 'anat'
    :param series:      The series (listitem) that is appenden to the modality
    :return:            The new bidsmap
    """

    if not modality in bidsmodalities + (unknownmodality,):
        raise ValueError(f"invalid modality '{modality}'")

    if bidsmap[source][modality] is None:
        bidsmap[source][modality] = [series]
    else:
        bidsmap[source][modality].append(series)

    return bidsmap


def get_matching_dicomseries(dicomfile: str, bidsmap: dict) -> dict:
    """
    Find the matching series in the bidsmap heuristics using the dicom attributes. Then fill-in the missing values (values are cleaned-up to be BIDS-valid)

    :param dicomfile:   The full pathname of the dicom-file
    :param bidsmap:     Full BIDS bidsmap data structure, with all options, BIDS labels and attributes, etc
    :return:            The matching and filled-in series item and modality (NB: not run_index) from the bidsmap {'series': series, 'modality': modality}
    """

    # TODO: generalize for non-DICOM (dicomfile -> file)?
    source = 'DICOM'

    # Loop through all bidsmodalities and series; all info goes into series_
    for modality in bidsmodalities + (unknownmodality,):
        if bidsmap[source][modality] is None: continue

        for series in bidsmap[source][modality]:

            series_ = dict(provenance={}, attributes={}, bids={})                                           # The CommentedMap API is not guaranteed for the future so keep this line as an alternative
            match   = any([series['attributes'][key] is not None for key in series['attributes']])          # Make match False if all attributes are empty

            # Try to see if the dicomfile matches all of the attributes and fill all of them
            for attrkey in series['attributes']:

                attrvalue  = series['attributes'][attrkey]
                dicomvalue = get_dicomfield(attrkey, dicomfile)

                # Check if the attribute value matches with the info from the dicomfile
                if attrvalue:
                    if not dicomvalue:
                        match = False
                    elif isinstance(attrvalue, list):                     # The user-edited 'wildcard' option
                        match = match and any([attrvalue_ in dicomvalue for attrvalue_ in attrvalue])
                    else:
                        match = match and attrvalue==dicomvalue

                # Fill the empty attribute with the info from the dicomfile
                series_['attributes'][attrkey] = dicomvalue

            # Try to fill the bids-labels
            for key in series['bids']:
                bidsvalue = series['bids'][key]
                if not bidsvalue:
                    series_['bids'][key] = bidsvalue

                # Intelligent filling of the value is done runtime by bidscoiner
                elif bidsvalue.startswith('<<') and bidsvalue.endswith('>>'):
                    series_['bids'][key] = bidsvalue

                # Fill any bids-label with the <annotated> dicom attribute
                elif bidsvalue.startswith('<') and bidsvalue.endswith('>'):
                    label        = get_dicomfield(bidsvalue[1:-1], dicomfile)
                    series_['bids'][key] = cleanup_label(label)

                else:
                    series_['bids'][key] = cleanup_label(bidsvalue)

                # SeriesDescriptions (and ProtocolName?) may get a suffix like '_SBRef' from the vendor, try to strip it off
                series_ = strip_suffix(series_)

            # Stop searching the bidsmap if we have a match
            if match:
                # TODO: check if there are more matches (i.e. conflicts)
                series_['provenance'] = dicomfile
                return {'series': series_, 'modality': modality}

    # We don't have a match (all tests failed, so modality should be the last one, i.e. unknownmodality)
    series_['provenance'] = dicomfile
    return {'series': series_, 'modality': modality}


def get_bidsname(subid: str, sesid: str, modality: str, series: dict, run: str='', subprefix: str='sub-', sesprefix: str='ses-') -> str:
    """
    Composes a filename as it should be according to the BIDS standard using the BIDS labels in series

    :param subid:       The subject identifier, i.e. name of the subject folder (e.g. 'sub-001' or just '001'). Can be left empty
    :param sesid:       The optional session identifier, i.e. name of the session folder (e.g. 'ses-01' or just '01'). Can be left empty
    :param modality:    The bidsmodality (choose from bids.bidsmodalities)
    :param series:      The series mapping with the BIDS labels
    :param run:         The optional runindex label (e.g. 'run-01'). Can be left ''
    :param subprefix:   The optional subprefix (e.g. 'sub-'). Used to parse the sub-value from the provenance as default subid
    :param sesprefix:   The optional sesprefix (e.g. 'ses-'). If it is found in the provenance then a default sesid will be set
    :return:            The composed BIDS file-name (without file-extension)
    """
    assert modality in bidsmodalities + (unknownmodality,)

    # Add default value for subid and sesid (e.g. for the bidseditor)
    if not subid:
        subid = os.path.dirname(series['provenance']).rsplit(os.sep + subprefix)[1].split(os.sep)[0]
    if not sesid and os.sep + sesprefix in series['provenance']:
        sesid = os.path.dirname(series['provenance']).rsplit(os.sep + sesprefix)[1].split(os.sep)[0]

    # Add sub- and ses- prefixes if they are not there
    subid = 'sub-' + subid.lstrip('sub-')
    if sesid:
        sesid = 'ses-' + sesid.lstrip('ses-')

    # Do some checks to allow for dragging the series entries between the different modality-sections
    for bidslabel in bidslabels:
        if bidslabel not in series['bids']: series['bids'][bidslabel] = ''

    # Compose the BIDS filename (-> switch statement)
    if modality == 'anat':

        defacemask = False       # TODO: account for the 'defacemask' possibility
        if defacemask:
            suffix = 'defacemask'
            mod    = series['bids']['suffix']
        else:
            suffix = series['bids']['suffix']
            mod    = ''

        # bidsname: sub-<participant_label>[_ses-<session_label>][_acq-<label>][_ce-<label>][_rec-<label>][_run-<index>][_mod-<label>]_suffix
        bidsname = '{sub}{_ses}{_acq}{_ce}{_rec}{_run}{_mod}_{suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            _acq    = add_prefix('_acq-', series['bids']['acq_label']),
            _ce     = add_prefix('_ce-', series['bids']['ce_label']),
            _rec    = add_prefix('_rec-', series['bids']['rec_label']),
            _run    = add_prefix('_run-', run),
            _mod    = add_prefix('_mod-', mod),
            suffix  = suffix)

    elif modality == 'func':

        # bidsname: sub-<participant_label>[_ses-<session_label>]_task-<task_label>[_acq-<label>][_rec-<label>][_run-<index>][_echo-<index>]_suffix
        bidsname = '{sub}{_ses}_{task}{_acq}{_rec}{_run}{_echo}_{suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            task    = f"task-{series['bids']['task_label']}",
            _acq    = add_prefix('_acq-', series['bids']['acq_label']),
            _rec    = add_prefix('_rec-', series['bids']['rec_label']),
            _run    = add_prefix('_run-', run),
            _echo   = add_prefix('_echo-', series['bids']['echo_index']),
            suffix  = series['bids']['suffix'])

    elif modality == 'dwi':

        # bidsname: sub-<participant_label>[_ses-<session_label>][_acq-<label>][_run-<index>]_suffix
        bidsname = '{sub}{_ses}{_acq}{_run}_{suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            _acq    = add_prefix('_acq-', series['bids']['acq_label']),
            _run    = add_prefix('_run-', run),
            suffix  = series['bids']['suffix'])

    elif modality == 'fmap':

        # TODO: add more fieldmap logic?

        # bidsname: sub-<participant_label>[_ses-<session_label>][_acq-<label>][_dir-<dir_label>][_run-<run_index>]_suffix
        bidsname = '{sub}{_ses}{_acq}{_dir}{_run}_{suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            _acq    = add_prefix('_acq-', series['bids']['acq_label']),
            _dir    = add_prefix('_dir-', series['bids']['dir_label']),
            _run    = add_prefix('_run-', run),
            suffix  = series['bids']['suffix'])

    elif modality == 'beh':

        # bidsname: sub-<participant_label>[_ses-<session_label>]_task-<task_name>_suffix
        bidsname = '{sub}{_ses}_{task}_{suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            task    = f"task-{series['bids']['task_label']}",
            suffix  = series['bids']['suffix'])

    elif modality == 'pet':

        # bidsname: sub-<participant_label>[_ses-<session_label>]_task-<task_label>[_acq-<label>][_rec-<label>][_run-<index>]_suffix
        bidsname = '{sub}{_ses}_{task}{_acq}{_rec}{_run}_{suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            task    = f"task-{series['bids']['task_label']}",
            _acq    = add_prefix('_acq-', series['bids']['acq_label']),
            _rec    = add_prefix('_rec-', series['bids']['rec_label']),
            _run    = add_prefix('_run-', run),
            suffix  = series['bids']['suffix'])

    elif modality == unknownmodality:

        # bidsname: sub-<participant_label>[_ses-<session_label>]_acq-<label>[..][_suffix]
        bidsname = '{sub}{_ses}_{acq}{_ce}{_rec}{_task}{_echo}{_dir}{_run}{_suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            acq     = f"acq-{series['bids']['acq_label']}",
            _ce     = add_prefix('_ce-', series['bids']['ce_label']),
            _rec    = add_prefix('_rec-', series['bids']['rec_label']),
            _task   = add_prefix('_task-',series['bids']['task_label']),
            _echo   = add_prefix('_echo-', series['bids']['echo_index']),
            _dir    = add_prefix('_dir-', series['bids']['dir_label']),
            _run    = add_prefix('_run-', run),
            _suffix = add_prefix('_', series['bids']['suffix']))

    else:
        raise ValueError(f'Critical error: modality "{modality}" not implemented, please inform the developers about this error')

    return bidsname


def set_bidslabel(bidsname: str, bidskey: str, newvalue: str='') -> str:
    """
    Sets the bidslabel, i.e. '*_bidskey-*_' is replaced with '*_bidskey-bidsvalue_'. If the key is not in the bidsname
    then the newvalue is appended to the acquisition label. If newvalue is empty (= default), then the parsed existing
    bidsvalue is returned and nothing is set

    :param bidsname:    The bidsname (e.g. as returned from get_bidsname or fullpath)
    :param bidskey:     The name of the bidskey, e.g. 'echo'
    :param newvalue:    The new bidsvalue
    :return:            The bidsname with the new bidsvalue or, if newvalue is empty, the existing bidsvalue
    """

    newvalue = cleanup_label(newvalue)
    pathname = os.path.dirname(bidsname)
    bidsname = os.path.basename(bidsname)

    # Get the existing bidsvalue
    oldvalue = ''
    acqvalue = ''
    for label in bidsname.split('_'):
        if '-' in str(label):
            key, value = str(label).split('-', 1)
            if key == bidskey:
                oldvalue = value
            if key == 'acq':
                acqvalue = value

    # Replace the existing bidsvalue with the new value or append the newvalue to the acquisition value
    if newvalue:
        if f'_{bidskey}-' not in bidsname:
            bidskey  = 'acq'
            oldvalue = acqvalue
            newvalue = acqvalue + newvalue
        return os.path.join(pathname, bidsname.replace(f'{bidskey}-{oldvalue}', f'{bidskey}-{newvalue}'))

    # Or just return the parsed old bidsvalue
    else:
        return oldvalue


def increment_runindex(bidsfolder: str, bidsname: str, ext: str='.*') -> str:
    """
    Checks if a file with the same the bidsname already exists in the folder and then increments the runindex (if any)
    until no such file is found

    :param bidsfolder:  The full pathname of the bidsfolder
    :param bidsname:    The bidsname with a provisional runindex
    :param ext:         The file extension for which the runindex is incremented (default = '.*')
    :return:            The bidsname with the incremented runindex
    """

    if not '_run-' in bidsname:
        return bidsname

    while glob.glob(os.path.join(bidsfolder, bidsname + ext)):

        basename, runindex = bidsname.rsplit('_run-', 1)
        if '_' in runindex:
            runindex, suffix = runindex.split('_',1)
            suffix = '_' + suffix
        else:
            suffix = ''

        bidsname = f'{basename}_run-{int(runindex) + 1}{suffix}'

    return bidsname
