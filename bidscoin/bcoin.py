#!/usr/bin/env python3
"""
BIDScoin is a toolkit to convert and organize raw data-sets according to the Brain Imaging Data Structure (BIDS)

The basic workflow is to run these two tools:

  $ bidsmapper sourcefolder bidsfolder        # This produces a study bidsmap and launches a GUI
  $ bidscoiner sourcefolder bidsfolder        # This converts your data to BIDS according to the study bidsmap

Set the environment variable BIDSCOIN_DEBUG=TRUE in your console to run BIDScoin in its more verbose DEBUG logging mode

For more documentation see: https://bidscoin.readthedocs.io
"""

import argparse
import coloredlogs
import inspect
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
import textwrap
import urllib.request
from functools import lru_cache
from importlib.metadata import entry_points
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from typing import Tuple, Union, List
from ruamel.yaml import YAML
from tqdm import tqdm
try:
    from .due import due, Doi
except ImportError:
    from due import due, Doi

yaml = YAML()

# Add the BIDScoin citation
due.cite(Doi('10.3389/fninf.2021.770608'), description='A toolkit to convert source data to the Brain Imaging Data Structure (BIDS)', path='bidscoin')

# Define the default paths
tutorialurl      = 'https://surfdrive.surf.nl/files/index.php/s/HTxdUbykBZm2cYM/download'
bidscoinfolder   = Path(__file__).parent
schemafolder     = bidscoinfolder/'schema'
heuristicsfolder = bidscoinfolder/'heuristics'
pluginfolder     = bidscoinfolder/'plugins'
bidsmap_template = heuristicsfolder/'bidsmap_dccn.yaml'     # Default template bidsmap TODO: make it a user setting (in $HOME)?

# Get the BIDSCOIN_DEBUG environment variable to set the log-messages and logging level, etc
debug  = os.environ.get('BIDSCOIN_DEBUG')
debug  = True if debug and debug.upper() not in ('0', 'FALSE', 'N', 'NO', 'NONE') else False

LOGGER = logging.getLogger(__name__)

class TqdmUpTo(tqdm):

    def update_to(self, b=1, bsize=1, tsize=None):
        """
        Adds a tqdm progress bar to urllib.request.urlretrieve()
        https://gist.github.com/leimao/37ff6e990b3226c2c9670a2cd1e4a6f5

        :param b:       Number of blocks transferred so far [default: 1].
        :param bsize:   Size of each block (in tqdm units) [default: 1].
        :param tsize:   Total size (in tqdm units). If [default: None] remains unchanged.
        """
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)  # will also set self.n = b * bsize


def setup_logging(logfile: Path=Path()):
    """
    Set up the logging framework:
    1) Add a 'bcdebug', 'verbose' and a 'success' logging level
    2) Add a console streamhandler
    3) If logfile then add a normal log and a warning/error filehandler

    :param logfile:     Name of the logfile
    :return:
     """

    # Set the default formats
    if debug:
        fmt  = '%(asctime)s - %(name)s - %(levelname)s | %(message)s'
        cfmt = '%(levelname)s - %(name)s | %(message)s'
    else:
        fmt  = '%(asctime)s - %(levelname)s | %(message)s'
        cfmt = '%(levelname)s | %(message)s'
    datefmt  = '%Y-%m-%d %H:%M:%S'

    # Add a BIDScoin debug logging level = 11 (NB: using the standard debug mode will generate may debug messages from imports)
    logging.BCDEBUG = 11
    logging.addLevelName(logging.BCDEBUG, 'BCDEBUG')
    logging.__all__ += ['BCDEBUG'] if 'BCDEBUG' not in logging.__all__ else []
    def bcdebug(self, message, *args, **kws):
        if self.isEnabledFor(logging.BCDEBUG): self._log(logging.BCDEBUG, message, args, **kws)
    logging.Logger.bcdebug = bcdebug

    # Add a verbose logging level = 15
    logging.VERBOSE = 15
    logging.addLevelName(logging.VERBOSE, 'VERBOSE')
    logging.__all__ += ['VERBOSE'] if 'VERBOSE' not in logging.__all__ else []
    def verbose(self, message, *args, **kws):
        if self.isEnabledFor(logging.VERBOSE): self._log(logging.VERBOSE, message, args, **kws)
    logging.Logger.verbose = verbose

    # Add a success logging level = 25
    logging.SUCCESS = 25
    logging.addLevelName(logging.SUCCESS, 'SUCCESS')
    logging.__all__ += ['SUCCESS'] if 'SUCCESS' not in logging.__all__ else []
    def success(self, message, *args, **kws):
        if self.isEnabledFor(logging.SUCCESS): self._log(logging.SUCCESS, message, args, **kws)
    logging.Logger.success = success

    # Set the root logging level
    logger = logging.getLogger()
    logger.setLevel('BCDEBUG' if debug else 'VERBOSE')

    # Add the console streamhandler and bring some color to those boring logs! :-)
    coloredlogs.install(level='BCDEBUG' if debug else 'VERBOSE' if not logfile.name else 'INFO', fmt=cfmt, datefmt=datefmt)   # NB: Using tqdm sets the streamhandler level to 0, see: https://github.com/tqdm/tqdm/pull/1235
    coloredlogs.DEFAULT_LEVEL_STYLES['verbose']['color'] = 245  # = Gray

    if not logfile.name:
        if debug: LOGGER.info('\t<<<<<<<<<< Running BIDScoin in DEBUG mode >>>>>>>>>>')
        return

    # Add the log filehandler
    logfile.parent.mkdir(parents=True, exist_ok=True)      # Create the log dir if it does not exist
    formatter  = logging.Formatter(fmt=fmt, datefmt=datefmt)
    loghandler = logging.FileHandler(logfile)
    loghandler.setLevel('BCDEBUG')
    loghandler.setFormatter(formatter)
    loghandler.set_name('loghandler')
    logger.addHandler(loghandler)

    # Add the error/warnings filehandler
    errorhandler = logging.FileHandler(logfile.with_suffix('.errors'), mode='w')
    errorhandler.setLevel('WARNING')
    errorhandler.setFormatter(formatter)
    errorhandler.set_name('errorhandler')
    logger.addHandler(errorhandler)

    if debug: LOGGER.info('\t<<<<<<<<<< Running BIDScoin in DEBUG mode >>>>>>>>>>')


def reporterrors() -> str:
    """
    Summarized the warning and errors from the logfile

    :return:    The errorlog
    """

    # Find the filehandlers and report the errors and warnings
    errors = ''
    for handler in logging.getLogger().handlers:
        if handler.name == 'errorhandler':

            errorfile = Path(handler.baseFilename)
            if errorfile.is_file():
                if errorfile.stat().st_size:
                    errors = errorfile.read_text()
                    LOGGER.info(f"The following BIDScoin errors and warnings were reported:\n\n{40 * '>'}\n{errors}{40 * '<'}\n")

                else:
                    LOGGER.success(f'No BIDScoin errors or warnings were reported')
                    LOGGER.info('')

        elif handler.name == 'loghandler':
            logfile = Path(handler.baseFilename)

    # Final message
    if 'logfile' in locals():
        LOGGER.info(f"For the complete log see: {logfile}\n"
                    f"NB: That folder may contain privacy sensitive information, e.g. pathnames in logfiles and provenance data samples")

    return errors


def version(check: bool=False) -> Union[str, Tuple]:
    """
    Reads the BIDSCOIN version from the VERSION.TXT file and from pypi

    :param check:   Check if the current version is up-to-date
    :return:        The version number or (version number, checking message) if check=True
    """

    localversion = (bidscoinfolder/'version.txt').read_text().strip()

    # Check pypi for the latest version number
    if check:
        try:
            stream      = urllib.request.urlopen('https://pypi.org/pypi/bidscoin/json').read()
            pypiversion = json.loads(stream)['info']['version']
        except Exception as pypierror:
            LOGGER.info(f"Checking BIDScoin version on https://pypi.org/pypi/bidscoin failed:\n{pypierror}")
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

    return (schemafolder/'BIDS_VERSION').read_text().strip()


def run_command(command: str) -> int:
    """
    Runs a command in a shell using subprocess.run(command, ..)

    :param command: The command that is executed
    :return:        Errorcode (i.e. 0 if the command was successfully executed (no errors), > 0 otherwise)
    """

    LOGGER.info(f"Command:\n{command}")
    process = subprocess.run(command, shell=True, capture_output=True, text=True)
    if process.stderr or process.returncode != 0:
        LOGGER.error(f"Failed to run:\n{command}\nErrorcode {process.returncode}:\n{process.stdout}\n{process.stderr}")
    else:
        LOGGER.info(f"Output:\n{process.stdout}")

    return process.returncode


def lsdirs(folder: Path, wildcard: str='*') -> List[Path]:
    """
    Gets all directories in a folder, ignores files

    :param folder:      The full pathname of the folder
    :param wildcard:    Simple (glob.glob) shell-style wildcards. Foldernames starting with a dot are considered hidden and will be skipped. Use '**/wildcard for recursive search'
    :return:            A list with all directories in the folder
    """

    return sorted([fname for fname in sorted(folder.glob(wildcard)) if fname.is_dir() and not fname.name.startswith('.')])


def list_executables(show: bool=False) -> list:
    """
    :return:            List of BIDScoin console scripts
    """

    if show: LOGGER.info('Executable BIDScoin tools:')

    scripts = []
    if sys.version_info.major == 3 and sys.version_info.minor < 10:
        console_scripts = entry_points()['console_scripts']                 # Raises DeprecationWarning for python >= 3.10: SelectableGroups dict interface is deprecated
    else:
        console_scripts = entry_points().select(group='console_scripts')    # The select method was introduced in python = 3.10
    for script in console_scripts:
        if script.value.startswith('bidscoin'):
            scripts.append(script.name)
            if show: LOGGER.info(f"- {script.name}")

    return scripts


def list_plugins(show: bool=False) -> Tuple[List[Path], List[Path]]:
    """
    :param show: Print the template bidsmaps and installed plugins if True
    :return:     List of the installed plugins and template bidsmaps
    """

    if show: LOGGER.info(f"Installed template bidsmaps ({heuristicsfolder}):")
    templates = []
    for template in heuristicsfolder.glob('*.yaml'):
        if template.stem != '__init__':
            templates.append(template)
            if show: LOGGER.info(f"- {template.stem}{' (default)' if template.samefile(bidsmap_template) else ''}")

    if show: LOGGER.info(f"Installed plugins ({pluginfolder}):")
    plugins = []
    for plugin in pluginfolder.glob('*.py'):
        if plugin.stem != '__init__':
            plugins.append(plugin)
            if show: LOGGER.info(f"- {plugin.stem}")

    return plugins, templates


def install_plugins(filenames: List[str]=()) -> None:
    """
    Installs template bidsmaps and plugins and adds the plugin Options and data format section to the default template bidsmap

    :param filenames:   Fullpath filenames of the and template bidsmaps plugins that need to be installed
    :return:            Nothing
    """

    if not filenames: return

    files = [Path(file) for file in filenames if file.endswith('.yaml') or file.endswith('.py')]

    # Load the default template bidsmap
    with open(bidsmap_template, 'r') as stream:
        template = yaml.load(stream)

    # Install the template bidsmaps and plugins in their targetfolder
    for file in files:

        # Copy the file to their target folder
        targetfolder = heuristicsfolder if file.suffix == '.yaml' else pluginfolder
        LOGGER.info(f"Installing: '{file}'")
        try:
            shutil.copyfile(file, targetfolder/file.name)
        except IOError as install_failure:
            LOGGER.error(f"{install_failure}\nFailed to install: '{file.name}' in '{targetfolder}'")
            continue
        if file.suffix == '.yaml':
            LOGGER.success(f"The '{file.name}' template bidsmap was successfully installed")
            continue

        # Check if we can import the plugin
        module = import_plugin(file, ('bidsmapper_plugin', 'bidscoiner_plugin'))
        if not module:
            LOGGER.error(f"Plugin failure, please re-install a valid version of '{file.name}'")
            continue

        # Add the Options and data format section of the plugin to the default template bidsmap
        if 'OPTIONS' in dir(module) or 'BIDSMAP' in dir(module):
            if 'OPTIONS' in dir(module):
                LOGGER.info(f"Adding default {file.name} bidsmap options to the {bidsmap_template.stem} template")
                template['Options']['plugins'][file.stem] = module.OPTIONS
            if 'BIDSMAP' in dir(module):
                for key, value in module.BIDSMAP.items():
                    LOGGER.info(f"Adding default {key} bidsmappings to the {bidsmap_template.stem} template")
                    template[key] = value
            with open(bidsmap_template, 'w') as stream:
                yaml.dump(template, stream)

        LOGGER.success(f"The '{file.name}' plugin was successfully installed")


def uninstall_plugins(filenames: List[str]=(), wipe: bool=True) -> None:
    """
    Uninstalls template bidsmaps and plugins and removes the plugin Options and data format section from the default template bidsmap

    :param filenames:   Fullpath filenames of the and template bidsmaps plugins that need to be uninstalled
    :param wipe:        Removes the plugin bidsmapping section if True
    :return:            None
    """

    if not filenames: return

    files = [Path(file) for file in filenames if file.endswith('.yaml') or file.endswith('.py')]

    # Load the default template bidsmap
    with open(bidsmap_template, 'r') as stream:
        template = yaml.load(stream)

    # Uninstall the plugins
    for file in files:

        # First check if we can import the plugin
        if file.suffix == '.py':
            module = import_plugin(pluginfolder/file.name, ('bidsmapper_plugin', 'bidscoiner_plugin'))
        else:
            module = None

        # Remove the file from the target folder
        LOGGER.info(f"Uninstalling: '{file}'")
        sourcefolder = heuristicsfolder if file.suffix == '.yaml' else pluginfolder
        try:
            (sourcefolder/file.name).unlink()
        except IOError as uninstall_error:
            LOGGER.error(f"{uninstall_error}\nFailed to uninstall: '{file.name}' from {sourcefolder}")
            continue
        if file.suffix == '.yaml':
            LOGGER.success(f"The '{file.name}' template bidsmap was successfully uninstalled")
            continue

        # Remove the Options and data format section from the default template bidsmap
        if not module:
            LOGGER.warning(f"Cannot remove any {file.stem} bidsmap options from the {bidsmap_template.stem} template")
            continue
        if 'OPTIONS' in dir(module) or 'BIDSMAP' in dir(module):
            if 'OPTIONS' in dir(module):
                LOGGER.info(f"Removing default {file.stem} bidsmap options from the {bidsmap_template.stem} template")
                template['Options']['plugins'].pop(file.stem, None)
            if wipe and 'BIDSMAP' in dir(module):
                for key, value in module.BIDSMAP.items():
                    LOGGER.info(f"Removing default {key} bidsmappings from the {bidsmap_template.stem} template")
                    template.pop(key, None)
            with open(bidsmap_template, 'w') as stream:
                yaml.dump(template, stream)

        LOGGER.success(f"The '{file.stem}' plugin was successfully uninstalled")


@lru_cache()
def import_plugin(plugin: Union[Path,str], functions: tuple=()) -> module_from_spec:
    """
    Imports the plugin if it contains any of the specified functions

    :param plugin:      Name of the plugin in the bidscoin "plugins" folder or the fullpath name
    :param functions:   List of functions of which at least one of them should be present in the plugin
    :return:            The imported plugin-module
    """

    if not plugin: return

    # Get the full path to the plugin-module
    plugin = Path(plugin).with_suffix('.py')
    if len(plugin.parents) == 1:
        plugin = pluginfolder/plugin

    # See if we can find the plug-in
    if not plugin.is_file():
        LOGGER.error(f"Could not find plugin: '{plugin}'")
        return

    # Load the plugin-module
    LOGGER.verbose(f"Importing plugin: '{plugin}'")
    try:
        spec   = spec_from_file_location('bidscoin.plugin.' + plugin.stem, plugin)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

        functionsfound = []
        for function in functions:
            if function not in dir(module):
                LOGGER.verbose(f"Could not find '{function}' in the '{plugin}' plugin")
            elif not callable(getattr(module, function)):
                LOGGER.error(f"'The {function}' attribute in the '{plugin}' plugin is not callable")
            else:
                functionsfound.append(function)

        if functions and not functionsfound:
            LOGGER.info(f"Plugin '{plugin}' does not contain {functions} functions")
        else:
            return module

    except Exception as pluginerror:
        LOGGER.error(f"Could not import {plugin}:\n{pluginerror}")


def test_plugin(plugin: Union[Path,str], options: dict) -> int:
    """
    Performs runtime tests of the plug-in

    :param plugin:  The name of the plugin that is being tested
    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']['plugins'][plugin.stem]
    :return:        The result of the plugin test routine (e.g. 0 if it passed or 1 if there was a general plug-in error)
    """

    if not plugin: return 1

    LOGGER.info(f"--------- Testing the '{plugin}' plugin ---------")

    # First test to see if we can import the plugin
    module = import_plugin(plugin, ('bidsmapper_plugin','bidscoiner_plugin'))
    if not inspect.ismodule(module):
        LOGGER.error(f"Invalid plugin: '{plugin}'")
        return 1

    # Then run the plugin's own 'test' routine (if implemented)
    if 'test' in dir(module) and callable(getattr(module, 'test')):
        try:
            returncode = module.test(options)
            if returncode == 0:
                LOGGER.success(f"The'{plugin}' plugin functioned correctly")
            else:
                LOGGER.warning(f"The'{plugin}' plugin did not function correctly")
            return returncode
        except Exception as pluginerror:
            LOGGER.error(f"Could not run {plugin}.test(options):\n{pluginerror}")
            return 1
    else:
        LOGGER.info(f"The '{plugin}' did not have a test routine")
        return 0


def test_bidsmap(bidsmapfile: str):
    """
    Tests the bidsmaps run-items and their bidsname using BIDScoin's check and the bids-validator

    :param bidsmapfile: The bidsmap or the full pathname / basename of the bidsmap yaml-file
    :return:
    """

    if not bidsmapfile:
        return

    try:  # Include the import in the test + moving the import to the top of this module will cause circular import issues
        from bidscoin import bids
    except ImportError:
        import bids  # This should work if bidscoin was not pip-installed

    LOGGER.info('--------- Testing bidsmap runs and their bids-names ---------')

    bidsmapfile = Path(bidsmapfile)
    if bidsmapfile.is_dir():
        bidsfolder  = bidsmapfile/'code'/'bidscoin'
        bidsmapfile = Path()
    else:
        bidsfolder  = Path()
    bidsmap, _ = bids.load_bidsmap(bidsmapfile, bidsfolder, check=(True,True,True))

    return bids.validate_bidsmap(bidsmap, 1)


def test_bidscoin(bidsmapfile: Union[Path,dict], options: dict=None, testplugins: bool=True, testgui: bool=True, testtemplate: bool=True) -> int:
    """
    Performs a bidscoin installation test

    :param bidsmapfile: The bidsmap or the full pathname / basename of the bidsmap yaml-file
    :param options:     The bidscoin options. If empty, the default options are used
    :return:            0 if the test was successful, otherwise 1
    """

    if not bidsmapfile: return 1

    LOGGER.info("--------- Testing the BIDScoin's core functionality ---------")

    # Test loading the template bidsmap
    success = True
    if isinstance(bidsmapfile, (str, Path)):
        if not bidsmapfile.is_file():
            LOGGER.info(f"Cannot find bidsmap-file: {bidsmapfile}")
            return 1
        LOGGER.info(f"Running bidsmap checks:")
        try:            # Moving the import to the top of this module will cause circular import issues
            try:  from bidscoin import bids
            except ImportError: import bids         # This should work if bidscoin was not pip-installed
            bidsmap, _ = bids.load_bidsmap(Path(bidsmapfile), check=(True,True,False))
        except Exception as bidsmaperror:
            LOGGER.error(f"An error occurred when loading {bidsmapfile}:\n{bidsmaperror}\nThis may be due to invalid YAML syntax. You can check this using a YAML validator (e.g. https://www.yamllint.com)")
            bidsmap = {'Options': {}}
            success = False
    else:
        bidsmap = bidsmapfile

    # Check if all entities of each datatype in the bidsmap are present
    if testtemplate:
        try:                # Moving the import to the top of this module will cause circular import issues
            try:  from bidscoin import bids
            except ImportError: import bids  # This should work if bidscoin was not pip-installed
            success = bids.check_template(bidsmap) and success
        except ImportError:
            LOGGER.info(f"Could not fully test: {bidsmap}")

    # Test PyQt
    if testgui:
        LOGGER.info('Testing the PyQt GUI setup:')
        try:
            from PyQt5.QtWidgets import QApplication, QPushButton
            app = QApplication(sys.argv)
            window = QPushButton('Minimal GUI test: OK')
            window.show()
            QApplication.quit()
            LOGGER.success('The GUI seems to work OK')
        except Exception as pyqterror:
            LOGGER.error(f"The installed PyQt version does not seem to work for your system:\n{pyqterror}")
            success = False

    # Test the DRMAA configuration (used by pydeface only)
    try:
        import pydeface
        LOGGER.info('Testing the DRMAA setup:')
        try:
            import drmaa
            LOGGER.success('The DRMAA library was successfully imported')
        except (RuntimeError, OSError, FileNotFoundError, ModuleNotFoundError, ImportError) as drmaaerror:
            LOGGER.warning(f"The DRMAA library could not be imported. This is OK if you want to run pydeface locally and not use the option to distribute jobs on a compute cluster\n{drmaaerror}")
    except ModuleNotFoundError:
        pass

    # Show an overview of the bidscoin tools. TODO: test the entry points?
    list_executables(True)

    # Test the plugins
    options = bidsmap['Options'] if not options and bidsmap else {}
    if not options.get('plugins'):
        LOGGER.warning('No plugins found in the bidsmap (BIDScoin will likely not do anything)')
    if testplugins:

        # Show an overview of the plugins and show the test results
        list_plugins(True)
        for plugin in pluginfolder.glob('*.py'):
            if plugin.stem != '__init__':
                errorcode = test_plugin(plugin.stem, options['plugins'].get(plugin.stem,{}) if options else {})
                success   = not errorcode and success
                if errorcode:
                    LOGGER.warning(f"Failed test: {plugin.stem}")

    if not success:
        LOGGER.warning('Not all tests finishd successfully (this may be ok, but check the output above)')
    else:
        LOGGER.success('All tests finished successfully :-)')

    return not success


def pulltutorialdata(tutorialfolder: str) -> None:
    """
    Download and unzip tutorial.tar.gz file

    :param tutorialfolder:  The full pathname of the target folder in which the tutorial data will be downloaded
    :return:
    """

    if not tutorialfolder: return

    tutorialfolder = Path(tutorialfolder).resolve()
    tutorialtargz  = tutorialfolder/'bidscointutorial.tar.gz'
    tutorialfolder.mkdir(parents=True, exist_ok=True)

    # Download the data
    LOGGER.info(f"Downloading the tutorial dataset...")
    with TqdmUpTo(unit='B', unit_scale=True, unit_divisor=1024, miniters=1, desc=tutorialtargz.name) as t:
        urllib.request.urlretrieve(tutorialurl, tutorialtargz, reporthook=t.update_to)  # NB: Much faster than requests.get(url, stream=True). In case of ssl certificate issues use: with urllib.request.urlopen(tutorialurl, context=ssl.SSLContext()) as data, open(tutorialtargz, 'wb') as targz_fid: shutil.copyfileobj(data, targz_fid)

    # Unzip the data in the target folder
    LOGGER.info(f"Unzipping the downloaded data in: {tutorialfolder}")
    with tarfile.open(tutorialtargz, 'r') as targz_fid:
        for member in tqdm(iterable=targz_fid.getmembers(), total=len(targz_fid.getmembers()), leave=False):
            targz_fid.extract(member, tutorialfolder)
    tutorialtargz.unlink()
    LOGGER.success(f"Done")


def main():
    """Console script usage"""

    setup_logging()
    localversion, versionmessage = version(check=True)

    # Parse the input arguments and run bidscoiner(args)
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidscoin -l\n'
                                            '  bidscoin -d data/bidscoin_tutorial\n'
                                            '  bidscoin -t\n'
                                            '  bidscoin -t my_template_bidsmap\n'
                                            '  bidscoin -b my_study_bidsmap\n'
                                            '  bidscoin -i data/my_template_bidsmap.yaml downloads/my_plugin.py\n ')
    parser.add_argument('-l', '--list',        help='List all executables (i.e. the apps, bidsapps and utilities)', action='store_true')
    parser.add_argument('-p', '--plugins',     help='List all installed plugins and template bidsmaps', action='store_true')
    parser.add_argument('-i', '--install',     help='A list of template bidsmaps and/or bidscoin plugins to install', nargs='+')
    parser.add_argument('-u', '--uninstall',   help='A list of template bidsmaps and/or bidscoin plugins to uninstall', nargs='+')
    parser.add_argument('-d', '--download',    help='Download folder. If given, tutorial MRI data will be downloaded here')
    parser.add_argument('-t', '--test',        help='Test the bidscoin installation and template bidsmap', nargs='?', const=bidsmap_template)
    parser.add_argument('-b', '--bidsmaptest', help='Test the run-items and their bidsnames of all normal runs in the study bidsmap. Provide the bids-folder or the bidsmap filepath')
    parser.add_argument('-v', '--version',     help='Show the installed version and check for updates', action='version', version=f"BIDS-version:\t\t{bidsversion()}\nBIDScoin-version:\t{localversion}, {versionmessage}")
    args = parser.parse_args(None if sys.argv[1:] else ['--help'])

    list_executables(show=args.list)
    list_plugins(show=args.plugins)
    uninstall_plugins(filenames=args.uninstall)
    install_plugins(filenames=args.install)
    pulltutorialdata(tutorialfolder=args.download)
    test_bidscoin(bidsmapfile=args.test)
    test_bidsmap(bidsmapfile=args.bidsmaptest)


if __name__ == "__main__":
    main()
