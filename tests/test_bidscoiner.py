import shutil
from pydicom.data import get_testdata_file
from pathlib import Path
from bidscoin import bidscoin, bidsmapper, bidscoiner


def test_bidscoiner(rawfolder, bidsfolder, bidsmap):
    if not bidsmap.is_file():
        shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, rawfolder, dirs_exist_ok=True)
        shutil.rmtree(rawfolder/'TINY_ALPHA')
        bidsmapper.bidsmapper(rawfolder, bidsfolder, bidsmap, bidscoin.bidsmap_template, [], '*', '*', '', noedit=True)
        (bidsmap.parent/'bidsmapper.errors').unlink()
    bidscoiner.bidscoiner(rawfolder, bidsfolder)
    assert (bidsmap.parent/'bidscoiner.errors').stat().st_size == 0


# def test_addmetadata(bidsfolder, bidsmap):
#     bidsmap, _ = bids.load_bidsmap(bidsmap)
#     bidscoiner.addmetadata(bidsfolder/'sub-something'/'ses-else', '*', '*')
