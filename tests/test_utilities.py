import shutil
from pydicom.data import get_testdata_file
from pathlib import Path
try:
    from bidscoin import bidscoin
    from utilities import dicomsort
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))         # This should work if bidscoin was not pip-installed
    sys.path.append(str(Path(__file__).parents[1]/'utilities'))
    import bidscoin, dicomsort

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
