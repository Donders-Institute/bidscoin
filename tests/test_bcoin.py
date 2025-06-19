import sys
import bidscoin
from bidscoin import bcoin
from pathlib import Path


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
    assert bidscoin.run_command('bidscoin') == 0


def test_list_executables():
    executables = bcoin.list_executables()
    assert 'bidsmapper' in executables
    assert 'dicomsort' in executables
    assert 'deface' in executables
    for executable in executables:
        assert bidscoin.run_command(f"{executable} -h") == 0
        if not sys.platform.startswith('win'):
            manpage = (Path(sys.executable).parents[1]/'share'/'man'/'man1'/f"{executable}.1").read_text()
            assert executable in manpage.splitlines()       # Tests if manpage NAME == argparse prog for each console script


def test_list_plugins():
    plugins, templates = bcoin.list_plugins()
    assert 'dcm2niix2bids' in [plugin.stem for plugin in plugins]
    assert 'bidsmap_dccn' in [template.stem for template in templates]


def test_drmaa_nativespec():

    class DrmaaSession:
        def __init__(self, drmaaImplementation):
            self.drmaaImplementation = drmaaImplementation

    specs = bcoin.drmaa_nativespec('-l walltime=00:10:00,mem=2gb', DrmaaSession('PBS Pro'))
    assert specs == '-l walltime=00:10:00,mem=2gb'

    specs = bcoin.drmaa_nativespec('-l walltime=00:10:00,mem=2gb', DrmaaSession('Slurm'))
    assert specs == '--time=00:10:00 --mem=2000'

    specs = bcoin.drmaa_nativespec('-l mem=200,walltime=00:10:00', DrmaaSession('Slurm'))
    assert specs == '--mem=200 --time=00:10:00'

    specs = bcoin.drmaa_nativespec('-l walltime=00:10:00,mem=2gb', DrmaaSession('Unsupported'))
    assert specs == ''
