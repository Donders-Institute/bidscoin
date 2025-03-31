"""
BIDScoin is a toolkit to convert and organize raw data-sets according to the Brain Imaging Data Structure (BIDS)

The basic workflow is to run these two command-line tools:

  $ bidsmapper sourcefolder bidsfolder        # This produces a study bidsmap and launches a GUI
  $ bidscoiner sourcefolder bidsfolder        # This converts your data to BIDS according to the study bidsmap

The `bids` library module can be used to build plugins and interact with bidsmaps. The `bcoin` module can be
used as a library as well from the command line to get help and perform generic management tasks.

For more documentation see: https://bidscoin.readthedocs.io
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import urllib.request, urllib.parse, urllib.error
import json
import getpass
import re
import os
import platform
import hashlib
import shelve
import datetime
import shutil
import warnings
import tempfile
import subprocess
import traceback
from pathlib import Path
from importlib import metadata
from typing import Union
from logging import getLogger
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
__license__    = 'GNU General Public License v3.0 or later (GPLv3+)'
__copyright__  = f"2018-{datetime.date.today().year}, Marcel Zwiers"
__disclaimer__ = """\
This module and all modules in this package are part of BIDScoin (https://github.com/Donders-Institute/bidscoin).

BIDScoin is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License
as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

BIDScoin is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details. 
"""

# Define the default paths
tutorialurl  = 'https://surfdrive.surf.nl/files/index.php/s/HTxdUbykBZm2cYM/download'
bidscoinroot = Path(__file__).parent
schemafolder = bidscoinroot/'schema'
tracking     = {'url': 'https://telemetry.dccn.nl/bidscoin', 'sleep': 1}
"""Sleep: Nr of sleeping hours during which usage/events are not tracked"""

# Get the LOGGER and BIDSCOIN_DEBUG environment variable to set the log-messages and logging level, etc
LOGGER = getLogger(__name__)
DEBUG  = os.getenv('BIDSCOIN_DEBUG','').upper() in ('1', 'TRUE', 'Y', 'YES')

# Create a BIDScoin user configuration directory if needed
configdir      = Path(os.getenv('BIDSCOIN_CONFIGDIR') or (Path.home() if os.access(Path.home(),os.W_OK) else Path(tempfile.gettempdir()))/'.bidscoin')/__version__
configfile     = configdir/'config.toml'
pluginfolder   = configdir/'plugins'
pluginfolder.mkdir(parents=True, exist_ok=True)
templatefolder = configdir/'templates'
templatefolder.mkdir(parents=True, exist_ok=True)
if not configfile.is_file():
    print(f"Creating BIDScoin user configuration:\n-> {configfile}")
    configfile.write_text(f"[bidscoin]\n"
                          f"bidsmap_template = '{templatefolder}/bidsmap_dccn.yaml'     # The default template bidsmap (change to use a different default)\n"
                          f"trackusage       = 'yes'     # Upload anonymous usage data if 'yes' (maximally 1 upload every {tracking['sleep']} hour) (see `bidscoin --tracking show`)\n")
if not (configdir/'README').is_file():
    (configdir/'README').write_text(f"You can add or adapt all files in this directory to suit your needs. The pre-installed files will automatically be re-created from source when deleted / missing")
for plugin in (bidscoinroot/'plugins').glob('*.py'):
    if not (pluginfolder/plugin.name).is_file() and not plugin.name.startswith('_'):
        print(f"-> {pluginfolder/plugin.name}")
        shutil.copyfile(plugin, pluginfolder/plugin.name)
for template in [*(bidscoinroot/'heuristics').glob('*.yaml')] + [bidscoinroot/'heuristics'/'schema.json']:
    if not (templatefolder/template.name).is_file():
        print(f"-> {templatefolder/template.name}")
        shutil.copyfile(template, templatefolder/template.name)

# Load the BIDScoin user settings
with configfile.open('+rb') as fid:
    config = tomllib.load(fid)
bidsmap_template = Path(config['bidscoin']['bidsmap_template'])
if not bidsmap_template.is_file():
    warnings.warn(f"Missing template bidsmap: {bidsmap_template} (see {configfile})", RuntimeWarning)

# Register the BIDScoin citation
due.cite(Doi('10.3389/fninf.2021.770608'), description='A versatile toolkit to convert source data to the Brain Imaging Data Structure (BIDS)',
         path='bidscoin', version=__version__, cite_module=True, tags=['reference-implementation'])


def check_version() -> tuple[str, Union[bool, None], str]:
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


def is_hidden(path: Path):
    """Checks if the filename or one of its parent folders is hidden"""

    hidden = any(part.startswith('.') for part in path.parts)
    if hidden:
        LOGGER.verbose(f"Ignoring hidden file/folder: {path}")

    return hidden


def lsdirs(folder: Path, wildcard: str='*') -> list[Path]:
    """
    Gets all sorted directories in a folder, ignores files. Foldernames starting with a dot are considered hidden and will be skipped

    :param folder:      The full pathname of the folder
    :param wildcard:    Simple (glob.glob) shell-style wildcards. Use '**/wildcard for recursive search'
    :return:            A list with all directories in the folder
    """

    return sorted([item for item in sorted(folder.glob(wildcard)) if item.is_dir() and not is_hidden(item.relative_to(folder))])


def run_command(command: str, success: tuple=(0,None)) -> int:
    """
    Runs a command in a shell using subprocess.run(command, ..)

    :param command: The command that is executed
    :param success: The return codes for successful operation (e,g, for dcm2niix it is (0,3))
    :return:        The return code (e.g. 0 if the command was successfully executed (no errors), > 0 otherwise)
    """

    LOGGER.verbose(f"Command:\n{command}")
    process = subprocess.run(command, shell=True, capture_output=True, text=True)
    if (process.stderr and 'spec2nii' not in command) or process.returncode not in success:
        LOGGER.error(f"Failed to run:\n{command}\nErrorcode {process.returncode}:\n{process.stdout}\n{process.stderr}")
    else:
        LOGGER.verbose(f"Output:\n{process.stdout}")

    return process.returncode


def trackusage(event: str, message='', dryrun: bool=False) -> dict:
    """Sends a url GET request with usage data parameters (if tracking is allowed and we are not asleep)

    :param event:   A label that describes the tracking event
    :param message: An (error) message that is added to the usage data
    :param dryrun:  Collect the usage data but don't actually send anything
    :return:        The usage data
    """

    # Collect the usage data
    data = {'event':    event,
            'bidscoin': __version__,
            'python':   platform.python_version(),
            'system':   platform.system(),
            'release':  platform.release(),
            'userid':   hashlib.md5(getpass.getuser().encode('utf8')).hexdigest(),
            'hostid':   hashlib.md5(platform.node().encode('utf8')).hexdigest()}
    if message:
        if isinstance(message, Exception):
            trace   = traceback.extract_tb(traceback.sys.exc_info()[2])[-1]     # Get the last traceback entry
            message = f"{message} ({trace.filename},{trace.lineno})"            # Append the traceback info
        data['message'] = str(message)
    if container := os.getenv('CONTAINER'):
        data['container'] = container

    # Return if the user disallows tracking, if it is a dry-, pytest-, or a DRMAA-run, or if this is not a stable (#.#.#) version
    if not (os.getenv('BIDSCOIN_TRACKUSAGE') or config['bidscoin'].get('trackusage','yes')).upper() in ('1', 'TRUE', 'Y', 'YES') or dryrun \
            or "PYTEST_CURRENT_TEST" in os.environ or 'BIDSCOIN_JOB' in os.environ or re.match(r"^\d+\.\d+\.\d+$", __version__) is None:
        return data

    # Return if we are asleep
    trackfile = configdir/'usage'/f"bidscoin_{data['userid']}"
    try:
        trackfile.parent.mkdir(parents=True, exist_ok=True)
        with shelve.open(str(trackfile), writeback=True) as tracked:
            now    = datetime.datetime.now()
            before = tracked.get(event, now.replace(year=2000))
            if (now - before).total_seconds() < tracking['sleep'] * 60 * 60:
                return data
            tracked[event] = now

    # If something goes wrong, add an error message, clear the shelf and return if we can't sleep
    except Exception as shelveerror:
        data['event']   = 'trackusage_exception'
        data['message'] = f"({event}){shelveerror}"
        for corruptfile in (shelvefiles := list(trackfile.parent.glob(trackfile.name + '.*'))):
            print(f"Deleting corrupt file: {corruptfile}")
            corruptfile.unlink()
        if not shelvefiles:                         # Return without uploading (no shelve files means no sleep)
            warnings.warn(f"Please report the following error to the developers:\n{shelveerror}: {trackfile}", RuntimeWarning)
            return data

    # Upload the usage data
    try:
        req = urllib.request.Request(f"{tracking['url']}?{urllib.parse.urlencode(data)}", headers={'User-agent': 'bidscoin-telemetry'})
        with urllib.request.urlopen(req, timeout=3) as f: pass
    except urllib.error.URLError as urlerror:
        print(f"{tracking['url']}:\n{urlerror}")

    return data
