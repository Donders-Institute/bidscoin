from pathlib import Path
try:
    from bidscoin import bidscoin as bcoin
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))         # This should work if bidscoin was not pip-installed
    import bidscoin as bcoin

bcoin.setup_logging()

assert bcoin.schemafolder.is_dir()
assert bcoin.heuristicsfolder.is_dir()
assert bcoin.pluginfolder.is_dir()
assert bcoin.bidsmap_template.is_file()


def test_version():
    assert isinstance(bcoin.version(False), str)
    assert isinstance(bcoin.version(True), tuple)


def test_bidsversion():
    assert isinstance(bcoin.bidsversion(), str)


def test_runcommand():
    assert bcoin.run_command('bidscoin') == 0


def test_list_executables():
    executables = bcoin.list_executables()
    assert 'bidsmapper' in executables
    assert 'dicomsort' in executables
    assert 'deface' in executables
    for executable in executables:
        assert bcoin.run_command(f"{executable} -h") == 0


def test_list_plugins():
    plugins, templates = bcoin.list_plugins()
    assert 'dcm2niix2bids' in [plugin.stem for plugin in plugins]
    assert 'bidsmap_dccn' in [template.stem for template in templates]
