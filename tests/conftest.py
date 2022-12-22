import pytest
import shutil
from pathlib import Path
from pydicom.data import get_testdata_file
try:
    from utilities import dicomsort
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'utilities'))         # This should work if bidscoin was not pip-installed
    import dicomsort


@pytest.fixture(scope='session')
def raw_dicomdir(tmp_path_factory):
    raw = tmp_path_factory.mktemp('raw_dicomdir')
    shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, raw, dirs_exist_ok=True)
    shutil.rmtree(raw/'TINY_ALPHA')                                     # Does not contain normal DICOM fields / evokes warnings or errors
    dicomsort.sortsessions(raw/'DICOMDIR')                              # The bidsmapper/coiner are NOT picking up the multi-subject DICOMDIR data properly :-(
    return raw


@pytest.fixture(scope='session')
def bids_dicomdir(tmp_path_factory):
    return tmp_path_factory.mktemp('bids_dicomdir')


@pytest.fixture()
def bidsmap_dicomdir(bids_dicomdir):
    return bids_dicomdir/'code'/'bidscoin'/'bidsmap.yaml'
