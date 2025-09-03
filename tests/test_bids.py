import copy
import pandas as pd
import pytest
import shutil
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from pydicom.data import get_testdata_file
from bidscoin import bcoin, bids, bidsmap_template, bidscoinroot
from bidscoin.bids import BidsMap, RunItem, DataSource, Plugin, Meta


@pytest.fixture(scope='module')
def dcm_file():
    return Path(get_testdata_file('MR_small.dcm'))


@pytest.fixture(scope='module')
def dcm_xa60_file(test_data):
    return Path(test_data/'XA60'/'00001_1.3.12.2.1107.5.2.43.66068.30000024121907551118800028571.IMA')


@pytest.fixture(scope='module')
def dicomdir():
    return Path(get_testdata_file('DICOMDIR'))


@pytest.fixture(scope='module')
def dataset_bidsmap(test_data: Path):
    """The path to the dataset bidsmap `test_data/bidsmap.yaml`"""
    return test_data/'bidsmap.yaml'


class TestDataSource:
    """Test the bids.DataSource class"""

    @pytest.fixture()
    def datasource(self, dcm_file):
        return DataSource(dcm_file, {'dcm2niix2bids': Plugin({})}, 'DICOM')

    @pytest.fixture()
    def extdatasource(self, dcm_file, tmp_path):
        ext_dcm_file = shutil.copyfile(dcm_file, tmp_path/dcm_file.name)
        with ext_dcm_file.with_suffix('.json').open('w') as sidecar:
            json.dump({'PatientName': 'ExtendedAttributesTest'}, sidecar)
        return DataSource(ext_dcm_file, {'dcm2niix2bids': Plugin({})}, 'DICOM')

    def test_is_datasource(self, datasource):
        assert datasource.has_support()
        assert datasource.dataformat == 'DICOM'

    def test_properties(self, datasource):
        assert datasource.property('filepath:.*/(.*?)_files/.*') == 'test'   # path = [..]/pydicom/data/test_files/MR_small.dcm'
        assert datasource.property(r'filename:MR_(.*?)\.dcm') == 'small'
        assert datasource.property('filesize') == '9.60 kB'
        assert datasource.property('nrfiles') in (75, 76, 86)  # Depends on the pydicom version

    def test_attributes(self, datasource, extdatasource):
        assert datasource.attribute(r'PatientName:.*\^(.*?)1') == 'MR'         # PatientName = 'CompressedSamples^MR1'
        assert extdatasource.attribute('PatientName') == 'ExtendedAttributesTest'

    def test_age_derived(self, dcm_xa60_file):
        datasource = DataSource(dcm_xa60_file, {'dcm2niix2bids': Plugin({})}, 'DICOM')
        assert datasource.attribute('PatientAge') == '036Y'
        assert datasource.attribute('PatientAgeDerived') == '36.36139630390144'

    @pytest.mark.parametrize('subid',  ['sub-001', 'pat^visit'])
    @pytest.mark.parametrize('sesid',  ['ses-01',  'visit^01', ''])
    @pytest.mark.parametrize('subprefix', ['sub-', 'pat^', '*'])
    @pytest.mark.parametrize('sesprefix', ['ses-', 'visit^', '*'])
    def test_subid_sesid(self, subid, sesid, subprefix, sesprefix, tmp_path, dcm_file):
        subsesdir     = tmp_path/'data'/subid/sesid
        subsesdir.mkdir(parents=True)
        subses_file   = shutil.copy(dcm_file, subsesdir)
        options       = {'subprefix': subprefix, 'sesprefix': sesprefix}
        subses_source = DataSource(subses_file, {'dcm2niix2bids': Plugin({})}, 'DICOM', options)
        sub, ses      = subses_source.subid_sesid(f"<<filepath:/data/{subses_source.resubprefix}(.*?)/>>", f"<<filepath:/data/{subses_source.resubprefix}.*?/{subses_source.resesprefix}(.*?)/>>")
        expected_sub  = 'sub-' + bids.sanitize(re.sub(f"^{subses_source.resubprefix}", '', subid)  if subid.startswith(subprefix) or subprefix=='*' else '')  # NB: this expression is too complicated/resembles the actual code too much :-/
        expected_ses  = 'ses-' + bids.sanitize(re.sub(f"^{subses_source.resesprefix}", '', sesid)) if (subid.startswith(subprefix) or subprefix=='*') and (sesid.startswith(sesprefix) or sesprefix=='*') and sesid else ''
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
        assert datasource.dynamicvalue(r"<Patient's Name>")                                      == 'CompressedSamplesMR1'    # Patient's Name, 0x00100010, 0x10,0x10, (0x10,0x10), and (0010,0010) index keys are all equivalent
        assert datasource.dynamicvalue(r'<0x00100010>')                                          == 'CompressedSamplesMR1'
        assert datasource.dynamicvalue(r'<0x10,0x10>')                                           == 'CompressedSamplesMR1'
        assert datasource.dynamicvalue(r'<(0x10,0x10)>')                                         == 'CompressedSamplesMR1'
        assert datasource.dynamicvalue(r'<(0010,0010)>')                                         == 'CompressedSamplesMR1'


class TestRunItem:
    """Test the bids.RunItem class"""

    def test_check_run(self):

        # Create a valid func run-item (NB: this is dependent on the BIDS version)
        runitem = RunItem('DICOM', 'func', {'bids': {'task':'rest', 'acq':'', 'ce':'', 'dir':'', 'rec':'', 'run':'<<>>', 'echo':'1', 'part': ['','mag','phase','real','imag',0], 'chunk':'', 'suffix':'bold'}})
        checks  = (True, True, True)             # = (keys, suffixes, values)

        # Check various data types
        runitem.datatype = 'foo';  assert runitem.check(checks) == (None, None,  None)
        runitem.datatype = 'anat'; assert runitem.check(checks) == (None, False, None)
        runitem.datatype = 'func'; assert runitem.check(checks) == (True, True,  True)

        # Check bids-keys
        runitem.bids['flip'] = 'foo'    # Add a false key
        assert runitem.check(checks) == (False, True, None)
        del runitem.bids['flip']        # Remove the false key
        del runitem.bids['acq']         # Remove a valid key
        assert runitem.check(checks) == (False, True, True)
        runitem.bids['acq'] = 'foo'     # Restore the valid key

        # Check bids-suffix
        runitem.bids['suffix'] = 'T1w'  # Set an invalid suffix
        assert runitem.check(checks) == (None, False, None)
        runitem.bids['suffix'] = 'bold' # Restore the suffix

        # Check bids-values
        runitem.bids['task'] = ''       # Remove a required value
        assert runitem.check(checks) == (True, True, False)
        runitem.bids['task'] = 'f##'    # Add invalid characters
        assert runitem.check(checks) == (True, True, False)
        runitem.bids['task'] = 'rest'   # Restore the value
        runitem.bids['run']  = 'a'      # Add an invalid (non-numeric) index
        assert runitem.check(checks) == (True, True, False)

    def test_get_bidsname(self, raw_dicomdir):

        # Get a run-item from a bidsmap
        runitem            = RunItem('DICOM', '', {'bids': {'acq':'py#dicom', 'foo@':'bar#123', 'run':'<<SeriesNumber>>', 'suffix':'T0w'}}, plugins={'dcm2niix2bids': {}})
        runitem.provenance = str(raw_dicomdir/'Doe^Archibald'/'01-XR C Spine Comp Min 4 Views'/'001-Cervical LAT'/'6154')

        bidsname = runitem.bidsname('sub-001', 'ses-01', validkeys=False, cleanup=False)  # Test default: runtime=False
        assert bidsname == 'sub-001_ses-01_acq-py#dicom_run-<<SeriesNumber>>_foo@-bar#123_T0w'

        bidsname = runitem.bidsname('sub-001', 'ses-01', validkeys=False, runtime=False, cleanup=True)
        assert bidsname == 'sub-001_ses-01_acq-pydicom_run-SeriesNumber_foo@-bar123_T0w'

        bidsname = runitem.bidsname('sub-001', 'ses-01', validkeys=False, runtime=True,  cleanup=False)
        assert bidsname == 'sub-001_ses-01_acq-py#dicom_run-1_foo@-bar#123_T0w'

        bidsname = runitem.bidsname('sub-001', 'ses-01', validkeys=True,  runtime=True,  cleanup=False)
        assert bidsname == 'sub-001_ses-01_acq-py#dicom_run-1_T0w'

        runitem.bids['run'] = '<<1>>'
        bidsname = runitem.bidsname('sub-001', '', validkeys=True, runtime=True)          # Test default: cleanup=True
        assert bidsname == 'sub-001_acq-pydicom_run-1_T0w'

        runitem.bids['run'] = '<<>>'
        bidsname = runitem.bidsname('sub-001', '', validkeys=True, runtime=True)          # Test default: cleanup=True
        assert bidsname == 'sub-001_acq-pydicom_T0w'

    def test_increment_runindex(self, tmp_path):
        """Test if run-index is preserved or added to the bidsname, files are renamed and scans-table updated"""

        # Define the test data
        outfolder = tmp_path/'bids'/'sub-01'/'anat'
        outfolder.mkdir(parents=True)
        runless   = 'sub-01_T1w'
        run1      = 'sub-01_run-1_T1w'
        run2      = 'sub-01_run-2_T1w'
        run3      = 'sub-01_run-3_T1w'

        # ------- Tests with no existing output files -------

        runitem  = RunItem('', '', {'bids': {'run': '<<>>'}})
        bidsname = runitem.increment_runindex(outfolder, runless)
        assert bidsname == runless

        runitem  = RunItem('', '', {'bids': {'run': '<<1>>'}})
        bidsname = runitem.increment_runindex(outfolder, run1 + '.nii')
        assert bidsname == run1 + '.nii'

        runitem  = RunItem('', '', {'bids': {'run': '<<2>>'}})
        bidsname = runitem.increment_runindex(outfolder, run2 + '.nii.gz')
        assert bidsname == run2 + '.nii.gz'

        # ------- Tests with run-less output files -------

        # Create run-less output files
        for suffix in ('.nii.gz', '.json'):
            (outfolder/runless).with_suffix(suffix).touch()

        # Test renaming of run-less to run-1 + updating scans_table
        runitem  = RunItem('', '', {'bids': {'run': '<<>>'}})
        bidsname = runitem.increment_runindex(outfolder, runless)
        assert bidsname == run2
        for suffix in ('.nii.gz', '.json'):
            assert (outfolder/runless).with_suffix(suffix).is_file() is False
            assert (outfolder/run1   ).with_suffix(suffix).is_file() is True

        # We now have run-1 files only
        runitem  = RunItem('', '', {'bids': {'run': '<<1>>'}})
        bidsname = runitem.increment_runindex(outfolder, run1)
        assert bidsname == run2

        # ------- Tests with run-1 & run-2 output files -------

        # Create run-2 output files
        for suffix in ('.nii.gz', '.json'):
            (outfolder/run2).with_suffix(suffix).touch()

        runitem  = RunItem('', '', {'bids': {'run': '<<>>'}})
        bidsname = runitem.increment_runindex(outfolder, runless + '.nii.gz')
        assert bidsname == run3 + '.nii.gz'

        runitem  = RunItem('', '', {'bids': {'run': '<<1>>'}})
        bidsname = runitem.increment_runindex(outfolder, run1)
        assert bidsname == run3

        runitem  = RunItem('', '', {'bids': {'run': '<<AttrKey>>'}})
        bidsname = runitem.increment_runindex(outfolder, run1)
        assert bidsname == run1                         # -> Must remain untouched

        runitem  = RunItem('', '', {'bids': {'run': '2'}})
        bidsname = runitem.increment_runindex(outfolder, run1)
        assert bidsname == run1                         # -> Must remain untouched

    def test_strip_suffix(self):
        pass


class TestDataType:
    """Test the bids.DataType class"""

    def test_runitems(self):
        pass

    def test_isert_run(self):
        pass

    def test_replace_run(self):
        pass


class TestDataFormat:
    """Test the bids.DataFormat class"""

    def test_subject(self):
        pass

    def test_session(self):
        pass

    def test_datatypes(self):
        pass

    def test_datatype(self):
        pass

    def test_add_datatype(self):
        pass

    def test_delete_runs(self):
        pass


class TestBidsMap:
    """Test the bids.BidsMap class"""

    def test_init(self, dataset_bidsmap):

        # Test loading with standard arguments
        bidsmap = BidsMap(Path(dataset_bidsmap.name), dataset_bidsmap.parent)
        assert bidsmap.filepath == dataset_bidsmap
        assert bidsmap.dataformat('DICOM').datatype('anat').runitems[0].provenance == '/Users/galassiae/Projects/bidscoin/bidscointutorial/raw/sub-001/ses-01/007-t1_mprage_sag_ipat2_1p0iso/00001_1.3.12.2.1107.5.2.43.66068.2020042808523182387402502.IMA'
        assert bidsmap.dataformat('DICOM').datatype('func').runitems[0].bids['part'] == ['', 'mag', 'phase', 'real', 'imag', 0]
        assert bidsmap.dataformat('DICOM').datatype('func').runitems[1].bids['part'] == ['', 'mag', 'phase', 'real', 'imag', 3]
        assert bidsmap.dataformat('DICOM').datatype('func').runitems[2].bids['part'] == ['', 'mag', 'phase', 'real', 'imag', 0]

        # Test loading with fullpath argument
        bidsmap = BidsMap(dataset_bidsmap)
        assert bidsmap.dataformat('DICOM').datatype('anat').runitems[0].provenance == '/Users/galassiae/Projects/bidscoin/bidscointutorial/raw/sub-001/ses-01/007-t1_mprage_sag_ipat2_1p0iso/00001_1.3.12.2.1107.5.2.43.66068.2020042808523182387402502.IMA'

        # Test loading with standard argument for the template bidsmap
        bidsmap = BidsMap(Path('bidsmap_dccn'))
        assert bidsmap.dataformat('DICOM').datatype('anat').runitems[0].provenance == str(Path('sub-unknown/ses-unknown/DICOM_anat_id001'))     # Account for Windows paths

        # Test loading with a dummy argument
        bidsmap = BidsMap(Path('dummy'))
        assert len(bidsmap.dataformats) == 0
        assert bidsmap.filepath.name    == 'dummy.yaml'

    def test_check_templates(self):

        # Test the default template bidsmaps
        for template in (bidscoinroot/'heuristics').glob('*.yaml'):

            # Load a valid template
            print(f"Checking: {template}")
            bidsmap = BidsMap(template, checks=(False, False, False))
            assert bidsmap.check_template() is True

            # Add and remove an invalid data type
            bidsmap.dataformats[0].add_datatype('foo')
            assert bidsmap.check_template() is False
            bidsmap.dataformats[0].remove_datatype('foo')
            assert bidsmap.check_template() is True

            # # Remove a valid suffix (BIDS-entity)
            # valid_run = bidsmap.dataformats[0].datatype('anat').runitems[-2].provenance     # NB: [-2] -> The first item(s) can be non-unique, the last item can be a non-BIDS entity, i.e. CT
            # bidsmap.dataformats[0].datatype('anat').delete_run(valid_run)
            # assert bidsmap.check_template() is False

    def test_dataformat(self):
        pass

    def test_add_dataformat(self):
        pass

    def test_remove_dataformat(self):
        pass

    def test_validate(self, dataset_bidsmap):

        # Load a BIDS-valid dataset bidsmap
        bidsmap = BidsMap(dataset_bidsmap)
        assert bidsmap.validate() is True

        # Validate the bids-keys
        runitem = bidsmap.dataformat('DICOM').datatype('func').runitems[0]
        runitem.bids['flip'] = 'foo'     # Add a false key
        assert bidsmap.validate() is False
        del runitem.bids['flip']
        del runitem.bids['task']         # Remove a required key
        assert bidsmap.validate() is False
        runitem.bids['task'] = 'foo'

        # Check bids-suffix
        runitem.bids['suffix'] = 'T1w'   # Set an invalid suffix
        assert bidsmap.validate() is False
        runitem.bids['suffix'] = 'bold'

        # Check bids-values
        runitem.bids['task'] = ''        # Remove a required value
        assert bidsmap.validate() is False
        runitem.bids['task'] = 'f##'     # Add invalid characters (they are cleaned out)
        assert bidsmap.validate() is True
        runitem.bids['task'] = 'foo'
        runitem.bids['run']  = 'a'       # Add an invalid (non-numeric) index
        assert bidsmap.validate() is False


    def test_check(self, dataset_bidsmap):

        # Load a template and a dataset bidsmap
        templatebidsmap = BidsMap(bidsmap_template, checks=(True, True, False))
        datasetbidsmap  = BidsMap(dataset_bidsmap)

        # Test the output of the template bidsmap
        checks   = (True, True, False)              # Check keys and suffixes, but not the values (as that makes no sense for a template bidsmap)
        is_valid = templatebidsmap.check(checks)
        for valid, check in zip(is_valid, checks):
            assert valid in (None, True, False)
            if check:
                assert valid in (None, True)

        # Test the output of the dataset bidsmap
        checks   = (True, True, True)               # Check keys, suffixes and values (should all be checked for a dataset bidsmap)
        is_valid = datasetbidsmap.check(checks)
        for valid, check in zip(is_valid, checks):
            assert valid in (None, True, False)
            if check:
                assert valid is True

    def test_find_run(self, dataset_bidsmap):

        # Load a bidsmap and create a duplicate dataformat section named PET
        bidsmap = BidsMap(dataset_bidsmap)
        dformat = copy.deepcopy(bidsmap.dataformat('DICOM'))
        dformat.dataformat = 'PET'
        bidsmap.add_dataformat(dformat)

        # Collect provenance of the first anat run-item
        provenance = bidsmap.dataformat('DICOM').datatype('anat').runitems[0].provenance
        provtag    = '123456789'
        bidsmap.dataformat('PET').datatype('anat').runitems[0].provenance = provtag

        # Find run with the wrong dataformat
        run = bidsmap.find_run(provenance, dataformat='PET')
        assert run is None

        # Find run with the wrong data type
        run = bidsmap.find_run(provenance, datatype='func')
        assert run is None

        # Find run with partial provenance
        run = bidsmap.find_run('sub-001')
        assert run is None

        # Find run with full provenance
        run = bidsmap.find_run(provenance)
        assert isinstance(run, RunItem)
        run = bidsmap.find_run(provtag, dataformat='PET', datatype='anat')
        assert run.provenance == provtag


    def test_delete_run(self, dataset_bidsmap):

        # Load a dataset bidsmap and delete one anat run
        bidsmap    = BidsMap(dataset_bidsmap)
        nritems    = len(bidsmap.dataformat('DICOM').datatype('anat').runitems)
        provenance = bidsmap.dataformat('DICOM').datatype('anat').runitems[0].provenance
        bidsmap.delete_run(provenance)

        assert len(bidsmap.dataformat('DICOM').datatype('anat').runitems) == nritems - 1
        assert bidsmap.find_run(provenance) is None


    def test_insert_run(self, dataset_bidsmap):

        # Load a dataset bidsmap and delete one anat run
        bidsmap = BidsMap(dataset_bidsmap)

        # Get and modify the first anat run-item
        runitem              = copy.deepcopy(bidsmap.dataformat('DICOM').datatype('anat').runitems[0])
        runitem.dataformat   = 'Foo'
        runitem.datatype     = 'Bar'
        runitem.bids['part'] = ['', 'mag', 'phase', 'real', 'imag', 3]

        # Insert the run elsewhere in the bidsmap
        bidsmap.insert_run(runitem)
        assert Path(bidsmap.dataformat(  'Foo').datatype( 'Bar').runitems[0].provenance) == Path(runitem.provenance)
        assert Path(bidsmap.dataformat('DICOM').datatype('anat').runitems[0].provenance) == Path(runitem.provenance)
        assert bidsmap.dataformat(  'Foo').datatype( 'Bar').runitems[0].bids['part']     == ['', 'mag', 'phase', 'real', 'imag', 3]
        assert bidsmap.dataformat('DICOM').datatype('anat').runitems[0].bids['part']     == ['', 'mag', 'phase', 'real', 'imag', 0]

        # Insert another run at the end and at the front of the list
        runitem = copy.deepcopy(runitem)
        runitem.bids['part'] = ['', 'mag', 'phase', 'real', 'imag', 4]
        bidsmap.insert_run(runitem)
        bidsmap.insert_run(runitem, 0)
        assert bidsmap.dataformat('Foo').datatype('Bar').runitems[0].bids['part'] == ['', 'mag', 'phase', 'real', 'imag', 4]
        assert bidsmap.dataformat('Foo').datatype('Bar').runitems[1].bids['part'] == ['', 'mag', 'phase', 'real', 'imag', 3]
        assert bidsmap.dataformat('Foo').datatype('Bar').runitems[2].bids['part'] == ['', 'mag', 'phase', 'real', 'imag', 4]

    def test_update_bidsmap(self, dataset_bidsmap):

        # Load a dataset bidsmap and move the first run-item from func to anat
        bidsmap = BidsMap(dataset_bidsmap)

        # Collect and modify the first func run-item
        runitem          = copy.deepcopy(bidsmap.dataformat('DICOM').datatype('func').runitems[0])
        runitem.datatype = 'anat'

        # Update the bidsmap
        bidsmap.update('func', runitem)
        assert Path(bidsmap.dataformat('DICOM').datatype('anat').runitems[-1].provenance) == Path(runitem.provenance)
        assert Path(bidsmap.dataformat('DICOM').datatype('func').runitems[ 0].provenance) != Path(runitem.provenance)

        # Modify the last anat run-item and update the bidsmap
        runitem.bids['foo'] = 'bar'
        bidsmap.update('anat', runitem)
        assert bidsmap.dataformat('DICOM').datatype('anat').runitems[-1].bids['foo'] == 'bar'

    def test_exist_run(self, dataset_bidsmap):

        # Load a bidsmap
        bidsmap = BidsMap(dataset_bidsmap)

        # Collect the first anat run-item
        runitem = copy.deepcopy(bidsmap.dataformat('DICOM').datatype('anat').runitems[0])

        # Find the run in the wrong data type
        assert bidsmap.exist_run(runitem, 'func') is False

        # Find run with in the right data type and in all datatypes
        assert bidsmap.exist_run(runitem, 'anat') is True
        assert bidsmap.exist_run(runitem) is True

        # Find the wrong run in all datatypes
        runitem.attributes['ProtocolName'] = 'abcdefg'
        assert bidsmap.exist_run(runitem) is False
        runitem.attributes['ProtocolName'] = ''
        assert bidsmap.exist_run(runitem) is False


def test_get_datasource(dicomdir):
    datasource = bids.get_datasource(dicomdir.parent, {'dcm2niix2bids': {}})
    assert datasource.has_support()
    assert datasource.dataformat == 'DICOM'


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


def test_insert_bidskeyval():

    bidsname = bids.insert_bidskeyval(Path('bids')/'sub-01'/'anat'/'sub-01_T1w', 'run', '1', True)
    assert bidsname == Path('bids')/'sub-01'/'anat'/'sub-01_run-1_T1w'

    bidsname = bids.insert_bidskeyval(Path('bids')/'sub-01'/'anat'/'sub-01_run-2_T1w.nii', 'run', '', True)
    assert bidsname == Path('bids')/'sub-01'/'anat'/'sub-01_T1w.nii'

    bidsname = bids.insert_bidskeyval('sub-01_foo-bar_T1w', 'foo', 'baz', True)
    assert bidsname == 'sub-01_T1w'

    bidsname = bids.insert_bidskeyval('anat/sub-01_foo-bar_T1w.nii', 'foo', 'baz', False)
    assert bidsname == str(Path('anat/sub-01_foo-baz_T1w.nii'))


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
    extdatasource = DataSource(sourcefile, {'dcm2niix2bids': Plugin({})}, 'DICOM')

    # Create the metadata sidecar file
    outfolder = tmp_path/'bids'/'sub-001'/'ses-01'/'anat'
    outfolder.mkdir(parents=True)
    sidecar = outfolder/'sub-001_ses-01_sidecar.json'
    with sidecar.open('w') as fid:
        json.dump({'PatientName': 'SidecarTest'}, fid)

    # Create the user metadata
    usermeta = Meta({'PatientName':       'UserTest',
                     'DynamicName':       '<<(0010,0010)>>',
                     'B0FieldSource':     'Source<<session_id:[-2:2]>>',
                     'B0FieldIdentifier': ['Identifier<<session_id>>', 'Identifier'],
                     'foo':               ''})

    # Test if the user metadata takes precedence
    metadata = bids.poolmetadata(extdatasource, sidecar, usermeta, ['.json'])
    assert metadata['PatientName']       == 'UserTest'
    assert metadata['DynamicName']       == 'CompressedSamples^MR1'
    assert metadata['B0FieldSource']     == 'Source<<ses01:[-2:2]>>'
    assert metadata['B0FieldIdentifier'] == ['Identifier<<ses01>>', 'Identifier']
    assert 'foo' not in metadata
    assert not (outfolder/sourcefile.with_suffix('.jsn').name).is_file()

    # Test if the source metadata takes precedence
    metadata = bids.poolmetadata(extdatasource, sidecar, Meta({}), ['.jsn', '.json'], sourcefile)
    assert metadata['PatientName'] == 'SourceTest'
    assert (outfolder/sourcefile.with_suffix('.jsn').name).is_file()

    # Test if the sidecar metadata takes precedence
    metadata = bids.poolmetadata(extdatasource, sidecar, Meta({}), [])
    assert metadata['PatientName'] == 'SidecarTest'
