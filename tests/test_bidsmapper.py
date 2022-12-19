import shutil
from pydicom.data import get_testdata_file
from pathlib import Path
try:
    from bidscoin import bids, bidscoin, bidsmapper
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))         # This should work if bidscoin was not pip-installed
    import bidscoin, bids, bidsmapper

bidscoin.setup_logging()


def test_bidsmapper(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir):
    shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, raw_dicomdir, dirs_exist_ok=True)  # NB: This is NOT picking up the DICOMDIR data :-(
    shutil.rmtree(raw_dicomdir/'TINY_ALPHA')
    bidsmapper.bidsmapper(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir, bidscoin.bidsmap_template, [], '*', '', '', noedit=True)
    assert bidsmap_dicomdir.is_file()
    assert (bidsmap_dicomdir.parent/'bidsmapper.errors').stat().st_size==0
    (bidsmap_dicomdir.parent/'bidsmapper.errors').unlink()


def test_setprefix(raw_dicomdir, bidsmap_dicomdir):
    bidsmap_dicomdir, _ = bids.load_bidsmap(bidsmap_dicomdir)
    # TODO: manipulate prefixes
    bidsmapper.setprefix(bidsmap_dicomdir, '*', '*', raw_dicomdir)
