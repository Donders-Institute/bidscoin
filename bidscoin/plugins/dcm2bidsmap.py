"""
Contains the bidsmapper plugin to scan the session DICOM and PAR/REC source-files to build a study bidsmap
"""

import logging
import shutil
from pathlib import Path
try:
    from bidscoin import bidscoin, bids
except ImportError:
    import bidscoin, bids         # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger(__name__)


def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
    """
    All the logic to map the Philips PAR/XML fields onto bids labels go into this function

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The study bidsmap that we are building
    :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
    :param template:    The template bidsmap with the default heuristics
    :param store:       The paths of the source- and target-folder
    :return:
    """

    # Loop of the different DICOM runs (series) and collect source files
    sourcefiles = []
    dataformat  = bids.get_dataformat(session)
    if not dataformat:
        return

    if dataformat == 'DICOM':
        for sourcedir in bidscoin.lsdirs(session):
            sourcefile = bids.get_dicomfile(sourcedir)
            if sourcefile.name:
                sourcefiles.append(sourcefile)

    if dataformat == 'PAR':
        sourcefiles = bids.get_parfiles(session)

    # Update the bidsmap with the info from the source files
    for sourcefile in sourcefiles:

        # Input checks
        if not sourcefile.name or (not template[dataformat] and not bidsmap_old[dataformat]):
            LOGGER.info(f"No {dataformat} source information found in the bidsmap and template")
            return

        # See if we can find a matching run in the old bidsmap
        run, datatype, index = bids.get_matching_run(sourcefile, bidsmap_old, dataformat)

        # If not, see if we can find a matching run in the template
        if index is None:
            run, datatype, _ = bids.get_matching_run(sourcefile, template, dataformat)

        # See if we have collected the run somewhere in our new bidsmap
        if not bids.exist_run(bidsmap_new, dataformat, '', run):

            # Communicate with the user if the run was not present in bidsmap_old or in template, i.e. that we found a new sample
            LOGGER.info(f"Found '{datatype}' {dataformat} sample: {sourcefile}")

            # Now work from the provenance store
            if store:
                targetfile        = store['target']/sourcefile.relative_to(store['source'])
                targetfile.parent.mkdir(parents=True, exist_ok=True)
                run['provenance'] = str(shutil.copy2(sourcefile, targetfile))

            # Copy the filled-in run over to the new bidsmap
            bids.append_run(bidsmap_new, dataformat, datatype, run)
