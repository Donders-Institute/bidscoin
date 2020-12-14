"""
Reads PHYSIO data and writes it to a BIDS compliant tsv-file
"""


import logging
from pathlib import Path
from readphysio import readphysio

LOGGER = logging.getLogger('bidscoin')


def physio2tsv(physiofile: Path, tsvfile: Path):
    """

    :param fnphysio: Fullpath input as in readphysio
    :return:         physio
    """

    # Read the physiological data
    physio = readphysio(physiofile)

    # Synchronize the clock with the clock of the associated run
    runfile = list(physiofile.parent.glob(physiofile.with_suffix('').name + '.nii*'))
    if len(runfile) > 1:
        LOGGER.error(f"fMultiple runfiles found:\n{runfile}")

    # Write a BIDS-compliant tsv-file
    with tsvfile.open('w'):
        pass
