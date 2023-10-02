import sys
import bidscoin
from bidscoin import bcoin
from pathlib import Path

bcoin.setup_logging()

assert bidscoin.schemafolder.is_dir()
assert bidscoin.templatefolder.is_dir()
assert bidscoin.pluginfolder.is_dir()
assert bidscoin.bidsmap_template.is_file()


def test_check_version():
    version, uptodate, message = bidscoin.check_version()
    assert isinstance(version, str)
    assert isinstance(uptodate, bool) or version is None
    assert isinstance(message, str)


def test_bidsversion():
    assert isinstance(bidscoin.bidsversion(), str)


def test_runcommand():
    assert bcoin.run_command('bidscoin') == 0


def test_list_executables():
    executables = bcoin.list_executables()
    assert 'bidsmapper' in executables
    assert 'dicomsort' in executables
    assert 'deface' in executables
    for executable in executables:
        assert bcoin.run_command(f"{executable} -h") == 0
        if not sys.platform.startswith('win'):
            manpage = (Path(sys.executable).parents[1]/'share'/'man'/'man1'/f"{executable}.1").read_text()
            assert executable in manpage.splitlines()       # Tests if manpage NAME == argparse prog for each console script


def test_list_plugins():
    plugins, templates = bcoin.list_plugins()
    assert 'dcm2niix2bids' in [plugin.stem for plugin in plugins]
    assert 'bidsmap_dccn' in [template.stem for template in templates]
