#!/usr/bin/env python3
"""
BIDScoin is a toolkit to convert raw data-sets according to the Brain Imaging Data Structure (BIDS)

The basic workflow is to run these two tools:

  $ bidsmapper sourcefolder bidsfolder     # This produces a study bidsmap and launches a GUI
  $ bidscoiner sourcefolder bidsfolder     # This converts your data to BIDS according to the study bidsmap

Default settings and template bidsmaps are stored in the `.bidscoin` configuration folder in your home
directory (you can modify the configuration files to your needs with any plain text editor)

Set the environment variable `BIDSCOIN_DEBUG=TRUE` to run BIDScoin in a more verbose logging mode and
`BIDSCOIN_CONFIGDIR=/writable/path/to/configdir` for using a different configuration (root) directory.
Citation reports can be generated with the help of duecredit (https://github.com/duecredit/duecredit)

For more documentation see: https://bidscoin.readthedocs.io
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse
import textwrap
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parents[2]))
from bidscoin import check_version, __version__, bidsversion, bidsmap_template


def get_parser() -> argparse.ArgumentParser:
    """Build an argument parser with input arguments for bcoin.py"""

    _, _, versionmessage = check_version()

    parser = argparse.ArgumentParser(prog='bidscoin',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidscoin -l\n'
                                            '  bidscoin -d data/bidscoin_tutorial\n'
                                            '  bidscoin -t\n'
                                            '  bidscoin -t my_template_bidsmap\n'
                                            '  bidscoin -b my_study_bidsmap\n'
                                            '  bidscoin -i data/my_template_bidsmap.yaml downloads/my_plugin.py\n'
                                            '  bidscoin -c myproject/bids\n'
                                            '  bidscoin -c myproject/bids format bibtex\n'
                                            '  bidscoin --tracking show\n ')
    parser.add_argument('-l', '--list',        help='List all executables (i.e. the apps, bidsapps and utilities)', action='store_true')
    parser.add_argument('-p', '--plugins',     help='List all installed plugins and template bidsmaps', action='store_true')
    parser.add_argument('-i', '--install',     help='A list of template bidsmaps and/or bidscoin plugins to install', nargs='+')
    parser.add_argument('-u', '--uninstall',   help='A list of template bidsmaps and/or bidscoin plugins to uninstall', nargs='+')
    parser.add_argument('-d', '--download',    help='Download tutorial MRI data to the DOWNLOAD folder')
    parser.add_argument('-t', '--test',        help='Test the bidscoin installation and template bidsmap', nargs='?', const=bidsmap_template)
    parser.add_argument('-b', '--bidsmaptest', help='Test the run-items and their bidsnames of all normal runs in the study bidsmap. Provide the bids-folder or the bidsmap filepath')
    parser.add_argument('-c', '--credits',     help='Show duecredit citations for your BIDS repository. You can also add duecredit summary arguments (without dashes), e.g. `style {apa,harvard1}` or `format {text,bibtex}`.', nargs='+')
    parser.add_argument(      '--tracking',    help='Show the usage tracking info {show}, or set usage tracking to {yes} or {no}', choices=['yes','no','show'])
    parser.add_argument('-v', '--version',     help='Show the installed version and check for updates', action='version', version=f"BIDS-version:\t\t{bidsversion()}\nBIDScoin-version:\t{__version__}, {versionmessage}")

    return parser
