import pytest
import re
from bidscoin import bcoin, bidsmapper, bidsmap_template

bcoin.setup_logging()


@pytest.mark.parametrize('subprefix', ['Doe', 'Doe^', '*'])
@pytest.mark.parametrize('sesprefix', ['0', '*'])
@pytest.mark.parametrize('store', [False, True])
def test_bidsmapper_dicomdir(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir, subprefix, sesprefix, store):
    resubprefix = '' if subprefix=='*' else re.escape(subprefix).replace(r'\-','-')
    resesprefix = '' if sesprefix=='*' else re.escape(sesprefix).replace(r'\-','-')
    bidsmap     = bidsmapper.bidsmapper(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir, bidsmap_template, [], subprefix, sesprefix, '', store=store, automated=True, force=True)
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


def test_bidsmapper_neurobs(bids_neurobs, bidsmap_neurobs, test_data):

    testdata = str(test_data/'neurobs')
    bidsmap  = bidsmapper.bidsmapper(testdata, bids_neurobs, 'bidsmap.yaml', bidsmap_template, ['events2bids'], 'sub-', 'ses-', '', automated=True)

    assert bidsmap.filepath == bidsmap_neurobs
    assert isinstance(bidsmap.dataformat('Presentation')._data, dict)
    assert len(bidsmap.dataformat('Presentation').datatype(   'exclude').runitems) == 0
    assert len(bidsmap.dataformat('Presentation').datatype(      'func').runitems) == 1
    assert len(bidsmap.dataformat('Presentation').datatype('extra_data').runitems) == 1
    assert bidsmap.dataformat('Presentation').datatype('extra_data').runitems[0].attributes['Scenario'] == 'Flanker'
    assert (bids_neurobs/'code'/'bidscoin'/'bidsmap.yaml').is_file()
    assert 'M059' in bidsmap.filepath.read_text()                       # Make sure we have discovered `M059` samples (-> provenance)
    assert (bidsmap.filepath.parent/'bidsmapper.errors').stat().st_size == 0
