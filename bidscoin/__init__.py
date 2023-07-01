"""
BIDScoin is a toolkit to convert and organize raw data-sets according to the Brain Imaging Data Structure (BIDS)

The basic workflow is to run these two commandline tools:

  $ bidsmapper sourcefolder bidsfolder        # This produces a study bidsmap and launches a GUI
  $ bidscoiner sourcefolder bidsfolder        # This converts your data to BIDS according to the study bidsmap

The `bids` library module can be used to build plugins and interact with bidsmaps. The `bcoin` module can be
used as a library as well from the commandline to get help and perform generic management tasks.

For more documentation see: https://bidscoin.readthedocs.io

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path

__version__ = (Path(__file__).parent/'version.txt').read_text().strip()
