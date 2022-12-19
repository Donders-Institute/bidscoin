import pytest


@pytest.fixture(scope='session')
def raw_dicomdir(tmp_path_factory):
    return tmp_path_factory.mktemp('raw_dicomdir')


@pytest.fixture(scope='session')
def bids_dicomdir(tmp_path_factory):
    return tmp_path_factory.mktemp('bids_dicomdir')


@pytest.fixture()
def bidsmap_dicomdir(bids_dicomdir):
    return bids_dicomdir/'code'/'bidscoin'/'bidsmap.yaml'

