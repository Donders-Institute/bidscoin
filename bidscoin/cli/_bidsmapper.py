"""
The bidsmapper scans your source data repository to identify different data types by matching
them against the run-items in the template bidsmap. Once a match is found, a mapping to BIDS
output data types is made and the run-item is added to the study bidsmap. You can check and
edit these generated bids-mappings to your needs with the (automatically launched) bidseditor.
Re-run the bidsmapper whenever something was changed in your data acquisition protocol and
edit the new data type to your needs (your existing bidsmap will be re-used).

The bidsmapper uses plugins, as stored in the bidsmap['Options'], to do the actual work
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse
import textwrap
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parents[1]))
from bidscoin import bidsmap_template


def get_parser() -> argparse.ArgumentParser:
    """Build an argument parser with input arguments for bidsmapper.py"""

    parser = argparse.ArgumentParser(prog='bidsmapper',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidsmapper myproject/raw myproject/bids\n'
                                            '  bidsmapper myproject/raw myproject/bids -t bidsmap_custom  # Uses a template bidsmap of choice\n'
                                            '  bidsmapper myproject/raw myproject/bids -p nibabel2bids    # Uses a plugin of choice\n'
                                            "  bidsmapper myproject/raw myproject/bids -u '*.tar.gz'      # Unzip tarball sourcefiles\n ")
    parser.add_argument('sourcefolder',       help='The study root folder containing the raw source data folders')
    parser.add_argument('bidsfolder',         help='The destination folder with the (future) bids data and the bidsfolder/code/bidscoin/bidsmap.yaml output file')
    parser.add_argument('-b','--bidsmap',     help="The study bidsmap file with the mapping heuristics. If the bidsmap filename is just the basename (i.e. no '/' in the name) then it is assumed to be located in the current directory or in bidsfolder/code/bidscoin. Default: bidsmap.yaml", default='bidsmap.yaml')
    parser.add_argument('-t','--template',    help=f"The bidsmap template file with the default heuristics (this could be provided by your institute). If the bidsmap filename is just the basename (i.e. no '/' in the name) then it is assumed to be located in the bidscoin config folder. Default: {bidsmap_template.stem}", default=bidsmap_template)
    parser.add_argument('-p','--plugins',     help='List of plugins to be used. Default: the plugin list of the study/template bidsmap)', nargs='+', default=[])
    parser.add_argument('-n','--subprefix',   help="The prefix common for all the source subject-folders (e.g. 'Pt' is the subprefix if subject folders are named 'Pt018', 'Pt019', ...). Use '*' when your subject folders do not have a prefix. Default: the value of the study/template bidsmap, e.g. 'sub-'")
    parser.add_argument('-m','--sesprefix',   help="The prefix common for all the source session-folders (e.g. 'M_' is the subprefix if session folders are named 'M_pre', 'M_post', ..). Use '*' when your session folders do not have a prefix. Default: the value of the study/template bidsmap, e.g. 'ses-'")
    parser.add_argument('-u','--unzip',       help='Wildcard pattern to unpack tarball/zip-files in the sub/ses sourcefolder that need to be unzipped (in a tempdir) to make the data readable. Default: the value of the study/template bidsmap')
    parser.add_argument('-s','--store',       help='Store provenance data samples in the bidsfolder/code/provenance folder (useful for inspecting e.g. zipped or transferred datasets)', action='store_true')
    parser.add_argument('-a','--automated',   help='Save the automatically generated bidsmap to disk and without interactively tweaking it with the bidseditor', action='store_true')
    parser.add_argument('-f','--force',       help='Discard the previously saved bidsmap and logfile', action='store_true')
    parser.add_argument('--no-update',        help="Do not update any sub/sesprefixes in or prepend the sourcefolder name to the <<filepath:regex>> expression that extracts the subject/session labels. This is normally done to make the extraction more robust, but could cause problems for certain use cases", action='store_true')

    return parser
