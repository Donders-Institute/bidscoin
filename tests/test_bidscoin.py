from pathlib import Path
try:
    from bidscoin import bidscoin
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))         # This should work if bidscoin was not pip-installed
    import bidscoin

bidscoin.setup_logging()

assert bidscoin.schemafolder.is_dir()
assert bidscoin.heuristicsfolder.is_dir()
assert bidscoin.pluginfolder.is_dir()
assert bidscoin.bidsmap_template.is_file()


def test_version():
    assert isinstance(bidscoin.version(False), str)
    assert isinstance(bidscoin.version(True), tuple)


def test_bidsversion():
    assert isinstance(bidscoin.bidsversion(), str)


def test_runcommand():
    assert bidscoin.run_command('bidscoin') == 0


def test_list_executables():
    executables = bidscoin.list_executables()
    assert 'bidsmapper' in executables
    assert 'dicomsort' in executables
    assert 'deface' in executables
    for executable in executables:
        assert bidscoin.run_command(f"{executable} -h") == 0


def test_list_plugins():
    plugins, templates = bidscoin.list_plugins()
    assert 'dcm2niix2bids' in [plugin.stem for plugin in plugins]
    assert 'bidsmap_dccn' in [template.stem for template in templates]
