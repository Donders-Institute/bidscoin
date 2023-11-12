import json
import pickle
from pathlib import Path
from bidscoin import bcoin, bidsmapper, bidscoiner, bidsmap_template, __version__

bcoin.setup_logging()


def test_bidscoiner(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir):
    if not bidsmap_dicomdir.is_file():
        bidsmapper.bidsmapper(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir, bidsmap_template, [], 'Doe^', '*', unzip='', noeditor=True, force=True)
        try:
            (bidsmap_dicomdir.parent/'bidsmapper.errors').unlink(missing_ok=True)
        except Exception:
            pass
    bidscoiner.bidscoiner(raw_dicomdir, bids_dicomdir)
    logs     = (bidsmap_dicomdir.parent/'bidscoiner.errors').read_text()
    sidecars = sorted((bids_dicomdir/'sub-Peter'/'ses-03Brain'/'extra_data').glob('*TestExtAtrributes*.json'))
    try:
        (bidsmap_dicomdir.parent/'bidscoiner.errors').unlink(missing_ok=True)
    except Exception:
        pass
    assert 'ERROR' not in logs
    # assert 'WARNING' not in logs
    # assert (bidsmap_dicomdir.parent/'bidscoiner.errors').stat().st_size == 0
    assert (bids_dicomdir/'sub-Archibald'/'ses-02CTHEADBRAINWOCONTRAST').is_dir()
    assert (bids_dicomdir/'sub-Peter'/'ses-01').is_dir()
    assert (bids_dicomdir/'sub-Peter'/'ses-04BrainMRA').is_dir()
    assert len(list(bids_dicomdir.rglob('*.nii*'))) > 3             # Exact number (10) is a bit arbitrary (depends on what dcm2niix can convert)
    assert sidecars[0].is_file()
    with sidecars[0].open('r') as json_fid:
        metadict = json.load(json_fid)
    assert metadict.get('ProtocolName')      == 'T/S/C RF FAST PILOT'
    assert metadict.get('SeriesDescription') == 'TestExtAtrributes'
    assert metadict.get('Comment')           == 'TestExtComment'

    with Path('./.duecredit.p').open('rb') as fid:
        credits = pickle.load(fid)
    assert '10.3389/fninf.2021.770608' in [key.entry_key for key in credits.citations.keys()]
    for key, val in credits.citations.items():
        if key.entry_key == '10.3389/fninf.2021.770608':
            assert val.cite_module == True
            assert val.path        == 'bidscoin'
            assert val.version     == __version__


# def test_addmetadata(bids_dicomdir, bidsmap_dicomdir):
#     bidsmap, _ = bids.load_bidsmap(bidsmap_dicomdir)
#     bidscoiner.addmetadata(bids_dicomdir/'sub-something'/'ses-else', '*', '*')
