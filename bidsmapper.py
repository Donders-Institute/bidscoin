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


def get_par_file(folder):
    """
    Returns the first PAR file from a folder.
    """
    for file in os.listdir(folder):
        if is_parfile(file):
            return os.path.join(folder, file)
    warnings.warn('Cannot find PAR files in:' + folder)


def get_p7_file(folder):
    """
    Returns the first P7 file from a folder.
    """
    for file in os.listdir(folder):
        if is_p7file(file):
            return os.path.join(folder, file)
    warnings.warn('Cannot find P7 files in:' + folder)


def get_nifti_file(folder):
    """
    Returns the first nifti file from a folder.
    """
    for file in os.listdir(folder):
        if is_niftifile(file):
            return os.path.join(folder, file)
    warnings.warn('Cannot find nifti files in:' + folder)


def parse_from_x_protocol(pattern, dicomfile):
    """
    Siemens writes a protocol structure as text into each DICOM file.
    This structure is necessary to recreate a scanning protocol from a DICOM,
    since the DICOM information alone wouldn't be sufficient.
    This function extracts values from the dicomfile according to a given pattern.
    """
    if not is_dicomfile_siemens(dicomfile):
        warnings.warn('This does not seem to be a Siemens DICOM file')
    with open(dicomfile, 'rb') as openfile:
        regexp = '^' + pattern + '\t = \t(.*)\n'
        regex  = re.compile(regexp.encode('utf-8'))
        for line in openfile:
            match = regex.match(line)
            if match:
                return int(match.group(1).decode('utf-8'))
    warnings.warn('Pattern: "' + regexp.encode('unicode_escape').decode() + '" not found in: ' + dicomfile)


def get_dicomfield(tagname, dicomfile):
    """
    Robustly reads a DICOM tag from a dictionary or from vendor specific fields
    NB: profiling shows this is currently the most expensive function
    :param tagname:
    :param dicomfile:
    :return:
    """
    import pydicom
    try:
        # TODO: implement regexp
        dicomdict = pydicom.dcmread(dicomfile)
        value     = dicomdict.get(tagname)
    except IOError:
        warnings.warn('Cannot read' + dicomfile)
    except Exception:
        try:
            value = parse_from_x_protocol(tagname, dicomfile)
        except Exception:
            value = ''
            warnings.warn('Could not extract {} tag from {}'.format(tagname, dicomfile))
    return value


def get_heuristics(yamlfile):

    # Get the full paths to the bidsmapper yaml-file and add a standard file-extension if needed
    if os.path.basename(yamlfile)==yamlfile:
        yamlfile = os.path.join(os.path.dirname(__file__), 'heuristics', yamlfile)
    if not os.path.splitext(yamlfile)[1] and not os.path.exists(yamlfile):
        yamlfile = yamlfile + '.yaml'

    # Read the heuristics from the bidsmapper files
    with open(yamlfile, 'r') as stream:
        heuristics = yaml.load(stream)
    return heuristics


def exist_series(series, serieslist):
    """
    Checks if there is already an entry in [serieslist] with the same attributes and labels as [series]
    :param series:
    :param serieslist:
    :return: Boolean
    """
    for seriesitem in serieslist:

        match = True

        # Search for a case where all series items match with the seriesitem items
        for item in series:

            try:
                if item=='attributes':

                    seriesattributes = series['attributes'][0]      # TODO: figure out why the data lives one level deeper
                    itemattributes   = seriesitem['attributes'][0]  # TODO: figure out why the data lives one level deeper

                    for attrkey in seriesattributes:

                        seriesvalue = seriesattributes[attrkey]  # for attrkey,attrvalue doesn't work...?
                        itemvalue   = itemattributes[attrkey]
                        match       = match and (seriesvalue == itemvalue)

                else:

                    seriesvalue = series[item]  # for attrkey,attrvalue doesn't work...?
                    itemvalue   = seriesitem[item]
                    match       = match and (seriesvalue == itemvalue)

            except KeyError:    # Errors may be evoked when matching bids-labels which exist in one modality but not in the other
                match = False

        # Stop if we found one (i.e. match is still True after all the tests)
        if match:
            return True

    return False


def cleanup_label(label):
    """
    Return the given label converted to a label that can be used as a clean BIDS label.
    Remove leading and trailing spaces; convert other spaces, special BIDS characters
    and anything that is not an alphanumeric, dash, underscore, or dot to #.
    >> cleanup_label("Joe's reward_task")
    'Joesxreward_task'
    :param label:
    :return: validlabel
    """
    special_characters = (' ', '_', '-',)

    for special in special_characters:
        label = str(label).strip().replace(special, '#')
    return re.sub(r'(?u)[^-\w.]', '#', label)


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

    # Loop through all bidsmodalities and series; all info goes into series
    for bidsmodality in bidsmodalities:
        for series in heuristics['DICOM'][bidsmodality]:
            for item in series:

                # Try to see if the dicomfile matches all of the attributes and try to fill all of them
                if item == 'attributes':

                    attributes = series['attributes'][0]    # TODO: figure out why the data lives one level deeper

                    for attrkey in attributes:

                        attrvalue  = attributes[attrkey]       # for attrkey,attrvalue doesn't work...?
                        dicomvalue = get_dicomfield(attrkey, dicomfile)

                        # Check if the attribute value matches with the info from the dicomfile
                        if attrvalue:
                            if not 'match' in locals(): match = True
                            match = match and (attrvalue == dicomvalue)    # TODO: implement regexp

                        # Else, fill the empty attribute with the info from the dicomfile
                        else:
                            attributes[attrkey] = dicomvalue

                    series['attributes'][0] = attributes    # TODO: figure out why the data lives one level deeper

                # Try to fill all the bids-labels
                else:

                    bidsvalue = series[item]
                    if not bidsvalue:
                        continue

                    # Intelligent filling of the run-index is done runtime by bidscoiner
                    if item == 'run_index' and bidsvalue == '<automatic>':
                        pass

                    # Fill any bids-label with the annotated series attribute
                    elif bidsvalue.startswith('<') and bidsvalue.endswith('>'):
                        attrkey      = bidsvalue[1:-2]
                        series[item] = get_dicomfield(attrkey, dicomfile)

            # TODO: check if copying over like done below is possible/allowed with ruamel.yaml (raising yaml.dump errors)
            # If we have a match, copy the filled-in series over to the bidsmap as a standard bidsmodality
            if 'match' in locals() and match:
                if not exist_series(series, bidsmap['DICOM'][bidsmodality]):
                    bidsmap['DICOM'][bidsmodality].append(series)

            # If not, copy the filled-in series over to the bidsmap as an unknown modality
            else:
                if not exist_series(series, bidsmap['DICOM'][unknownmodality]):
                    bidsmap['DICOM'][unknownmodality].append(series)

            if 'match' in locals(): del match

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
    # for bidsmodality in bidsmodalities:
    #     for series in heuristics['DICOM'][bidsmodality]:
    #
    #         # Try to see if the dicomfile matches all of the attributes of any of the modalities
    # ETC

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

    # Create a copy / bidsmap skeleton with no modality entries
    bidsmap = copy.deepcopy(heuristics)
    for datasource in ('DICOM', 'PAR', 'P7', 'Nifti', 'FileSystem'):
        for modality in bidsmodalities + (unknownmodality,):
            if bidsmap[datasource] and modality in bidsmap[datasource]:
                bidsmap[datasource][modality] = []

    # Loop over all subjects and sessions and built up the bidsmap entries
    subjects = lsdirs(rawfolder, 'sub-*')
    for subject in subjects:

        sessions = lsdirs(subject, 'ses-*')
        if not sessions:
            sessions = subject
        for session in sessions:

            mriseries = lsdirs(session)
            for series in mriseries:

                print('Parsing: ' + series)

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
    with open(bidsmapfile, 'w') as stream:
        print('Writing bidsmap to: ' + bidsmapfile)
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
