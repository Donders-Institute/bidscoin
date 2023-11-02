import copy
import pandas as pd
import pytest
import shutil
import re
import json
import ruamel.yaml.comments
from pathlib import Path
from nibabel.testing import data_path
from pydicom.data import get_testdata_file
from bidscoin import bcoin, bids, bidsmap_template

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


@pytest.fixture(scope='module')
def test_bidsmap():
    """The path to the study bidsmap `test_data/bidsmap.yaml`"""
    return Path(__file__).parent/'test_data'/'bidsmap.yaml'


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
        assert datasource.properties( 'nrfiles')                    == 76

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
        expected_sub  = 'sub-' + bids.sanitize(re.sub(f"^{subses_source.resubprefix()}", '', subid)  if subid.startswith(subprefix) or subprefix=='*' else '')  # NB: this expression is too complicated / resembles the actual code too much :-/
        expected_ses  = 'ses-' + bids.sanitize(re.sub(f"^{subses_source.resesprefix()}", '', sesid)) if (subid.startswith(subprefix) or subprefix=='*') and (sesid.startswith(sesprefix) or sesprefix=='*') and sesid else ''
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

    # Load a valid template
    bidsmap, _ = bids.load_bidsmap(template, checks=(False, False, False))
    assert isinstance(bidsmap, dict) and bidsmap
    assert bids.check_template(bidsmap) == True

    # Add an invalid data type
    bidsmap['DICOM']['foo'] = bidsmap['DICOM']['extra_data']
    assert bids.check_template(bidsmap) == False
    del bidsmap['DICOM']['foo']

    # Remove a valid suffix (BIDS-entity)
    bidsmap['DICOM']['anat'].pop(-2)        # NB: Assumes CT is the last item, MTR the second last
    assert bids.check_template(bidsmap) == False


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


def test_load_bidsmap(test_bidsmap):

    # Test loading with recommended arguments for load_bidsmap
    full_arguments_map, return_path = bids.load_bidsmap(Path(test_bidsmap.name), test_bidsmap.parent)
    assert type(full_arguments_map) == ruamel.yaml.comments.CommentedMap
    assert full_arguments_map is not []

    # Test loading with no input folder0, should load default from heuristics folder
    no_input_folder_map, _ = bids.load_bidsmap(test_bidsmap)
    assert type(no_input_folder_map) == ruamel.yaml.comments.CommentedMap
    assert no_input_folder_map is not []

    # Test loading with full path to only bidsmap file
    full_path_to_bidsmap_map, _ = bids.load_bidsmap(test_bidsmap)
    assert type(full_path_to_bidsmap_map) == ruamel.yaml.comments.CommentedMap
    assert no_input_folder_map is not []


def test_validate_bidsmap(test_bidsmap):

    # Load a BIDS-valid study bidsmap
    bidsmap, _ = bids.load_bidsmap(test_bidsmap)
    run        = bidsmap['DICOM']['func'][0]
    assert bids.validate_bidsmap(bidsmap) == True

    # Validate the bids-keys
    run['bids']['flip'] = 'foo'     # Add a false key
    assert bids.validate_bidsmap(bidsmap) == False
    del run['bids']['flip']
    del run['bids']['task']         # Remove a required key
    assert bids.validate_bidsmap(bidsmap) == False
    run['bids']['task'] = 'foo'

    # Check bids-suffix
    run['bids']['suffix'] = 'T1w'   # Set an invalid suffix
    assert bids.validate_bidsmap(bidsmap) == False
    run['bids']['suffix'] = 'bold'

    # Check bids-values
    run['bids']['task'] = ''        # Remove a required value
    assert bids.validate_bidsmap(bidsmap) == False
    run['bids']['task'] = 'f##'     # Add invalid characters (they are cleaned out)
    assert bids.validate_bidsmap(bidsmap) == True
    run['bids']['task'] = 'foo'
    run['bids']['run']  = 'a'       # Add an invalid (non-numeric) index
    assert bids.validate_bidsmap(bidsmap) == False


def test_check_bidsmap(test_bidsmap):

    # Load a template and a study bidsmap
    template_bidsmap, _ = bids.load_bidsmap(bidsmap_template, checks=(True, True, False))
    study_bidsmap, _    = bids.load_bidsmap(test_bidsmap)

    # Test the output of the template bidsmap
    checks   = (True, True, False)
    is_valid = bids.check_bidsmap(template_bidsmap, checks)
    for each, check in zip(is_valid, checks):
        assert each in (None, True, False)
        if check:
            assert each in (None, True)

    # Test the output of the study bidsmap
    is_valid = bids.check_bidsmap(study_bidsmap, checks)
    for each, check in zip(is_valid, checks):
        assert each in (None, True, False)
        if check:
            assert each == True


def test_check_run(test_bidsmap):

    # Load a bidsmap
    bidsmap, _ = bids.load_bidsmap(test_bidsmap)

    # Collect the first func run-item
    checks = (True, True, True)             # = (keys, suffixes, values)
    run    = bidsmap['DICOM']['func'][0]

    # Check data type
    assert bids.check_run('func', run, checks) == (True, True, True)
    assert bids.check_run('anat', run, checks) == (None, False, None)
    assert bids.check_run('foo',  run, checks) == (None, None, None)

    # Check bids-keys
    run['bids']['flip'] = 'foo'     # Add a false key
    assert bids.check_run('func', run, checks) == (False, True, None)
    del run['bids']['flip']
    del run['bids']['acq']          # Remove a valid key
    assert bids.check_run('func', run, checks) == (False, True, True)
    run['bids']['acq'] = 'foo'

    # Check bids-suffix
    run['bids']['suffix'] = 'T1w'   # Set an invalid suffix
    assert bids.check_run('func', run, checks) == (None, False, None)
    run['bids']['suffix'] = 'bold'

    # Check bids-values
    run['bids']['task'] = ''        # Remove a required value
    assert bids.check_run('func', run, checks) == (True, True, False)
    run['bids']['task'] = 'f##'     # Add invalid characters
    assert bids.check_run('func', run, checks) == (True, True, False)
    run['bids']['task'] = 'foo'
    run['bids']['run']  = 'a'       # Add an invalid (non-numeric) index
    assert bids.check_run('func', run, checks) == (True, True, False)


def test_check_ignore():

    bidsignore = ['mrs/', 'sub-*_foo.*', '*foo/sub-*_bar.*']

    assert bids.check_ignore('mrs',                bidsignore)         == True      # Test default: datatype = 'dir'
    assert bids.check_ignore('mrs',                bidsignore, 'file') == False
    assert bids.check_ignore('mrs/sub-01_foo.nii', bidsignore, 'dir')  == False
    assert bids.check_ignore('mrs/sub-01_bar.nii', bidsignore, 'file') == False
    assert bids.check_ignore('foo/sub-01_bar.nii', bidsignore, 'file') == True
    assert bids.check_ignore('bar/sub-01_bar.nii', bidsignore, 'file') == False
    assert bids.check_ignore('bar/sub-01_foo.nii', bidsignore, 'file') == False
    assert bids.check_ignore('sub-01_foo.nii',     bidsignore, 'file') == True


def test_find_run(test_bidsmap):

    # Load a bidsmap and create a duplicate dataformat section
    bidsmap, _     = bids.load_bidsmap(test_bidsmap)
    bidsmap['PET'] = copy.deepcopy(bidsmap['DICOM'])

    # Collect provenance of the first anat run-item
    provenance                              = bidsmap['DICOM']['anat'][0]['provenance']
    tag                                     = '123456789'
    bidsmap['PET']['anat'][0]['provenance'] = tag

    # Find run with the wrong dataformat
    run = bids.find_run(bidsmap, provenance, dataformat='PET')
    assert run == {}

    # Find run with the wrong data type
    run = bids.find_run(bidsmap, provenance, datatype='func')
    assert run == {}

    # Find run with partial provenance
    run = bids.find_run(bidsmap, 'sub-001')
    assert run == {}

    # Find run with full provenance
    run = bids.find_run(bidsmap, provenance)
    assert isinstance(run, dict)
    run = bids.find_run(bidsmap, tag, dataformat='PET', datatype='anat')
    assert run.get('provenance') == tag


def test_delete_run(test_bidsmap):

    # Load a study bidsmap and delete one anat run
    bidsmap, _ = bids.load_bidsmap(test_bidsmap)
    nritems    = len(bidsmap['DICOM']['anat'])
    provenance = bidsmap['DICOM']['anat'][0]['provenance']
    bids.delete_run(bidsmap, provenance)

    assert len(bidsmap['DICOM']['anat']) == nritems - 1
    assert bids.find_run(bidsmap, provenance) == {}


def test_append_run(test_bidsmap):

    # Load a study bidsmap and delete one anat run
    bidsmap, _ = bids.load_bidsmap(test_bidsmap)

    # Collect and modify the first anat run-item
    run                          = copy.deepcopy(bidsmap['DICOM']['anat'][0])
    run['datasource'].dataformat = 'Foo'
    run['datasource'].datatype   = 'Bar'

    # Append the run elsewhere in the bidsmap
    bids.append_run(bidsmap, run)
    assert bidsmap['Foo']['Bar'][0]['provenance'] == run['provenance']


def test_update_bidsmap(test_bidsmap):

    # Load a study bidsmap and move the first run-item from func to anat
    bidsmap, _ = bids.load_bidsmap(test_bidsmap)

    # Collect and modify the first func run-item
    run                        = copy.deepcopy(bidsmap['DICOM']['func'][0])
    run['datasource'].datatype = 'anat'

    # Update the bidsmap
    bids.update_bidsmap(bidsmap, 'func', run)
    assert bidsmap['DICOM']['anat'][-1]['provenance'] == run['provenance']
    assert bidsmap['DICOM']['func'] [0]['provenance'] != run['provenance']

    # Modify the last anat run-item and update the bidsmap
    run['bids']['foo'] = 'bar'
    bids.update_bidsmap(bidsmap, 'anat', run)
    assert bidsmap['DICOM']['anat'][-1]['bids']['foo'] == 'bar'


def test_exist_run(test_bidsmap):

    # Load a bidsmap
    bidsmap, _ = bids.load_bidsmap(test_bidsmap)

    # Collect the first anat run-item
    run = copy.deepcopy(bidsmap['DICOM']['anat'][0])

    # Find the run in the wrong data type
    assert bids.exist_run(bidsmap, 'func', run) == False

    # Find run with in the right data type and in all datatypes
    assert bids.exist_run(bidsmap, 'anat', run) == True
    assert bids.exist_run(bidsmap, '',     run) == True

    # Find the wrong run in all datatypes
    run['attributes']['ProtocolName'] = 'abcdefg'
    assert bids.exist_run(bidsmap, '', run)     == False
    run['attributes']['ProtocolName'] = ''
    assert bids.exist_run(bidsmap, '', run)     == False


def test_increment_runindex_no_run1(tmp_path):
    """Test if run-index is preserved or added to the bidsname"""

    # Test runindex is <<>>, so no run is added to the bidsname
    outfolder = tmp_path/'bids'/'sub-01'/'anat'
    bidsname  = bids.increment_runindex(outfolder, 'sub-01_T1w', {'bids': {'run': '<<>>'}})
    assert bidsname == 'sub-01_T1w'

    # Test runindex is <<1>>, so run-1 is preserved in the bidsname
    bidsname = bids.increment_runindex(outfolder, 'sub-01_run-1_T1w', {'bids': {'run': '<<1>>'}})
    assert bidsname == 'sub-01_run-1_T1w'

    # Test runindex is <<2>>, so run-2 is preserved in the bidsname
    bidsname = bids.increment_runindex(outfolder, 'sub-01_run-2_T1w', {'bids': {'run': '<<2>>'}})
    assert bidsname == 'sub-01_run-2_T1w'


def test_increment_runindex_rename_run1(tmp_path):
    """Test runindex is <<>>, so run-2 is added to the bidsname and existing run-less files are renamed to run-1"""

    # Create the run-less files
    old_run1name = 'sub-01_T1w'
    new_run1name = 'sub-01_run-1_T1w'
    outfolder    = tmp_path/'bids'/'sub-01'/'anat'
    outfolder.mkdir(parents=True)
    for suffix in ('.nii.gz', '.json'):
        (outfolder/old_run1name).with_suffix(suffix).touch()

    # Create the scans table
    scans_data         = {'filename': ['anat/sub-01_T2w.nii.gz', f"anat/{old_run1name}.nii.gz"], 'acq_time': ['acq1', 'acq2']}  # One matching run-less file
    result_scans_data  = {'filename': ['anat/sub-01_T2w.nii.gz', f"anat/{new_run1name}.nii.gz"], 'acq_time': ['acq1', 'acq2']}  # One matching run-1 file
    scans_table        = pd.DataFrame(scans_data).set_index('filename')
    result_scans_table = pd.DataFrame(result_scans_data).set_index('filename')

    # Increment the run-index
    bidsname = bids.increment_runindex(outfolder, 'sub-01_T1w', {'bids': {'run': '<<>>'}}, scans_table)

    # Check the results
    assert bidsname == 'sub-01_run-2_T1w'
    assert result_scans_table.equals(scans_table)
    for suffix in ('.nii.gz', '.json'):
        assert (outfolder/old_run1name).with_suffix(suffix).is_file() == False
        assert (outfolder/new_run1name).with_suffix(suffix).is_file() == True


def test_increment_runindex_run1_run2_exists(tmp_path):
    """Test if run-3 is added to the bidsname"""

    # Create the run-1 and run-2 files
    outfolder = tmp_path/'bids'/'sub-01'/'anat'
    outfolder.mkdir(parents=True)
    for suffix in ('.nii.gz', '.json'):
        (outfolder/'sub-01_run-1_T1w').with_suffix(suffix).touch()
        (outfolder/'sub-01_run-2_T1w').with_suffix(suffix).touch()

    # Test run-index is <<>>, so the run-index is incremented
    bidsname = bids.increment_runindex(outfolder, 'sub-01_T1w.nii.gz', {'bids': {'run': '<<>>'}})
    assert bidsname == 'sub-01_run-3_T1w.nii.gz'

    # Test run-index is <<1>>, so the run-index is incremented
    bidsname = bids.increment_runindex(outfolder, 'sub-01_run-1_T1w', {'bids': {'run': '<<1>>'}})
    assert bidsname == 'sub-01_run-3_T1w'

    # Test run-index is <<AttrKey>>, so the run-index is untouched
    bidsname  = bids.increment_runindex(outfolder, 'sub-01_run-1_T1w', {'bids': {'run': '<<AttrKey>>'}})
    assert bidsname == 'sub-01_run-1_T1w'

    # Test run-index is 2, so the run-index is untouched
    bidsname  = bids.increment_runindex(outfolder, 'sub-01_run-1_T1w', {'bids': {'run': '2'}})
    assert bidsname == 'sub-01_run-1_T1w'


def test_get_bidsname(raw_dicomdir):

    dicomfile   = raw_dicomdir/'Doe^Archibald'/'01-XR C Spine Comp Min 4 Views'/'001-Cervical LAT'/'6154'
    run         = {'datasource': bids.DataSource(dicomfile, {'dcm2niix2bids': {}}, 'DICOM')}
    run['bids'] = {'acq':'py#dicom', 'foo@':'bar#123', 'run':'<<SeriesNumber>>', 'suffix':'T0w'}

    bidsname = bids.get_bidsname('sub-001', 'ses-01', run, validkeys=False, cleanup=False)  # Test default: runtime=False
    assert bidsname == 'sub-001_ses-01_acq-py#dicom_run-<<SeriesNumber>>_foo@-bar#123_T0w'

    bidsname = bids.get_bidsname('sub-001', 'ses-01', run, validkeys=False, runtime=False, cleanup=True)
    assert bidsname == 'sub-001_ses-01_acq-pydicom_run-SeriesNumber_foo@-bar123_T0w'

    bidsname = bids.get_bidsname('sub-001', 'ses-01', run, validkeys=False, runtime=True,  cleanup=False)
    assert bidsname == 'sub-001_ses-01_acq-py#dicom_run-1_foo@-bar#123_T0w'

    bidsname = bids.get_bidsname('sub-001', 'ses-01', run, validkeys=True,  runtime=True,  cleanup=False)
    assert bidsname == 'sub-001_ses-01_acq-py#dicom_run-1_T0w'

    run['bids']['run'] = '<<1>>'
    bidsname = bids.get_bidsname('sub-001', '', run, validkeys=True, runtime=True)          # Test default: cleanup=True
    assert bidsname == 'sub-001_acq-pydicom_run-1_T0w'

    run['bids']['run'] = '<<>>'
    bidsname = bids.get_bidsname('sub-001', '', run, validkeys=True, runtime=True)          # Test default: cleanup=True
    assert bidsname == 'sub-001_acq-pydicom_T0w'


def test_poolmetadata(dcm_file, tmp_path):
    """Test if metadata is added to the dictionary and copied over"""

    # Create the extended datasource
    sourcefile = shutil.copyfile(dcm_file, tmp_path/dcm_file.name)
    sourcefile.with_suffix('.jsn').touch()
    with sourcefile.with_suffix('.json').open('w') as fid:
        json.dump({'PatientName': 'SourceTest'}, fid)
    extdatasource = bids.DataSource(sourcefile, {'dcm2niix2bids': {}}, 'DICOM')

    # Create the metadata sidecar file
    outfolder = tmp_path/'bids'/'sub-01'/'anat'
    outfolder.mkdir(parents=True)
    sidecar = outfolder/'sidecar.json'
    with sidecar.open('w') as fid:
        json.dump({'PatientName': 'SidecarTest'}, fid)

    # Test if the user metadata takes precedence
    metadata = bids.poolmetadata(sourcefile, sidecar, {'PatientName': 'UserTest', 'DynamicName': '<<(0010, 0010)>>'}, ['.json'], extdatasource)
    assert metadata['PatientName'] == 'UserTest'
    assert metadata['DynamicName'] == 'CompressedSamples^MR1'
    assert not (outfolder/sourcefile.with_suffix('.jsn').name).is_file()

    # Test if the source metadata takes precedence
    metadata = bids.poolmetadata(sourcefile, sidecar, {}, ['.jsn', '.json'], extdatasource)
    assert metadata['PatientName'] == 'SourceTest'
    assert (outfolder/sourcefile.with_suffix('.jsn').name).is_file()

    # Test if the sidecar metadata takes precedence
    metadata = bids.poolmetadata(sourcefile, sidecar, {}, [], extdatasource)
    assert metadata['PatientName'] == 'SidecarTest'
