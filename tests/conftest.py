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

Path('./.duecredit.p').unlink(missing_ok=True)


@pytest.fixture(scope='session')
def raw_dicomdir(tmp_path_factory):
    """The dicomsorted DICOMDIR data from pydicom"""
    raw = tmp_path_factory.mktemp('raw_dicomdir')
    shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, raw, dirs_exist_ok=True)
    shutil.rmtree(raw/'TINY_ALPHA')                                     # Does not contain normal DICOM fields / evokes warnings or errors
    dicomsort.sortsessions(raw/'DICOMDIR')                              # The bidsmapper/coiner are NOT picking up the multi-subject DICOMDIR data properly :-(
    sourcesidecar = raw/'Doe^Peter'/'03-Brain'/'002-TSC RF FAST PILOT/4950.json'
    with sourcesidecar.open('w') as sidecar:
        json.dump({'SeriesDescription': 'TestExtAtrributes',  'Comment': 'TestExtComment'}, sidecar)
    return raw


@pytest.fixture(scope='session')
def bids_dicomdir(tmp_path_factory):
    """The bids directory created from 'raw_dicomdir'"""
    return tmp_path_factory.mktemp('bids_dicomdir')


@pytest.fixture()
def bidsmap_dicomdir(bids_dicomdir):
    """The bidsmap file in 'bids_dicomdir' (created from 'raw_dicomdir')"""
    return bids_dicomdir/'code'/'bidscoin'/'bidsmap.yaml'
