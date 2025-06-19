import pytest
import shutil
import json
from pathlib import Path
from pydicom.data import get_testdata_file
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    import sys
    sys.path.append(str(Path(__file__).parents[2]))
from bidscoin.utilities import dicomsort
from bidscoin import bcoin

Path('./.duecredit.p').unlink(missing_ok=True)
bcoin.setup_logging()

@pytest.fixture(scope='session')
def raw_dicomdir(tmp_path_factory):
    """The dicomsorted DICOMDIR data from pydicom"""
    raw = tmp_path_factory.mktemp('raw_dicomdir')
    shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, raw, dirs_exist_ok=True)
    shutil.rmtree(raw/'TINY_ALPHA')                                     # Does not contain normal DICOM fields / evokes warnings or errors
    dicomsort.sortsessions(raw/'DICOMDIR', None)                        # The bidsmapper/coiner are NOT picking up the multi-subject DICOMDIR data properly :-(
    dicomfile = sorted((raw/'Doe^Peter'/'03-Brain'/'002-TSC RF FAST PILOT/').iterdir())[0]   # Make sure this is the first file
    with dicomfile.with_suffix('.json').open('w') as sidecar:
        print(f"Saving extended metadata file: {dicomfile.with_suffix('.json')}")           # = raw_dicomdir0/Doe^Peter/03-Brain/002-TSC RF FAST PILOT/4950.json
        json.dump({'SeriesDescription': 'TestExtAtrributes',  'Comment': 'TestExtComment'}, sidecar)
    return raw


@pytest.fixture(scope='session')
def test_data():
    """The path to BIDScoin's `test_data` folder"""
    return Path(__file__).parent/'test_data'


@pytest.fixture(scope='session')
def bids_dicomdir(tmp_path_factory):
    """The bids directory created from 'raw_dicomdir'"""
    return tmp_path_factory.mktemp('bids_dicomdir')


@pytest.fixture()
def bidsmap_dicomdir(bids_dicomdir):
    """The bidsmap file in 'bids_dicomdir' (created from 'raw_dicomdir')"""
    return bids_dicomdir/'code'/'bidscoin'/'bidsmap.yaml'


@pytest.fixture(scope='session')
def bids_neurobs(tmp_path_factory):
    """The bids directory created from 'raw_neurobsdir'"""
    return tmp_path_factory.mktemp('bids_neurobs')


@pytest.fixture()
def bidsmap_neurobs(bids_neurobs):
    """The bidsmap file in 'bids_dicomdir' (created from 'raw_dicomdir')"""
    return bids_neurobs/'code'/'bidscoin'/'bidsmap.yaml'
