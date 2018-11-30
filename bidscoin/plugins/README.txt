# bidscoin plugin API:

def bidsmapper_plugin(seriesfolder, bidsmap, heuristics):
    """
    The plugin to map info onto bids labels

    :param seriesfolder:    The full-path name of the source folder
    :param dict bidsmap:    The bidsmap
    :param dict heuristics: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :return:                The bidsmap with new entries in it
    :rtype: dict
    """

    pass


def bidscoiner_plugin(session, bidsmap, bidsfolder, personals, LOG):
    """
    The plugin to cast the series into the bids folder

    :param str session:    The full-path name of the subject/session source folder
    :param dict bidsmap:   The full mapping heuristics from the bidsmap YAML-file
    :param str bidsfolder: The full-path name of the BIDS root-folder
    :param dict personals: The dictionary with the personal information
    :param str LOG:        The full-path name of the bidscoiner.log file
    :return:               Nothing
    :rtype: NoneType
    """

    pass
