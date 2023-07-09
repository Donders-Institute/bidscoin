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

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import urllib.request
import json
from pathlib import Path
from importlib.metadata import version as libversion
from typing import Tuple, Union
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
try:
    from .due import due, Doi
except ImportError:
    from due import due, Doi

# Add the BIDScoin citation
due.cite(Doi('10.3389/fninf.2021.770608'), description='A toolkit to convert source data to the Brain Imaging Data Structure (BIDS)', path='bidscoin')

# Get the BIDScoin version
try:
    __version__ = libversion('bidscoin')
except Exception:
    with open(Path(__file__).parents[1]/'pyproject.toml', 'rb') as fid:
        __version__ = tomllib.load(fid)['project']['version']

# Define the default paths
tutorialurl      = 'https://surfdrive.surf.nl/files/index.php/s/HTxdUbykBZm2cYM/download'
bidscoinfolder   = Path(__file__).parent
schemafolder     = bidscoinfolder/'schema'
heuristicsfolder = bidscoinfolder/'heuristics'
pluginfolder     = bidscoinfolder/'plugins'
bidsmap_template = heuristicsfolder/'bidsmap_dccn.yaml'     # Default template bidsmap TODO: make it a user setting (in $HOME)?


def version(check: bool=False) -> Union[str, Tuple]:
    """
    Reads the BIDSCOIN version from the VERSION.TXT file and from pypi

    :param check:   Check if the current version is up-to-date
    :return:        The version number or (version number, checking message) if check=True
    """

    # Check pypi for the latest version number
    if check:
        try:
            stream      = urllib.request.urlopen('https://pypi.org/pypi/bidscoin/json').read()
            pypiversion = json.loads(stream)['info']['version']
        except Exception as pypierror:
            return __version__, "(Could not check for new BIDScoin versions)"
        if __version__ != pypiversion:
            return __version__, f"NB: Your BIDScoin version is NOT up-to-date: {__version__} -> {pypiversion}"
        else:
            return __version__, "Your BIDScoin version is up-to-date :-)"

    return __version__


def bidsversion() -> str:
    """
    Reads the BIDS version from the BIDS_VERSION.TXT file

    :return:    The BIDS version number
    """

    return (schemafolder/'BIDS_VERSION').read_text().strip()
