import shutil
from pydicom.data import get_testdata_file
from pathlib import Path
try:
    from bidscoin import bidscoin, bidsmapper, bidscoiner
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))         # This should work if bidscoin was not pip-installed
    import bidscoin, bidsmapper, bidscoiner


def test_bidscoiner(rawfolder, bidsfolder, bidsmap):
    if not bidsmap.is_file():
        shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, rawfolder, dirs_exist_ok=True)  # NB: This is NOT picking up the DICOMDIR data :-(
        shutil.rmtree(rawfolder/'TINY_ALPHA')
        bidsmapper.bidsmapper(rawfolder, bidsfolder, bidsmap, bidscoin.bidsmap_template, [], '*', '', '', noedit=True)
        (bidsmap.parent/'bidsmapper.errors').unlink()
    bidscoiner.bidscoiner(rawfolder, bidsfolder)
    logs = (bidsmap.parent/'bidscoiner.errors').read_text()
    assert 'ERROR' not in logs
    # assert 'WARNING' not in logs
    # assert (bidsmap.parent/'bidscoiner.errors').stat().st_size == 0
    # assert (bidsfolder/'sub-DoePeter').is_dir()   # Patient: 98890234: Doe^Peter
    assert (bidsfolder/'sub-77654033').is_dir()     # Patient: 77654033: Doe^Archibald
    assert (bidsfolder/'sub-98892001').is_dir()
    assert (bidsfolder/'sub-98892003').is_dir()

# def test_addmetadata(bidsfolder, bidsmap):
#     bidsmap, _ = bids.load_bidsmap(bidsmap)
#     bidscoiner.addmetadata(bidsfolder/'sub-something'/'ses-else', '*', '*')
