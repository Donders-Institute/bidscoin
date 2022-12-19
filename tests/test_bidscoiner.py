import shutil
from pydicom.data import get_testdata_file
from pathlib import Path
try:
    from bidscoin import bidscoin, bidsmapper, bidscoiner
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))         # This should work if bidscoin was not pip-installed
    import bidscoin, bidsmapper, bidscoiner

bidscoin.setup_logging()


def test_bidscoiner(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir):
    if not bidsmap_dicomdir.is_file():
        shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, raw_dicomdir, dirs_exist_ok=True)  # NB: This is NOT picking up the DICOMDIR data :-(
        shutil.rmtree(raw_dicomdir/'TINY_ALPHA')
        bidsmapper.bidsmapper(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir, bidscoin.bidsmap_template, [], '*', '', '', noedit=True)
        (bidsmap_dicomdir.parent/'bidsmapper.errors').unlink()
    bidscoiner.bidscoiner(raw_dicomdir, bids_dicomdir)
    logs = (bidsmap_dicomdir.parent/'bidscoiner.errors').read_text()
    assert 'ERROR' not in logs
    # assert 'WARNING' not in logs
    # assert (bidsmap_dicomdir.parent/'bidscoiner.errors').stat().st_size == 0
    # assert (bids_dicomdir/'sub-DoePeter').is_dir()   # Patient: 98890234: Doe^Peter
    assert (bids_dicomdir/'sub-77654033').is_dir()     # Patient: 77654033: Doe^Archibald
    assert (bids_dicomdir/'sub-98892001').is_dir()
    assert (bids_dicomdir/'sub-98892003').is_dir()

# def test_addmetadata(bids_dicomdir, bidsmap_dicomdir):
#     bidsmap_dicomdir, _ = bids.load_bidsmap(bidsmap_dicomdir)
#     bidscoiner.addmetadata(bids_dicomdir/'sub-something'/'ses-else', '*', '*')
