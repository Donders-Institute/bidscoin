#!/usr/bin/env python
"""
Takes example files from the samples folder to create a bidsmapper config file
"""

import bids
import os.path
import glob
import shutil
import copy
import textwrap
from ruamel.yaml import YAML
yaml = YAML()

def built_dicommapper(dicomfile, bidsmapper, heuristics):
    """
    All the logic to map dicomfields onto bids labels go into this function

    :param str dicomfile:   The full-path name of the source dicom-file
    :param dict bidsmapper: The bidsmapper as we had it
    :param dict heuristics: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmapper with new entries in it
    :rtype: dict
    """

    # Get the bidsmodality and dirname (= bidslabel) from the pathname (samples/bidsmodality/[dirname/]dicomfile)
    dirname = os.path.basename(os.path.dirname(dicomfile))
    if dirname in bids.bidsmodalities:
        bidsmodality = dirname
    else:
        bidsmodality = os.path.basename(os.path.dirname(os.path.dirname(dicomfile)))

    # Input checks
    if not dicomfile or not heuristics['DICOM'] or not heuristics['DICOM'][bidsmodality]:
        return bidsmapper
    if bidsmodality not in bids.bidsmodalities:
        raise ValueError("Don't know what to do with this bidsmodality directory name: {}\n{}".format(bidsmodality, dicomfile))

    # Copy the bids-labels over from the matching series in heuristics to series_, Then fill the attributes and append it to bidsmapper
    for series in heuristics['DICOM'][bidsmodality]:

        match   = False
        series_ = dict()    # Creating a new object is safe in that we don't change the original heuristics object. However, we lose all comments and formatting within the series (which is not such a disaster probably). It is also much faster and more robust with aliases compared with a deepcopy

        # Copy the bids labels for the different bidsmodality matches
        if bidsmodality == 'beh':       # beh should not have subdirectories as it (in the cuurent BIDS version doesn't have a suffix)
            for key in series:
                series_[key] = series[key]
            match = True

        else:
            if ('modality_label' in series and dirname==series['modality_label']) or ('suffix' in series and dirname==series['suffix']):
                for key in series:
                    series_[key] = series[key]
                match = True

        if match:

            # Fill the empty attribute with the info from the dicomfile
            series_['attributes'] = dict()              # Clear the yaml objects that were copied over
            for attrkey in series['attributes']:
                series_['attributes'][attrkey] = bids.get_dicomfield(attrkey, dicomfile)

            # Copy the filled-in series over to the bidsmapper
            if bidsmapper['DICOM'][bidsmodality] is None:
                bidsmapper['DICOM'][bidsmodality] = [series_]
            elif not bids.exist_series(series_, bidsmapper['DICOM'][bidsmodality]):
                bidsmapper['DICOM'][bidsmodality].append(series_)

            return bidsmapper

    raise ValueError("Oops, this should not happen! BIDS modality '{}' or one of the bidslabels is not accounted for in the code\n{}".format(bidsmodality, dicomfile))


def built_parmapper(parfile, bidsmapper, heuristics):
    """
    All the logic to map PAR/REC fields onto bids labels go into this function

    :param str parfile:     The full-path name of the source PAR-file
    :param dict bidsmapper: The bidsmapper as we had it
    :param dict heuristics: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmapper with new entries in it
    :rtype: dict
    """

    # Input checks
    if not parfile or not heuristics['PAR']:
        return bidsmapper

    # TODO: Loop through all bidsmodalities and series

    return bidsmapper


def built_p7mapper(p7file, bidsmapper, heuristics):
    """
    All the logic to map P7-fields onto bids labels go into this function

    :param str p7file:      The full-path name of the source P7-file
    :param dict bidsmapper: The bidsmapper as we had it
    :param dict heuristics: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmapper with new entries in it
    :rtype: dict
    """

    # Input checks
    if not p7file or not heuristics['P7']:
        return bidsmapper

    # TODO: Loop through all bidsmodalities and series

    return bidsmapper


def built_niftimapper(niftifile, bidsmapper, heuristics):
    """
    All the logic to map nifti-info onto bids labels go into this function

    :param str niftifile:   The full-path name of the source nifti-file
    :param dict bidsmapper: The bidsmapper as we had it
    :param dict heuristics: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmapper with new entries in it
    :rtype: dict
    """

    # Input checks
    if not niftifile or not heuristics['Nifti']:
        return bidsmapper

    # TODO: Loop through all bidsmodalities and series

    return bidsmapper


def built_filesystemmapper(seriesfolder, bidsmapper, heuristics):
    """
    All the logic to map filesystem-info onto bids labels go into this function

    :param str seriesfolder: The full-path name of the source-folder
    :param dict bidsmapper:  The bidsmapper as we had it
    :param dict heuristics:  Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                 The bidsmapper with new entries in it
    :rtype: dict
    """

    # Input checks
    if not seriesfolder or not heuristics['FileSystem']:
        return bidsmapper

    # TODO: Loop through all bidsmodalities and series

    return bidsmapper


def built_pluginmapper(sample, bidsmapper):
    """
    Call the plugin to map info onto bids labels

    :param str sample:      The full-path name of the source-file
    :param dict bidsmapper: The bidsmapper as we had it
    :return:                The bidsmapper with new entries in it
    :rtype: dict
    """

    from importlib import import_module

    # Input checks
    if not sample or not bidsmapper['PlugIn']:
        return bidsmapper

    # Import and run the plugins
    for pluginfunction in bidsmapper['PlugIn']:
        plugin     = import_module(os.path.join(__file__,'..','plugins', pluginfunction))
        # TODO: check first if the plug-in function exist
        bidsmapper = plugin.bidstrainer(sample, bidsmapper)

    return bidsmapper


def bidstrainer(bidsfolder, samplefolder='', bidsmapper='bidsmapper.yaml'):
    """
    Main function uses all samples in the samplefolder as training / example  data to generate a
    maximally filled-in bidsmapper_sample.yaml file.

    :param str bidsfolder:    The name of the BIDS root folder
    :param str samplefolder:  The name of the root directory of the tree containing the sample files / training data. If left empty, bidsfolder/code/samples is used or such an empty directory tree is created
    :param dict bidsmapper:   The name of the bidsmapper yaml-file
    :return:                  The name of the new (trained) bidsmapper yaml-file that is save in bidsfolder/code
    :rtype: str
    """

    # Input checking
    if not samplefolder:
        samplefolder = os.path.join(bidsfolder,'code','samples')
        if not os.path.isdir(samplefolder):
            print('Creating an empty samples directory tree: ' + samplefolder)
            shutil.copytree(os.path.join(os.path.dirname(__file__),'..','heuristics','samples'), samplefolder)
            print('Fill the directory tree with example DICOM files and re-run bidstrainer.py')
            return
    bidsfolder   = os.path.abspath(os.path.expanduser(bidsfolder))
    samplefolder = os.path.abspath(os.path.expanduser(samplefolder))

    # Get the heuristics for creating the bidsmapper
    heuristics = bids.get_heuristics(bidsmapper)

    # Create a copy / bidsmapper skeleton with no modality entries (i.e. bidsmapper with empty lists)
    bidsmapper = copy.deepcopy(heuristics)
    for logic in ('DICOM', 'PAR', 'P7', 'Nifti', 'FileSystem'):
        for modality in bids.bidsmodalities:

            if bidsmapper[logic] and modality in bidsmapper[logic]:
                bidsmapper[logic][modality] = None

    # Loop over all bidsmodalities and instances and built up the bidsmapper entries
    samples = glob.glob(os.path.join(samplefolder,'**'), recursive=True)
    for sample in samples:

        if not os.path.isfile(sample): continue
        print('Parsing: ' + sample)

        # Try to get a dicom mapping
        if bids.is_dicomfile(sample) and heuristics['DICOM']:
            bidsmapper = built_dicommapper(sample, bidsmapper, heuristics)

        # Try to get a PAR/REC mapping
        if bids.is_parfile(sample) and heuristics['PAR']:
            bidsmapper = built_parmapper(sample, bidsmapper, heuristics)

        # Try to get a P7 mapping
        if bids.is_p7file(sample) and heuristics['P7']:
            bidsmapper = built_p7mapper(sample, bidsmapper, heuristics)

        # Try to get a nifti mapping
        if bids.is_niftifile(sample) and heuristics['Nifti']:
            bidsmapper = built_niftimapper(sample, bidsmapper, heuristics)

        # Try to get a file-system mapping
        if heuristics['FileSystem']:
            bidsmapper = built_filesystemmapper(sample, bidsmapper, heuristics)

        # Try to get a plugin mapping
        if heuristics['PlugIn']:
            bidsmapper = built_pluginmapper(sample, bidsmapper)

    # Create the bidsmapper_sample yaml-file in bidsfolder/code
    os.makedirs(os.path.join(bidsfolder,'code'), exist_ok=True)
    bidsmapperfile = os.path.join(bidsfolder,'code','bidsmapper_sample.yaml')

    # Initiate the bidsmapper with some helpful text
    bidsmapper.yaml_set_start_comment = textwrap.dedent("""\
        ------------------------------------------------------------------------------
        Config file that maps the extracted fields to the BIDS modalities and BIDS
        labels (see also [bidsmapper.yaml] and [bidsmapper.py]). You can edit these.
        fields before passing it to [bidscoiner.py] which uses it to cast the datasets
        into the BIDS folder. The datastructure of this config file should be 5 or 6
        levels deep and follow: dict > dict > list > dict > dict [> list]
        ------------------------------------------------------------------------------""")

    # Save the bidsmapper to the bidsmapper yaml-file
    print('Writing bidsmapper to: ' + bidsmapperfile)
    with open(bidsmapperfile, 'w') as stream:
        yaml.dump(bidsmapper, stream)

    return bidsmapperfile


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run bidstrainer(args)
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='example:\n  bidsmapper.py /project/foo/bids\n  bidsmapper.py /project/foo/bids /project/foo/samples bidsmapper_dccn')
    parser.add_argument('bidsfolder',   help='The destination folder with the bids data structure')
    parser.add_argument('samplefolder', help='The root folder of the directory tree containing the sample files / training data. Optional argument, if left empty, bidsfolder/code/samples is used or such an empty directory tree is created', nargs='?', default='')
    parser.add_argument('bidsmapper',   help='The bidsmapper yaml-file with the BIDS heuristics (optional argument, default: ./heuristics/bidsmapper.yaml)', nargs='?', default='bidsmapper.yaml')
    args = parser.parse_args()

    bidsmapperfile = bidstrainer(samplefolder=args.samplefolder, bidsfolder=args.bidsfolder, bidsmapper=args.bidsmapper)
