#!/usr/bin/env python3
"""
BIDScoin is a toolkit to convert and organize raw data-sets according to the Brain Imaging Data Structure (BIDS)

The basic workflow is to run these two tools:

  $ bidsmapper sourcefolder bidsfolder        # This produces a study bidsmap and launches a GUI
  $ bidscoiner sourcefolder bidsfolder        # This converts your data to BIDS according to the study bidsmap

For more documentation see: https://bidscoin.readthedocs.io
"""

import argparse
import textwrap
import tarfile
import shutil
import ssl
import sys
import logging
import coloredlogs
import inspect
import subprocess
import urllib.request
import json
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
from importlib.metadata import entry_points
from typing import Tuple, Union, List

tutorialurl    = 'https://surfdrive.surf.nl/files/index.php/s/HTxdUbykBZm2cYM/download'
bidscoinfolder = Path(__file__).parent
LOGGER         = logging.getLogger(__name__)


def setup_logging(log_file: Path=Path(), debug: bool=False):
    """
    Setup the logging

    :param log_file:    Name of the logfile
    :param debug:       Set log level to DEBUG if debug==True
    :return:
     """

    # Get the root logger
    logger = logging.getLogger()

    # Set the format and logging level
    if debug:
        fmt = '%(asctime)s - %(name)s - %(levelname)s | %(message)s'
        logger.setLevel(logging.DEBUG)
    else:
        fmt = '%(asctime)s - %(levelname)s | %(message)s'
        logger.setLevel(logging.INFO)
    datefmt   = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    # Set & add the streamhandler and add some color to those boring terminal logs! :-)
    coloredlogs.install(level=logger.level, fmt=fmt, datefmt=datefmt)

    if not log_file.name:
        return

    # Set & add the log filehandler
    log_file.parent.mkdir(parents=True, exist_ok=True)      # Create the log dir if it does not exist
    loghandler = logging.FileHandler(log_file)
    loghandler.setLevel(logging.DEBUG)
    loghandler.setFormatter(formatter)
    loghandler.set_name('loghandler')
    logger.addHandler(loghandler)

    # Set & add the error / warnings handler
    error_file = log_file.with_suffix('.errors')            # Derive the name of the error logfile from the normal log_file
    errorhandler = logging.FileHandler(error_file, mode='w')
    errorhandler.setLevel(logging.WARNING)
    errorhandler.setFormatter(formatter)
    errorhandler.set_name('errorhandler')
    logger.addHandler(errorhandler)


def version(check: bool=False) -> Union[str, Tuple]:
    """
    Reads the BIDSCOIN version from the VERSION.TXT file and from pypi

    :param check:   Check if the current version is up-to-date
    :return:        The version number or (version number, checking message) if check=True
    """

    localversion = (Path(__file__).parent/'version.txt').read_text().strip()

    # Check pypi for the latest version number
    if check:
        try:
            stream      = urllib.request.urlopen('https://pypi.org/pypi/bidscoin/json').read()
            pypiversion = json.loads(stream)['info']['version']
        except Exception as pypierror:
            print(f"Checking BIDScoin version on https://pypi.org/pypi/bidscoin failed:\n{pypierror}")
            return localversion, "(Could not check for new BIDScoin versions)"
        if localversion != pypiversion:
            return localversion, f"NB: Your BIDScoin version is NOT up-to-date: {localversion} -> {pypiversion}"
        else:
            return localversion, "Your BIDScoin version is up-to-date :-)"

    return localversion


def bidsversion() -> str:
    """
    Reads the BIDS version from the BIDSVERSION.TXT file

    :return:    The BIDS version number
    """

    return (Path(__file__).parent/'bidsversion.txt').read_text().strip()


def reporterrors() -> None:
    """
    Summarized the warning and errors from the logfile

    :return:
    """

    # Find the filehandlers and report the errors and warnings
    for filehandler in logging.getLogger().handlers:
        if filehandler.name == 'errorhandler':

            errorfile = Path(filehandler.baseFilename)
            if errorfile.stat().st_size:
                LOGGER.info(f"The following BIDScoin errors and warnings were reported:\n\n{40 * '>'}\n{errorfile.read_text()}{40 * '<'}\n")

            else:
                LOGGER.info(f'No BIDScoin errors or warnings were reported')
                LOGGER.info('')

        elif filehandler.name == 'loghandler':
            logfile = Path(filehandler.baseFilename)

    # Final message
    if 'logfile' in locals():
        LOGGER.info(f"For the complete log see: {logfile}\n"
                    f"NB: Files in {logfile.parent} may contain privacy sensitive information, e.g. pathnames in logfiles and provenance data samples")


def run_command(command: str) -> bool:
    """
    Runs a command in a shell using subprocess.run(command, ..)

    :param command: The command that is executed
    :return:        True if the were no errors, False otherwise
    """

    LOGGER.info(f"Running: {command}")
    process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)          # TODO: investigate shell=False and capture_output=True for python 3.7
    LOGGER.info(f"Output:\n{process.stdout.decode('utf-8')}")

    if process.stderr.decode('utf-8') or process.returncode!=0:
        LOGGER.exception(f"Failed to run:\n{command}\nErrorcode {process.returncode}:\n{process.stderr.decode('utf-8')}")
        return False

    return True


def lsdirs(folder: Path, wildcard: str='*') -> List[Path]:
    """
    Gets all directories in a folder, ignores files

    :param folder:      The full pathname of the folder
    :param wildcard:    Simple (glob.glob) shell-style wildcards. Foldernames starting with a dot are considered hidden and will be skipped"
    :return:            A list with all directories in the folder
    """

    return [fname for fname in sorted(folder.glob(wildcard)) if fname.is_dir() and not fname.name.startswith('.')]


def list_executables(show: bool=False) -> list:
    """
    :return:                Nothing
    """

    if show:
        print('BIDScoin executables:')

    scripts = []
    for script in entry_points()['console_scripts']:
        if script.value.startswith('bidscoin'):
            scripts.append(script.name)
            if show:
                print(f"- {script.name}")

    return scripts


def list_plugins(show: bool=False) -> list:
    """
    :param show: Print the installed plugins if True
    :return:     List of the installed plugins
    """

    if show:
        print('BIDScoin installed plugins:')

    plugins = []
    for plugin in (bidscoinfolder/'plugins').glob('*.py'):
        if plugin.stem != '__init__':
            plugins.append(plugin)
            if show:
                print(f"- {plugin.stem}")

    return plugins


def install_plugins(plugins: Tuple[Path]=()) -> bool:
    """
    :return:                Nothing
    """

    if not plugins:
        return True

    for plugin in plugins:
        plugin = Path(plugin)
        print(f"Installing: '{plugin}'")
        try:
            shutil.copyfile(plugin, bidscoinfolder/'plugins'/plugin.with_suffix('.py').name)
        except IOError as install_failure:
            print(f"{install_failure}\nFailed to install: '{plugin.name}' in '{bidscoinfolder/'plugins'}'")
            return False
        if not import_plugin(plugin, ('bidsmapper_plugin', 'bidscoiner_plugin')):
            print(f"Import failure, please re-install a valid version of '{plugin.name}'")
            return False

    return True


def uninstall_plugins(plugins: Tuple[str]=()) -> bool:
    """
    :return:                Nothing
    """

    if not plugins:
        return True

    for plugin in plugins:
        try:
            print(f"Uninstalling: '{plugin}'")
            (bidscoinfolder/'plugins'/plugin).with_suffix('.py').unlink()
        except IOError as uninstall_failure:
            print(f"Failed to uninstall: '{plugin}' in '{bidscoinfolder/'plugins'}', Exciting\n{uninstall_failure}")
            return False

    return True


def import_plugin(plugin: Path, functions: tuple=()) -> module_from_spec:
    """
    Imports the plugin if it contains any of the specified functions

    :param plugin:      Name of the plugin in the bidscoin "plugins" folder or the fullpath name
    :param functions:   List of functions of which at least one of them should be present in the plugin
    :return:            The imported plugin-module
    """

    # Get the full path to the plugin-module
    plugin = Path(plugin).with_suffix('.py')
    if len(plugin.parents) == 1:
        plugin = Path(__file__).parent/'plugins'/plugin

    # See if we can find the plug-in
    if not plugin.is_file():
        LOGGER.error(f"Could not find plugin: '{plugin}'")
        return None

    # Load the plugin-module
    LOGGER.info(f"Importing plugin: '{plugin}'")
    try:
        spec   = spec_from_file_location('bidscoin.plugin.' + plugin.stem, plugin)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

        functionsfound = []
        for function in functions:
            if function not in dir(module):
                LOGGER.debug(f"Could not find '{function}' in the '{plugin}' plugin")
            elif not callable(getattr(module, function)):
                LOGGER.error(f"'The {function}' attribute in the '{plugin}' plugin is not callable")
            else:
                functionsfound.append(function)

        if functions and not functionsfound:
            LOGGER.info(f"Plugin '{plugin}' does not contain {functions} functions")
        else:
            return module

    except Exception as pluginerror:
        LOGGER.exception(f"Could not import {plugin}:\n{pluginerror}")


def test_plugin(plugin: Path, options: dict) -> bool:
    """
    Performs import tests of the plug-in

    :param plugin:  The name of the plugin that is being tested
    :return:        True if the plugin generated the expected result, False if there
                    was a plug-in error, None if this function has an implementation error
    """

    LOGGER.info(f"Testing the '{plugin}' plugin:")

    # First test to see if we can import the plugin
    module = import_plugin(plugin, ('bidsmapper_plugin','bidscoiner_plugin'))
    if inspect.ismodule(module):
        LOGGER.info(f"Succesfully imported the '{plugin}' docstring:\n{module.__doc__}")
    else:
        return False

    # Then run the plugin's own 'test' routine (if implemented)
    if 'test' in dir(module) and callable(getattr(module, 'test')):
        try:
            return module.test(options)
        except Exception as pluginerror:
            LOGGER.exception(f"Could not run {plugin}.test(options):\n{pluginerror}")
            return False

    return True


def test_bidscoin(options: dict):
    """
    WIP
    :return:
    """
    LOGGER.info('Testing BIDScoin: not (yet) implemented :-)')

    return True


def pulltutorialdata(tutorialfolder: str) -> None:
    """
    Download and unzip tutorial.tar.gz file

    :param tutorialfolder:  The full pathname of the target folder in which the tutorial data will be downloaded
    :return:
    """

    if not tutorialfolder:
        return

    tutorialfolder = Path(tutorialfolder).resolve()
    tutorialtargz  = tutorialfolder/'bidscointutorial.tar.gz'
    tutorialfolder.mkdir(parents=True, exist_ok=True)

    # Download the data, avoiding ssl certificate issues
    print(f"Downloading the tutorial dataset...")
    with urllib.request.urlopen(tutorialurl, context=ssl.SSLContext()) as data, open(tutorialtargz, 'wb') as targz_fid:
        shutil.copyfileobj(data, targz_fid)

    # Unzip the data in the target folder
    print(f"Unzipping the downloaded data in: {tutorialfolder}")
    with tarfile.open(tutorialtargz, 'r') as targz_fid:
        targz_fid.extractall(tutorialfolder)
    tutorialtargz.unlink()


def main():
    """Console script usage"""

    localversion, versionmessage = version(check=True)

    # Parse the input arguments and run bidscoiner(args)
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidscoin -l\n'
                                            '  bidscoin -d data/bidscoin_tutorial\n'
                                            '  bidscoin -i python/project/my_plugin.py downloads/handy_plugin.py\n ')
    parser.add_argument('-l', '--list',      help='List all bidscoin tools', action='store_true')
    parser.add_argument('-p', '--plugins',   help='List all installed plugins', action='store_true')
    parser.add_argument('-i', '--install',   help='A list of bidscoin plugins to install', nargs='+')
    parser.add_argument('-u', '--uninstall', help='A list of bidscoin plugins to uninstall', nargs='+')
    parser.add_argument('-d', '--download',  help='Download folder. If given, tutorial MRI data will be downloaded here')
    # parser.add_argument('-t', '--test',      help='Test the bidscoin installation', action='store_true')  # TODO: implement bidscoin tests
    parser.add_argument('-v', '--version',   help='Show the installed version and check for updates', action='version', version=f"BIDS-version:\t\t{bidsversion()}\nBIDScoin-version:\t{localversion}, {versionmessage}")
    if len(sys.argv) == 1:
        parser.print_help()
        return
    args = parser.parse_args()

    list_executables(show=args.list)
    list_plugins(show=args.plugins)
    uninstall_plugins(plugins=args.uninstall)
    install_plugins(plugins=args.install)
    pulltutorialdata(tutorialfolder=args.download)


if __name__ == "__main__":
    main()
