"""
This application launches a graphical user interface for editing the bidsmap that is produced
by the bidsmapper. You can edit the BIDS data types and entities until all run-items have a
meaningful and nicely readable BIDS output name. The (saved) bidsmap.yaml output file will be
used by the bidscoiner to do the conversion of the source data to BIDS.

You can hoover with your mouse over items to get help text (pop-up tooltips).
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse
import textwrap
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parents[2]))
from bidscoin import bidsmap_template


def get_parser() -> argparse.ArgumentParser:
    """Build an argument parser with input arguments for bidseditor.py"""

    parser = argparse.ArgumentParser(prog='bidseditor',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog=textwrap.dedent("""
                                         examples:
                                           bidseditor myproject/bids
                                           bidseditor myproject/bids -t bidsmap_dccn.yaml
                                           bidseditor myproject/bids -b my/custom/bidsmap.yaml"""))

    parser.add_argument('bidsfolder',      help='The destination folder with the (future) bids data')
    parser.add_argument('-b','--bidsmap',  help='The study bidsmap file with the mapping heuristics. If the bidsmap filename is just the basename (i.e. no "/" in the name) then it is assumed to be located in the current directory or in bidsfolder/code/bidscoin. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-t','--template', help=f'The template bidsmap file with the default heuristics (this could be provided by your institute). If the bidsmap filename is just the basename (i.e. no "/" in the name) then it is assumed to be located in the bidscoin config folder. Default: {bidsmap_template.stem}', default=bidsmap_template)

    return parser
