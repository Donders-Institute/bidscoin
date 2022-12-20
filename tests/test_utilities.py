import shutil
import csv
from pydicom.data import get_testdata_file
from pathlib import Path
try:
    from bidscoin import bidscoin
    from utilities import dicomsort, rawmapper, bidsparticipants
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))         # This should work if bidscoin was not pip-installed
    sys.path.append(str(Path(__file__).parents[1]/'utilities'))
    import bidscoin, dicomsort, rawmapper, bidsparticipants

bidscoin.setup_logging()


def test_dicomsort(tmp_path):
    shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, tmp_path, dirs_exist_ok=True)
    sessions = dicomsort.sortsessions(tmp_path/'DICOMDIR', namescheme='{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber}_{InstanceNumber}.IMA', force=True)
    assert dicomsort.sortsessions(tmp_path/'DICOMDIR', folderscheme='{SeriesNumber:03d_{SeriesDescription}') == []
    assert (tmp_path/'Doe^Peter').is_dir()           # Patient: 98890234: Doe^Peter
    assert (tmp_path/'Doe^Archibald').is_dir()       # Patient: 77654033: Doe^Archibald
    assert len(sorted((tmp_path/'Doe^Archibald').rglob('*')))                == 13
    assert len(sorted((tmp_path/'Doe^Peter').rglob('*')))                    == 37
    assert sorted(sorted(sessions[0].iterdir())[0].iterdir())[0].name        == '001_Cervical LAT__1.IMA'
    assert sorted(sorted(sessions[0].iterdir())[0].iterdir())[0].parent.name == '001-Cervical LAT'


def test_bidsparticipants(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir):
    participantsfile = bids_dicomdir/'participants.tsv'
    if participantsfile.is_file():
        with open(participantsfile) as file:
            olddata = list(csv.reader(file, delimiter='\t'))
        bidsparticipants.bidsparticipants(raw_dicomdir, bids_dicomdir, ['age', 'sex', 'size', 'weight'])
        with open(participantsfile) as file:
            newdata = list(csv.reader(file, delimiter='\t'))
        assert olddata == newdata


def test_rawmapper(tmp_path):
    shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, tmp_path, dirs_exist_ok=True)
    dicomsort.sortsessions(tmp_path/'DICOMDIR', namescheme='{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber}_{InstanceNumber}.IMA', force=True)

    rawmapper.rawmapper(tmp_path, dicomfield=('PatientID','PatientComments'), subprefix='Doe', sesprefix='*')
    mapperfile = tmp_path/'rawmapper_PatientID_PatientComments.tsv'
    with open(mapperfile) as file:
        mapperdata = list(csv.reader(file, delimiter='\t'))
    assert len(mapperdata) == 7
    assert mapperdata[0]   == ['subid', 'sesid', 'seriesname', 'PatientID', 'PatientComments']
    assert mapperdata[1]   == ['Doe^Archibald', '01-XR C Spine Comp Min 4 Views', '001-Cervical LAT', '77654033', '']
    assert mapperdata[2]   == ['Doe^Archibald', '02-CT, HEADBRAIN WO CONTRAST', '002-Routine Brain', '77654033', '']

    rawmapper.rawmapper(tmp_path, dicomfield=('PatientID',), rename=True, subprefix='Doe', sesprefix='01')
    mapperfile = tmp_path/'rawmapper_PatientID.tsv'
    with open(mapperfile) as file:
        mapperdata = list(csv.reader(file, delimiter='\t'))
    assert len(mapperdata) == 3
    assert mapperdata[0]   == ['subid', 'sesid', 'newsubid', 'newsesid']
    assert mapperdata[1]   == ['Doe^Archibald', '01-XR C Spine Comp Min 4 Views', 'Doe77654033', '01-XR C Spine Comp Min 4 Views']
    assert mapperdata[2]   == ['Doe^Peter', '01-', 'Doe98890234', '01-']
    assert (tmp_path/'Doe77654033'/'01-XR C Spine Comp Min 4 Views').is_dir()
    assert (tmp_path/'Doe98890234'/'01-').is_dir()

    rawmapper.rawmapper(tmp_path, dicomfield=('PatientID',), rename=True, subprefix='Doe', sesprefix='02')
    with open(mapperfile) as file:
        mapperdata = list(csv.reader(file, delimiter='\t'))
    assert len(mapperdata) == 5
    assert mapperdata[0]   == ['subid', 'sesid', 'newsubid', 'newsesid']
    assert mapperdata[1]   == ['Doe^Archibald', '01-XR C Spine Comp Min 4 Views', 'Doe77654033', '01-XR C Spine Comp Min 4 Views']
    assert mapperdata[4]   == ['Doe^Peter', '02-Carotids', 'Doe98890234', '02-Carotids']
    assert (tmp_path/'Doe98890234'/'02-Carotids').is_dir()

    rawmapper.rawmapper(tmp_path, dicomfield=('PatientID',), rename=True, subprefix='Doe', sesprefix='*')
    with open(mapperfile) as file:
        mapperdata = list(csv.reader(file, delimiter='\t'))
    assert len(mapperdata) == 7
    assert mapperdata[6]   == ['Doe^Peter', '04-Brain-MRA', 'Doe98890234', '04-Brain-MRA']
    assert (tmp_path/'Doe98890234'/'04-Brain-MRA').is_dir()
