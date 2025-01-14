import pytest
import re
from bidscoin import bcoin, bidsmapper, bidsmap_template

bcoin.setup_logging()


@pytest.mark.parametrize('subprefix', ['Doe', 'Doe^', '*'])
@pytest.mark.parametrize('sesprefix', ['0', '*'])
@pytest.mark.parametrize('store', [False, True])
def test_bidsmapper(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir, subprefix, sesprefix, store):
    resubprefix = '' if subprefix=='*' else re.escape(subprefix).replace(r'\-','-')
    resesprefix = '' if sesprefix=='*' else re.escape(sesprefix).replace(r'\-','-')
    bidsmap     = bidsmapper.bidsmapper(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir, bidsmap_template, [], subprefix, sesprefix, unzip='', store=store, automated=True, force=True)
    assert isinstance(bidsmap.dataformats[0]._data, dict)
    assert bidsmap.options['subprefix'] == subprefix
    assert bidsmap.options['sesprefix'] == sesprefix
    assert bidsmap.dataformat('DICOM').subject                           == f"<<filepath:/{raw_dicomdir.name}/{resubprefix}(.*?)/>>"
    assert bidsmap.dataformat('DICOM').session                           == f"<<filepath:/{raw_dicomdir.name}/{resubprefix}.*?/{resesprefix}(.*?)/>>"
    assert len(bidsmap.dataformat('DICOM').datatype('exclude').runitems) > 1
    for run in bidsmap.dataformat('DICOM').datatype('exclude').runitems:
        assert 'LOCALIZER' in run.attributes['SeriesDescription'] or 'DERIVED' in run.attributes['ImageType']
    assert bidsmap_dicomdir.is_file()
    assert 'Doe^Archibald' in bidsmap_dicomdir.read_text()                                      # Make sure we have discovered `Archibald` samples (-> provenance)
    assert 'Doe^Peter' in bidsmap_dicomdir.read_text()                                          # Make sure we have discovered `Peter` samples (-> provenance)
    assert (bidsmap_dicomdir.parent/'bidsmapper.errors').stat().st_size == 0
    assert (bidsmap_dicomdir.parent/'provenance').is_dir()              == store
    try:
        (bidsmap_dicomdir.parent/'bidsmapper.errors').unlink(missing_ok=True)
    except Exception:
        pass
