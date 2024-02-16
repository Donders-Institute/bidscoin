"""
BIDScoin is a toolkit to convert and organize raw data-sets according to the Brain Imaging Data Structure (BIDS)

The basic workflow is to run these two commandline tools:

  $ bidsmapper sourcefolder bidsfolder        # This produces a study bidsmap and launches a GUI
  $ bidscoiner sourcefolder bidsfolder        # This converts your data to BIDS according to the study bidsmap

The `bids` library module can be used to build plugins and interact with bidsmaps. The `bcoin` module can be
used as a library as well from the commandline to get help and perform generic management tasks.

For more documentation see: https://bidscoin.readthedocs.io
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import urllib.request, urllib.parse, urllib.error
import json
import getpass
import os
import platform
import hashlib
import shelve
import datetime
import shutil
import warnings
import tempfile
from pathlib import Path
from importlib import metadata
from typing import Tuple, Union, List
from .due import due, Doi
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

# Get the BIDScoin version
try:
    __version__ = metadata.version('bidscoin')
except Exception:
    with open(Path(__file__).parents[1]/'pyproject.toml', 'rb') as fid:
        __version__ = tomllib.load(fid)['project']['version']

# Add license metadata
__license__    = 'GNU General Public License v3 or later (GPLv3+)'
__copyright__  = f"2018-{datetime.date.today().year}, Marcel Zwiers"
__disclaimer__ = """\
This module and all modules in this package are part of BIDScoin (https://github.com/Donders-Institute/bidscoin).

BIDScoin is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License
as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

BIDScoin is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details. 
"""

# Define the default paths
tracking     = {'url': 'https://telemetry.dccn.nl/bidscoin', 'sleep': 1}              # Sleep = Nr of sleeping hours during which usage is not tracked
tutorialurl  = 'https://surfdrive.surf.nl/files/index.php/s/HTxdUbykBZm2cYM/download'
bidscoinroot = Path(__file__).parent
schemafolder = bidscoinroot/'schema'
pluginfolder = bidscoinroot/'plugins'

# Get the BIDSCOIN_DEBUG environment variable to set the log-messages and logging level, etc
DEBUG = os.getenv('BIDSCOIN_DEBUG','').upper() in ('1', 'TRUE', 'Y', 'YES')

# Create a BIDScoin user configuration directory if needed and load the BIDScoin user settings
configfile = Path(os.getenv('BIDSCOIN_CONFIGDIR') or
                  (Path.home() if os.access(Path.home(),os.W_OK) else Path(tempfile.gettempdir()))/'.bidscoin')/__version__/'config.toml'
templatefolder = configfile.parent/'templates'
templatefolder.mkdir(parents=True, exist_ok=True)
if not configfile.is_file():
    print(f"Creating BIDScoin configuration:\n-> {configfile}")
    configfile.write_text(f"[bidscoin]\n"
                          f"bidsmap_template = '{templatefolder}/bidsmap_dccn.yaml'     # The default template bidsmap (change to use a different default)\n"
                          f"trackusage       = 'yes'     # Upload anonymous usage data if 'yes' (maximally 1 upload every {tracking['sleep']} hour) (see `bidscoin --tracking show`)\n")
for template in list((bidscoinroot/'heuristics').glob('*.yaml')) + [bidscoinroot/'heuristics'/'schema.json']:
    if not (templatefolder/template.name).is_file():
        print(f"-> {templatefolder/template.name}")
        shutil.copyfile(template, templatefolder/template.name)
with configfile.open('+rb') as fid:
    config = tomllib.load(fid)
bidsmap_template = Path(config['bidscoin']['bidsmap_template'])
if not bidsmap_template.is_file():
    warnings.warn(f"Missing template bidsmap: {bidsmap_template} (see {configfile})", RuntimeWarning)

# Register the BIDScoin citation
due.cite(Doi('10.3389/fninf.2021.770608'), description='A versatile toolkit to convert source data to the Brain Imaging Data Structure (BIDS)',
         path='bidscoin', version=__version__, cite_module=True, tags=['reference-implementation'])


def check_version() -> Tuple[str, Union[bool, None], str]:
    """
    Compares the BIDSCOIN version from the local metadata to the remote pypi repository

    :return:    A `(pypi version number, up-to-date-boolean, checking message)` tuple
    """

    # Check pypi for the latest version number
    try:
        stream      = urllib.request.urlopen('https://pypi.org/pypi/bidscoin/json', timeout=5).read()
        pypiversion = json.loads(stream)['info']['version']
    except Exception as pypierror:
        print(pypierror)
        return '', None, '(Could not check https://pypi.org/pypi/bidscoin for new BIDScoin versions)'
    if __version__.split('+')[0] != pypiversion:
        return pypiversion, False, f"NB: Your BIDScoin version is NOT up-to-date: {__version__} -> {pypiversion}"
    else:
        return pypiversion, True, 'Your BIDScoin version is up-to-date :-)'


def bidsversion() -> str:
    """
    Reads the BIDS version from the BIDS_VERSION.TXT file

    :return:    The BIDS version number
    """

    return (schemafolder/'BIDS_VERSION').read_text().strip()


def lsdirs(folder: Path, wildcard: str='*') -> List[Path]:
    """
    Gets all sorted directories in a folder, ignores files. Foldernames starting with a dot are considered hidden and will be skipped

    :param folder:      The full pathname of the folder
    :param wildcard:    Simple (glob.glob) shell-style wildcards. Use '**/wildcard for recursive search'
    :return:            A list with all directories in the folder
    """

    # Checks if a path is or contains a hidden rootfolder
    is_hidden = lambda path: any([part.startswith('.') for part in path.parts])

    return sorted([item for item in sorted(folder.glob(wildcard)) if item.is_dir() and not is_hidden(item.relative_to(folder))])


def trackusage(event: str, dryrun: bool=False) -> dict:
    """Sends a url GET request with usage data parameters (if tracking is allowed and we are not asleep)

    :param event:  A label that describes the tracking event
    :param dryrun: Collect the usage data but don't actually send anything
    :return:       The usage data
    """

    data = {'event':    event,
            'bidscoin': __version__,
            'python':   platform.python_version(),
            'system':   platform.system(),
            'release':  platform.release(),
            'userid':   hashlib.md5(getpass.getuser().encode('utf8')).hexdigest(),
            'hostid':   hashlib.md5(platform.node().encode('utf8')).hexdigest()}

    # Check if the user allows tracking or if it is a dry/test run
    if not config['bidscoin'].get('trackusage', 'yes') == 'yes' or dryrun or "PYTEST_CURRENT_TEST" in os.environ:
        return data

    # Check if we are not asleep
    trackfile = configfile.parent/'usage'/f"bidscoin_{data['userid']}"
    trackfile.parent.mkdir(parents=True, exist_ok=True)
    try:
        with shelve.open(str(trackfile), 'c', writeback=True) as tracked:
            now    = datetime.datetime.now()
            before = tracked.get(event, now.replace(year=2000))
            if (now - before).total_seconds() < tracking['sleep'] * 60 * 60:
                return data
            tracked[event] = now

    except Exception as shelveerror:
        warnings.warn(f"Please report the following error to the developers:\n{shelveerror}", RuntimeWarning)
        for corruptfile in trackfile.parent.glob(trackfile.stem + '.*'):
            corruptfile.unlink()
        data['event'] = 'trackusage_exception'

    # Upload the usage data
    try:
        req = urllib.request.Request(f"{tracking['url']}?{urllib.parse.urlencode(data)}", headers={'User-agent': 'bidscoin-telemetry'})
        with urllib.request.urlopen(req, timeout=5) as f: pass
    except urllib.error.URLError as urlerror:
        print(f"{tracking['url']}:\n{urlerror}")

    return data
