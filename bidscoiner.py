import os


def run_dicomcoiner(seriesfolder, heuristics):
    """
    TODO: Run the dicom coiner to cast the series into the bids folder
    :param seriesfolder:
    :param heuristics:
    :return: heuristics
    """


def run_plugincoiner(seriesfolder, heuristics):
    """
    TODO: Run the plugin coiner to cast the series into the bids folder
    :param seriesfolder:
    :param heuristics:
    :return: heuristics
    """

    # Input checks
    if not seriesfolder or not heuristics['PlugIn']:
        return heuristics

    # Import and run the plugins
    from importlib import import_module
    for pluginfunction in heuristics['PlugIn']:
        plugin     = import_module(os.path.join(__file__, 'plugins', pluginfunction))
        heuristics = plugin.coin(seriesfolder, heuristics)
    return heuristics


def coin_bidsmap(rawfolder, bidsfolder, bidsmapper='code/bidsmap.yaml'):
    """
    Main function that processes all the subjects and session in the rawfolder
    and uses the bidsmap.yaml file in bidsfolder/code to cast the data into the
    BIDS folder.

    :param rawfolder:     folder tree containing folders with dicom files
    :param bidsfolder:    BIDS root folder
    :param bidsmapper:    bidsmapper yaml-file
    :return: bidsmap:     bidsmap.yaml file
    """


# Shell usage
if __name__ == "__main__":

    # Check input arguments and run query(args)
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n  bidscoiner.py ~/mridata/raw bidsmapper_dccn.yaml -s M\n  bidscoiner.py /project/foo/raw /project/foo/mymapper.yaml -o ')
    parser.add_argument('rawfolder',  help='The source folder containing the raw data in sub-###/ses-##/series format')
    parser.add_argument('bidsfolder', help='The destination folder with the bids data structure')
    parser.add_argument('bidsmapper', help='The bidsmapper yaml-file with the BIDS heuristics. Default: code/bidsmap.yaml)')
    args = parser.parse_args()

    coin_bidsmap(args.rawfolder, args.bidsfolder, args.bidsmapper)

