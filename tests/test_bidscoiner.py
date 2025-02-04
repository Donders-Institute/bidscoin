import os
import json
import yaml
import csv
import logging
from bidscoin import bcoin, bidsmapper, bidscoiner, bidsmap_template, __version__
from duecredit.io import load_due, DUECREDIT_FILE

bcoin.setup_logging()


def test_bidscoiner_dicomdir(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir):

    if not bidsmap_dicomdir.is_file():
        bidsmapper.bidsmapper(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir, bidsmap_template, [], 'Doe^', '*', unzip='', automated=True, force=True)
        try:
            (bidsmap_dicomdir.parent/'bidsmapper.errors').unlink(missing_ok=True)
        except Exception:
            pass
    bidscoiner.bidscoiner(raw_dicomdir, bids_dicomdir)
    logs    = (bidsmap_dicomdir.parent/'bidscoiner.errors').read_text()
    sidecar = sorted((bids_dicomdir/'sub-Peter'/'ses-03Brain').rglob('*TestExtAtrributes*.json'))[0]
    with bidsmap_dicomdir.open('r') as fid:
        bidsmap = yaml.safe_load(fid)
    try:
        (bidsmap_dicomdir.parent/'bidscoiner.errors').unlink(missing_ok=True)
    except Exception:
        pass
    assert 'ERROR' not in logs
    # assert 'WARNING' not in logs
    assert bidsmap['Options']['bidscoin']['unknowntypes'][-1] == 'extra_data'
    assert sidecar.relative_to(bids_dicomdir).as_posix()      == 'sub-Peter/ses-03Brain/extra_data/sub-Peter_ses-03Brain_acq-TSCRFFASTPILOTi00001_mod-TestExtAtrributes_GR.json'
    assert (bids_dicomdir/'sub-Archibald'/'ses-02CTHEADBRAINWOCONTRAST').is_dir()
    assert (bids_dicomdir/'sub-Peter'/'ses-01').is_dir()
    assert (bids_dicomdir/'sub-Peter'/'ses-04BrainMRA').is_dir()
    assert len(list(bids_dicomdir.rglob('*.nii*'))) > 3             # Exact number (10) is a bit arbitrary (depends on what dcm2niix can convert)
    with sidecar.open('r') as json_fid:
        metadict = json.load(json_fid)
    assert metadict.get('ProtocolName')      == 'T/S/C RF FAST PILOT'
    assert metadict.get('SeriesDescription') == 'TestExtAtrributes'
    assert metadict.get('Comment')           == 'TestExtComment'

    if os.getenv('DUECREDIT_ENABLE','').lower() in ('1', 'yes', 'true'):
        credits = load_due(DUECREDIT_FILE)
        assert DUECREDIT_FILE in ('.duecredit.p', str(bids_dicomdir/'code'/'bidscoin'/'.duecredit_bidscoiner.p'))
        assert '10.3389/fninf.2021.770608' in [key.entry_key for key in credits.citations.keys()]
        for (path, entry_key), citation in credits.citations.items():
            if entry_key == '10.3389/fninf.2021.770608':
                assert path                 == 'bidscoin'
                assert citation.cite_module is True
                assert citation.version     == __version__

    participantsfile = bids_dicomdir/'participants.tsv'
    with open(participantsfile) as fid:
        data = list(csv.reader(fid, delimiter='\t'))
    with open(participantsfile.with_suffix('.json')) as fid:
        meta = json.load(fid)
    # participant_id  session_id                      age     sex     height  weight
    # sub-Archibald   ses-02CTHEADBRAINWOCONTRAST     42      n/a     n/a     n/a
    # sub-Peter       ses-01                          43      M       n/a     81.632700
    assert data[0] == list(meta.keys())
    assert data[0] == ['participant_id', 'session_id', 'age', 'sex', 'height', 'weight']
    assert data[2] == ['sub-Peter',      'ses-01',     '43',  'M',   'n/a',    '81.632700']


def test_bidscoiner_neurobs(bids_neurobs, bidsmap_neurobs, test_data):

    testdata = str(test_data/'neurobs')
    if not bidsmap_neurobs.is_file():
        bidsmapper.bidsmapper(testdata, str(bids_neurobs), bidsmap_neurobs, bidsmap_template, ['events2bids'], 'sub-', 'ses-', '', automated=True)
        try:
            (bidsmap_neurobs.parent/'bidsmapper.errors').unlink(missing_ok=True)
        except Exception:
            pass
    with bidsmap_neurobs.open('r') as fid:
        bidsmap = yaml.safe_load(fid)
    bidsmap['Presentation']['func'][0]['events']['rows'][0]['condition'] = {'Event Type': 'Pict.*'}
    bidsmap['Presentation']['func'][0]['events']['rows'].append({})
    bidsmap['Presentation']['func'][0]['events']['rows'][1]['condition'] = {'Code': 'instr.*'}
    bidsmap['Presentation']['func'][0]['events']['rows'][1]['cast']      = {'xtra': 'test'}
    with bidsmap_neurobs.open('w') as fid:
        yaml.dump(bidsmap, fid)
    bidscoiner.bidscoiner(testdata, bids_neurobs)
    logs = (bidsmap_neurobs.parent/'bidscoiner.errors').read_text()
    try:
        (bidsmap_neurobs.parent/'bidscoiner.errors').unlink(missing_ok=True)
    except Exception:
        pass
    assert 'ERROR' not in logs
    assert 'WARNING' not in logs
    assert len(list(bids_neurobs.rglob('sub-*.json*'))) == 2

    tsvfile1 = bids_neurobs/'sub-M059'/'func'/'sub-M059_events.tsv'
    tsvfile2 = bids_neurobs/'sub-M059'/'extra_data'/'sub-M059_task-Flanker_events.tsv'
    with open(tsvfile1) as fid:
        data = list(csv.reader(fid, delimiter='\t'))
    # onset     duration code         trial_type  trial_nr xtra
    # 1.0167    5.523    instruction  Picture     1        test
    # 6.5397    1.4517   instruction  Picture     2        test
    # 7.9914    1.5184   instruction  Picture     3        test
    # 147.0519  2.019    break        Picture     6
    assert len(data) == 361
    assert data[0]   == ['onset',    'duration', 'code',        'trial_type', 'trial_nr', 'xtra']
    assert data[3]   == ['7.9914',   '1.5184',   'instruction', 'Picture',    '3',        'test']
    assert data[4]   == ['147.0519', '2.019',    'break',       'Picture',    '6',        '']
    assert tsvfile2.is_file()

    participantsfile = bids_neurobs/'participants.tsv'
    with open(participantsfile) as fid:
        data = list(csv.reader(fid, delimiter='\t'))
    assert len(data) == 2
    assert data[0]   == ['participant_id']
    assert data[1]   == ['sub-M059']

    for handler in logging.getLogger().handlers:
        handler.close()
    bcoin.setup_logging()
    (bidsmap_neurobs.parent/'bidscoiner.log').unlink(missing_ok=True)
    bidscoiner.bidscoiner(testdata, bids_neurobs)
    logs = (bidsmap_neurobs.parent/'bidscoiner.log').read_text()
    assert '>>> Coining' not in logs
    assert '>>> Skipping' in logs

# def test_addmetadata(bids_dicomdir, bidsmap_dicomdir):
#     """WIP"""
#     with bidsmap_dicomdir.open('r')":
#         bidsmap = yaml.safe_load(fid)
#     bidscoiner.addmetadata(bids_dicomdir/'sub-something'/'ses-else', '*', '*')
