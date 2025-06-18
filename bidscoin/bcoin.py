#!/usr/bin/env python3
"""
A BIDScoin library and application with utilities to perform generic management tasks (See also cli/_bcoin.py)

@author: Marcel Zwiers
"""

import os
import types
import logging
import shutil
import sys
import urllib.request
import time
import argparse
import re
from duecredit.cmdline import cmd_summary
from functools import lru_cache
from importlib.metadata import entry_points
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from typing import Union
from rich.progress import track, Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn, TimeElapsedColumn
from rich.logging import RichHandler
from rich.theme import Theme
from rich.console import Console
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    sys.path.append(str(Path(__file__).parents[1]))
from bidscoin import templatefolder, pluginfolder, bidsmap_template, tutorialurl, trackusage, tracking, configdir, configfile, config, DEBUG, __version__

LOGGER = logging.getLogger(__name__)


def drmaa_nativespec(specs: str, session) -> str:
    """
    Converts (CLI default) native Torque walltime and memory specifications to the DRMAA implementation (currently only Slurm is supported)

    :param specs:   Native Torque walltime and memory specifications, e.g. '-l walltime=00:10:00,mem=2gb'
    :param session: The DRMAA session
    :return:        The converted native specifications
    """

    jobmanager: str = session.drmaaImplementation

    if '-l ' in specs and 'pbs' not in jobmanager.lower():

        if 'slurm' in jobmanager.lower():
            specs = (specs.replace('-l ', '')
                          .replace(',', ' ')
                          .replace('walltime', '--time')
                          .replace('mem', '--mem')
                          .replace('gb','000'))
        else:
            LOGGER.warning(f"Default `--cluster` native specifications are not (yet) provided for {jobmanager}. Please add them to your command if you get DRMAA errors")
            specs = ''

    return specs.strip()


def synchronize(pbatch, jobids: list, event: str, wait: int=15):
    """
    Shows Rich progress bars for queued and running DRMAA jobs. Waits until all jobs have finished +
    some extra wait time to give NAS systems the opportunity to fully synchronize.

    :param pbatch: The DRMAA session
    :param jobids: The job ids
    :param event:  The event that is passed to trackusage()
    :param wait:   The extra wait time for the NAS
    """

    if not jobids:
        return

    match = re.search(r"(slurm|pbs|torque|sge|lsf|condor|uge)", pbatch.drmaaImplementation.lower())
    trackusage(f"{event}_{match.group(1) if match else 'drmaa'}")

    with Progress(TextColumn('{task.description}'), BarColumn(), TextColumn('{task.completed}/{task.total}'), TimeElapsedColumn(), transient=True) as progress:

        qtask = progress.add_task('[white]Queued  ', total=len(jobids))
        rtask = progress.add_task('[green]Running ', total=len(jobids))

        done = 0
        while done < len(jobids):
            jobs   = [pbatch.jobStatus(jobid) for jobid in jobids]
            done   = sum(status in ('done', 'failed', 'undetermined') for status in jobs)
            qcount = sum(status == 'queued_active'                    for status in jobs)
            rcount = sum(status == 'running'                          for status in jobs)
            progress.update(qtask, completed=qcount)
            progress.update(rtask, completed=rcount)
            time.sleep(2)

        if failedjobs := [jobid for jobid in jobids if pbatch.jobStatus(jobid) == 'failed']:
            LOGGER.error(f"{len(failedjobs)} HPC jobs failed to run:\n{failedjobs}\nThis may well be due to an underspecified `--cluster` input option (e.g. not enough memory)")

        # Synchronization wait bar
        for t in track(range(wait*100), description='[cyan]Synchronizing', transient=True):
            time.sleep(0.01)


def setup_logging(logfile: Path=Path()) -> Console:
    """
    Set up the logging framework:
    1) Extend the Logger class with custom 'bcdebug', 'verbose' and 'success' logging levels / methods
    2) Add a console streamhandler
    3) If given a logfile, then add a regular verbose + a warning/error filehandler

    :param logfile: Name of the log file
    :return:        The rich console (e.g. needed for progress tracking)
    """

    # Register custom logging levels
    for name, level in {'BCDEBUG': 11, 'VERBOSE': 15, 'SUCCESS': 25}.items():
        logging.addLevelName(level, name)
        setattr(logging, name, level)

    # Register custom logging methods
    def bcdebug(self, message, *args, **kws):
        if self.isEnabledFor(logging.BCDEBUG):
            self._log(logging.BCDEBUG, message, args, **kws)
    logging.getLoggerClass().bcdebug = bcdebug

    def verbose(self, message, *args, **kws):
        if self.isEnabledFor(logging.VERBOSE):
            self._log(logging.VERBOSE, message, args, **kws)
    logging.getLoggerClass().verbose = verbose

    def success(self, message, *args, **kws):
        if self.isEnabledFor(logging.SUCCESS):
            self._log(logging.SUCCESS, message, args, **kws)
    logging.getLoggerClass().success = success

    # Set the root logging level
    logger = logging.getLogger()
    logger.setLevel('BCDEBUG' if DEBUG else 'VERBOSE')

    # Add the Rich console handler and bring some color to those boring logs! :-)
    if 'consolehandler' not in (handlers := [handler.name for handler in logger.handlers]):
        console        = Console(theme=Theme({'logging.level.verbose': 'grey50', 'logging.level.success': 'green bold', 'logging.level.bcdebug': 'bright_yellow'}))
        keywords       = RichHandler.KEYWORDS + ['IntendedFor', 'B0FieldIdentifier', 'B0FieldSource', 'TaskName', '->', '-->']
        level          = 'BCDEBUG' if DEBUG else 'VERBOSE' if not logfile.name else 'INFO'
        consolehandler = RichHandler(console=console, show_time=False, show_level=True, show_path=DEBUG, rich_tracebacks=True, markup=True, keywords=keywords, level=level)
        consolehandler.set_name('consolehandler')
        logger.addHandler(consolehandler)
    else:
        console = next((handler.console for handler in logger.handlers if handler.get_name() == 'consolehandler'), None)

    # Add the optional file handlers
    if logfile.name:

        logfile.parent.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter(fmt=f"%(asctime)s - %({'level' if DEBUG else ''}name)s | %(message)s", datefmt='%Y-%m-%d %H:%M:%S')
        for handler in [handler for handler in logger.handlers if handler.get_name() in ('loghandler', 'errorhandler')]:
            logger.removeHandler(handler)

        # Add the verbose file handler
        loghandler = logging.FileHandler(logfile)
        loghandler.setLevel('BCDEBUG')
        loghandler.setFormatter(formatter)
        loghandler.set_name('loghandler')
        logger.addHandler(loghandler)

        # Add the error/warnings file handler
        errorhandler = logging.FileHandler(logfile.with_suffix('.errors'), mode='w')
        errorhandler.setLevel('WARNING')
        errorhandler.setFormatter(formatter)
        errorhandler.set_name('errorhandler')
        logger.addHandler(errorhandler)

    if DEBUG:
        LOGGER.info('[bright_yellow bold]============= Running BIDScoin in DEBUG mode =============')
        settracking('show')

    return console


def reporterrors() -> str:
    """
    Summarized the warning and errors from the log file

    :return:    The errorlog
    """

    # Find the root filehandlers and report the errors and warnings
    errors = ''
    for handler in logging.getLogger().handlers:
        if handler.get_name() == 'errorhandler':

            errorfile = Path(handler.baseFilename)
            if errorfile.is_file():
                if errorfile.stat().st_size:
                    errors = errorfile.read_text()
                    LOGGER.warning(f"The following BIDScoin errors and warnings were reported:\n\n{40 * '>'}\n{errors}{40 * '<'}\n")
                    trackusage(f"{errorfile.stem}_{'error' if 'ERROR' in errors else 'warning'}")

                else:
                    LOGGER.success(f'No BIDScoin errors or warnings were reported')
                    LOGGER.info('')

        elif handler.get_name() == 'loghandler':
            logfile = Path(handler.baseFilename)

    # Final message
    if 'logfile' in locals():
        LOGGER.info(f"For the complete log see: {logfile}\n"
                    f"NB: That folder may contain privacy sensitive information, e.g. pathnames in logfiles and provenance data samples")

    return errors


def list_executables(show: bool=False) -> list:
    """
    :param show:    Print the installed console scripts if True
    :return:        List of BIDScoin console scripts
    """

    if show: LOGGER.info('[bright_yellow]Executable BIDScoin tools:')

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


def list_plugins(show: bool=False) -> tuple[list[Path], list[Path]]:
    """
    :param show: Print the template bidsmaps and installed plugins if True
    :return:     List of the installed plugins and template bidsmaps
    """

    if show: LOGGER.info(f"[bright_yellow]Installed template bidsmaps ({templatefolder}):")
    templates = []
    for template in templatefolder.glob('*.yaml'):
        if template.stem != '__init__':
            templates.append(template)
            if show: LOGGER.info(f"- {template.stem}{' (default)' if template.samefile(bidsmap_template) else ''}")

    if show: LOGGER.info(f"[bright_yellow]Installed plugins ({pluginfolder}):")
    plugins = []
    for plugin in pluginfolder.glob('*.py'):
        if plugin.stem != '__init__':
            plugins.append(plugin)
            if show: LOGGER.info(f"- {plugin.stem}")

    return plugins, templates


def install_plugins(filenames: list[str]=()) -> None:
    """
    Installs template bidsmaps and plugins

    :param filenames:   Fullpath filenames of the plugins and template bidsmaps that need to be installed
    :return:            Nothing
    """

    if not filenames: return

    files = [Path(file) for file in filenames if file.endswith('.yaml') or file.endswith('.py')]

    # Install the template bidsmaps and plugins in their target folder
    for file in files:

        # Check if we can import the plugin
        module = import_plugin(file.resolve())
        if not module:
            LOGGER.error(f"Plugin failure, please re-install a valid version of '{file.name}'")
            continue

        # Copy the file to their target folder
        targetfolder = templatefolder if file.suffix == '.yaml' else pluginfolder
        LOGGER.info(f"Installing: '{file}'")
        try:
            shutil.copyfile(file, targetfolder/file.name)
        except (IOError, OSError) as install_failure:
            LOGGER.error(f"{install_failure}\nFailed to install: '{file.name}' in '{targetfolder}'")
            continue
        if file.suffix == '.yaml':
            LOGGER.success(f"The '{file.name}' template bidsmap was successfully installed")
            continue

        LOGGER.success(f"The '{file.name}' plugin was successfully installed")


def uninstall_plugins(filenames: list[str]=(), wipe: bool=False) -> None:
    """
    Uninstalls template bidsmaps and plugins

    :param filenames:   Fullpath filenames of the and template bidsmaps plugins that need to be uninstalled
    :param wipe:        Removes the plugin bidsmapping section if True
    :return:            None
    """

    if not filenames: return

    files = [Path(file) for file in filenames if file.endswith('.yaml') or file.endswith('.py')]

    # Uninstall the plugins
    for file in files:

        # Remove the file from the target folder
        LOGGER.info(f"Uninstalling: '{file}'")
        sourcefolder = templatefolder if file.suffix == '.yaml' else pluginfolder
        try:
            (sourcefolder/file.name).unlink()
        except (IOError, OSError) as uninstall_error:
            LOGGER.error(f"{uninstall_error}\nFailed to uninstall: '{file.name}' from {sourcefolder}")
            continue
        if file.suffix == '.yaml':
            LOGGER.success(f"The '{file.name}' template bidsmap was successfully uninstalled")
            continue

        LOGGER.success(f"The '{file.stem}' plugin was successfully uninstalled")


@lru_cache()
def import_plugin(plugin: Union[Path,str], classes: tuple=('Interface',)) -> Union[types.ModuleType, None]:
    """
    Imports the plugin if it contains any of the specified functions

    :param plugin:  Name of the plugin in the bidscoin "plugins" folder or the fullpath name
    :param classes: List of classes of which at least one of them should be present in the plugin
    :return:        The imported plugin-module
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
    LOGGER.bcdebug(f"Importing plugin: '{plugin}'")
    try:
        spec   = spec_from_file_location(f"bidscoin.{pluginfolder.name}." + plugin.stem, plugin)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

        classesfound = []
        for klass in classes:
            if not hasattr(module, klass):
                LOGGER.bcdebug(f"The '{plugin}' plugin does not contain an implementation for '{klass}'")
            elif not callable(getattr(module, klass)):
                LOGGER.error(f"'The {klass}' attribute in the '{plugin}' plugin is not callable")
            else:
                classesfound.append(klass)

        if classes and len(classes) != len(classesfound):
            LOGGER.bcdebug(f"Plugin '{plugin}' does not contain all {classes} classes, found only: {classesfound}")
        else:
            return module

    except Exception as pluginerror:
        LOGGER.error(f"Could not import {plugin}:\n{pluginerror}")


def test_plugin(plugin: Union[Path,str], options: dict) -> int:
    """
    Performs runtime tests of the plug-in

    :param plugin:  The name of the plugin that is being tested
    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap.plugins[plugin.stem]
    :return:        The result of the plugin test routine (e.g. 0 if it passed or 1 if there was a general plug-in error)
    """

    if not plugin: return 1

    LOGGER.info(f"[bright_yellow]--------- Testing the '{plugin}' plugin:")

    # First test to see if we can import the plugin interface
    module = import_plugin(plugin)
    if module is None:
        return 1

    # Then run the plugin's own 'test' routine (if implemented)
    try:
        returncode = module.Interface().test(options)
        if returncode == 0:
            LOGGER.success(f"The '{plugin}' plugin functioned correctly")
        else:
            LOGGER.warning(f"The '{plugin}' plugin did not function correctly")
        return returncode
    except Exception as pluginerror:
        LOGGER.error(f"Could not run {plugin}.test(options):\n{pluginerror}")
        return 1


def test_bidsmap(bidsmapfile: str):
    """
    Tests the bidsmaps run-items and their bidsname using BIDScoin's check and the bids-validator

    :param bidsmapfile: The bidsmap or the full path/base name of the bidsmap yaml-file
    :return:            True if all tested runs in bidsmap were bids-valid, otherwise False
    """

    if not bidsmapfile:
        return

    # Include the import in the test + moving the import to the top of this module will cause circular import issues
    from bidscoin import bids

    LOGGER.info('[bright_yellow]--------- Testing bidsmap runs and their bids-names:')

    bidsmapfile = Path(bidsmapfile)
    if bidsmapfile.is_dir():
        bidsmapfile = bidsmapfile/'code'/'bidscoin'/'bidsmap.yaml'
    bidsmap = bids.BidsMap(bidsmapfile, checks=(True, True, True))

    return bidsmap.validate(1)


def test_bidscoin(bidsmapfile, options: dict=None, testplugins: bool=True, testgui: bool=True, testtemplate: bool=True) -> int:
    """
    Performs a bidscoin installation test

    :param bidsmapfile: The full path/base name of the bidsmap yaml-file or the bidsmap object itself
    :param options:     The bidscoin options. If empty, the default options are used
    :return:            0 if the test was successful, otherwise 1
    """

    if not bidsmapfile: return 1

    LOGGER.info(f"[bright_yellow]--------- Testing BIDScoin's {__version__} core:")

    # Test loading the template bidsmap
    success = True
    if isinstance(bidsmapfile, (str, Path)):
        bidsmapfile = Path(bidsmapfile)
        LOGGER.info(f"Running bidsmap checks:")
        try:            # Moving the import to the top of this module will cause circular import issues
            from bidscoin import bids
            bidsmap = bids.BidsMap(bidsmapfile, checks=(True, True, False))
        except Exception as bidsmaperror:
            LOGGER.error(f"An error occurred when loading {bidsmapfile}:\n{bidsmaperror}\nThis may be due to invalid YAML syntax. You can check this using a YAML validator (e.g. https://www.yamllint.com)")
            bidsmap = {'Options': {}}
            success = False
    else:
        bidsmap = bidsmapfile

    # Check if all entities of each data type in the bidsmap are present
    if testtemplate:
        try:                # Moving the import to the top of this module will cause circular import issues
            from bidscoin import bids
            success = bidsmap.check_template() and success
        except ImportError:
            LOGGER.info(f"Could not fully test: {bidsmap}")

    # Test PyQt
    if testgui:
        LOGGER.info('[bright_yellow]--------- Testing the PyQt GUI setup:')
        if find_spec('tkinter'):                    # Not always installed (e.g. WSL2)
            LOGGER.info('Opening a standard graphical window')
            import tkinter as tk
            try:
                root = tk.Tk()                      # Test opening a window using the TKinter standard library
                root.after(200, root.destroy)   # Destroy after 200ms to prevent blocking
                root.mainloop()                     # Run event loop (shows the window)
            except tk.TclError as display_error:
                LOGGER.error(f"Cannot open a graphical display on your system:\n{display_error}")
                success = False
        try:
            LOGGER.info('Opening a PyQt window')
            from PyQt6.QtWidgets import QApplication, QPushButton
            from PyQt6.QtCore import QTimer
            app = QApplication([])
            window = QPushButton('Minimal GUI test: OK')
            window.show()
            QTimer.singleShot(200, app.quit)        # Quit after 200ms to prevent blocking
            LOGGER.success('The GUI seems to work OK')
        except Exception as pyqterror:
            LOGGER.error(f"The installed PyQt version does not seem to work for your system:\n{pyqterror}")
            success = False

    # Test the DRMAA configuration (used by pydeface only)
    try:
        import pydeface
        LOGGER.info('[bright_yellow]--------- Testing the DRMAA setup:')
        try:
            import drmaa
            with drmaa.Session() as s:
                LOGGER.success(f"The {s.drmaaImplementation} library was successfully imported")
        except (RuntimeError, OSError, IOError, FileNotFoundError, ModuleNotFoundError, ImportError) as drmaaerror:
            LOGGER.warning(f"The DRMAA library could not be imported. This is OK if you want to run pydeface locally and not use the option to distribute jobs on a compute cluster\n{drmaaerror}")
    except ModuleNotFoundError:
        pass

    # Show an overview of the bidscoin tools
    list_executables(True)

    # Test the plugins
    if not bidsmap.plugins:
        LOGGER.warning('No plugins found in the bidsmap (BIDScoin will likely not do anything)')
    if testplugins:

        # Show an overview of the plugins and show the test results
        list_plugins(True)
        for plugin in pluginfolder.glob('*.py'):
            if plugin.stem != '__init__':
                errorcode = test_plugin(plugin.stem, bidsmap.plugins.get(plugin.stem, {}))
                success   = not errorcode and success
                if errorcode:
                    LOGGER.warning(f"Failed test: {plugin.stem}\nThis may be fine if you do not neend and did not install this plugin")

    if not success:
        LOGGER.warning('Not all tests finished successfully (this may be OK, but check the output above)')
        trackusage('bidscoin_error')
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
    with Progress(TextColumn('[blue bold]{task.fields[filename]}'), BarColumn(), DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn()) as progress:
        task = progress.add_task('[cyan]Download', filename=tutorialtargz.name, total=None)
        def reporthook(blocknum: int, blocksize: int, totalsize: int):
            if totalsize > 0 and progress.tasks[task].total is None:
                progress.update(task, total=totalsize)
            progress.update(task, completed=blocknum * blocksize)

        urllib.request.urlretrieve(tutorialurl, tutorialtargz, reporthook=reporthook)  # NB: In case of ssl certificate issues use: with urllib.request.urlopen(tutorialurl, context=ssl.SSLContext()) as data, open(tutorialtargz, 'wb') as targz_fid: shutil.copyfileobj(data, targz_fid)

    # Unzip the data in the target folder
    LOGGER.info(f"Unpacking the downloaded data in: {tutorialfolder}")
    try:
        shutil.unpack_archive(tutorialtargz, tutorialfolder)
        tutorialtargz.unlink()
        LOGGER.success(f"Done")
    except Exception as unpackerror:
        LOGGER.error(f"Could not unpack: {tutorialtargz}\n{unpackerror}")
        trackusage('bidscoin_error')


def reportcredits(args: list) -> None:
    """
    Shows the duecredit summary of all reports in the bids or current directory

    :param args: args[0] must be the bidsfolder and args[1:] should be key-value pairs, e.g. args[1] = 'style', args[2] = 'apa'
    :return:
    """

    if not args:
        return
    elif not len(args) % 2:
        LOGGER.warning(f"Unexpected additional `-c/--credits` arguments: {args[1:]}")

    parser = argparse.ArgumentParser()
    cmd_summary.setup_parser(parser)
    dueargs = parser.parse_args([arg if n%2 else '--'+arg for n,arg in enumerate(args[1:])])
    reports = sorted((Path(args[0])/'code'/'bidscoin').glob('.duecredit_*'))
    for report in reports or [Path.cwd()/'.duecredit.p']:
        tool = report.stem.split('_')[1].upper() if '_' in report.stem else 'BIDScoin'
        if report.is_file():
            print(f"\n{'-'*46}")
            LOGGER.info(f"DueCredit summary for {tool} usage:")
            print(f"{'-'*46}")
            dueargs.filename = report
            cmd_summary.run(dueargs)
        else:
            LOGGER.info(f"No DueCredit citation files found in {Path(args[0]).resolve()} and {report.parent}")


def reset(delete: bool) -> None:
    """
    Resets the configuration directory by deleting it if the `delete` parameter is set to True

    :param delete: If set to True, the configuration directory will be removed
    :return: None
    """

    if not delete: return

    LOGGER.info(f"Resetting: {configdir}")
    shutil.rmtree(configdir)


def settracking(value: str) -> None:
    """
    Set or show usage tracking

    :param value: Shows the tracking data if value == 'show', else write the tracking setting to the BIDScoin config file
    :return:
    """

    if not value: return

    setting = config['bidscoin']['trackusage']
    if value == 'show':
        data = trackusage('bidscoin', dryrun=True)
        show = '{\n' + '\n'.join([f"   {key}:\t{val}" for key, val in data.items()]) + '\n}'
        LOGGER.info(f"\ntrackusage          = {setting}\t# Upload anonymous usage data if this config setting is 'yes' (maximally 1 upload every {tracking['sleep']} hour)\n"
                    f"BIDSCOIN_TRACKUSAGE = {os.getenv('BIDSCOIN_TRACKUSAGE','  ')}\t# Same as trackusage, but this environment variable takes precedence if set (e.g. when testing)\n\n"
                    f"Data upload example: -> {tracking['url']}\n{show}")
        print('\nNB: As you can see above, BIDScoin does NOT upload any identifying details about you nor information about the data. '
              'Uploaded data is used to generate usage and error statistics, and helps the developers to improve BIDScoin\n')

    elif setting != value:
        data = configfile.read_text().splitlines()
        for n, line in enumerate(data):
            if line.startswith('trackusage'):
                data[n] = line.replace(f"'{setting}'", f"'{value}'")
                LOGGER.info(f"Writing: [{data[n]}] -> {configfile}")
        configfile.write_text('\n'.join(data) + '\n')

    else:
        LOGGER.verbose(f"Usage tracking is already set to '{value}'")


def main():
    """Console script entry point"""

    from bidscoin.cli._bcoin import get_parser

    trackusage('bidscoin')

    setup_logging()

    # Parse the input arguments and run bidscoiner(args)
    args = get_parser().parse_args(None if sys.argv[1:] else ['--help'])

    try:
        list_executables(show=args.list)
        list_plugins(show=args.plugins)
        uninstall_plugins(filenames=args.uninstall)
        install_plugins(filenames=args.install)
        pulltutorialdata(tutorialfolder=args.download)
        test_bidscoin(bidsmapfile=args.test)
        test_bidsmap(bidsmapfile=args.bidsmaptest)
        reset(delete=args.reset)
        settracking(value=args.tracking)
        reportcredits(args=args.credits)

    except Exception as error:
        trackusage('bidscoin_exception', error)
        raise


if __name__ == "__main__":
    main()
