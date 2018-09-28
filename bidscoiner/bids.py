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
import inspect
import datetime
import textwrap
import re
from ruamel.yaml import YAML
yaml = YAML()

bidsmodalities  = ('anat', 'func', 'dwi', 'fmap', 'beh')
unknownmodality = 'extra_data'


def printlog(message, logfile=None):
    """
    Print an annotated log-message to screen and optionally to a logfile

    :param str message: The output text
    :param str logfile: The full pathname of the logile
    :return:            Nothing
    :rtype: NoneType
    """

    # Get the name of the calling function
    frame  = inspect.stack()[1]
    module = inspect.getmodule(frame[0])
    caller = os.path.basename(module.__file__)

    # Print the logmessage
    logmessage = '\n{time} - {caller}:\n{message}\n'.format(
        time    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        caller  = caller,
        message = textwrap.indent(message, '\t'))
    print(logmessage)

    # Open or create a log-file and write the message
    if logfile:
        with open(logfile, 'a') as log_fid:
            log_fid.write(logmessage)


def lsdirs(folder, wildcard='*'):
    """
    Gets all directories in a folder, ignores files

    :param str folder:   The full pathname of the folder
    :param str wildcard: Simple (glob.glob) shell-style wildcards. Foldernames starting with a dot are special cases that are not matched by '*' and '?' patterns.") wildcard
    :return: folders:    An iterable filter object with all directories in a folder
    :rtype: iterable
    """

    if wildcard:
        folder = os.path.join(folder, wildcard)
    return [fname for fname in sorted(glob.glob(folder)) if os.path.isdir(fname)]


def is_dicomfile(file):
    """
    Checks whether a file is a DICOM-file. It uses the feature that Dicoms have the string DICM hardcoded at offset 0x80.

    :param str file: The full pathname of the file
    :return:         Returns true if a file is a DICOM-file
    :rtype: bool
    """

    if os.path.isfile(file):
        with open(file, 'rb') as dcmfile:
            dcmfile.seek(0x80, 1)
            return dcmfile.read(4) == b'DICM'


def is_dicomfile_siemens(file):
    """
    Checks whether a file is a *SIEMENS* DICOM-file. All Siemens Dicoms contain a dump of the
    MrProt structure. The dump is marked with a header starting with 'ASCCONV BEGIN'. Though
    this check is not foolproof, it is very unlikely to fail.

    :param str file: The full pathname of the file
    :return:         Returns true if a file is a Siemens DICOM-file
    :rtype: bool
    """

    return b'ASCCONV BEGIN' in open(file, 'rb').read()


def is_parfile(file):
    """
    Checks whether a file is a Philips PAR file

    WIP!!!!!!

    :param str file: The full pathname of the file
    :return:         Returns true if a file is a Philips PAR-file
    :rtype: bool
    """

    # TODO: Returns true if filetype is PAR.
    if os.path.isfile(file):
        with open(file, 'r') as parfile:
            pass
        return False


def is_p7file(file):
    """
    Checks whether a file is a GE P*.7 file

    WIP!!!!!!

    :param str file: The full pathname of the file
    :return:         Returns true if a file is a GE P7-file
    :rtype: bool
    """

    # TODO: Returns true if filetype is P7.
    if os.path.isfile(file):
        with open(file, 'r') as p7file:
            pass
        return False


def is_niftifile(file):
    """
    Checks whether a file is a nifti file

    WIP!!!!!!

    :param str file: The full pathname of the file
    :return:         Returns true if a file is a nifti-file
    :rtype: bool
    """

    # TODO: Returns true if filetype is nifti.
    if os.path.isfile(file):
        with open(file, 'r') as niftifile:
            pass
        return False


def is_incomplete_acquisition(folder):
    """
    If a scan was aborted in the middle of the experiment, it is likely that images will be saved
    anyway. We want to avoid converting these incomplete directories. This function checks the number
    of measurements specified in the protocol against the number of imaging files in the folder.

    :param str folder:  The full pathname of the folder
    :return:            Returns true if the acquisition was incomplete
    :rtype: bool
    """

    dicomfile = get_dicomfile(folder)
    nrep      = get_dicomfield('lRepetitions', dicomfile)
    nfiles    = len(os.listdir(folder))     # TODO: filter out non-imaging files

    if nrep and nrep > nfiles:
        warnings.warn('Incomplete acquisition found in: {}'\
                      '\nExpected {}, found {} dicomfiles'.format(folder, nrep, nfiles))
        return True
    else:
        return False


def get_dicomfile(folder):
    """
    Gets a dicom-file from the folder

    :param str folder: The full pathname of the folder
    :return:           The filename of the first dicom-file in the folder.
    :rtype: str
    """

    for file in sorted(os.listdir(folder)):
        if is_dicomfile(os.path.join(folder, file)):
            return os.path.join(folder, file)

    warnings.warn('Cannot find dicom files in:' + folder)
    return None


def get_parfile(folder):
    """
    Gets a Philips PAR-file from the folder

    :param str folder: The full pathname of the folder
    :return:           The filename of the first PAR-file in the folder.
    :rtype: str
    """

    for file in sorted(os.listdir(folder)):
        if is_parfile(file):
            return os.path.join(folder, file)

    warnings.warn('Cannot find PAR files in:' + folder)
    return None


def get_p7file(folder):
    """
    Gets a GE P*.7-file from the folder

    :param str folder: The full pathname of the folder
    :return:           The filename of the first P7-file in the folder.
    :rtype: str
    """

    for file in sorted(os.listdir(folder)):
        if is_p7file(file):
            return os.path.join(folder, file)

    warnings.warn('Cannot find P7 files in:' + folder)
    return None


def get_niftifile(folder):
    """
    Gets a nifti-file from the folder

    :param str folder: The full pathname of the folder
    :return:           The filename of the first nifti-file in the folder.
    :rtype: str
    """

    for file in sorted(os.listdir(folder)):
        if is_niftifile(file):
            return os.path.join(folder, file)

    warnings.warn('Cannot find nifti files in:' + folder)
    return None


def get_heuristics(yamlfile, folder=None):
    """
    Read the heuristics from the bidsmap yaml-file

    :param str yamlfile: The full pathname of the bidsmap yaml-file
    :param str folder:   Searches in the ./heuristics folder if folder=None
    :return:             Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :rtype: ruamel_yaml.comments.CommentedMap
    """

    # Input checking
    if not folder:
        folder = os.path.join(os.path.dirname(__file__),'..','heuristics')

    if not os.path.splitext(yamlfile)[1]:           # Add a standard file-extension if needed
        yamlfile = yamlfile + '.yaml'

    if os.path.basename(yamlfile) == yamlfile:      # Get the full paths to the bidsmap yaml-file
        yamlfile = os.path.join(folder, yamlfile)
        print('Using: ' + os.path.abspath(yamlfile))

    yamlfile = os.path.abspath(os.path.expanduser(yamlfile))

    # Read the heuristics from the bidsmap file
    with open(yamlfile, 'r') as stream:
        heuristics = yaml.load(stream)

    return heuristics


def parse_x_protocol(pattern, dicomfile):
    """
    Siemens writes a protocol structure as text into each DICOM file.
    This structure is necessary to recreate a scanning protocol from a DICOM,
    since the DICOM information alone wouldn't be sufficient.

    :param str pattern:    A regexp expression: '^' + pattern + '\t = \t(.*)\\n'
    :param str dicomfile:  The full pathname of the dicom-file
    :return:               The string extracted values from the dicom-file according to the given pattern
    :rtype: str
    """

    if not is_dicomfile_siemens(dicomfile):
        warnings.warn('Parsing {} may fail because {} does not seem to be a Siemens DICOM file'.format(pattern, dicomfile))

    regexp = '^' + pattern + '\t = \t(.*)\n'
    regex  = re.compile(regexp.encode('utf-8'))

    with open(dicomfile, 'rb') as openfile:
        for line in openfile:
            match = regex.match(line)
            if match:
                return match.group(1).decode('utf-8')

    warnings.warn('Pattern: "' + regexp.encode('unicode_escape').decode() + '" not found in: ' + dicomfile)
    return None


# Profiling shows this is currently the most expensive function, so therefore the (primitive but effective) _DICOMDICT_CACHE optimization
_DICOMDICT_CACHE = None
_DICOMFILE_CACHE = None
def get_dicomfield(tagname, dicomfile):
    """
    Robustly extracts a DICOM field/tag from a dictionary or from vendor specific fields

    :param tagname:       Name of the DICOM field
    :param str dicomfile: The full pathname of the dicom-file
    :return:              Extracted tag-values from the dicom-file
    :rtype: str or int
    """

    import pydicom
    global _DICOMDICT_CACHE, _DICOMFILE_CACHE

    try:
        if dicomfile != _DICOMFILE_CACHE:
            dicomdict        = pydicom.dcmread(dicomfile)
            _DICOMDICT_CACHE = dicomdict
            _DICOMFILE_CACHE = dicomfile
        else:
            dicomdict = _DICOMDICT_CACHE

        value = dicomdict.get(tagname)

    except IOError:
        warnings.warn('Cannot read' + dicomfile)

    except Exception:
        try:
            value = parse_x_protocol(tagname, dicomfile)

        except Exception:
            value = None
            warnings.warn('Could not extract {} tag from {}'.format(tagname, dicomfile))

    # Cast the dicom datatype to standard to int or str (i.e. to something that yaml.dump can handle)
    if not value:
        return

    elif isinstance(value, int):
        return int(value)

    elif not isinstance(value, str):    # Assume it's a MultiValue type and flatten it
        return str(value)

    else:
        return str(value)


def add_prefix(prefix, tag):
    """
    Simple function to account for optional BIDS tags in the bids file names, i.e. it prefixes 'prefix' only when tag is not empty

    :param str prefix:  The prefix (e.g. '_sub-')
    :param str tag:     The tag (e.g. 'control01')
    :return             The tag with the leading prefix (e.g. '_sub-control01') or just the empty tag ''
    :rtype: str
    """

    if tag:
        tag = prefix + tag
    else:
        tag = ''

    return tag


def strip_suffix(series):
    """
    Certain attributes such as SeriesDescriptions (but not ProtocolName!?) may get a suffix like '_SBRef' from the vendor,
    try to strip it off from the BIDS labels

    :param dict series: The series with potentially added suffixes that are the same as the BIDS suffixes
    :return:            The series with these suffixes removed
    :rtype: dict
    """

    # See if we have a suffix for this modality
    if 'suffix' in series:
        suffix = series['suffix'].lower()
    elif 'modality_label' in series:
        suffix = series['modality_label'].lower()
    else:
        return series

    # See if any of the BIDS labels ends with the same suffix. If so, then remove it
    for key in series:
        if key in ('attributes', 'modality_label', 'suffix'):
            continue
        if series[key] and (series[key].lower().endswith('_' + suffix) or series[key].lower().endswith('.' + suffix)):
            series[key] = series[key][0:-len(suffix)-1]

    return series


def cleanup_label(label):
    """
    Converts a given label to a cleaned-up label that can be used as a BIDS label. Remove leading and trailing spaces;
    convert other spaces, special BIDS characters and anything that is not an alphanumeric to a ''. This will for
    example map "Joe's reward_task" to "Joesrewardtask"

    :param str label: The given label that potentially contains undesired characters
    :return:          The cleaned-up / BIDS-valid label
    :rtype: str
    """

    special_characters = (' ', '_', '-','.')

    for special in special_characters:
        label = str(label).strip().replace(special, '')

    return re.sub(r'(?u)[^-\w.]', '', label)


def exist_series(series, serieslist, matchbidslabels=True):
    """
    Checks if there is already an entry in serieslist with the same attributes and, optionally, labels as series

    :param dict series:          The series labels and attributes that are to be searched for
    :param list serieslist:      List of series that is being searched
    :param bool matchbidslabels: If True, also matches the BIDS-labels, otherwise only series['attributes']
    :return:                     True if the series exists in serieslist
    :rtype: bool
    """

    for item in serieslist:

        match = any([series['attributes'][key] is not None for key in series['attributes']])  # Make match False if all attributes are empty

        # Search for a case where all series items match with the series items
        for key in series:

            try:
                if key == 'attributes':

                    for attrkey in series['attributes']:
                        seriesvalue = series['attributes'][attrkey]
                        itemvalue   = item['attributes'][attrkey]
                        match       = match and (seriesvalue == itemvalue)

                elif matchbidslabels:

                    seriesvalue = series[key]
                    itemvalue   = item[key]
                    match       = match and (seriesvalue == itemvalue)

            except KeyError:    # Errors may be evoked when matching bids-labels which exist in one modality but not in the other
                match = False

            if not match:       # There is no point in searching further within the series now that we've found a mismatch
                break

        # Stop searching if we found a matching series (i.e. which is the case if match is still True after all item tests)
        # TODO: maybe count how many instances, could perhaps be useful info
        if match:
            return True

    return False


def get_matching_dicomseries(dicomfile, heuristics):
    """
    Find the matching series in the bidsmap heuristics using the dicom attributes. Then fill-in the missing values (values are cleaned-up to be BIDS-valid)

    :param str dicomfile:   The full pathname of the dicom-file
    :param dict heuristics: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The matching and filled-in series item and modality (NB: not run_index) from the heuristics {'series': series, 'modality': modality}
    :rtype: dict
    """

    # TODO: generalize for non-DICOM (dicomfile -> file)?

    # Loop through all bidsmodalities and series; all info goes into series_
    for modality in bidsmodalities + (unknownmodality,):
        if not heuristics['DICOM'][modality]: continue

        for series in heuristics['DICOM'][modality]:

            series_ = dict(attributes={})           # Creating a new object is safe in that we don't change the original heuristics object. However, we lose all comments and formatting within the series (which is not such a disaster probably). It is also much faster and more robust with aliases compared with a deepcopy
            match   = any([series['attributes'][key] is not None for key in series['attributes']])  # Make match False if all attributes are empty

            for key in series:

                # Try to see if the dicomfile matches all of the attributes and fill all of them
                if key == 'attributes':

                    for attrkey in series['attributes']:

                        attrvalue  = series['attributes'][attrkey]
                        dicomvalue = get_dicomfield(attrkey, dicomfile)

                        # Check if the attribute value matches with the info from the dicomfile
                        if attrvalue:
                            if not dicomvalue:
                                match = False
                            elif isinstance(attrvalue, int):
                                match = match and attrvalue == dicomvalue
                            elif isinstance(attrvalue, list):
                                match = match and any([attrvalue_ in dicomvalue for attrvalue_ in attrvalue])
                            else:
                                match = match and (attrvalue in dicomvalue)

                        # Fill the empty attribute with the info from the dicomfile
                        series_['attributes'][attrkey] = dicomvalue

                # Try to fill the bids-labels
                else:

                    bidsvalue = series[key]
                    if not bidsvalue:
                        series_[key] = bidsvalue

                    # Intelligent filling of the value is done runtime by bidscoiner
                    elif bidsvalue.startswith('<<') and bidsvalue.endswith('>>'):
                        series_[key] = bidsvalue

                    # Fill any bids-label with the <annotated> dicom attribute
                    elif bidsvalue.startswith('<') and bidsvalue.endswith('>'):
                        label        = get_dicomfield(bidsvalue[1:-1], dicomfile)
                        series_[key] = cleanup_label(label)

                    else:
                        series_[key] = cleanup_label(bidsvalue)

                # SeriesDescriptions (and ProtocolName?) may get a suffix like '_SBRef' from the vendor, try to strip it off
                series_ = strip_suffix(series_)

            # Stop searching the heuristics if we have a match
            if match:
                # TODO: check if there are more matches (i.e. conflicts)
                return {'series': series_, 'modality': modality}

    # We don't have a match (all tests failed, so modality should be the last one, i.e. unknownmodality)

    return {'series': series_, 'modality': modality}


def get_bidsname(subid, sesid, modality, series, run=''):
    """
    Composes a filename as it should be according to the BIDS standard using the BIDS labels in series

    :param str subid:       The subject identifier, i.e. name of the subject folder (e.g. 'sub-01')
    :param str sesid:       The optional session identifier, i.e. name of the session folder (e.g. 'sub-01'). Can be left ''
    :param str modality:    The bidsmodality (choose from bids.bidsmodalities)
    :param dict series:     The series mapping with the BIDS labels
    :param str run:         The optional runindex label (e.g. 'run-01'). Can be left ''
    :return:                The composed BIDS file-name (without file-extension)
    :rtype: str
    """

    # Compose the BIDS filename (-> switch statement)
    if modality == 'anat':

        defacemask = False       # TODO: account for the 'defacemask' possibility
        if defacemask:
            suffix = 'defacemask'
            mod    = series['modality_label']
        else:
            suffix = series['modality_label']
            mod    = ''

        # bidsname: sub-<participant_label>[_ses-<session_label>][_acq-<label>][_ce-<label>][_rec-<label>][_run-<index>][_mod-<label>]_suffix
        bidsname = '{sub}{_ses}{_acq}{_ce}{_rec}{_run}{_mod}_{suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            _acq    = add_prefix('_acq-', series['acq_label']),
            _ce     = add_prefix('_ce-', series['ce_label']),
            _rec    = add_prefix('_rec-', series['rec_label']),
            _run    = add_prefix('_run-', run),
            _mod    = add_prefix('_mod-', mod),
            suffix  = suffix)

    elif modality == 'func':

        # bidsname: sub-<participant_label>[_ses-<session_label>]_task-<task_label>[_acq-<label>][_rec-<label>][_run-<index>][_echo-<index>]_suffix
        bidsname = '{sub}{_ses}_{task}{_acq}{_rec}{_run}{_echo}_{suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            task    = 'task-' + series['task_label'],
            _acq    = add_prefix('_acq-', series['acq_label']),
            _rec    = add_prefix('_rec-', series['rec_label']),
            _run    = add_prefix('_run-', run),
            _echo   = add_prefix('_echo-', series['echo_index']),
            suffix  = series['suffix'])

    elif modality == 'dwi':

        # bidsname: sub-<participant_label>[_ses-<session_label>][_acq-<label>][_run-<index>]_suffix
        bidsname = '{sub}{_ses}{_acq}{_run}_{suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            _acq    = add_prefix('_acq-', series['acq_label']),
            _run    = add_prefix('_run-', run),
            suffix  = series['suffix'])

    elif modality == 'fmap':

        # TODO: add more fieldmap logic?

        # bidsname: sub-<participant_label>[_ses-<session_label>][_acq-<label>][_dir-<dir_label>][_run-<run_index>]_suffix
        bidsname = '{sub}{_ses}{_acq}{_dir}{_run}_{suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            _acq    = add_prefix('_acq-', series['acq_label']),
            _dir    = add_prefix('_dir-', series['dir_label']),
            _run    = add_prefix('_run-', run),
            suffix  = series['suffix'])

    elif modality == 'beh':

        # bidsname: sub-<participant_label>[_ses-<session_label>]_task-<task_name>_suffix
        bidsname = '{sub}{_ses}_{task}_{suffix}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            task    = 'task-' + series['task_name'],
            suffix  = series['suffix'])

    elif modality == unknownmodality:

        # bidsname: sub-<participant_label>[_ses-<session_label>]_acq-<label>[_run-<index>]
        bidsname = '{sub}{_ses}_{acq}{_run}'.format(
            sub     = subid,
            _ses    = add_prefix('_', sesid),
            acq     = 'acq-' + series['acq_label'],
            _run    = add_prefix('_run-', run))

    else:
        raise ValueError('Critical error: Invalid modality "{}" found'.format(modality))

    return bidsname


def set_bidslabel(bidsname, bidskey, newvalue=''):
    """
    Sets the bidslabel, i.e. '*_bidskey-*_' is replaced with '*_bidskey-bidsvalue_'. If the key is not in the bidsname
    then the newvalue is appended to the acquisition label. If newvalue is empty (= default), then the parsed existing
    bidsvalue is returned and nothing is set

    :param str bidsname:    The bidsname (e.g. as returned from get_bidsname or fullpath)
    :param str bidskey:     The name of the bidskey, e.g. 'echo'
    :param str newvalue:    The new bidsvalue
    :return:                The bidsname with the new bidsvalue or, if newvalue is empty, the existing bidsvalue
    :rtype: str
    """

    newvalue = cleanup_label(newvalue)
    pathname = os.path.dirname(bidsname)
    bidsname = os.path.basename(bidsname)

    # Get the existing bidsvalue
    acqkey   = 'acq'
    acqvalue = ''
    oldvalue = ''
    for label in bidsname.split('_'):
        if '-' in str(label):
            key, value = str(label).split('-', 1)
            if key == bidskey:
                oldvalue = value
            if key == acqkey:
                acqvalue = value

    # Replace the existing bidsvalue with the new value or append the newvalue to the acquisition value
    if newvalue:
        if not oldvalue and acqvalue:
            bidskey  = acqkey
            oldvalue = acqvalue
            newvalue = acqvalue + newvalue
        return os.path.join(pathname, bidsname.replace(bidskey + '-' + oldvalue, bidskey + '-' + newvalue))

    # Or just return the parsed old bidsvalue
    else:
        return oldvalue


def increment_runindex(bidsfolder, bidsname, ext='.*'):
    """
    Checks if a file with the same the bidsname already exists in the folder and then increments the runindex (if any)
    until no such file is found

    :param str bidsfolder:  The full pathname of the bidsfolder
    :param str bidsname:    The bidsname with a provisional runindex
    :param str ext:         The file extension for which the runindex is incremented (default = '.*')
    :return:                The bidsname with the incremented runindex
    :rtype: str
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

        bidsname = '{basename}_run-{runindex}{suffix}'.format(
            basename = basename,
            runindex = int(runindex) + 1,
            suffix = suffix)

    return bidsname


def askfor_mapping(heuristics, series, filename=''):
    """
    Ask the user for help to resolve the mapping from the series attributes to the BIDS labels
    WIP!!!

    :param dict heuristics: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param dict series:     Dictionary with BIDS labels and attributes
    :param str filename:    The full-path name of the sourcefile for which the attributes could not be 'bidsmapped'
    :return:                Dictionary with return variables: {'modality':name of the modality, 'series': dictionary with the filled-in series labels and attributes}
    :rtype: dict
    """

    # Go through the BIDS structure as a decision tree
    # 1: Show all the series-info
    # 2: Ask: Which of the heuristics modalities is it?
    # 3: Ask: Which func suffix, anat modality, etc

    #  TODO: implement code

    return None # {'modality': modality, 'series': series}


def askfor_append(modality, series, bidsmapfile):
    """
    Ask the user to add the labelled series to their bidsmap yaml-file or send it to a central database
    WIP!!!

    :param str modality:    Name of the BIDS modality
    :param dict series:     Dictionary with BIDS labels and attributes
    :param str bidsmapfile: The full-path name of the bidsmap yaml-file to which the series should be saved
    :return:                Nothing
    :rtype: NoneType
    """

    # TODO: implement code

    return None
