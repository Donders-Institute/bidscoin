#!/usr/bin/env python
"""
Creates a bidsmap.yaml config file that maps the information from the data to the
BIDS modalities and BIDS labels (see also [bidsmapper.yaml] and [bidsmapper.py]).
You can edit the bidsmap file before passing it to [bidscoiner.py] which uses it
to cast the datasets into the BIDS folder structure

Derived from dac2bids.py from Daniel Gomez 29.08.2016
https://github.com/dangom/dac2bids/blob/master/dac2bids.py

@author: marzwi
"""

# Global imports (specific modules may be imported when needed)
import os.path
import glob
import warnings
import re
import textwrap
import copy
from ruamel_yaml import YAML
yaml = YAML()

bidsmodalities  = ('anat', 'func', 'beh', 'dwi', 'fmap')
unknownmodality = 'unknown'

# -----------------------------------------------------------------------------
# Will need to create a nifti file for each directory in folder.
# Note the implicit assumption that all folders contain only one series,
# echo or whatever.
# To do that, check some information from the dicom.
#
# To build a bidsmap.yaml file, we need the following info:
# 1. Is the imaging data going to anat, func, fmap, dwi or unknown?
# 2. Which imaging modality is it? (e.g. T1w, FLAIR, etc)
# 3. What kind of acquisition is it
#    - e.g. MB or MBME?
#    - What echo is it?
#    - Is it a magnitude or phase image?!
# 4. If func, is it resting-state or task? For that we'll have to
#    find and parse the stimulus presentation logfiles
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

def lsdirs(folder, wildcard='*'):
    """
    List all directories in a folder, ignores files
    :param folder:
    :param wildcard:
    :return:
    """
    return filter(lambda x:
                  os.path.isdir(os.path.join(folder, x)),
                  glob.glob(os.path.join(folder, wildcard)))


def is_dicomfile(file):
    """
    Returns true if a file is a DICOM. Dicoms have the string DICM hardcoded at offset 0x80.
    """
    if os.path.isfile(file):
        with open(file, 'rb') as dcmfile:
            dcmfile.seek(0x80, 1)
            return dcmfile.read(4) == b'DICM'


def is_dicomfile_siemens(dicomfile):
    """
    All Siemens Dicoms contain a dump of the MrProt structure.
    The dump is marked with a header starting with 'ASCCONV BEGIN'.
    Though this check is not foolproof, it is very unlikely to fail.
    """
    return b'ASCCONV BEGIN' in open(dicomfile, 'rb').read()


def is_parfile(file):
    # TODO: Returns true if filetype is PAR.
    if os.path.isfile(file):
        with open(file, 'r') as parfile:
            pass
        return False


def is_p7file(file):
    # TODO: Returns true if filetype is P7.
    if os.path.isfile(file):
        with open(file, 'r') as p7file:
            pass
        return False


def is_niftifile(file):
    # TODO: Returns true if filetype is nifti.
    if os.path.isfile(file):
        with open(file, 'r') as niftifile:
            pass
        return False


def get_dicom_file(folder):
    """
    Returns the first dicom file from a folder.
    """
    for file in os.listdir(folder):
        if is_dicomfile(os.path.join(folder, file)):
            return os.path.join(folder, file)

    warnings.warn('Cannot find dicom files in:' + folder)
    return None


def get_par_file(folder):
    """
    Returns the first PAR file from a folder.
    """
    for file in os.listdir(folder):
        if is_parfile(file):
            return os.path.join(folder, file)

    warnings.warn('Cannot find PAR files in:' + folder)
    return None


def get_p7_file(folder):
    """
    Returns the first P7 file from a folder.
    """
    for file in os.listdir(folder):
        if is_p7file(file):
            return os.path.join(folder, file)

    warnings.warn('Cannot find P7 files in:' + folder)
    return None


def get_nifti_file(folder):
    """
    Returns the first nifti file from a folder.
    """
    for file in os.listdir(folder):
        if is_niftifile(file):
            return os.path.join(folder, file)

    warnings.warn('Cannot find nifti files in:' + folder)
    return None


def parse_from_x_protocol(pattern, dicomfile):
    """
    Siemens writes a protocol structure as text into each DICOM file.
    This structure is necessary to recreate a scanning protocol from a DICOM,
    since the DICOM information alone wouldn't be sufficient.
    This function extracts values from the dicomfile according to a given pattern.
    """
    if not is_dicomfile_siemens(dicomfile):
        warnings.warn('This does not seem to be a Siemens DICOM file')

    regexp = '^' + pattern + '\t = \t(.*)\n'
    regex  = re.compile(regexp.encode('utf-8'))

    with open(dicomfile, 'rb') as openfile:
        for line in openfile:
            match = regex.match(line)
            if match:
                return match.group(1).decode('utf-8')

    warnings.warn('Pattern: "' + regexp.encode('unicode_escape').decode() + '" not found in: ' + dicomfile)
    return None


_DICOMDICT_MEMO = None
_DICOMFILE_MEMO = None
def get_dicomfield(tagname, dicomfile):
    """
    Robustly reads a DICOM tag from a dictionary or from vendor specific fields
    NB: profiling shows this is currently the most expensive function, so therefore
    the (primitive but effective) _DICOMDICT_MEMO optimization
    :param tagname:
    :param dicomfile:
    :return:
    """
    import pydicom
    global _DICOMDICT_MEMO, _DICOMFILE_MEMO

    try:

        if dicomfile != _DICOMFILE_MEMO:
            dicomdict       = pydicom.dcmread(dicomfile)
            _DICOMDICT_MEMO = dicomdict
            _DICOMFILE_MEMO = dicomfile
        else:
            dicomdict = _DICOMDICT_MEMO

        # TODO: implement regexp
        value = dicomdict.get(tagname)

    except IOError: warnings.warn('Cannot read' + dicomfile)
    except Exception:
        try:

            value = parse_from_x_protocol(tagname, dicomfile)

        except Exception:

            value = None
            warnings.warn('Could not extract {} tag from {}'.format(tagname, dicomfile))

    # Cast the dicom datatype to standard to int or str (i.e. to something that yaml.dump can handle)
    if isinstance(value, int):
        return int(value)

    elif not isinstance(value, str):    # Assume it's a MultiValue type and flatten it (TODO: deal with this properly)
        return str(value)

    else:
        return str(value)


def get_heuristics(yamlfile):

    # Get the full paths to the bidsmapper yaml-file and add a standard file-extension if needed
    if os.path.basename(yamlfile) == yamlfile:
        yamlfile = os.path.join(os.path.dirname(__file__), 'heuristics', yamlfile)
    if not os.path.splitext(yamlfile)[1] and not os.path.exists(yamlfile):
        yamlfile = yamlfile + '.yaml'

    # Read the heuristics from the bidsmapper files
    with open(yamlfile, 'r') as stream:
        heuristics = yaml.load(stream)

    return heuristics


def exist_series(series, serieslist, matchbidslabels=True):
    """
    Checks if there is already an entry in [serieslist] with the same attributes and labels as [series]
    :param series:
    :param serieslist:
    :param matchbidslabels:
    :return: Boolean
    """
    for seriesitem in serieslist:

        match = any([series['attributes'][key] is not None for key in series['attributes']])  # Make match False if all attributes are empty

        # Search for a case where all series items match with the seriesitem items
        for item in series:

            try:
                if item=='attributes':

                    for attrkey in series['attributes']:
                        seriesvalue = series['attributes'][attrkey]
                        itemvalue   = seriesitem['attributes'][attrkey]
                        match       = match and (seriesvalue == itemvalue)

                elif matchbidslabels:

                    seriesvalue = series[item]
                    itemvalue   = seriesitem[item]
                    match       = match and (seriesvalue == itemvalue)

            except KeyError:    # Errors may be evoked when matching bids-labels which exist in one modality but not in the other
                match = False

            if not match:       # There is no point in searching further within the series now that we've found a mismatch
                break

        # Stop searching if we found a matching series (i.e. which is the case if match is still True after all item tests)
        if match:
            return True

    return False


def cleanup_label(label):
    """
    Return the given label converted to a label that can be used as a clean BIDS label.
    Remove leading and trailing spaces; convert other spaces, special BIDS characters
    and anything that is not an alphanumeric, dash, underscore, or dot to a dot.
    >> cleanup_label("Joe's reward_task")
    'Joesxreward_task'
    :param label:
    :return: validlabel
    """
    special_characters = (' ', '_', '-',)

    for special in special_characters:
        label = str(label).strip().replace(special, '.')

    return re.sub(r'(?u)[^-\w.]', '.', label)


# -----------------------------------------------------------------------------
# Mapping functions
# -----------------------------------------------------------------------------

def built_dicommap(dicomfile, bidsmap, heuristics):
    """
    All the logic to map dicomfields onto bids labels go into this function
    :param dicomfile:
    :param heuristics:
    :return: bidsmap
    """

    # Input checks
    if not dicomfile or not heuristics['DICOM']:
        return bidsmap

    # Loop through all bidsmodalities and series; all info goes into series_
    for bidsmodality in bidsmodalities:
        for series in heuristics['DICOM'][bidsmodality]:

            # series_ = copy.deepcopy(series)       # NB: Deepcopy makes sure we don't change the original heuristics object, however, it is a very expensive operation.
            series_ = dict(attributes={})           # NB: This way is also safe, however, we loose all comments and formatting within the series (which is not such a disaster probably)
            match   = any([series['attributes'][key] is not None for key in series['attributes']])   # Make match False if all attributes are empty
            for item in series:

                # Try to see if the dicomfile matches all of the attributes and try to fill all of them
                if item == 'attributes':

                    for attrkey in series['attributes']:

                        attrvalue  = series['attributes'][attrkey]
                        dicomvalue = get_dicomfield(attrkey, dicomfile)

                        # Check if the attribute value matches with the info from the dicomfile
                        if attrvalue:
                            if isinstance(attrvalue, list):
                                match = match and any([attrvalue_ in dicomvalue for attrvalue_ in attrvalue])    # TODO: implement regexp
                            else:
                                match = match and (attrvalue in dicomvalue)         # TODO: implement regexp

                        # Fill the empty attribute with the info from the dicomfile
                        series_['attributes'][attrkey] = dicomvalue

                # Try to fill the bids-labels
                else:

                    bidsvalue = series[item]
                    if not bidsvalue:
                        series_[item] = bidsvalue

                    # Intelligent filling of the run-index is done runtime by bidscoiner
                    elif item == 'run_index' and bidsvalue == '<automatic>':
                        series_[item] = bidsvalue

                    # Fill any bids-label with the <annotated> dicom attribute
                    elif bidsvalue.startswith('<') and bidsvalue.endswith('>'):
                        label         = get_dicomfield(bidsvalue[1:-1], dicomfile)
                        series_[item] = cleanup_label(label)

                    else:
                        series_[item] = bidsvalue

            # If we have a match, copy the filled-in series over to the bidsmap as a standard bidsmodality and we are done!
            if match:
                if bidsmap['DICOM'][bidsmodality] is None:
                    bidsmap['DICOM'][bidsmodality] = [series_]
                elif not exist_series(series_, bidsmap['DICOM'][bidsmodality]):
                    bidsmap['DICOM'][bidsmodality].append(series_)

                return bidsmap

    # If nothing matched, copy the filled-in attributes series over to the bidsmap as an unknown modality and fill the unknown labels
    unknownseries = dict()      # Here we loose comments and formatting from the bidsmapper, but that is probably very minor
    for item in heuristics['DICOM'][unknownmodality]:
        if item == 'attributes':

            # Taking the last tested series is a convenient but arbitrary choice (potentially, other series can have different attributes listed in the bidsmapper)
            unknownseries['attributes'] = series_['attributes']

        else:

            unknownvalue = heuristics['DICOM'][unknownmodality][item]
            if not unknownvalue:
                unknownseries[item] = None

            # Intelligent filling of the run-index is done runtime by bidscoiner
            elif item=='run_index' and unknownvalue=='<automatic>':
                unknownseries[item] = '<automatic>'

            # Fill any bids-label with the <annotated> dicom attribute
            elif unknownvalue and unknownvalue.startswith('<') and unknownvalue.endswith('>'):
                label               = get_dicomfield(unknownvalue[1:-1], dicomfile)
                unknownseries[item] = cleanup_label(label)

            else:
                warnings.warn('Do not know what to do with unknown bidsmapper-value:\n {}: {}'.format(item, unknownvalue))
                unknownseries[item] = unknownvalue

    if bidsmap['DICOM'][unknownmodality] is None:
        bidsmap['DICOM'][unknownmodality] = [unknownseries]
    elif not exist_series(unknownseries, bidsmap['DICOM'][unknownmodality]):
        bidsmap['DICOM'][unknownmodality].append(unknownseries)

    return bidsmap


def built_parmap(parfile, bidsmap, heuristics):
    """
    All the logic to map PAR/REC fields onto bids labels go into this function
    :param parfile:
    :param bidsmap:
    :param heuristics:
    :return: bidsmap
    """

    # Input checks
    if not parfile or not heuristics['PAR']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_p7map(p7file, bidsmap, heuristics):
    """
    All the logic to map P7-fields onto bids labels go into this function
    :param pyfile:
    :param bidsmap:
    :param heuristics:
    :return: bidsmap
    """

    # Input checks
    if not p7file or not heuristics['P7']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_niftimap(niftifile, bidsmap, heuristics):
    """
    All the logic to map nifti-info onto bids labels go into this function
    :param niftifile:
    :param bidsmap:
    :param heuristics:
    :return: bidsmap
    """

    # Input checks
    if not niftifile or not heuristics['Nifti']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_filesystemmap(seriesfolder, bidsmap, heuristics):
    """
    All the logic to map filesystem-info onto bids labels go into this function
    :param seriesfolder:
    :param bidsmap:
    :param heuristics:
    :return: bidsmap
    """

    # Input checks
    if not seriesfolder or not heuristics['FileSystem']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_pluginmap(seriesfolder, bidsmap):
    """
    Call the plugin to map info onto bids labels
    :param seriesfolder:
    :param bidsmap:
    :return: bidsmap
    """

    # Input checks
    if not seriesfolder or not bidsmap['PlugIn']:
        return bidsmap

    # Import and run the plugins
    from importlib import import_module
    for pluginfunction in bidsmap['PlugIn']:
        plugin  = import_module(os.path.join(__file__, 'plugins', pluginfunction))
        bidsmap = plugin.map(seriesfolder, bidsmap)

    return bidsmap


def create_bidsmap(rawfolder, bidsfolder, bidsmapper='bidsmapper.yaml'):
    """
    Main function that processes all the subjects and session in the rawfolder
    and that generates a maximally filled-in bidsmap.yaml file in bidsfolder/code.
    Folders in rawfolder are assumed to contain a single dataset.

    :param rawfolder:     folder tree containing folders with dicom files
    :param bidsfolder:    BIDS root folder
    :param bidsmapper:    bidsmapper yaml-file
    :return: bidsmap:     bidsmap.yaml file
    """

    # Input checking
    rawfolder  = os.path.abspath(os.path.expanduser(rawfolder))
    bidsfolder = os.path.abspath(os.path.expanduser(bidsfolder))

    # Get the heuristics for creating the bidsmap
    heuristics = get_heuristics(bidsmapper)

    # Create a copy / bidsmap skeleton with no modality entries (i.e. bidsmapper with empty lists)
    bidsmap = copy.deepcopy(heuristics)
    for logic in ('DICOM', 'PAR', 'P7', 'Nifti', 'FileSystem'):
        for modality in bidsmodalities + (unknownmodality,):

            if bidsmap[logic] and modality in bidsmap[logic]:
                bidsmap[logic][modality] = None

    # Loop over all subjects and sessions and built up the bidsmap entries
    subjects = lsdirs(rawfolder, 'sub-*')
    for subject in subjects:

        sessions = lsdirs(subject, 'ses-*')
        if not sessions:
            sessions = subject
        for session in sessions:

            print('Parsing: ' + session)

            for series in lsdirs(session):

                # Update / append the dicom mapping
                if heuristics['DICOM']:
                    dicomfile = get_dicom_file(series)
                    bidsmap   = built_dicommap(dicomfile, bidsmap, heuristics)

                # Update / append the PAR/REC mapping
                if heuristics['PAR']:
                    parfile   = get_par_file(series)
                    bidsmap   = built_parmap(parfile, bidsmap, heuristics)

                # Update / append the P7 mapping
                if heuristics['P7']:
                    p7file    = get_p7_file(series)
                    bidsmap   = built_p7map(p7file, bidsmap, heuristics)

                # Update / append the nifti mapping
                if heuristics['Nifti']:
                    niftifile = get_nifti_file(series)
                    bidsmap   = built_niftimap(niftifile, bidsmap, heuristics)

                # Update / append the file-system mapping
                if heuristics['FileSystem']:
                    bidsmap   = built_filesystemmap(series, bidsmap, heuristics)

                # Update / append the plugin mapping
                if heuristics['PlugIn']:
                    bidsmap   = built_pluginmap(series, bidsmap)

    # Create the bidsmap yaml-file in bidsfolder/code
    os.makedirs(os.path.join(bidsfolder,'code'), exist_ok=True)
    bidsmapfile = os.path.join(bidsfolder,'code','bidsmap.yaml')

    # Initiate the bidsmap with some helpful text
    bidsmap.yaml_set_start_comment = textwrap.dedent("""\
        ------------------------------------------------------------------------------
        Config file that maps the extracted fields to the BIDS modalities and BIDS
        labels (see also [bidsmapper.yaml] and [bidsmapper.py]). You can edit these.
        fields before passing it to [bidscoiner.py] which uses it to cast the datasets
        into the BIDS folder. The datastructure of this config file should be 5 levels
        deep and follow: dict > dict > list > dict > list
        ------------------------------------------------------------------------------""")

    # Save the bidsmap to the bidsmap yaml-file
    print('Writing bidsmap to: ' + bidsmapfile)
    with open(bidsmapfile, 'w') as stream:
        yaml.dump(bidsmap, stream)

    return bidsmapfile


# Shell usage
if __name__ == "__main__":

    # Check input arguments and run the main create_bidsmap(args) function
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='example:\n  bidsmapper.py /project/foo/raw /project/foo/bids bidsmapper_dccn')
    parser.add_argument('rawfolder',  help='The source folder containing the raw data in sub-###/ses-##/series format')
    parser.add_argument('bidsfolder', help='The destination folder with the bids data structure')
    parser.add_argument('bidsmapper', help='The bidsmapper yaml-file with the BIDS heuristics (default: ./heuristics/bidsmapper.yaml)')
    args = parser.parse_args()

    bidsmapfile = create_bidsmap(args.rawfolder, args.bidsfolder, args.bidsmapper)
