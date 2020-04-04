#!/usr/bin/env python
"""
*** OBSOLETE function ***

Takes example files from the samples folder as training data and creates a key-value
mapping, i.e. a bidsmap_sample.yaml file, by associating the file attributes with the
file's BIDS-semantic pathname. This function has become obsolete / has been replaced
by the bidseditor, but it may still be useful for institutes that want to build large
bidsmap.yaml templates?
"""

import copy
import re
import textwrap
import logging
from pathlib import Path
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger('bidscoin')


def built_dicommap(dicomfile: Path, bidsmap: dict, template: dict) -> dict:
    """
    All the logic to map dicomfields onto bids labels go into this function

    :param dicomfile:   The full-path name of the source dicom-file
    :param bidsmap:     The bidsmap as we had it
    :param template:    Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:            The bidsmap with new entries in it
    """

    # Get the bidsmodality and dirname (= bidslabel) from the pathname (samples/bidsmodality/[dirname/]dicomfile)
    suffix = dicomfile.parts[-2]
    if suffix in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):
        modality = suffix
    else:
        modality = dicomfile.parts[-3]

    # Input checks
    if not bids.is_dicomfile(dicomfile) or not template['DICOM'] or not template['DICOM'][modality]:
        return bidsmap
    if modality not in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):
        raise ValueError("Don't know what to do with this bidsmodality directory name: {}\n{}".format(modality, dicomfile))

    # Get bids-labels from the matching run in the template
    run = bids.get_run(template, 'DICOM', modality, suffix, dicomfile)      # TODO: check if the dicomfile argument is not broken
    if not run:
        raise ValueError(f"Oops, this should not happen! BIDS modality '{modality}' or one of the bidslabels is not accounted for in the code\n{dicomfile}")

    # Copy the filled-in run over to the bidsmap
    if not bids.exist_run(bidsmap, 'DICOM', modality, run):
        bidsmap = bids.append_run(bidsmap, 'DICOM', modality, run)

    return bidsmap


def built_parmap(parfile: Path, bidsmap: dict, heuristics: dict) -> dict:
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


def built_p7map(p7file: Path, bidsmap: dict, heuristics: dict) -> dict:
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


def built_niftimap(niftifile: Path, bidsmap: dict, heuristics: dict) -> dict:
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


def built_filesystemmap(seriesfolder: Path, bidsmap: dict, heuristics: dict) -> dict:
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


def built_pluginmap(sample: Path, bidsmap: dict) -> dict:
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
        plugin  = import_module(Path(__file__).parent/'plugins'/pluginfunction)
        # TODO: check first if the plug-in function exist
        bidsmap = plugin.bidstrainer(sample, bidsmap)

    return bidsmap


def bidstrainer(bidsfolder: str, samplefolder: str, bidsmapfile: str, pattern: str) -> None:
    """
    Main function uses all samples in the samplefolder as training / example  data to generate a
    maximally filled-in bidsmap_sample.yaml file.

    :param bidsfolder:      The name of the BIDS root folder
    :param samplefolder:    The name of the root directory of the tree containing the sample files / training data. If left empty, bidsfolder/code/bidscoin/samples is used or such an empty directory tree is created
    :param bidsmapfile:     The name of the bidsmap YAML-file
    :param pattern:         The regular expression pattern used in re.match(pattern, dicomfile) to select the dicom files', default='.*\\.(IMA|dcm)$')
    :return:
    """

    bidsfolder   = Path(bidsfolder)
    samplefolder = Path(samplefolder)
    bidsmapfile  = Path(bidsmapfile)

    # Start logging
    bids.setup_logging(bidsfolder/'code'/'bidscoin'/'bidstrainer.log')
    LOGGER.info('------------ START BIDStrainer ------------')

    # Get the heuristics for creating the bidsmap
    heuristics, _ = bids.load_bidsmap(bidsmapfile, bidsfolder/'code'/'bidscoin')

    # Input checking
    if not samplefolder:
        samplefolder = bidsfolder/'code'/'bidscoin'/'provenance'
        if not samplefolder.is_dir():
            LOGGER.info(f"Creating an empty samples directory tree: {samplefolder}")
            for modality in bids.bidsmodalities + (bids.ignoremodality, bids.unknownmodality):
                for run in heuristics['DICOM'][modality]:
                    if not run['bids']['suffix']:
                        run['bids']['suffix'] = ''
                    (samplefolder/modality/run['bids']['suffix']).mkdir(parents=True, exist_ok=True)
            LOGGER.info('Fill the directory tree with example DICOM files and re-run bidstrainer.py')
            return

    # Create a copy / bidsmap skeleton with no modality entries (i.e. bidsmap with empty lists)
    bidsmap = copy.deepcopy(heuristics)
    for logic in ('DICOM', 'PAR', 'P7', 'Nifti', 'FileSystem'):
        for modality in bids.bidsmodalities:

            if bidsmap[logic] and modality in bidsmap[logic]:
                bidsmap[logic][modality] = None

    # Loop over all bidsmodalities and instances and built up the bidsmap entries
    files   = samplefolder.rglob('*')
    samples = [Path(dcmfile) for dcmfile in files if re.match(pattern, str(dcmfile))]
    for sample in samples:

        if not sample.is_file(): continue
        LOGGER.info(f"Parsing: {sample}")

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

    # Create the bidsmap_sample YAML-file in bidsfolder/code/bidscoin
    (bidsfolder/'code'/'bidscoin').mkdir(parents=True, exist_ok=True)
    bidsmapfile = bidsfolder/'code'/'bidscoin'/'bidsmap_sample.yaml'

    # Save the bidsmap to the bidsmap YAML-file
    bids.save_bidsmap(bidsmapfile, bidsmap)

    LOGGER.info('------------ FINISHED! ------------')


def main():
    """Console script usage"""

    # Parse the input arguments and run bidstrainer(args)
    import argparse
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n' 
                                            '  bidstrainer /project/foo/bids\n' 
                                            '  bidstrainer /project/foo/bids -s /project/foo/samples -t bidsmap_custom\n ')
    parser.add_argument('bidsfolder',           help='The destination folder with the bids data structure')
    parser.add_argument('-s','--samplefolder',  help='The root folder of the directory tree containing the sample files / training data. By default the bidsfolder/code/bidscoin/provenance folder is used or such an empty directory tree is created', default='')
    parser.add_argument('-t','--template',      help='The bidsmap template file with the BIDS heuristics (default: ./heuristics/bidsmap_template.yaml)', default='bidsmap_template.yaml')
    parser.add_argument('-p','--pattern',       help='The regular expression pattern used in re.match(pattern, dicomfile) to select the dicom files', default=r'.*\.(IMA|dcm)$')
    args = parser.parse_args()

    bidstrainer(bidsfolder   = args.bidsfolder,
                samplefolder = args.samplefolder,
                bidsmapfile  = args.template,
                pattern      = args.pattern)


if __name__ == "__main__":
    main()
