import copy
import pandas as pd
import pytest
import shutil
import re
import json
import ruamel.yaml.comments
from datetime import datetime, timedelta
from importlib.util import find_spec
from pathlib import Path
from nibabel.testing import data_path
from pydicom.data import get_testdata_file
from bidscoin import bcoin, bids, bidsmap_template
from bidscoin.bids import Run, Plugin

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


@pytest.fixture(scope='module')
def study_bidsmap():
    """The path to the study bidsmap `test_data/bidsmap.yaml`"""
    return Path(__file__).parent/'test_data'/'bidsmap.yaml'


class TestDataSource:
    """Test the bids.DataSource class"""

    @pytest.fixture()
    def datasource(self, dcm_file):
        return bids.DataSource(dcm_file, {'dcm2niix2bids': Plugin({})}, 'DICOM')

    @pytest.fixture()
    def extdatasource(self, dcm_file, tmp_path):
        ext_dcm_file = shutil.copyfile(dcm_file, tmp_path/dcm_file.name)
        with ext_dcm_file.with_suffix('.json').open('w') as sidecar:
            json.dump({'PatientName': 'ExtendedAttributesTest'}, sidecar)
        return bids.DataSource(ext_dcm_file, {'dcm2niix2bids': Plugin({})}, 'DICOM')

    def test_is_datasource(self, datasource):
        assert datasource.is_datasource()
        assert datasource.dataformat == 'DICOM'

    def test_properties(self, datasource):
        assert datasource.properties( 'filepath:.*/(.*?)_files/.*') == 'test'   # path = [..]/pydicom/data/test_files/MR_small.dcm'
        assert datasource.properties(r'filename:MR_(.*?)\.dcm')     == 'small'
        assert datasource.properties( 'filesize')                   == '9.60 kB'
        assert datasource.properties( 'nrfiles')                    in (75,76)  # Depends on the pydicom version

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
        subses_source = bids.DataSource(subses_file, {'dcm2niix2bids': Plugin({})}, 'DICOM', subprefix=subprefix, sesprefix=sesprefix)
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
    sessions, unpacked = bids.unpack(dicomdir.parent, '', tmp_path, None)   # None -> simulate commandline usage of dicomsort()
    assert unpacked
    assert len(sessions) == 6
    for session in sessions:
        assert 'Doe^Archibald' in session.parts or 'Doe^Peter' in session.parts


def test_is_dicomfile(dcm_file):
    assert bids.is_dicomfile(dcm_file)


def test_is_parfile(par_file):
    assert bids.is_parfile(par_file)


def test_get_dicomfile(dcm_file, dicomdir):
    assert bids.get_dicomfile(dcm_file.parent).name == '693_J2KI.dcm'
    assert bids.get_dicomfile(dicomdir.parent).name == '6154'


def test_get_datasource(dicomdir):
    datasource = bids.get_datasource(dicomdir.parent, {'dcm2niix2bids': Plugin({})})
    assert datasource.is_datasource()
    assert datasource.dataformat == 'DICOM'


def test_get_dicomfield(dcm_file_csa):

    # -> Standard DICOM
    value = bids.get_dicomfield('SeriesDescription', dcm_file_csa)
    assert value == 'CBU_DTI_64D_1A'

    # -> The special PhaseEncodingDirection tag
    value = bids.get_dicomfield('PhaseEncodingDirection', dcm_file_csa)
    assert value == 'AP'

    # -> CSA Series header
    value = bids.get_dicomfield('PhaseGradientAmplitude', dcm_file_csa)
    assert value == '0.0'

    # -> CSA Image header
    value = bids.get_dicomfield('ImaCoilString', dcm_file_csa)
    assert value == 'T:HEA;HEP'

    value = bids.get_dicomfield('B_matrix', dcm_file_csa)
    assert value == ''

    value = bids.get_dicomfield('NonExistingTag', dcm_file_csa)
    assert value == ''

    # -> CSA MrPhoenixProtocol
    if find_spec('dicom_parser'):
        value = bids.get_dicomfield('MrPhoenixProtocol.tProtocolName', dcm_file_csa)
        assert value == 'CBU+AF8-DTI+AF8-64D+AF8-1A'

        value = bids.get_dicomfield('MrPhoenixProtocol.sDiffusion', dcm_file_csa)
        assert value == "{'lDiffWeightings': 2, 'alBValue': [None, 1000], 'lNoiseLevel': 40, 'lDiffDirections': 64, 'ulMode': 256}"

        value = bids.get_dicomfield('MrPhoenixProtocol.sProtConsistencyInfo.tBaselineString', dcm_file_csa)
        assert value == 'N4_VB17A_LATEST_20090307'


@pytest.mark.parametrize('template', bcoin.list_plugins()[1])
def test_load_check_template(template: Path):

    # Load a valid template
    bidsmap, _ = bids.load_bidsmap(template, checks=(False, False, False))
    for dataformat in bidsmap:
        if dataformat not in ('$schema', 'Options'): break
    assert isinstance(bidsmap, dict) and bidsmap
    assert bids.check_template(bidsmap) is True

    # Add an invalid data type
    bidsmap[dataformat]['foo'] = bidsmap[dataformat]['extra_data']
    assert bids.check_template(bidsmap) is False
    del bidsmap[dataformat]['foo']

    # Remove a valid suffix (BIDS-entity)
    bidsmap[dataformat]['anat'].pop(-2)        # NB: Assumes CT is the last item, MTR the second last
    assert bids.check_template(bidsmap) is False


def test_match_runvalue():
    assert bids.match_runvalue('my_pulse_sequence_name', '_name')      is False
    assert bids.match_runvalue('my_pulse_sequence_name', '^my.*name$') is True
    assert bids.match_runvalue('T1_MPRage', '(?i).*(MPRAGE|T1w).*')    is True
    assert bids.match_runvalue(None, None)                             is True
    assert bids.match_runvalue(None, '')                               is True
    assert bids.match_runvalue('',   None)                             is True
    assert bids.match_runvalue('',   '')                               is True
    assert bids.match_runvalue(  [1, 2, 3],     [1,2,  3])             is True
    assert bids.match_runvalue(  [1,2,  3],    '[1, 2, 3]')            is True
    assert bids.match_runvalue(  [1, 2, 3],  r'\[1, 2, 3\]')           is True
    assert bids.match_runvalue( '[1, 2, 3]',   '[1, 2, 3]')            is True
    assert bids.match_runvalue( '[1, 2, 3]', r'\[1, 2, 3\]')           is True
    assert bids.match_runvalue( '[1, 2, 3]',    [1, 2, 3])             is True
    assert bids.match_runvalue( '[1,2,  3]',    [1,2,  3])             is False
    assert bids.match_runvalue(r'\[1, 2, 3\]',  [1, 2, 3])             is False


def test_load_bidsmap(study_bidsmap):

    # Test loading with standard arguments for load_bidsmap
    bidsmap, filepath = bids.load_bidsmap(Path(study_bidsmap.name), study_bidsmap.parent)
    assert type(bidsmap) == ruamel.yaml.comments.CommentedMap
    assert bidsmap != {}
    assert filepath == study_bidsmap
    assert bidsmap['DICOM']['anat'][0]['provenance'] == '/Users/galassiae/Projects/bidscoin/bidscointutorial/raw/sub-001/ses-01/007-t1_mprage_sag_ipat2_1p0iso/00001_1.3.12.2.1107.5.2.43.66068.2020042808523182387402502.IMA'

    # Test loading with fullpath argument
    bidsmap, _ = bids.load_bidsmap(study_bidsmap)
    assert type(bidsmap) == ruamel.yaml.comments.CommentedMap
    assert bidsmap != {}
    assert bidsmap['DICOM']['anat'][0]['provenance'] == '/Users/galassiae/Projects/bidscoin/bidscointutorial/raw/sub-001/ses-01/007-t1_mprage_sag_ipat2_1p0iso/00001_1.3.12.2.1107.5.2.43.66068.2020042808523182387402502.IMA'

    # Test loading with standard argument for the template bidsmap
    bidsmap, _ = bids.load_bidsmap(Path('bidsmap_dccn'))
    assert type(bidsmap) == ruamel.yaml.comments.CommentedMap
    assert bidsmap != {}
    assert bidsmap['DICOM']['anat'][0]['provenance'] == str(Path('sub--unknown/ses--unknown/DICOM_anat_id001'))     # Account for Windows paths

    # Test loading with a dummy argument
    bidsmap, filepath = bids.load_bidsmap(Path('dummy'))
    assert bidsmap  == {}
    assert filepath == bids.templatefolder/'dummy.yaml'


def test_validate_bidsmap(study_bidsmap):

    # Load a BIDS-valid study bidsmap
    bidsmap, _ = bids.load_bidsmap(study_bidsmap)
    run        = bidsmap['DICOM']['func'][0]
    assert bids.validate_bidsmap(bidsmap) is True

    # Validate the bids-keys
    run['bids']['flip'] = 'foo'     # Add a false key
    assert bids.validate_bidsmap(bidsmap) is False
    del run['bids']['flip']
    del run['bids']['task']         # Remove a required key
    assert bids.validate_bidsmap(bidsmap) is False
    run['bids']['task'] = 'foo'

    # Check bids-suffix
    run['bids']['suffix'] = 'T1w'   # Set an invalid suffix
    assert bids.validate_bidsmap(bidsmap) is False
    run['bids']['suffix'] = 'bold'

    # Check bids-values
    run['bids']['task'] = ''        # Remove a required value
    assert bids.validate_bidsmap(bidsmap) is False
    run['bids']['task'] = 'f##'     # Add invalid characters (they are cleaned out)
    assert bids.validate_bidsmap(bidsmap) is True
    run['bids']['task'] = 'foo'
    run['bids']['run']  = 'a'       # Add an invalid (non-numeric) index
    assert bids.validate_bidsmap(bidsmap) is False


def test_check_bidsmap(study_bidsmap):

    # Load a template and a study bidsmap
    templatebidsmap, _ = bids.load_bidsmap(bidsmap_template, checks=(True, True, False))
    studybidsmap, _    = bids.load_bidsmap(study_bidsmap)

    # Test the output of the template bidsmap
    checks   = (True, True, False)
    is_valid = bids.check_bidsmap(templatebidsmap, checks)
    for each, check in zip(is_valid, checks):
        assert each in (None, True, False)
        if check:
            assert each in (None, True)

    # Test the output of the study bidsmap
    is_valid = bids.check_bidsmap(studybidsmap, checks)
    for each, check in zip(is_valid, checks):
        assert each in (None, True, False)
        if check:
            assert each is True


def test_check_run(study_bidsmap):

    # Load a bidsmap
    bidsmap, _ = bids.load_bidsmap(study_bidsmap)

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

    assert bids.check_ignore('mrs',                bidsignore)         is True      # Test default: datatype = 'dir'
    assert bids.check_ignore('mrs',                bidsignore, 'file') is False
    assert bids.check_ignore('mrs/sub-01_foo.nii', bidsignore, 'dir')  is False
    assert bids.check_ignore('mrs/sub-01_bar.nii', bidsignore, 'file') is False
    assert bids.check_ignore('foo/sub-01_bar.nii', bidsignore, 'file') is True
    assert bids.check_ignore('bar/sub-01_bar.nii', bidsignore, 'file') is False
    assert bids.check_ignore('bar/sub-01_foo.nii', bidsignore, 'file') is False
    assert bids.check_ignore('sub-01_foo.nii',     bidsignore, 'file') is True


def test_sanitize():

    assert bids.sanitize('<<>>')              == ''
    assert bids.sanitize('<<1>>')             == '1'
    assert bids.sanitize('@foo-bar.baz#')     == 'foobarbaz'
    assert bids.sanitize("Joe's reward_task") == 'Joesrewardtask'


def test_find_run(study_bidsmap):

    # Load a bidsmap and create a duplicate dataformat section
    bidsmap, _     = bids.load_bidsmap(study_bidsmap)
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


def test_delete_run(study_bidsmap):

    # Load a study bidsmap and delete one anat run
    bidsmap, _ = bids.load_bidsmap(study_bidsmap)
    nritems    = len(bidsmap['DICOM']['anat'])
    provenance = bidsmap['DICOM']['anat'][0]['provenance']
    bids.delete_run(bidsmap, provenance)

    assert len(bidsmap['DICOM']['anat']) == nritems - 1
    assert bids.find_run(bidsmap, provenance) == {}


def test_append_run(study_bidsmap):

    # Load a study bidsmap and delete one anat run
    bidsmap, _ = bids.load_bidsmap(study_bidsmap)

    # Collect and modify the first anat run-item
    datasource                   = bidsmap['DICOM']['anat'][0]['datasource']
    run                          = bids.create_run(datasource, bidsmap)
    run['datasource'].dataformat = 'Foo'
    run['datasource'].datatype   = 'Bar'
    run['bids']['part']          = ['', 'mag', 'phase', 'real', 'imag', 3]

    # Append the run elsewhere in the bidsmap
    bids.append_run(bidsmap, run)
    assert Path(bidsmap['Foo']['Bar'][0]['provenance'])     == Path(run['provenance'])
    assert Path(bidsmap['DICOM']['anat'][0]['provenance'])  == Path(run['provenance'])
    assert bidsmap['Foo']['Bar'][0]['bids']['part']         == ['', 'mag', 'phase', 'real', 'imag', 3]
    assert bidsmap['DICOM']['anat'][0]['bids']['part']      == ['', 'mag', 'phase', 'real', 'imag', 0]


def test_update_bidsmap(study_bidsmap):

    # Load a study bidsmap and move the first run-item from func to anat
    bidsmap, _ = bids.load_bidsmap(study_bidsmap)

    # Collect and modify the first func run-item
    run                        = copy.deepcopy(bidsmap['DICOM']['func'][0])
    run['datasource'].datatype = 'anat'

    # Update the bidsmap
    bids.update_bidsmap(bidsmap, 'func', run)
    assert Path(bidsmap['DICOM']['anat'][-1]['provenance']) == Path(run['provenance'])
    assert Path(bidsmap['DICOM']['func'] [0]['provenance']) != Path(run['provenance'])

    # Modify the last anat run-item and update the bidsmap
    run['bids']['foo'] = 'bar'
    bids.update_bidsmap(bidsmap, 'anat', run)
    assert bidsmap['DICOM']['anat'][-1]['bids']['foo'] == 'bar'


def test_exist_run(study_bidsmap):

    # Load a bidsmap
    bidsmap, _ = bids.load_bidsmap(study_bidsmap)

    # Collect the first anat run-item
    run = copy.deepcopy(bidsmap['DICOM']['anat'][0])

    # Find the run in the wrong data type
    assert bids.exist_run(bidsmap, 'func', run) is False

    # Find run with in the right data type and in all datatypes
    assert bids.exist_run(bidsmap, 'anat', run) is True
    assert bids.exist_run(bidsmap, '',     run) is True

    # Find the wrong run in all datatypes
    run['attributes']['ProtocolName'] = 'abcdefg'
    assert bids.exist_run(bidsmap, '', run)     is False
    run['attributes']['ProtocolName'] = ''
    assert bids.exist_run(bidsmap, '', run)     is False


def test_insert_bidskeyval():

    bidsname = bids.insert_bidskeyval(Path('bids')/'sub-01'/'anat'/'sub-01_T1w', 'run', '1', True)
    assert bidsname == Path('bids')/'sub-01'/'anat'/'sub-01_run-1_T1w'

    bidsname = bids.insert_bidskeyval(Path('bids')/'sub-01'/'anat'/'sub-01_run-2_T1w.nii', 'run', '', True)
    assert bidsname == Path('bids')/'sub-01'/'anat'/'sub-01_T1w.nii'

    bidsname = bids.insert_bidskeyval('sub-01_foo-bar_T1w', 'foo', 'baz', True)
    assert bidsname == 'sub-01_T1w'

    bidsname = bids.insert_bidskeyval('anat/sub-01_foo-bar_T1w.nii', 'foo', 'baz', False)
    assert bidsname == str(Path('anat/sub-01_foo-baz_T1w.nii'))


def test_increment_runindex(tmp_path):
    """Test if run-index is preserved or added to the bidsname, files are renamed and scans-table updated"""

    # Define the test data
    outfolder = tmp_path/'bids'/'sub-01'/'anat'
    outfolder.mkdir(parents=True)
    runless   = 'sub-01_T1w'
    run1      = 'sub-01_run-1_T1w'
    run2      = 'sub-01_run-2_T1w'
    run3      = 'sub-01_run-3_T1w'

    # ------- Tests with no existing data -------

    bidsname = bids.increment_runindex(outfolder, runless, Run({'bids': {'run': '<<>>'}}))
    assert bidsname == runless

    bidsname = bids.increment_runindex(outfolder, run1 + '.nii', Run({'bids': {'run': '<<1>>'}}))
    assert bidsname == run1 + '.nii'

    bidsname = bids.increment_runindex(outfolder, run2 + '.nii.gz', Run({'bids': {'run': '<<2>>'}}))
    assert bidsname == run2 + '.nii.gz'

    # ------- Tests with run-less data -------

    # Create the run-less files
    for suffix in ('.nii.gz', '.json'):
        (outfolder/runless).with_suffix(suffix).touch()

    # Test renaming of run-less to run-1 + updating scans_table
    bidsname = bids.increment_runindex(outfolder, runless, Run({'bids': {'run': '<<>>'}}))
    assert bidsname == run2
    for suffix in ('.nii.gz', '.json'):
        assert (outfolder/runless).with_suffix(suffix).is_file() is False
        assert (outfolder/run1   ).with_suffix(suffix).is_file() is True

    # We now have run-1 files only
    bidsname = bids.increment_runindex(outfolder, run1, Run({'bids': {'run': '<<1>>'}}))
    assert bidsname == run2

    # ------- Tests with run-1 & run-2 data -------

    # Create the run-2 files
    for suffix in ('.nii.gz', '.json'):
        (outfolder/run2).with_suffix(suffix).touch()

    bidsname = bids.increment_runindex(outfolder, runless + '.nii.gz', Run({'bids': {'run': '<<>>'}}))
    assert bidsname == run3 + '.nii.gz'

    bidsname = bids.increment_runindex(outfolder, run1, Run({'bids': {'run': '<<1>>'}}))
    assert bidsname == run3

    bidsname = bids.increment_runindex(outfolder, run1, Run({'bids': {'run': '<<AttrKey>>'}}))
    assert bidsname == run1                         # -> Must remain untouched

    bidsname = bids.increment_runindex(outfolder, run1, Run({'bids': {'run': '2'}}))
    assert bidsname == run1                         # -> Must remain untouched


def test_check_runindices(tmp_path):

    scans_file = tmp_path/f"sub-01_scans.tsv"
    acq_time   = datetime.now()

    assert bids.check_runindices(tmp_path) is True

    scans_data = {'filename': ['anat/sub-01_run-1_T1w.nii.gz', 'anat/sub-01_run-2_T1w.nii.gz', 'extra_data/sub-01_run-1_T1w.nii.gz'],
                  'acq_time': [acq_time.isoformat(), (acq_time + timedelta(minutes=5)).isoformat(), (acq_time - timedelta(minutes=5)).isoformat()]}
    pd.DataFrame(scans_data).to_csv(scans_file, sep='\t')
    assert bids.check_runindices(tmp_path) is True

    scans_data = {'filename': ['anat/sub-01_run-1_T1w.nii.gz', 'anat/sub-01_run-2_T1w.nii.gz', 'extra_data/sub-01_run-1_T1w.nii.gz'],
                  'acq_time': [acq_time.isoformat(), None, (acq_time - timedelta(minutes=5)).isoformat()]}
    pd.DataFrame(scans_data).to_csv(scans_file, sep='\t', na_rep='n/a')
    assert bids.check_runindices(tmp_path) is True

    scans_data = {'filename': ['anat/sub-01_T1w.nii.gz', 'anat/sub-01_run-2_T1w.nii.gz', 'extra_data/sub-01_run-1_T1w.nii.gz'],
                  'acq_time': [acq_time.isoformat(), (acq_time + timedelta(minutes=5)).isoformat(), (acq_time - timedelta(minutes=5)).isoformat()]}
    pd.DataFrame(scans_data).to_csv(scans_file, sep='\t')
    assert bids.check_runindices(tmp_path) is False

    scans_data = {'filename': ['anat/sub-01_run-1_T1w.nii.gz', 'anat/sub-01_run-2_T1w.nii.gz', 'anat/sub-01_run-3_T1w.nii.gz'],
                  'acq_time': [acq_time.isoformat(), (acq_time + timedelta(minutes=10)).isoformat(), (acq_time + timedelta(minutes=5)).isoformat()]}
    pd.DataFrame(scans_data).to_csv(scans_file, sep='\t')
    assert bids.check_runindices(tmp_path) is False


def test_get_bidsname(raw_dicomdir):

    dicomfile   = raw_dicomdir/'Doe^Archibald'/'01-XR C Spine Comp Min 4 Views'/'001-Cervical LAT'/'6154'
    run         = {'datasource': bids.DataSource(dicomfile, {'dcm2niix2bids': Plugin({})}, 'DICOM')}
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


def test_get_bidsvalue():

    bidsfile = Path('/bids/sub-01/anat/sub-01_acq-foo_run-1_T1w.nii.gz')

    assert bids.get_bidsvalue(bidsfile, 'acq')      == 'foo'
    assert bids.get_bidsvalue(bidsfile, 'fallback') == ''
    assert bids.get_bidsvalue(bidsfile, 'acq', 'bar')      == Path('/bids/sub-01/anat/sub-01_acq-bar_run-1_T1w.nii.gz')
    assert bids.get_bidsvalue(bidsfile, 'fallback', 'bar') == Path('/bids/sub-01/anat/sub-01_acq-foobar_run-1_T1w.nii.gz')
    assert bids.get_bidsvalue(bidsfile, '', 'bar')         == Path('/bids/sub-01/anat/sub-01_acq-foo_run-1_T1w.nii.gz')

    bidsfile = 'sub-01_run-1_T1w.nii.gz'

    assert bids.get_bidsvalue(bidsfile, 'run', '2') == 'sub-01_run-2_T1w.nii.gz'
    assert bids.get_bidsvalue(bidsfile, 'fallback', 'bar') == 'sub-01_acq-bar_run-1_T1w.nii.gz'


def test_updatemetadata(dcm_file, tmp_path):
    """Test if metadata is added to the dictionary and copied over"""

    # Create the extended datasource
    sourcefile = shutil.copyfile(dcm_file, tmp_path/dcm_file.name)
    sourcefile.with_suffix('.jsn').touch()
    with sourcefile.with_suffix('.json').open('w') as fid:
        json.dump({'PatientName': 'SourceTest'}, fid)
    extdatasource = bids.DataSource(sourcefile, {'dcm2niix2bids': Plugin({})}, 'DICOM')

    # Create the metadata sidecar file
    outfolder = tmp_path/'bids'/'sub-001'/'ses-01'/'anat'
    outfolder.mkdir(parents=True)
    sidecar = outfolder/'sub-001_ses-01_sidecar.json'
    with sidecar.open('w') as fid:
        json.dump({'PatientName': 'SidecarTest'}, fid)

    # Create the user metadata
    usermeta = {'PatientName':       'UserTest',
                'DynamicName':       '<<(0010, 0010)>>',
                'B0FieldSource':     'Source_<<session>>',
                'B0FieldIdentifier': 'Identifier_<<session>>'}

    # Test if the user metadata takes precedence
    metadata = bids.updatemetadata(extdatasource, sidecar, usermeta, ['.json'])
    assert metadata['PatientName']       == 'UserTest'
    assert metadata['DynamicName']       == 'CompressedSamples^MR1'
    assert metadata['B0FieldSource']     == 'Source_01'
    assert metadata['B0FieldIdentifier'] == 'Identifier_01'
    assert not (outfolder/sourcefile.with_suffix('.jsn').name).is_file()

    # Test if the source metadata takes precedence
    metadata = bids.updatemetadata(extdatasource, sidecar, {}, ['.jsn', '.json'], sourcefile)
    assert metadata['PatientName'] == 'SourceTest'
    assert (outfolder/sourcefile.with_suffix('.jsn').name).is_file()

    # Test if the sidecar metadata takes precedence
    metadata = bids.updatemetadata(extdatasource, sidecar, {}, [])
    assert metadata['PatientName'] == 'SidecarTest'
