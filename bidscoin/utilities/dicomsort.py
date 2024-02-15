#!/usr/bin/env python3
"""Sorts and/or renames DICOM files into local subfolders (See also cli/_dicomsort.py)"""

import re
import logging
import uuid
from pydicom import fileset
from pathlib import Path
from typing import List, Set
from importlib.util import find_spec
from typing import Union
if find_spec('bidscoin') is None:
    import sys
    sys.path.append(str(Path(__file__).parents[2]))
from bidscoin import bcoin, bids, lsdirs, trackusage

LOGGER = logging.getLogger(__name__)


def construct_name(scheme: str, dicomfile: Path, force: bool) -> str:
    """
    Check the renaming scheme for presence in the DICOM file and use an alternative if available. Then construct the new
    name by replacing the DICOM keys for their values, and applying the formatted string

    :param scheme:      The renaming scheme
    :param dicomfile:   The DICOM file that should be renamed
    :param force:       Construct the new name even in the presence of missing DICOM fields in the scheme
    :return:            The new name constructed from the scheme
    """

    # Alternative field names based on earlier DICOM versions or on other reasons
    alternatives = {'PatientName':'PatientsName', 'SeriesDescription':'ProtocolName', 'InstanceNumber':'ImageNumber', 'SeriesNumber':'SeriesInstanceUID',
                    'PatientsName':'PatientName', 'ProtocolName':'SeriesDescription', 'ImageNumber':'InstanceNumber'}

    schemevalues = {}
    for field in re.findall(r'(?<={)([a-zA-Z0-9]+)(?::\d+[d-gD-Gn])?(?=})', scheme):
        value = cleanup(bids.get_dicomfield(field, dicomfile))
        if not value and value != 0 and field in alternatives.keys():
            value = cleanup(bids.get_dicomfield(alternatives[field], dicomfile))
            if field == 'SeriesNumber':
                value = int(value.replace('.',''))      # Convert the SeriesInstanceUID to an int
        if not value and value != 0 and not force:
            LOGGER.error(f"Missing '{field}' DICOM field specified in the '{scheme}' folder/naming scheme, cannot find a safe name for: {dicomfile}\n")
            trackusage('dicomsort_error')
            return ''
        else:
            schemevalues[field] = value

    return scheme.format(**schemevalues) if schemevalues else ''


def validscheme(scheme: str) -> bool:
    """
    Parse the naming scheme string and test if all attributes are present

    :param scheme: The renaming scheme
    :return:
    """

    if not re.fullmatch(r'(({[a-zA-Z0-9]+(:\d+[d-gD-Gn])?})|([a-zA-Z0-9_.-]+))*', scheme):
        LOGGER.error(f"Bad naming scheme: {scheme}. Only alphanumeric characters could be used for the field names (with the optional number of digits afterwards,"
                      "e.g. '{InstanceNumber:05d}'), and only alphanumeric characters, dots, and dashes + underscores could be used as separators.")
        return False
    else:
        return True


def cleanup(name: str) -> str:
    """
    Removes illegal characters from file- or folder-name

    :param name: The file- or folder-name
    :return:     The cleaned file- or folder-name
    """

    special_characters = ('/', '\\', '*', '?', '"')        # These are the worst offenders, but there are many more
    for special in special_characters:
        if isinstance(name, str):
            name = name.strip().replace(special, '')

    return name


def sortsession(sessionfolder: Path, dicomfiles: List[Path], folderscheme: str, namescheme: str, force: bool, dryrun: bool) -> None:
    """
    Sorts dicomfiles into subfolders (e.g. a 3-digit SeriesNumber-SeriesDescription subfolder, such as '003-T1MPRAGE')

    :param sessionfolder:   The name of the destination folder of the dicom files
    :param dicomfiles:      The list of dicomfiles to be sorted and/or renamed
    :param folderscheme:    Optional naming scheme for the sorted (e.g. Series) subfolders. Follows the Python string formatting syntax with DICOM field names in curly bracers with an optional number of digits for numeric fields, e.g. {SeriesNumber:03d}-{SeriesDescription}
    :param namescheme:      Optional naming scheme for renaming the files. Follows the Python string formatting syntax with DICOM field names in curly bracers, e.g. {PatientName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d}.IMA
    :param force:           Sort the DICOM data even the DICOM fields of the folder/name scheme are not in the data
    :param dryrun:          Boolean to just display the action
    :return:                Nothing
    """

    LOGGER.info(f">> Sorting: {sessionfolder} ({len(dicomfiles)} files)")
    if not dryrun:
        sessionfolder.mkdir(parents=True, exist_ok=True)

    # Sort the dicomfiles in (e.g. DICOM Series) subfolders
    for dicomfile in dicomfiles:

        # Check if the DICOM file exists (e.g. in case of DICOMDIRs this may not be the case)
        if not dicomfile.is_file():
            LOGGER.warning(f"Could not find the expected '{dicomfile}' DICOM file")
            continue

        # Create a new subfolder if needed
        if not folderscheme:
            destination = sessionfolder
        else:
            subfolder = construct_name(folderscheme, dicomfile, force)
            if not subfolder:
                LOGGER.error('Cannot create subfolders, aborting dicomsort()...')
                trackusage('dicomsort_error')
                return
            destination = sessionfolder/subfolder
            if not destination.is_dir():
                LOGGER.verbose(f"   Creating:  {destination}")
                if not dryrun:
                    destination.mkdir(parents=True)

        # Move and/or rename the dicomfiles in(to) the destination (sub)folder
        if namescheme:
            newfilename = destination/construct_name(namescheme, dicomfile, force)
        else:
            newfilename = destination/dicomfile.name
        if newfilename == dicomfile:
            continue
        if newfilename.is_file():
            newfilename = newfilename.with_name(newfilename.stem + str(uuid.uuid4()) + newfilename.suffix)
            LOGGER.debug(f"File already exists, renaming: {dicomfile} -> {newfilename}")
        if not dryrun:
            dicomfile.replace(newfilename)


def sortsessions(sourcefolder: Path, subprefix: Union[str,None]='', sesprefix: str='', folderscheme: str='{SeriesNumber:03d}-{SeriesDescription}',
                 namescheme: str='', pattern: str=r'.*\.(IMA|dcm)$', recursive: bool=True, force: bool=False, dryrun: bool=False) -> Set[Path]:
    """
    Wrapper around sortsession() to loop over subjects and sessions and map the session DICOM files

    :param sourcefolder: The root folder containing the source [sub/][ses/]dicomfiles or the DICOMDIR file
    :param subprefix:    The prefix for searching the sub folders in session. Use '' to sort DICOMDIR files directly in sourcefolder (None will add DICOMDIR-based sub-/ses-folders
    :param sesprefix:    The prefix for searching the ses folders in sub folder
    :param folderscheme: Optional naming scheme for the sorted (e.g. Series) subfolders. Follows the Python string formatting syntax with DICOM field names in curly bracers with an optional number of digits for numeric fields', default='{SeriesNumber:03d}-{SeriesDescription}'
    :param namescheme:   Optional naming scheme for renaming the files. Follows the Python string formatting syntax with DICOM field names in curly bracers, e.g. {PatientName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d}.IMA
    :param pattern:      The regular expression pattern used in re.match() to select the dicom files
    :param recursive:    Boolean to search for DICOM files recursively in a session folder
    :param force:        Sort the DICOM data even the DICOM fields of the folder/name scheme are not in the data
    :param dryrun:       Boolean to just display the action
    :return:             List of sorted sessions
    """

    # Input checking
    sourcefolder = Path(sourcefolder)
    if sourcefolder.is_file():
        if sourcefolder.name == 'DICOMDIR':
            sourcefolder = sourcefolder.parent
        else:
            LOGGER.error(f"Unexpected dicomsource argument '{sourcefolder}', aborting dicomsort()...")
            return set()
    elif not sourcefolder.is_dir():
        LOGGER.error(f"Sourcefolder '{sourcefolder}' not found")
        return set()
    if (folderscheme and not validscheme(folderscheme)) or (namescheme and not validscheme(namescheme)):
        LOGGER.error('Wrong scheme input argument(s), aborting dicomsort()...')
        return set()

    # Do a recursive call if a sub- or ses-prefix is given
    sessions: Set[Path] = set()                 # Collect the sorted session-folders
    if subprefix or sesprefix:
        LOGGER.info(f"Searching for subject/session folders in: {sourcefolder}")
        for subjectfolder in lsdirs(sourcefolder, (subprefix or '') + '*'):
            for sessionfolder in lsdirs(subjectfolder, sesprefix + '*') if sesprefix else [subjectfolder]:
                sessions.update(sortsessions(sessionfolder, '', '', folderscheme, namescheme, pattern, recursive, force, dryrun))

    # Use the DICOMDIR file if it is there
    elif (sourcefolder/'DICOMDIR').is_file():
        LOGGER.info(f"Reading: {sourcefolder/'DICOMDIR'}")
        dicomdir = fileset.FileSet(sourcefolder/'DICOMDIR')
        for patientid in dicomdir.find_values('PatientID'):
            patient = dicomdir.find(PatientID=patientid)
            for n, studyuid in enumerate(dicomdir.find_values('StudyInstanceUID', instances=patient), 1):
                study      = dicomdir.find(PatientID=patientid, StudyInstanceUID=studyuid)
                dicomfiles = [Path(instance.path) for instance in study]
                if dicomfiles:
                    if subprefix == '':         # == '' -> Recursive call of sortsessions() -> Sort directly in the sourcefolder
                        sessionfolder = sourcefolder
                    else:                       # CLI call -> Sort in subject/session folder
                        sessionfolder = sourcefolder/f"{subprefix or ''}{cleanup(patient[0].PatientName)}"/f"{sesprefix or ''}{n:02}-{cleanup(study[0].StudyDescription)}"
                    sortsession(sessionfolder, dicomfiles, folderscheme, namescheme, force, dryrun)
                    sessions.add(sessionfolder)

    # Sort the DICOM files in the sourcefolder
    else:
        dicomfiles = [dcmfile for dcmfile in sourcefolder.glob('**/*' if recursive else '*') if dcmfile.is_file() and re.match(pattern, str(dcmfile))]
        if dicomfiles:
            sortsession(sourcefolder, dicomfiles, folderscheme, namescheme, force, dryrun)
            sessions.add(sourcefolder)

    return sessions


def main():
    """Console script entry point"""

    from bidscoin.cli._dicomsort import get_parser

    args = get_parser().parse_args()

    # Set-up logging
    bcoin.setup_logging()

    trackusage('dicomsort')
    try:
        sortsessions(sourcefolder = args.dicomsource,
                     subprefix    = args.subprefix,
                     sesprefix    = args.sesprefix,
                     folderscheme = args.folderscheme,
                     namescheme   = args.namescheme,
                     pattern      = args.pattern,
                     force        = args.force,
                     dryrun       = args.dryrun)

    except Exception:
        trackusage('dicomsort_exception')
        raise


if __name__ == "__main__":
    main()
