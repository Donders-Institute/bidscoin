from pathlib import Path
import pytest
import re
try:
    from bidscoin import bids, bidscoin, bidsmapper
    from utilities import dicomsort
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))         # This should work if bidscoin was not pip-installed
    sys.path.append(str(Path(__file__).parents[1]/'utilities'))
    import bidscoin, bids, bidsmapper, dicomsort

bidscoin.setup_logging()


@pytest.mark.parametrize('subprefix', ['Doe', 'Doe^', '*'])
@pytest.mark.parametrize('sesprefix', ['0', '*'])
@pytest.mark.parametrize('store', [False, True])
def test_bidsmapper(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir, subprefix, sesprefix, store):
    resubprefix = '' if subprefix=='*' else re.escape(subprefix)
    resesprefix = '' if sesprefix=='*' else re.escape(sesprefix)
    bidsmap     = bidsmapper.bidsmapper(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir, bidscoin.bidsmap_template, [], subprefix, sesprefix, unzip='', store=store, noedit=True, force=True)
    assert bidsmap['Options']['bidscoin']['subprefix'] == subprefix
    assert bidsmap['Options']['bidscoin']['sesprefix'] == sesprefix
    assert bidsmap['DICOM']['subject']                 == f"<<filepath:/{raw_dicomdir.name}/{resubprefix}(.*?)/>>"
    assert bidsmap['DICOM']['session']                 == f"<<filepath:/{raw_dicomdir.name}/{resubprefix}.*?/{resesprefix}(.*?)/>>"
    assert bidsmap_dicomdir.is_file()
    assert 'Doe^Archibald' in bidsmap_dicomdir.read_text()                                      # Make sure we have discovered `Archibald` samples (-> provenance)
    assert 'Doe^Peter' in bidsmap_dicomdir.read_text()                                          # Make sure we have discovered `Peter` samples (-> provenance)
    assert (bidsmap_dicomdir.parent/'bidsmapper.errors').stat().st_size == 0
    assert (bidsmap_dicomdir.parent/'provenance').is_dir()              == store
    (bidsmap_dicomdir.parent/'bidsmapper.errors').unlink(missing_ok=True)
