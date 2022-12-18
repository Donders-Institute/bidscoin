import shutil
from pydicom.data import get_testdata_file
from pathlib import Path
try:
    from bidscoin import dicomsort
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'utilities'))         # This should work if bidscoin was not pip-installed
    import dicomsort


# sortsessions(sourcefolder: Path, subprefix: str='', sesprefix: str='', folderscheme: str='{SeriesNumber:03d}-{SeriesDescription}',
#                  namescheme: str='', pattern: str='.*\.(IMA|dcm)$', recursive: bool=True, force: bool=False, dryrun: bool=False) -> List[Path]:
def test_dicomsort(tmp_path):
    shutil.copytree(Path(get_testdata_file('DICOMDIR')).parent, tmp_path, dirs_exist_ok=True)
    dicomsort.sortsessions(tmp_path/'DICOMDIR')
    assert (tmp_path/'Doe^Peter').is_dir()           # Patient: 98890234: Doe^Peter
    assert (tmp_path/'Doe^Archibald').is_dir()       # Patient: 77654033: Doe^Archibald
    assert len(list((tmp_path/'Doe^Archibald').rglob('*'))) == 13
    assert len(list((tmp_path/'Doe^Peter').rglob('*')))     == 37
