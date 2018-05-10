#!/usr/bin/env python
"""
Creates a bidsmap.yaml config file that maps the information from the data to the
BIDS modalities and BIDS labels (see also [bidsmapper.yaml] and [bidsmapper.py]).
You can edit the bidsmap file before passing it to [bidscoiner.py] which uses it
to cast the datasets into the BIDS folder structure

@author: marzwi
"""

# Global imports (specific modules may be imported when needed)
import bids
import os.path
import textwrap
import copy
from ruamel_yaml import YAML
yaml = YAML()


def built_dicommap(dicomfile, bidsmap, heuristics, automatic):
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
    for bidsmodality in bids.bidsmodalities:

        if not heuristics['DICOM'][bidsmodality]: continue
        for series in heuristics['DICOM'][bidsmodality]:

            # series_ = copy.deepcopy(series)       # Deepcopy makes sure we don't change the original heuristics object, however, it is a very expensive operation.
            series_ = dict(attributes={})           # This way is also safe, however, we lose all comments and formatting within the series (which is not such a disaster probably). It is also more robust with aliases
            match   = any([series['attributes'][key] is not None for key in series['attributes']])   # Make match False if all attributes are empty
            for key in series:

                # Try to see if the dicomfile matches all of the attributes and try to fill all of them
                if key == 'attributes':

                    for attrkey in series['attributes']:

                        attrvalue  = series['attributes'][attrkey]
                        dicomvalue = bids.get_dicomfield(attrkey, dicomfile)

                        # Check if the attribute value matches with the info from the dicomfile
                        if attrvalue:
                            if isinstance(attrvalue, int):
                                match = match and attrvalue == dicomvalue
                            elif isinstance(attrvalue, list):
                                match = match and any([attrvalue_ in dicomvalue for attrvalue_ in attrvalue])  # TODO: implement regexp
                            else:
                                match = match and (attrvalue in dicomvalue)                                    # TODO: implement regexp

                        # Fill the empty attribute with the info from the dicomfile
                        series_['attributes'][attrkey] = dicomvalue

                # Try to fill the bids-labels
                else:

                    bidsvalue = series[key]
                    if not bidsvalue:
                        series_[key] = bidsvalue

                    # Intelligent filling of the run-index is done runtime by bidscoiner
                    elif key == 'run_index' and bidsvalue == '<automatic>':
                        series_[key] = bidsvalue

                    # Fill any bids-label with the <annotated> dicom attribute
                    elif bidsvalue.startswith('<') and bidsvalue.endswith('>'):
                        label        = bids.get_dicomfield(bidsvalue[1:-1], dicomfile)
                        series_[key] = bids.cleanup_label(label)

                    else:
                        series_[key] = bidsvalue

            # If we have a match, copy the filled-in series over to the bidsmap as a standard bidsmodality and we are done!
            if match:
                # TODO: check if there are more matches (i.e. conflicts)
                if bidsmap['DICOM'][bidsmodality] is None:
                    bidsmap['DICOM'][bidsmodality] = [series_]
                elif not bids.exist_series(series_, bidsmap['DICOM'][bidsmodality]):
                    bidsmap['DICOM'][bidsmodality].append(series_)

                return bidsmap

    # If nothing matched, ask the user for help
    if automatic:
        answer = bids.ask_for_mapping(heuristics['DICOM'], series_, dicomfile)      # Note: series_ will be referenced since heuristics['DICOM'][bidsmodality] should not all be empty

    if 'answer' in locals() and answer:                                             # A catch for users canceling the question for help
        series   = answer['series']
        modality = answer['modality']

    # Otherwise treat the series as as an unknown modality and fill the unknown labels
    else:
        series   = dict()                                       # Here we loose comments and formatting from the bidsmapper, but that is probably very minor
        modality = bids.unknownmodality

        for key in heuristics['DICOM'][modality]:

            if key == 'attributes':
                series['attributes'] = series_['attributes']    # Taking the last tested series is a convenient but arbitrary choice (potentially, other series can have different attributes listed in the bidsmapper)

            else:
                value = heuristics['DICOM'][modality][key]

                if not value:
                    series[key] = None

                # Intelligent filling of the run-index is done runtime by bidscoiner
                elif key=='run_index' and value=='<automatic>':
                    series[key] = '<automatic>'

                # Fill any bids-label with the <annotated> dicom attribute
                elif value and value.startswith('<') and value.endswith('>'):
                    label       = bids.get_dicomfield(value[1:-1], dicomfile)
                    series[key] = bids.cleanup_label(label)

                else:
                    series[key] = value

    # Copy the filled-in attributes series over to the bidsmap
    if bidsmap['DICOM'][modality] is None:
        bidsmap['DICOM'][modality] = [series]

    elif not bids.exist_series(series, bidsmap['DICOM'][modality]):
        bidsmap['DICOM'][modality].append(series)

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

    from importlib import import_module

    # Input checks
    if not seriesfolder or not bidsmap['PlugIn']:
        return bidsmap

    # Import and run the plugins
    for pluginfunction in bidsmap['PlugIn']:
        plugin  = import_module(os.path.join(__file__, 'plugins', pluginfunction))
        bidsmap = plugin.map(seriesfolder, bidsmap)

    return bidsmap


def bidsmapper(rawfolder, bidsfolder, bidsmapper='bidsmapper_sample.yaml', automatic=False):
    """
    Main function that processes all the subjects and session in the rawfolder
    and that generates a maximally filled-in bidsmap.yaml file in bidsfolder/code.
    Folders in rawfolder are assumed to contain a single dataset.

    :param rawfolder:     sub/ses/data/file tree containing folders with data files
    :param bidsfolder:    BIDS root folder
    :param bidsmapper:    bidsmapper yaml-file
    :return: bidsmap:     bidsmap.yaml file
    """

    # Input checking
    rawfolder  = os.path.abspath(os.path.expanduser(rawfolder))
    bidsfolder = os.path.abspath(os.path.expanduser(bidsfolder))

    # Get the heuristics for creating the bidsmap
    heuristics = bids.get_heuristics(bidsmapper, bidsfolder)

    # Create a copy / bidsmap skeleton with no modality entries (i.e. bidsmapper with empty lists)
    bidsmap = copy.deepcopy(heuristics)
    for logic in ('DICOM', 'PAR', 'P7', 'Nifti', 'FileSystem'):
        for modality in bids.bidsmodalities + (bids.unknownmodality,):

            if bidsmap[logic] and modality in bidsmap[logic]:
                bidsmap[logic][modality] = None

    # Loop over all subjects and sessions and built up the bidsmap entries
    subjects = bids.lsdirs(rawfolder, 'sub-*')
    for subject in subjects:

        sessions = bids.lsdirs(subject, 'ses-*')
        if not sessions: sessions = subject
        for session in sessions:

            print('Parsing: ' + session)

            for series in bids.lsdirs(session):

                # Update / append the dicom mapping
                if heuristics['DICOM']:
                    dicomfile = bids.get_dicom_file(series)
                    bidsmap   = built_dicommap(dicomfile, bidsmap, heuristics, automatic)

                # Update / append the PAR/REC mapping
                if heuristics['PAR']:
                    parfile   = bids.get_par_file(series)
                    bidsmap   = built_parmap(parfile, bidsmap, heuristics)

                # Update / append the P7 mapping
                if heuristics['P7']:
                    p7file    = bids.get_p7_file(series)
                    bidsmap   = built_p7map(p7file, bidsmap, heuristics)

                # Update / append the nifti mapping
                if heuristics['Nifti']:
                    niftifile = bids.get_nifti_file(series)
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
        into the BIDS folder. The datastructure of this config file should be 5 or 6
        levels deep and follow: dict > dict > list > dict > dict [> list]
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
    parser.add_argument('rawfolder',        help='The source folder containing the raw data in sub-###/ses-##/series format')
    parser.add_argument('bidsfolder',       help='The destination folder with the bids data structure')
    parser.add_argument('bidsmapper',       help='The bidsmapper yaml-file with the BIDS heuristics (default: bidsfolder/code/bidsmapper_sample.yaml)', nargs='?', default='bidsmapper_sample.yaml')
    parser.add_argument('-a','--automatic', help='If this flag is given the user will not be asked for help if an unknown series is encountered', action='store_true')
    args = parser.parse_args()

    bidsmapfile = bidsmapper(args.rawfolder, args.bidsfolder, args.bidsmapper, args.automatic)
