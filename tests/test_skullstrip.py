"""Focused tests for local SynthStrip command construction."""
from pathlib import Path
from unittest.mock import patch

from bidscoin.bidsapps import skullstrip


def test_skullstrip_literal_paths(tmp_path: Path):
    """Keep all three image paths intact under a non-shell-safe dataset root."""
    bidsdir = (tmp_path / "dataset with spaces;literal'quote").resolve()
    source = bidsdir/'sub-01'/'anat'/'sub-01_T1w.nii.gz'
    source.parent.mkdir(parents=True)
    source.touch()  # Synthetic placeholder; the command failure skips image I/O
    output = bidsdir/'derivatives'/'skullstrip'/'sub-01'/'anat'/'sub-01_space-orig_desc-brain_T1w.nii.gz'
    mask = output.with_name('sub-01_space-orig_desc-brain_mask.nii.gz')
    with patch.object(skullstrip.shutil, 'which', return_value='/synthetic/mri_synthstrip'), \
         patch.object(skullstrip.bcoin, 'setup_logging'), \
         patch.object(skullstrip, 'lsdirs', return_value=[]), \
         patch.object(skullstrip, 'track', side_effect=lambda items, **kwargs: items), \
         patch.object(skullstrip, 'run_command', return_value=1) as command:
        skullstrip.skullstrip(str(bidsdir), 'anat/*_T1w.nii.gz', ['01'], '', [], False, '--no-csf', '')
    command.assert_called_once()
    assert [str(arg) for arg in command.call_args.args[0]] == [
        'mri_synthstrip', '-i', str(source), '-o', str(output), '-m', str(mask), '--no-csf'
    ]
