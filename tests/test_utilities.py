import pytest
import shutil
import csv
from pydicom.data import get_testdata_file
from nibabel.testing import data_path
from pathlib import Path
from bidscoin import bcoin
from bidscoin import utilities
from bidscoin.utilities import dicomsort, rawmapper, bidsparticipants
from importlib.util import find_spec

bcoin.setup_logging()


@pytest.fixture(scope='module')
def dcm_file():
    return Path(get_testdata_file('MR_small.dcm'))


@pytest.fixture(scope='module')
def dcm_file_csa():
    return Path(data_path)/'1.dcm'


@pytest.fixture(scope='module')
def dicomdir():
    return Path(get_testdata_file('DICOMDIR'))


@pytest.fixture(scope='module')
def par_file():
    return Path(data_path)/'phantom_EPI_asc_CLEAR_2_1.PAR'


def test_unpack(dicomdir, tmp_path):
    sessions, unpacked = utilities.unpack(dicomdir.parent, '', tmp_path, None)   # None -> simulate command-line usage of dicomsort()
    assert unpacked
    assert len(sessions) == 6
    for session in sessions:
        assert 'Doe^Archibald' in session.parts or 'Doe^Peter' in session.parts


def test_is_dicomfile(dcm_file):
    assert utilities.is_dicomfile(dcm_file)


def test_is_parfile(par_file):
    assert utilities.is_parfile(par_file)


def test_get_dicomfile(dcm_file, dicomdir):
    assert utilities.get_dicomfile(dcm_file.parent).name == '693_J2KI.dcm'
    assert utilities.get_dicomfile(dicomdir.parent).name == '6154'


def test_get_dicomfield(dcm_file_csa):

    # -> Standard DICOM
    value = utilities.get_dicomfield('SeriesDescription', dcm_file_csa)
    assert value == 'CBU_DTI_64D_1A'

    # -> The pydicom-style hexadecimal tag number
    value = utilities.get_dicomfield('SeriesNumber', dcm_file_csa)
    assert value == 12
    assert value == utilities.get_dicomfield('0x00200011', dcm_file_csa)
    assert value == utilities.get_dicomfield('(0x20,0x11)', dcm_file_csa)
    assert value == utilities.get_dicomfield('(0020,0011)', dcm_file_csa)

    # -> The bracketed nested hexadecimal tags
    assert '1.3.12.2.1107.5.2.32.35119.2010011420070434054586384' == utilities.get_dicomfield('[(0x0008,0x1140)][0][0x8,0x1155]', dcm_file_csa)

    # -> The special PhaseEncodingDirection tag
    value = utilities.get_dicomfield('PhaseEncodingDirection', dcm_file_csa)
    assert value == 'AP'

    # -> CSA Series header
    value = utilities.get_dicomfield('PhaseGradientAmplitude', dcm_file_csa)
    assert value == '0.0'

    # -> CSA Image header
    value = utilities.get_dicomfield('ImaCoilString', dcm_file_csa)
    assert value == 'T:HEA;HEP'

    value = utilities.get_dicomfield('B_matrix', dcm_file_csa)
    assert value == ''

    value = utilities.get_dicomfield('NonExistingTag', dcm_file_csa)
    assert value == ''

    # -> CSA MrPhoenixProtocol
    if find_spec('dicom_parser'):
        value = utilities.get_dicomfield('MrPhoenixProtocol.tProtocolName', dcm_file_csa)
        assert value == 'CBU+AF8-DTI+AF8-64D+AF8-1A'

        value = utilities.get_dicomfield('MrPhoenixProtocol.sDiffusion', dcm_file_csa)
        assert value == "{'lDiffWeightings': 2, 'alBValue': [None, 1000], 'lNoiseLevel': 40, 'lDiffDirections': 64, 'ulMode': 256}"

        value = utilities.get_dicomfield('MrPhoenixProtocol.sProtConsistencyInfo.tBaselineString', dcm_file_csa)
        assert value == 'N4_VB17A_LATEST_20090307'


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
        bidsparticipants.bidsparticipants(raw_dicomdir, bids_dicomdir, ['age', 'sex', 'size', 'weight'], bidsmap=bidsmap_dicomdir)
        with open(participantsfile) as fid:
            newdata = list(csv.reader(fid, delimiter='\t'))
        assert newdata == refdata


def test_rawmapper(raw_dicomdir, tmp_path):
    shutil.copytree(raw_dicomdir, tmp_path, dirs_exist_ok=True)

    mapperfile = tmp_path/'rawmapper_PatientID_PatientComments.tsv'
    rawmapper.rawmapper(tmp_path, field=('PatientID', 'PatientComments'), subprefix='Doe^', sesprefix='*')
    with open(mapperfile) as fid:
        mapperdata = list(csv.reader(fid, delimiter='\t'))
    assert len(mapperdata) == 7
    assert mapperdata[0]   == ['subid', 'sesid', 'seriesname', 'PatientID', 'PatientComments']
    assert mapperdata[1]   == ['Doe^Archibald', '01-XR C Spine Comp Min 4 Views', '001-Cervical LAT', '77654033', '']
    assert mapperdata[2]   == ['Doe^Archibald', '02-CT, HEADBRAIN WO CONTRAST', '002-Routine Brain', '77654033', '']

    mapperfile = tmp_path/'rawmapper_PatientID.tsv'
    rawmapper.rawmapper(tmp_path, field=('PatientID',), rename=True, subprefix='Doe^', sesprefix='01')
    with open(mapperfile) as fid:
        mapperdata = list(csv.reader(fid, delimiter='\t'))
    assert len(mapperdata) == 3
    assert mapperdata[0]   == ['subid', 'sesid', 'newsubid', 'newsesid']
    assert mapperdata[1]   == ['Doe^Archibald', '01-XR C Spine Comp Min 4 Views', 'Doe^77654033', '01-XR C Spine Comp Min 4 Views']
    assert mapperdata[2]   == ['Doe^Peter', '01-', 'Doe^98890234', '01-']
    assert (tmp_path/'Doe^77654033'/'01-XR C Spine Comp Min 4 Views').is_dir()
    assert (tmp_path/'Doe^98890234'/'01-').is_dir()

    rawmapper.rawmapper(tmp_path, field=('PatientID',), rename=True, subprefix='Doe^', sesprefix='02')
    with open(mapperfile) as fid:
        mapperdata = list(csv.reader(fid, delimiter='\t'))
    assert len(mapperdata) == 5
    assert mapperdata[0]   == ['subid', 'sesid', 'newsubid', 'newsesid']
    assert mapperdata[1]   == ['Doe^Archibald', '01-XR C Spine Comp Min 4 Views', 'Doe^77654033', '01-XR C Spine Comp Min 4 Views']
    assert mapperdata[4]   == ['Doe^Peter', '02-Carotids', 'Doe^98890234', '02-Carotids']
    assert (tmp_path/'Doe^98890234'/'02-Carotids').is_dir()

    rawmapper.rawmapper(tmp_path, field=('PatientID',), rename=True, subprefix='Doe^', sesprefix='*')
    with open(mapperfile) as fid:
        mapperdata = list(csv.reader(fid, delimiter='\t'))
    assert len(mapperdata) == 7
    assert mapperdata[6]   == ['Doe^Peter', '04-Brain-MRA', 'Doe^98890234', '04-Brain-MRA']
    assert (tmp_path/'Doe^98890234'/'04-Brain-MRA').is_dir()
