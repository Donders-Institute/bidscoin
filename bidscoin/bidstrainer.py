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
import re
import textwrap
import logging
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger('bidscoin')


def built_dicommap(dicomfile: str, bidsmap: dict, template: dict) -> dict:
    """
    All the logic to map dicomfields onto bids labels go into this function

    :param dicomfile:   The full-path name of the source dicom-file
    :param bidsmap:     The bidsmap as we had it
    :param template:    Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Get the bidsmodality and dirname (= bidslabel) from the pathname (samples/bidsmodality/[dirname/]dicomfile)
    suffix = os.path.basename(os.path.dirname(dicomfile))
    if suffix in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):
        modality = suffix
    else:
        modality = os.path.basename(os.path.dirname(os.path.dirname(dicomfile)))

    # Input checks
    if not bids.is_dicomfile(dicomfile) or not template['DICOM'] or not template['DICOM'][modality]:
        return bidsmap
    if modality not in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):
        raise ValueError("Don't know what to do with this bidsmodality directory name: {}\n{}".format(modality, dicomfile))

    # Copy the bids-labels over from the matching series in heuristics to series_, Then fill the attributes and append it to bidsmap
    series = bids.get_series(template, 'DICOM', modality, suffix)

    if series:

        # Fill the empty attribute with the info from the dicomfile
        series['provenance'] = dicomfile
        for attrkey in series['attributes']:
            series['attributes'][attrkey] = bids.get_dicomfield(attrkey, dicomfile)

        # Copy the filled-in series over to the bidsmap
        if not bids.exist_series(bidsmap, 'DICOM', modality, series):
            bidsmap = bids.append_series(bidsmap, 'DICOM', modality, series)

        return bidsmap

    raise ValueError(f"Oops, this should not happen! BIDS modality '{modality}' or one of the bidslabels is not accounted for in the code\n{dicomfile}")


def built_parmap(parfile: str, bidsmap: dict, heuristics: dict) -> dict:
    """
    All the logic to map PAR/REC fields onto bids labels go into this function

    :param parfile:     The full-path name of the source PAR-file
    :param bidsmap:     The bidsmap as we had it
    :param heuristics:  Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not parfile or not heuristics['PAR']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_p7map(p7file: str, bidsmap: dict, heuristics: dict) -> dict:
    """
    All the logic to map P7-fields onto bids labels go into this function

    :param p7file:      The full-path name of the source P7-file
    :param bidsmap:     The bidsmap as we had it
    :param heuristics:  Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not p7file or not heuristics['P7']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_niftimap(niftifile: str, bidsmap: dict, heuristics: dict) -> dict:
    """
    All the logic to map nifti-info onto bids labels go into this function

    :param niftifile:   The full-path name of the source nifti-file
    :param bidsmap:     The bidsmap as we had it
    :param heuristics:  Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Input checks
    if not niftifile or not heuristics['Nifti']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_filesystemmap(seriesfolder: str, bidsmap: dict, heuristics: dict) -> dict:
    """
    All the logic to map filesystem-info onto bids labels go into this function

    :param seriesfolder:    The full-path name of the source-folder
    :param bidsmap:         The bidsmap as we had it
    :param heuristics:      Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmap with new entries in it
    """

    # Input checks
    if not seriesfolder or not heuristics['FileSystem']:
        return bidsmap

    # TODO: Loop through all bidsmodalities and series

    return bidsmap


def built_pluginmap(sample: str, bidsmap: dict) -> dict:
    """
    Call the plugin to map info onto bids labels

    :param sample:  The full-path name of the source-file
    :param bidsmap: The bidsmap as we had it
    :return:        The bidsmap with new entries in it
    """

    from importlib import import_module

    # Input checks
    if not sample or not bidsmap['PlugIn']:
        return bidsmap

    # Import and run the plugins
    for pluginfunction in bidsmap['PlugIn']:
        plugin  = import_module(os.path.join(os.path.dirname(__file__),'plugins', pluginfunction))
        # TODO: check first if the plug-in function exist
        bidsmap = plugin.bidstrainer(sample, bidsmap)

    return bidsmap


def bidstrainer(bidsfolder: str, samplefolder: str, bidsmapfile: str, pattern: str) -> str:
    """
    Main function uses all samples in the samplefolder as training / example  data to generate a
    maximally filled-in bidsmap_sample.yaml file.

    :param bidsfolder:      The name of the BIDS root folder
    :param samplefolder:    The name of the root directory of the tree containing the sample files / training data. If left empty, bidsfolder/code/samples is used or such an empty directory tree is created
    :param bidsmapfile:     The name of the bidsmap YAML-file
    :param pattern:         The regular expression pattern used in re.match(pattern, dicomfile) to select the dicom files', default='.*\\.(IMA|dcm)$')
    :return:                The name of the new (trained) bidsmap YAML-file that is save in bidsfolder/code
    """

    # Input checking
    bidsfolder = os.path.abspath(os.path.expanduser(bidsfolder))
    if not samplefolder:
        samplefolder = os.path.join(bidsfolder,'code','samples')
        if not os.path.isdir(samplefolder):
            print('Creating an empty samples directory tree: ' + samplefolder)
            shutil.copytree(os.path.join(os.path.dirname(bids.__file__),'..','heuristics','samples'), samplefolder)
            print('Fill the directory tree with example DICOM files and re-run bidstrainer.py')
            return ''
    samplefolder = os.path.abspath(os.path.expanduser(samplefolder))

    # Start logging
    bids.setup_logging(os.path.join(bidsfolder, 'code', 'bidstrainer.log'))
    LOGGER.info('------------ START BIDStrainer ------------')

    # Get the heuristics for creating the bidsmap
    heuristics, _ = bids.load_bidsmap(bidsmapfile, os.path.join(bidsfolder, 'code'))

    # Create a copy / bidsmap skeleton with no modality entries (i.e. bidsmap with empty lists)
    bidsmap = copy.deepcopy(heuristics)
    for logic in ('DICOM', 'PAR', 'P7', 'Nifti', 'FileSystem'):
        for modality in bids.bidsmodalities:

            if bidsmap[logic] and modality in bidsmap[logic]:
                bidsmap[logic][modality] = None

    # Loop over all bidsmodalities and instances and built up the bidsmap entries
    files   = glob.glob(os.path.join(samplefolder,'**'), recursive=True)
    samples = [dcmfile for dcmfile in files if re.match(pattern, dcmfile)]
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
    bids.save_bidsmap(bidsmapfile, bidsmap)

    LOGGER.info('------------ FINISHED! ------------')


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run bidstrainer(args)
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n' 
                                            '  bidstrainer.py /project/foo/bids\n' 
                                            '  bidstrainer.py /project/foo/bids -s /project/foo/samples -t bidsmap_custom\n ')
    parser.add_argument('bidsfolder',           help='The destination folder with the bids data structure')
    parser.add_argument('-s','--samplefolder',  help='The root folder of the directory tree containing the sample files / training data. By default the bidsfolder/code/samples folder is used or such an empty directory tree is created', default='')
    parser.add_argument('-t','--template',      help='The bidsmap template file with the BIDS heuristics (default: ./heuristics/bidsmap_template.yaml)', default='bidsmap_template.yaml')
    parser.add_argument('-p','--pattern',       help='The regular expression pattern used in re.match(pattern, dicomfile) to select the dicom files', default=r'.*\.(IMA|dcm)$')
    args = parser.parse_args()

    bidstrainer(bidsfolder   = args.bidsfolder,
                samplefolder = args.samplefolder,
                bidsmapfile  = args.template,
                pattern      = args.pattern)
