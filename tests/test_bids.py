import pytest
import shutil
import re
from pathlib import Path
from pydicom.data import get_testdata_file
try:
    from bidscoin import bidscoin, bids
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))         # This should work if bidscoin was not pip-installed
    import bidscoin, bids

bidscoin.setup_logging()


@pytest.fixture(scope='module')
def dcm_file():
    return Path(get_testdata_file('MR_small.dcm'))


@pytest.fixture(scope='module')
def dicomdir():
    return Path(get_testdata_file('DICOMDIR'))


class TestDataSource:
    """Test the bids.DataSource class"""

    @pytest.fixture()
    def datasource(self, dcm_file):
        return bids.DataSource(dcm_file, {'dcm2niix2bids': {}}, 'DICOM')

    def test_is_datasource(self, datasource):
        assert datasource.is_datasource()
        assert datasource.dataformat == 'DICOM'

    def test_properties(self, datasource):
        assert datasource.properties('filepath:.*/(.*?)_files/.*') == 'test'    # path = [..]/pydicom/data/test_files/MR_small.dcm'
        assert datasource.properties('filename:MR_(.*?)\.dcm')     == 'small'
        assert datasource.properties('filesize')                   == '9.60 kB'
        assert datasource.properties('nrfiles')                    == 75

    def test_attributes(self, datasource):
        assert datasource.attributes('PatientName:.*\^(.*?)1') == 'MR'          # PatientName = 'CompressedSamples^MR1'

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
        assert subses_source.subid_sesid(f"<<PatientName:.*\^(.*?)1>>", '') == ('sub-MR', '')

    def test_dynamicvalue(self, datasource):
        assert datasource.dynamicvalue('PatientName:.*\^(.*?)1') == 'PatientName:.*\\^(.*?)1'
        assert datasource.dynamicvalue('<PatientName:.*\^(.*?)1>') == 'MR'
        assert datasource.dynamicvalue('<<PatientName:.*\^(.*?)1>>') == '<<PatientName:.*\\^(.*?)1>>'
        assert datasource.dynamicvalue('<<PatientName:.*\^(.*?)1>>', runtime=True) == 'MR'
        assert datasource.dynamicvalue('pat-<PatientName:.*\^(.*?)1>I<filename:MR_(.*?)\.dcm>') == 'patMRIsmall'


def test_unpack(dicomdir, tmp_path):
    unpacked = bids.unpack(dicomdir.parent, '', tmp_path)
    assert unpacked[1]
    assert len(unpacked[0]) == 6
    for ses in unpacked[0]:
        assert 'Doe^Archibald' in ses.parts or 'Doe^Peter' in ses.parts


def test_is_dicomfile(dcm_file):
    assert bids.is_dicomfile(dcm_file)


def test_get_dicomfile(dcm_file, dicomdir):
    assert bids.get_dicomfile(dcm_file.parent).name == '693_J2KI.dcm'
    assert bids.get_dicomfile(dicomdir.parent).name == '6154'


def test_get_datasource(dicomdir):
    datasource = bids.get_datasource(dicomdir.parent, {'dcm2niix2bids': {}})
    assert datasource.is_datasource()
    assert datasource.dataformat == 'DICOM'


@pytest.mark.parametrize('template', bidscoin.list_plugins()[1])
def test_load_check_template(template):
    bidsmap, _ = bids.load_bidsmap(template, check=(False,False,False))
    assert isinstance(bidsmap, dict) and bidsmap
    # assert bids.check_template(bidsmap)   # NB: Skip until the deprecated bids-entitities are removed from the BIDS schema


def test_match_runvalue():
    assert bids.match_runvalue('my_pulse_sequence_name', '_name')      == False
    assert bids.match_runvalue('my_pulse_sequence_name', '^my.*name$') == True
    assert bids.match_runvalue('T1_MPRage', '(?i).*(MPRAGE|T1w).*')    == True
    assert bids.match_runvalue('', None)                               == True
    assert bids.match_runvalue(None, '')                               == True
    assert bids.match_runvalue(  [1, 2, 3],    [1,2,  3])              == True
    assert bids.match_runvalue(  [1,2,  3],   '[1, 2, 3]')             == True
    assert bids.match_runvalue(  [1, 2, 3],  '\[1, 2, 3\]')            == True
    assert bids.match_runvalue( '[1, 2, 3]',  '[1, 2, 3]')             == True
    assert bids.match_runvalue( '[1, 2, 3]', '\[1, 2, 3\]')            == True
    assert bids.match_runvalue( '[1, 2, 3]',   [1, 2, 3])              == True
    assert bids.match_runvalue( '[1,2,  3]',   [1,2,  3])              == False
    assert bids.match_runvalue('\[1, 2, 3\]',  [1, 2, 3])              == False
