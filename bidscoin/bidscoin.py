#!/usr/bin/env python3
"""
BIDScoin converts and organizes raw MRI data-sets according to the Brain Imaging Data Structure (BIDS)

For more documentation see: https://bidscoin.readthedocs.io
"""

import argparse
import textwrap
import tarfile
import urllib.request
import shutil
import ssl
from pathlib import Path
from importlib.metadata import entry_points
from typing import Tuple
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed

tutorialurl                  = 'https://surfdrive.surf.nl/files/index.php/s/HTxdUbykBZm2cYM/download'
localversion, versionmessage = bids.version(check=True)
bidscoinfolder               = Path(__file__).parent


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
    :return:                Nothing
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
        if not bids.import_plugin(plugin, ('bidsmapper_plugin', 'bidscoiner_plugin')):
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

    # Parse the input arguments and run bidscoiner(args)
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidscoin -l\n'
                                            '  bidscoin -d data/bidscoin_tutorial\n'
                                            '  bidscoin -i python/project/my_plugin.py download/handy_plugin.py\n ')
    parser.add_argument('-l', '--list',      help='List all bidscoin executables', action='store_true')
    parser.add_argument('-p', '--plugins',   help='List all installed plugins', action='store_true')
    parser.add_argument('-i', '--install',   help='A list of bidscoin plugins to install', nargs='+')
    parser.add_argument('-u', '--uninstall', help='A list of bidscoin plugins to uninstall', nargs='+')
    parser.add_argument('-d', '--download',  help='Download folder. If given, tutorial MRI data will be downloaded here')
    # parser.add_argument('-t', '--test',      help='Test the bidscoin installation', action='store_true')  # TODO: implement bidscoin tests
    parser.add_argument('-v', '--version',   help='Show the installed version and check for updates', action='version', version=f"BIDS-version:\t\t{bids.bidsversion()}\nBIDScoin-version:\t{localversion}, {versionmessage}")
    args = parser.parse_args()

    list_executables(show=args.list)
    list_plugins(show=args.plugins)
    uninstall_plugins(plugins=args.uninstall)
    install_plugins(plugins=args.install)
    pulltutorialdata(tutorialfolder=args.download)

if __name__ == "__main__":
    main()
