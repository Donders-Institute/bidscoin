import unittest
import logging
import tempfile

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
