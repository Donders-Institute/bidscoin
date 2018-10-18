#!/usr/bin/env python
"""
Takes example files from the samples folder as training data and creates a key-value
mapping, i.e. a bidsmap_sample.yaml file, by associating the file attributes with the
file's BIDS-semantic pathname
"""

import os.path
import glob
import shutil
import copy
import textwrap
from bin import bids
from ruamel.yaml import YAML
yaml = YAML()


def built_dicommap(dicomfile, bidsmap, heuristics):
    """
    All the logic to map dicomfields onto bids labels go into this function

    :param str dicomfile:   The full-path name of the source dicom-file
    :param dict bidsmap:    The bidsmap as we had it
    :param dict heuristics: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmap with new entries in it
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
        return bidsmap
    if bidsmodality not in bids.bidsmodalities:
        raise ValueError("Don't know what to do with this bidsmodality directory name: {}\n{}".format(bidsmodality, dicomfile))

    # Copy the bids-labels over from the matching series in heuristics to series_, Then fill the attributes and append it to bidsmap
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

            # Copy the filled-in series over to the bidsmap
            if bidsmap['DICOM'][bidsmodality] is None:
                bidsmap['DICOM'][bidsmodality] = [series_]
            elif not bids.exist_series(series_, bidsmap['DICOM'][bidsmodality]):
                bidsmap['DICOM'][bidsmodality].append(series_)

            return bidsmap

    raise ValueError("Oops, this should not happen! BIDS modality '{}' or one of the bidslabels is not accounted for in the code\n{}".format(bidsmodality, dicomfile))


def built_parmap(parfile, bidsmap, heuristics):
    """
    All the logic to map PAR/REC fields onto bids labels go into this function

    :param str parfile:     The full-path name of the source PAR-file
    :param dict bidsmap:    The bidsmap as we had it
    :param dict heuristics: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmap with new entries in it
    :rtype: dict
    """

    # Input checks
    if not parfile or not heuristics['PAR']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_p7map(p7file, bidsmap, heuristics):
    """
    All the logic to map P7-fields onto bids labels go into this function

    :param str p7file:      The full-path name of the source P7-file
    :param dict bidsmap:    The bidsmap as we had it
    :param dict heuristics: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmap with new entries in it
    :rtype: dict
    """

    # Input checks
    if not p7file or not heuristics['P7']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_niftimap(niftifile, bidsmap, heuristics):
    """
    All the logic to map nifti-info onto bids labels go into this function

    :param str niftifile:   The full-path name of the source nifti-file
    :param dict bidsmap:    The bidsmap as we had it
    :param dict heuristics: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmap with new entries in it
    :rtype: dict
    """

    # Input checks
    if not niftifile or not heuristics['Nifti']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_filesystemmap(seriesfolder, bidsmap, heuristics):
    """
    All the logic to map filesystem-info onto bids labels go into this function

    :param str seriesfolder: The full-path name of the source-folder
    :param dict bidsmap:     The bidsmap as we had it
    :param dict heuristics:  Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                 The bidsmap with new entries in it
    :rtype: dict
    """

    # Input checks
    if not seriesfolder or not heuristics['FileSystem']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_pluginmap(sample, bidsmap):
    """
    Call the plugin to map info onto bids labels

    :param str sample:   The full-path name of the source-file
    :param dict bidsmap: The bidsmap as we had it
    :return:             The bidsmap with new entries in it
    :rtype: dict
    """

    from importlib import import_module

    # Input checks
    if not sample or not bidsmap['PlugIn']:
        return bidsmap

    # Import and run the plugins
    for pluginfunction in bidsmap['PlugIn']:
        plugin  = import_module(os.path.join(__file__,'..','plugins', pluginfunction))
        # TODO: check first if the plug-in function exist
        bidsmap = plugin.bidstrainer(sample, bidsmap)

    return bidsmap


def bidstrainer(bidsfolder, samplefolder='', bidsmapfile='bidsmap_template.yaml'):
    """
    Main function uses all samples in the samplefolder as training / example  data to generate a
    maximally filled-in bidsmap_sample.yaml file.

    :param str bidsfolder:    The name of the BIDS root folder
    :param str samplefolder:  The name of the root directory of the tree containing the sample files / training data. If left empty, bidsfolder/code/samples is used or such an empty directory tree is created
    :param str bidsmapfile:   The name of the bidsmap YAML-file
    :return:                  The name of the new (trained) bidsmap YAML-file that is save in bidsfolder/code
    :rtype: str
    """

    # Input checking
    bidsfolder = os.path.abspath(os.path.expanduser(bidsfolder))
    if not samplefolder:
        samplefolder = os.path.join(bidsfolder,'code','samples')
        if not os.path.isdir(samplefolder):
            print('Creating an empty samples directory tree: ' + samplefolder)
            shutil.copytree(os.path.join(os.path.dirname(__file__),'..','heuristics','samples'), samplefolder)
            print('Fill the directory tree with example DICOM files and re-run bidstrainer.py')
            return
    samplefolder = os.path.abspath(os.path.expanduser(samplefolder))

    # Get the heuristics for creating the bidsmap
    heuristics = bids.get_heuristics(bidsmapfile)

    # Create a copy / bidsmap skeleton with no modality entries (i.e. bidsmap with empty lists)
    bidsmap = copy.deepcopy(heuristics)
    for logic in ('DICOM', 'PAR', 'P7', 'Nifti', 'FileSystem'):
        for modality in bids.bidsmodalities:

            if bidsmap[logic] and modality in bidsmap[logic]:
                bidsmap[logic][modality] = None

    # Loop over all bidsmodalities and instances and built up the bidsmap entries
    samples = glob.glob(os.path.join(samplefolder,'**'), recursive=True)
    for sample in samples:

        if not os.path.isfile(sample): continue
        print('Parsing: ' + sample)

        # Try to get a dicom mapping
        if bids.is_dicomfile(sample) and heuristics['DICOM']:
            bidsmap = built_dicommap(sample, bidsmap, heuristics)

        # Try to get a PAR/REC mapping
        if bids.is_parfile(sample) and heuristics['PAR']:
            bidsmap = built_parmap(sample, bidsmap, heuristics)

        # Try to get a P7 mapping
        if bids.is_p7file(sample) and heuristics['P7']:
            bidsmap = built_p7map(sample, bidsmap, heuristics)

        # Try to get a nifti mapping
        if bids.is_niftifile(sample) and heuristics['Nifti']:
            bidsmap = built_niftimap(sample, bidsmap, heuristics)

        # Try to get a file-system mapping
        if heuristics['FileSystem']:
            bidsmap = built_filesystemmap(sample, bidsmap, heuristics)

        # Try to get a plugin mapping
        if heuristics['PlugIn']:
            bidsmap = built_pluginmap(sample, bidsmap)

    # Create the bidsmap_sample YAML-file in bidsfolder/code
    os.makedirs(os.path.join(bidsfolder,'code'), exist_ok=True)
    bidsmapfile = os.path.join(bidsfolder,'code','bidsmap_sample.yaml')

    # Save the bidsmap to the bidsmap YAML-file
    print('Writing bidsmap to: ' + bidsmapfile)
    with open(bidsmapfile, 'w') as stream:
        yaml.dump(bidsmap, stream)

    return bidsmapfile


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run bidstrainer(args)
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n  bidstrainer.py /project/foo/bids\n  bidstrainer.py /project/foo/bids /project/foo/samples bidsmap_custom\n ')
    parser.add_argument('bidsfolder',   help='The destination folder with the bids data structure')
    parser.add_argument('samplefolder', help='The root folder of the directory tree containing the sample files / training data. Optional argument, if left empty, bidsfolder/code/samples is used or such an empty directory tree is created', nargs='?', default='')
    parser.add_argument('bidsmap',      help='The bidsmap YAML-file with the BIDS heuristics (optional argument, default: ./heuristics/bidsmap_template.yaml)', nargs='?', default='bidsmap_template.yaml')
    args = parser.parse_args()

    bidsmapfile = bidstrainer(bidsfolder=args.bidsfolder, samplefolder=args.samplefolder, bidsmapfile=args.bidsmap)
