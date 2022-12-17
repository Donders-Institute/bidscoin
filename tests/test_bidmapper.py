import shutil
from pydicom.data import get_testdata_file
from pathlib import Path
from bidscoin import bids, bidscoin, bidsmapper


def test_bidsmapper(rawfolder, bidsfolder, bidsmap):
    shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, rawfolder, dirs_exist_ok=True)
    shutil.rmtree(rawfolder/'TINY_ALPHA')
    bidsmapper.bidsmapper(rawfolder, bidsfolder, bidsmap, bidscoin.bidsmap_template, [], '*', '*', '', noedit=True)
    assert bidsmap.is_file()
    assert (bidsmap.parent/'bidsmapper.errors').stat().st_size == 0
    (bidsmap.parent/'bidsmapper.errors').unlink()


def test_setprefix(rawfolder, bidsmap):
    bidsmap, _ = bids.load_bidsmap(bidsmap)
    # TODO: manipulate prefixes
    bidsmapper.setprefix(bidsmap, '*', '*', rawfolder)
