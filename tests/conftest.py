import pytest


@pytest.fixture(scope='session')
def rawfolder(tmp_path_factory):
    return tmp_path_factory.mktemp('raw')


@pytest.fixture(scope='session')
def bidsfolder(tmp_path_factory):
    return tmp_path_factory.mktemp('bids')


@pytest.fixture()
def bidsmap(bidsfolder):
    return bidsfolder/'code'/'bidscoin'/'bidsmap.yaml'

