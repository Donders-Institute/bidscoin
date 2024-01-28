import shutil
import csv
from pydicom.data import get_testdata_file
from pathlib import Path
from bidscoin import bcoin
from bidscoin.utilities import dicomsort, rawmapper, bidsparticipants

bcoin.setup_logging()


def test_dicomsort(tmp_path):
    shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, tmp_path, dirs_exist_ok=True)
    session = sorted(dicomsort.sortsessions(tmp_path/'DICOMDIR', None, folderscheme='{SeriesNumber:04d}-{SeriesDescription}', namescheme='{SeriesNumber:02d}_{SeriesDescription}_{AcquisitionNumber}_{InstanceNumber}.IMA', force=True))
    assert dicomsort.sortsessions(tmp_path/'DICOMDIR', None, folderscheme='{SeriesNumber:04d]-{SeriesDescription}') == set()  # Invalid scheme -> clean return
    assert dicomsort.validscheme('{foo:04d}-{123}') is True
    assert dicomsort.validscheme('{foo:04d]-{bar}') is False
    assert dicomsort.validscheme('{foo:04}-{bar}')  is False
    assert (tmp_path/'Doe^Peter').is_dir()                                                                              # Subject (Patient): 98890234 -> Doe^Peter
    assert (tmp_path/'Doe^Archibald').is_dir()                                                                          #                    77654033 -> Doe^Archibald
    assert len(list((tmp_path/'Doe^Archibald').rglob('*')))                 == 13                                       #  6 directories +  7 files
    assert len(list((tmp_path/'Doe^Peter').rglob('*')))                     == 37                                       # 13 directories + 24 files
    assert session[0].parent.name                                           == 'Doe^Archibald'                          # Subject (Patient)
    assert session[0].name                                                  == '01-XR C Spine Comp Min 4 Views'         # Session (Study)
    assert sorted(sorted(session[0].iterdir())[0].iterdir())[0].parent.name == '0001-Cervical LAT'                      # Series -> folderscheme
    assert sorted(sorted(session[0].iterdir())[0].iterdir())[0].name        == '01_Cervical LAT__1.IMA'                 # File   -> namescheme


def test_bidsparticipants(raw_dicomdir, bids_dicomdir, bidsmap_dicomdir):
    participantsfile = bids_dicomdir/'participants.tsv'
    if participantsfile.is_file():                                  # Compare newly generated data with reference data from test_bidscoiner
        with open(participantsfile) as fid:
            refdata = list(csv.reader(fid, delimiter='\t'))
        bidsparticipants.bidsparticipants(raw_dicomdir, bids_dicomdir, ['age', 'sex', 'size', 'weight'], bidsmapfile=bidsmap_dicomdir)
        with open(participantsfile) as fid:
            newdata = list(csv.reader(fid, delimiter='\t'))
        assert newdata == refdata


def test_rawmapper(raw_dicomdir, tmp_path):
    shutil.copytree(raw_dicomdir, tmp_path, dirs_exist_ok=True)

    mapperfile = tmp_path/'rawmapper_PatientID_PatientComments.tsv'
    rawmapper.rawmapper(tmp_path, dicomfield=('PatientID','PatientComments'), subprefix='Doe^', sesprefix='*')
    with open(mapperfile) as fid:
        mapperdata = list(csv.reader(fid, delimiter='\t'))
    assert len(mapperdata) == 7
    assert mapperdata[0]   == ['subid', 'sesid', 'seriesname', 'PatientID', 'PatientComments']
    assert mapperdata[1]   == ['Doe^Archibald', '01-XR C Spine Comp Min 4 Views', '001-Cervical LAT', '77654033', '']
    assert mapperdata[2]   == ['Doe^Archibald', '02-CT, HEADBRAIN WO CONTRAST', '002-Routine Brain', '77654033', '']

    mapperfile = tmp_path/'rawmapper_PatientID.tsv'
    rawmapper.rawmapper(tmp_path, dicomfield=('PatientID',), rename=True, subprefix='Doe^', sesprefix='01')
    with open(mapperfile) as fid:
        mapperdata = list(csv.reader(fid, delimiter='\t'))
    assert len(mapperdata) == 3
    assert mapperdata[0]   == ['subid', 'sesid', 'newsubid', 'newsesid']
    assert mapperdata[1]   == ['Doe^Archibald', '01-XR C Spine Comp Min 4 Views', 'Doe^77654033', '01-XR C Spine Comp Min 4 Views']
    assert mapperdata[2]   == ['Doe^Peter', '01-', 'Doe^98890234', '01-']
    assert (tmp_path/'Doe^77654033'/'01-XR C Spine Comp Min 4 Views').is_dir()
    assert (tmp_path/'Doe^98890234'/'01-').is_dir()

    rawmapper.rawmapper(tmp_path, dicomfield=('PatientID',), rename=True, subprefix='Doe^', sesprefix='02')
    with open(mapperfile) as fid:
        mapperdata = list(csv.reader(fid, delimiter='\t'))
    assert len(mapperdata) == 5
    assert mapperdata[0]   == ['subid', 'sesid', 'newsubid', 'newsesid']
    assert mapperdata[1]   == ['Doe^Archibald', '01-XR C Spine Comp Min 4 Views', 'Doe^77654033', '01-XR C Spine Comp Min 4 Views']
    assert mapperdata[4]   == ['Doe^Peter', '02-Carotids', 'Doe^98890234', '02-Carotids']
    assert (tmp_path/'Doe^98890234'/'02-Carotids').is_dir()

    rawmapper.rawmapper(tmp_path, dicomfield=('PatientID',), rename=True, subprefix='Doe^', sesprefix='*')
    with open(mapperfile) as fid:
        mapperdata = list(csv.reader(fid, delimiter='\t'))
    assert len(mapperdata) == 7
    assert mapperdata[6]   == ['Doe^Peter', '04-Brain-MRA', 'Doe^98890234', '04-Brain-MRA']
    assert (tmp_path/'Doe^98890234'/'04-Brain-MRA').is_dir()
