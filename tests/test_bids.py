import unittest
import tempfile
import pytest
import shutil
import re
import json
from pathlib import Path
from nibabel.testing import data_path

import ruamel.yaml.comments
from pydicom.data import get_testdata_file
try:
    from bidscoin import bcoin, bids
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))         # This should work if bidscoin was not pip-installed
    import bcoin, bids

bcoin.setup_logging()


@pytest.fixture(scope='module')
def dcm_file():
    return Path(get_testdata_file('MR_small.dcm'))


@pytest.fixture(scope='module')
def dicomdir():
    return Path(get_testdata_file('DICOMDIR'))


@pytest.fixture(scope='module')
def par_file():
    return Path(data_path)/'phantom_EPI_asc_CLEAR_2_1.PAR'


class TestDataSource:
    """Test the bids.DataSource class"""

    @pytest.fixture()
    def datasource(self, dcm_file):
        return bids.DataSource(dcm_file, {'dcm2niix2bids': {}}, 'DICOM')

    @pytest.fixture()
    def extdatasource(self, dcm_file, tmp_path):
        ext_dcm_file = shutil.copyfile(dcm_file, tmp_path/dcm_file.name)
        with ext_dcm_file.with_suffix('.json').open('w') as sidecar:
            json.dump({'PatientName': 'ExtendedAttributesTest'}, sidecar)
        return bids.DataSource(ext_dcm_file, {'dcm2niix2bids': {}}, 'DICOM')

    def test_is_datasource(self, datasource):
        assert datasource.is_datasource()
        assert datasource.dataformat == 'DICOM'

    def test_properties(self, datasource):
        assert datasource.properties( 'filepath:.*/(.*?)_files/.*') == 'test'   # path = [..]/pydicom/data/test_files/MR_small.dcm'
        assert datasource.properties(r'filename:MR_(.*?)\.dcm')     == 'small'
        assert datasource.properties( 'filesize')                   == '9.60 kB'
        assert datasource.properties( 'nrfiles')                    == 75

    def test_attributes(self, datasource, extdatasource):
        assert datasource.attributes(r'PatientName:.*\^(.*?)1') == 'MR'         # PatientName = 'CompressedSamples^MR1'
        assert extdatasource.attributes('PatientName')          == 'ExtendedAttributesTest'

    @pytest.mark.parametrize('subid',  ['sub-001', 'pat^visit'])
    @pytest.mark.parametrize('sesid',  ['ses-01',  'visit^01', ''])
    @pytest.mark.parametrize('subprefix', ['sub-', 'pat^', '*'])
    @pytest.mark.parametrize('sesprefix', ['ses-', 'visit^', '*'])
    def test_subid_sesid(self, subid, sesid, subprefix, sesprefix, tmp_path, dcm_file):
        subsesdir     = tmp_path/'data'/subid/sesid
        subsesdir.mkdir(parents=True)
        subses_file   = shutil.copy(dcm_file, subsesdir)
        subses_source = bids.DataSource(subses_file, {'dcm2niix2bids': {}}, 'DICOM', subprefix=subprefix, sesprefix=sesprefix)
        sub, ses      = subses_source.subid_sesid(f"<<filepath:/data/{subses_source.resubprefix()}(.*?)/>>", f"<<filepath:/data/{subses_source.resubprefix()}.*?/{subses_source.resesprefix()}(.*?)/>>")
        expected_sub  = 'sub-' + bids.cleanup_value(re.sub(f"^{subses_source.resubprefix()}", '', subid)  if subid.startswith(subprefix)  or subprefix=='*' else '')  # NB: this expression is too complicated / resembles the actual code too much :-/
        expected_ses  = 'ses-' + bids.cleanup_value(re.sub(f"^{subses_source.resesprefix()}", '', sesid)) if (subid.startswith(subprefix) or subprefix=='*') and (sesid.startswith(sesprefix) or sesprefix=='*') and sesid else ''
        print(f"[{subprefix}, {subid}] -> {sub}\t\t[{sesprefix}, {sesid}] -> {ses}")
        assert (sub, ses) == (expected_sub, expected_ses)
        assert subses_source.subid_sesid(r'<<PatientName:.*\^(.*?)1>>', '') == ('sub-MR', '')

    def test_dynamicvalue(self, datasource):
        assert datasource.dynamicvalue(r'<PatientName>')                                         == 'CompressedSamplesMR1'
        assert datasource.dynamicvalue(r'PatientName:.*\^(.*?)1')                                == r'PatientName:.*\^(.*?)1'
        assert datasource.dynamicvalue(r'<PatientName:.*\^(.*?)1>')                              == 'MR'
        assert datasource.dynamicvalue(r'<<PatientName:.*\^(.*?)1>>')                            == r'<<PatientName:.*\^(.*?)1>>'
        assert datasource.dynamicvalue(r'<<PatientName:.*\^(.*?)1>>', runtime=True)              == 'MR'
        assert datasource.dynamicvalue(r'pat-<PatientName:.*\^(.*?)1>I<filename:MR_(.*?)\.dcm>') == 'patMRIsmall'
        assert datasource.dynamicvalue(r"<Patient's Name>")                                      == 'CompressedSamplesMR1'    # Patient's Name, 0x00100010, 0x10,0x10, (0x10, 0x10), and (0010, 0010) index keys are all equivalent
        assert datasource.dynamicvalue(r'<0x00100010>')                                          == 'CompressedSamplesMR1'
        assert datasource.dynamicvalue(r'<0x10,0x10>')                                           == 'CompressedSamplesMR1'
        assert datasource.dynamicvalue(r'<(0x10, 0x10)>')                                        == 'CompressedSamplesMR1'
        assert datasource.dynamicvalue(r'<(0010, 0010)>')                                        == 'CompressedSamplesMR1'

def test_unpack(dicomdir, tmp_path):
    unpacked = bids.unpack(dicomdir.parent, '', tmp_path)
    assert unpacked[1]
    assert len(unpacked[0]) == 6
    for ses in unpacked[0]:
        assert 'Doe^Archibald' in ses.parts or 'Doe^Peter' in ses.parts


def test_is_dicomfile(dcm_file):
    assert bids.is_dicomfile(dcm_file)


def test_is_parfile(par_file):
    assert bids.is_parfile(par_file)


def test_get_dicomfile(dcm_file, dicomdir):
    assert bids.get_dicomfile(dcm_file.parent).name == '693_J2KI.dcm'
    assert bids.get_dicomfile(dicomdir.parent).name == '6154'


def test_get_datasource(dicomdir):
    datasource = bids.get_datasource(dicomdir.parent, {'dcm2niix2bids': {}})
    assert datasource.is_datasource()
    assert datasource.dataformat == 'DICOM'


@pytest.mark.parametrize('template', bcoin.list_plugins()[1])
def test_load_check_template(template):
    bidsmap, _ = bids.load_bidsmap(template, check=(False,False,False))
    assert isinstance(bidsmap, dict) and bidsmap
    assert bids.check_template(bidsmap)


def test_match_runvalue():
    assert bids.match_runvalue('my_pulse_sequence_name', '_name')      == False
    assert bids.match_runvalue('my_pulse_sequence_name', '^my.*name$') == True
    assert bids.match_runvalue('T1_MPRage', '(?i).*(MPRAGE|T1w).*')    == True
    assert bids.match_runvalue('', None)                               == True
    assert bids.match_runvalue(None, '')                               == True
    assert bids.match_runvalue(  [1, 2, 3],     [1,2,  3])             == True
    assert bids.match_runvalue(  [1,2,  3],    '[1, 2, 3]')            == True
    assert bids.match_runvalue(  [1, 2, 3],  r'\[1, 2, 3\]')           == True
    assert bids.match_runvalue( '[1, 2, 3]',   '[1, 2, 3]')            == True
    assert bids.match_runvalue( '[1, 2, 3]', r'\[1, 2, 3\]')           == True
    assert bids.match_runvalue( '[1, 2, 3]',    [1, 2, 3])             == True
    assert bids.match_runvalue( '[1,2,  3]',    [1,2,  3])             == False
    assert bids.match_runvalue(r'\[1, 2, 3\]',  [1, 2, 3])             == False


@pytest.fixture()
def test_bidsmap_path():
    return Path(__file__).parent/'test_data'/'bidsmap.yaml'

def test_load_bidsmap(test_bidsmap_path):
    # test loading with recommended arguments for load_bidsmap
    full_arguments_map, return_path = bids.load_bidsmap(Path(test_bidsmap_path.name),
                                                        test_bidsmap_path.parent)
    assert type(full_arguments_map) == ruamel.yaml.comments.CommentedMap
    assert full_arguments_map is not []

    # test loading with no input folder0, should load default from heuristics folder
    no_input_folder_map, _ = bids.load_bidsmap(test_bidsmap_path)
    assert type(no_input_folder_map) == ruamel.yaml.comments.CommentedMap
    assert no_input_folder_map is not []

    # test loading with full path to only bidsmap file
    full_path_to_bidsmap_map, _ = bids.load_bidsmap(test_bidsmap_path)
    assert type(full_path_to_bidsmap_map) == ruamel.yaml.comments.CommentedMap
    assert no_input_folder_map is not []


def test_find_run(test_bidsmap_path):

    # load bidsmap
    bidsmap, _ = bids.load_bidsmap(test_bidsmap_path)

    # collect provenance from bidsmap for anat, pet, and func
    anat_provenance = bidsmap['DICOM']['anat'][0]['provenance']
    func_provenance = bidsmap['DICOM']['func'][0]['provenance']

    # find run with partial provenance
    not_found_run = bids.find_run(bidsmap=bidsmap, provenance='sub-001', dataformat='DICOM')
    assert not_found_run is None

    # find run with full provenance
    found_run = bids.find_run(bidsmap=bidsmap, provenance=anat_provenance)
    assert found_run is not None

    # create a duplicate provenance but in a different datatype
    bidsmap['PET'] = bidsmap['DICOM']
    # mark the entry in the PET section to make sure we're getting the right one
    tag = 123456789
    bidsmap['PET']['anat'][0]['properties']['nrfiles'] = tag
    # locate PET datatype run
    pet_run = bids.find_run(bidsmap, provenance=anat_provenance, dataformat='PET')
    assert pet_run['properties']['nrfiles'] == tag


def test_delete_run(test_bidsmap_path):
    # create a copy of the bidsmap
    with tempfile.TemporaryDirectory() as tempdir:
        temp_bidsmap = Path(tempdir) / Path(test_bidsmap_path.name)
        shutil.copy(test_bidsmap_path, temp_bidsmap)
        bidsmap, _ = bids.load_bidsmap(temp_bidsmap)
        anat_provenance = bidsmap['DICOM']['anat'][0]['provenance']
        # now delete it from the bidsmap
        bids.delete_run(bidsmap, anat_provenance)
        assert len(bidsmap['DICOM']['anat']) == 0
        # verify this gets deleted when rewritten
        bids.save_bidsmap(_, bidsmap)
        written_bidsmap, _ = bids.load_bidsmap(_)
        deleted_run = bids.find_run(written_bidsmap, anat_provenance)
        assert deleted_run is None
