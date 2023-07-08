import pytest
from pathlib import Path
from bidscoin import bcoin, bids

# setup logger
bcoin.setup_logging()


@pytest.fixture()
def setup_bidsmaps():
    template_bidsmap_path = Path('../bidscoin/heuristics/bidsmap_dccn.yaml')
    bidsmap_path          = Path('tests/test_data/bidsmap.yaml')
    full_bidsmap_path     = Path(bidsmap_path.resolve())
    return {'template_bidsmap_path': template_bidsmap_path, 'full_bidsmap_path': full_bidsmap_path}


def test_template_bidsmap_is_valid(setup_bidsmaps):
    template_bidsmap, _ = bids.load_bidsmap(setup_bidsmaps['template_bidsmap_path'])
    is_valid = bids.check_bidsmap(template_bidsmap)
    for each in is_valid:
        assert each is None
