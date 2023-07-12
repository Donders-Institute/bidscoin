#!/usr/bin/env python3
""" Reads and writes SIEMENS advanced physiological log / DICOM files (See also cli/_physio2tsv.py)"""

import logging
import coloredlogs
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parents[2]))
import bidscoin.utilities.physio as ph

# Set-up logging
LOGGER = logging.getLogger(__name__)
if not LOGGER.handlers:
    coloredlogs.install(fmt='%(asctime)s - %(levelname)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


def main():
    """Console script entry point"""

    from bidscoin.cli._physio2tsv import get_parser

    args   = get_parser().parse_args()
    physio = ph.readphysio(args.physiofile)
    ph.physio2tsv(physio, args.tsvfile)


if __name__ == "__main__":
    main()
