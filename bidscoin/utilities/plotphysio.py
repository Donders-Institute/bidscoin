#!/usr/bin/env python3
""" Plots SIEMENS advanced physiological log/DICOM files (See also cli/_plotphysio.py)"""

import logging
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parents[2]))
import bidscoin.utilities.physio as ph

# Set-up logging
LOGGER = logging.getLogger(__name__)


def main():
    """Console script entry point"""

    from bidscoin.cli._plotphysio import get_parser
    from bidscoin import bcoin

    bcoin.setup_logging()
    args   = get_parser().parse_args()
    physio = ph.readphysio(args.filename)
    ph.plotphysio(physio, args.showsamples)


if __name__ == "__main__":
    main()
