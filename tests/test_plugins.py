"""
Run the plugin test routines

@author: Marcel Zwiers
"""

import pytest
import inspect
import bidscoin.plugins as plugins
from importlib.util import find_spec
from pathlib import Path
from pydicom.data import get_testdata_file
from nibabel.testing import data_path
from bidscoin import bcoin, bids, bidsmap_template

bcoin.setup_logging()
template = bids.BidsMap(bidsmap_template, checks=(False, False, False))


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


# Test all plugins using the template & default options
@pytest.mark.parametrize('plugin', bcoin.list_plugins()[0])
@pytest.mark.parametrize('options', [template.plugins, {}])
def test_plugin(plugin, options):

    # First test to see if we can import the plugin
    module = bcoin.import_plugin(plugin)
    if not inspect.ismodule(module):
        raise ImportError(f"Invalid plugin: '{plugin}'")

    # Then run the plugin's own 'test' routine (if implemented)
    assert module.Interface().test(options.get(plugin.stem, {})) == 0

    # Test that we don't import invalid plugins
    module = bcoin.import_plugin(plugin, ('foo_plugin', 'bar_plugin'))
    if module is not None:
        raise ImportError(f"Unintended plugin import: '{plugin}'")


def test_unpack(dicomdir, tmp_path):
    sessions, unpacked = plugins.unpack(dicomdir.parent, '', tmp_path, None)   # None -> simulate commandline usage of dicomsort()
    assert unpacked
    assert len(sessions) == 6
    for session in sessions:
        assert 'Doe^Archibald' in session.parts or 'Doe^Peter' in session.parts


def test_is_dicomfile(dcm_file):
    assert plugins.is_dicomfile(dcm_file)


def test_is_parfile(par_file):
    assert plugins.is_parfile(par_file)


def test_get_dicomfile(dcm_file, dicomdir):
    assert plugins.get_dicomfile(dcm_file.parent).name == '693_J2KI.dcm'
    assert plugins.get_dicomfile(dicomdir.parent).name == '6154'


def test_get_dicomfield(dcm_file_csa):

    # -> Standard DICOM
    value = plugins.get_dicomfield('SeriesDescription', dcm_file_csa)
    assert value == 'CBU_DTI_64D_1A'

    # -> The pydicom-style tag number
    value = plugins.get_dicomfield('SeriesNumber', dcm_file_csa)
    assert value == 12
    assert value == plugins.get_dicomfield('0x00200011', dcm_file_csa)
    assert value == plugins.get_dicomfield('(0x20,0x11)', dcm_file_csa)
    assert value == plugins.get_dicomfield('(0020,0011)', dcm_file_csa)

    # -> The special PhaseEncodingDirection tag
    value = plugins.get_dicomfield('PhaseEncodingDirection', dcm_file_csa)
    assert value == 'AP'

    # -> CSA Series header
    value = plugins.get_dicomfield('PhaseGradientAmplitude', dcm_file_csa)
    assert value == '0.0'

    # -> CSA Image header
    value = plugins.get_dicomfield('ImaCoilString', dcm_file_csa)
    assert value == 'T:HEA;HEP'

    value = plugins.get_dicomfield('B_matrix', dcm_file_csa)
    assert value == ''

    value = plugins.get_dicomfield('NonExistingTag', dcm_file_csa)
    assert value == ''

    # -> CSA MrPhoenixProtocol
    if find_spec('dicom_parser'):
        value = plugins.get_dicomfield('MrPhoenixProtocol.tProtocolName', dcm_file_csa)
        assert value == 'CBU+AF8-DTI+AF8-64D+AF8-1A'

        value = plugins.get_dicomfield('MrPhoenixProtocol.sDiffusion', dcm_file_csa)
        assert value == "{'lDiffWeightings': 2, 'alBValue': [None, 1000], 'lNoiseLevel': 40, 'lDiffDirections': 64, 'ulMode': 256}"

        value = plugins.get_dicomfield('MrPhoenixProtocol.sProtConsistencyInfo.tBaselineString', dcm_file_csa)
        assert value == 'N4_VB17A_LATEST_20090307'
