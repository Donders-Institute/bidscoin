import json
import shutil
from pathlib import Path
from bidscoin.bidsapps.fixmeta import fixmeta


def test_fixmeta(tmp_path, test_data):

    # Get the data
    bidsdir  = shutil.copytree(test_data/'7t_trt', tmp_path/'7t_trt')
    jsonfile = Path(bidsdir)/'sub-01'/'ses-1'/'fmap'/'sub-01_ses-1_run-1_phasediff.json'
    jsondata = {'EchoTime1': 0.006,
                'EchoTime2': 0.00702,
                'IntendedFor': 'bids::sub-01/ses-1/func/sub-01_ses-1_task-rest_acq-fullbrain_run-1_bold.nii.gz'}

    # Test full replacement and partial substitution
    fixmeta(bidsdir, '*run-1_phasediff*', {'IntendedFor': ['run-1','run-3', 'full','empty'], 'EchoTime2': 999}, [])
    with jsonfile.open('r') as json_fid:
        jsonfixed = json.load(json_fid)
    assert jsonfixed['IntendedFor'] == 'bids::sub-01/ses-1/func/sub-01_ses-1_task-rest_acq-emptybrain_run-3_bold.nii.gz'
    assert jsonfixed['EchoTime1']   == jsondata['EchoTime1']
    assert jsonfixed['EchoTime2']   == 999

    # Test IntendedFor dynamic value
    fixmeta(bidsdir, '*run-1_phasediff*', {'IntendedFor': '<<func/*_run-2_bold>>'}, ['01'])
    with jsonfile.open('r') as json_fid:
        jsonfixed = json.load(json_fid)
    assert jsonfixed['IntendedFor'] == ['bids::sub-01/ses-1/func/sub-01_ses-1_task-rest_acq-fullbrain_run-2_bold.nii.gz']
