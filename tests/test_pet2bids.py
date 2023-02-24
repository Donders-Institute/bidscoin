import unittest
import logging
import tempfile
import datetime
import pytest
import ruamel
from pathlib import Path

try:
    from bidscoin import bidscoin, bids
    from bidscoin.plugins import pet2bids
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))# This should work if bidscoin was not pip-installed
    sys.path.append(str(Path(__file__).parents[1]/'plugins'))# This should work if bidscoin was not pip-installed
    import bidscoin, bids
    from plugins import pet2bids



# setup logger
LOGGER = logging.getLogger(__name__)
bidscoin.setup_logging()


@pytest.fixture()
def setup_bidsmaps():
    template_bidsmap_path = Path('../bidscoin/heuristics/bidsmap_dccn.yaml')
    bidsmap_path = Path('tests/test_data/bidsmap.yaml')
    full_bidsmap_path = Path(bidsmap_path.resolve())
    return {'template_bidsmap_path': template_bidsmap_path, 'full_bidsmap_path': full_bidsmap_path}


def test_template_bidsmap_is_valid(setup_bidsmaps):
    template_bidsmap, _ = bids.load_bidsmap(setup_bidsmaps['template_bidsmap_path'])
    is_valid = bids.check_bidsmap(template_bidsmap)
    for each in is_valid:
        assert each is None


@pytest.fixture()
def setup_petxlsx():
    petxlsx_path = Path('test_data/subject_metadata_multisheet_example.xlsx').resolve()
    if petxlsx_path.exists():
        return petxlsx_path
    else:
        petxlsx_path = Path('tests/test_data/subject_metadata_multisheet_example.xlsx').resolve()
        if petxlsx_path.exists():
            return petxlsx_path
        else:
            raise FileNotFoundError(petxlsx_path)
def test_is_petxls_file(setup_petxlsx):
    assert pet2bids.is_sourcefile(setup_petxlsx) == ""

def test_petxls_get_attribute(setup_petxlsx):
    manufacturer = pet2bids.get_attribute('', setup_petxlsx, 'Manufacturer')
    time_zero = pet2bids.get_attribute('', setup_petxlsx, 'TimeZero')
    assert manufacturer == 'Siemens'
    assert time_zero == datetime.time(12,12,12)
