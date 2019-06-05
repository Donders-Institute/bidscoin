#!/usr/bin/env python
"""
BIDSCOIN is a top level wrapper function that performs 3 steps needed to convert (raw) source data to BIDS. That is, it
sequentially runs:

    1. bidsmapper.py
    2. bidseditor.py
    3. bidscoiner.py

Typically this wrapper function is applied only once to a dataset. If new source data is added after running this function,
the user should only run the last step, the bidscoiner, directly. Only when the data acquisition parameters have changed,
it is adviced to re-run this function.

For more information, see: https://github.com/Donders-Institute/bidscoin
"""

try:
    from bidscoin import bids
    from bidscoin import bidsmapper
    from bidscoin import bidseditor
    from bidscoin import bidscoiner
except ImportError:
    import bids               # This should work if bidscoin was not pip-installed
    import bidsmapper         # This should work if bidscoin was not pip-installed
    import bidseditor         # This should work if bidscoin was not pip-installed
    import bidscoiner         # This should work if bidscoin was not pip-installed


def bidscoin(sourcefolder: str, bidsfolder: str, bidsmapfile: str, templatefile: str, subprefix: str= 'sub-', sesprefix: str= 'ses-') -> None:
    """
    Top level function that sequentially runs the bidsmapper, the bidseditor and the bidscoiner.

    :param sourcefolder:       The root folder-name of the sub/ses/data/file tree containing the source data files
    :param bidsfolder:      The name of the BIDS root folder
    :param bidsmapfile:     The name of the bidsmap YAML-file
    :param templatefile:
    :param subprefix:       The prefix common for all source subject-folders
    :param sesprefix:       The prefix common for all source session-folders
    :return:bidsmapfile:    The name of the mapped bidsmap YAML-file
    """

    bidsmapper.bidsmapper(sourcefolder, bidsfolder, bidsmapfile, subprefix, sesprefix)
    bidseditor.bidseditor(bidsfolder, sourcefolder, templatefile=templatefile)
    bidscoiner.bidscoiner(sourcefolder, bidsfolder, subprefix=subprefix, sesprefix=sesprefix)


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run bidsmapper(args)
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidsmapper.py /project/foo/raw /project/foo/bids\n'
                                            '  bidsmapper.py /project/foo/raw /project/foo/bids -b bidsmap_dccn\n ')
    parser.add_argument('sourcefolder',     help='The source folder containing the raw data in sub-#/ses-#/series format (or see below for different prefixes)')
    parser.add_argument('bidsfolder',       help='The destination folder with the (future) bids data and the bidsfolder/code/bidsmap.yaml output file')
    parser.add_argument('-b','--bidsmap',   help='The (non-default) bidsmap YAML-file with the BIDS heuristics')
    parser.add_argument('-t','--template',  help='The bidsmap template with the default heuristics (this could be provided by your institute). If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/. Default: bidsmap_template.yaml')
    parser.add_argument('-n','--subprefix', help="The prefix common for all the source subject-folders. Default: 'sub-'", default='sub-')
    parser.add_argument('-m','--sesprefix', help="The prefix common for all the source session-folders. Default: 'ses-'", default='ses-')
    parser.add_argument('-v','--version',   help="Show the BIDS and BIDScoin version", action='version', version=f'BIDS-version:\t\t{bids.bidsversion()}\nBIDScoin-version:\t{bids.version()}')
    args = parser.parse_args()

    bidscoin(sourcefolder = args.sourcefolder,
             bidsfolder   = args.bidsfolder,
             bidsmapfile  = args.bidsmap,
             templatefile = args.template,
             subprefix    = args.subprefix,
             sesprefix    = args.sesprefix)
