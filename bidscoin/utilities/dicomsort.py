#!/usr/bin/env python3
"""
Sorts and / or renames DICOM files into local subfolders, e.g. with 3-digit SeriesNumber-SeriesDescription
folder names (i.e. following the same listing as on the scanner console)
"""

import re
import logging
import pydicom
import uuid
from pathlib import Path
from typing import List
try:
    from bidscoin import bidscoin, bids
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]))             # This should work if bidscoin was not pip-installed
    import bidscoin, bids

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
    alternatives = {'PatientName':'PatientsName', 'SeriesDescription':'ProtocolName', 'InstanceNumber':'ImageNumber',
                    'PatientsName':'PatientName', 'ProtocolName':'SeriesDescription', 'ImageNumber':'InstanceNumber'}

    schemevalues = {}
    for field in re.findall('(?<={)([a-zA-Z]+)(?::\\d+d)?(?=})', scheme):
        value = cleanup(bids.get_dicomfield(field, dicomfile))
        if not value and value != 0 and field in alternatives.keys():
            value = cleanup(bids.get_dicomfield(alternatives[field], dicomfile))
        if not value and value != 0 and not force:
            LOGGER.error(f"Missing '{field}' DICOM field specified in the '{scheme}' folder/naming scheme, cannot find a safe name for: {dicomfile}\n")
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

    if not re.fullmatch('(({[a-zA-Z]+(:\\d+d)?})|([a-zA-Z0-9\-_.]+))*', scheme):
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
    subfolders = []
    for dicomfile in dicomfiles:

        # Check if the DICOM file exists (e.g. in case of DICOMDIRs this may not be the case)
        if not dicomfile.is_file():
            LOGGER.warning(f"Could not find the expected '{dicomfile}' DICOM file")
            continue

        # Create a new subfolder if needed
        if not folderscheme:
            pathname = sessionfolder
        else:
            subfolder = construct_name(folderscheme, dicomfile, force)
            if not subfolder:
                LOGGER.error('Cannot create subfolders, aborting dicomsort()...')
                return
            if subfolder not in subfolders:
                subfolders.append(subfolder)
            pathname = sessionfolder/subfolder
            if not pathname.is_dir():
                LOGGER.info(f"   Creating:  {pathname}")
                if not dryrun:
                    pathname.mkdir(parents=True)

        # Move and/or rename the dicomfiles in(to) the (sub)folder
        if namescheme:
            newfilename = pathname/construct_name(namescheme, dicomfile, force)
        else:
            newfilename = pathname/dicomfile.name
        if newfilename == dicomfile:
            continue
        if newfilename.is_file():
            LOGGER.warning(f"File already exists: {dicomfile} -> {newfilename}")
            newfilename = newfilename.with_name(newfilename.stem + str(uuid.uuid4()) + newfilename.suffix)
            LOGGER.info(f"Using new file-name: {dicomfile} -> {newfilename}")
        if not dryrun:
            dicomfile.replace(newfilename)


def sortsessions(sourcefolder: Path, subprefix: str='', sesprefix: str='', folderscheme: str='{SeriesNumber:03d}-{SeriesDescription}',
                 namescheme: str='', pattern: str='.*\.(IMA|dcm)$', recursive: bool=True, force: bool=False, dryrun: bool=False) -> List[Path]:
    """
    Wrapper around sortsession() to loop over subjects and sessions and map the session DICOM files

    :param sourcefolder: The root folder containing the source [sub/][ses/]dicomfiles or the DICOMDIR file
    :param subprefix:    The prefix for searching the sub folders in session
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
            return []
    if (folderscheme and not validscheme(folderscheme)) or (namescheme and not validscheme(namescheme)):
        LOGGER.error('Wrong scheme input argument(s), aborting dicomsort()...')
        return []
    if not subprefix: subprefix = ''
    if not sesprefix: sesprefix = ''

    # Use the DICOMDIR file if it is there
    sessions = []       # Collect the sorted session-folders
    if (sourcefolder/'DICOMDIR').is_file():
        LOGGER.info(f"Reading: {sourcefolder/'DICOMDIR'}")
        dicomdir = pydicom.dcmread(str(sourcefolder/'DICOMDIR'))
        for patient in dicomdir.patient_records:
            for n, study in enumerate(patient.children, 1):
                dicomfiles = [sourcefolder.joinpath(*image.ReferencedFileID) for series in study.children for image in series.children]
                if dicomfiles:
                    sessionfolder = sourcefolder/f"{subprefix}{cleanup(patient.PatientName)}"/f"{sesprefix}{n:02}-{cleanup(study.StudyDescription)}"
                    sortsession(sessionfolder, dicomfiles, folderscheme, namescheme, force, dryrun)
                    sessions.append(sessionfolder)

    # Do a recursive call if a sub- or ses-prefix is given
    elif subprefix or sesprefix:
        LOGGER.info(f"Searching for subject/session folders in: {sourcefolder}")
        for subjectfolder in bidscoin.lsdirs(sourcefolder, subprefix + '*'):
            if sesprefix:
                sessionfolders = bidscoin.lsdirs(subjectfolder, sesprefix + '*')
            else:
                sessionfolders = [subjectfolder]
            for sessionfolder in sessionfolders:
                sessions += sortsessions(sessionfolder, folderscheme=folderscheme, namescheme=namescheme, pattern=pattern, recursive=recursive, dryrun=dryrun)

    # Sort the DICOM files in the sourcefolder
    else:
        sessions = [sourcefolder]
        if recursive:
            dicomfiles = [dcmfile for dcmfile in sourcefolder.rglob('*') if dcmfile.is_file() and re.match(pattern, str(dcmfile))]
        else:
            dicomfiles = [dcmfile for dcmfile in sourcefolder.iterdir()  if dcmfile.is_file() and re.match(pattern, str(dcmfile))]
        if dicomfiles:
            sortsession(sourcefolder, dicomfiles, folderscheme, namescheme, force, dryrun)

    return sorted(set(sessions))


def main():
    """Console script usage"""

    # Parse the input arguments and run the sortsessions(args)
    import argparse
    import textwrap

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass

    parser = argparse.ArgumentParser(formatter_class=CustomFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  dicomsort sub-011/ses-mri01\n'
                                            '  dicomsort sub-011/ses-mri01/DICOMDIR -n {AcquisitionNumber:05d}_{InstanceNumber:05d}.dcm\n'
                                            '  dicomsort myproject/raw/DICOMDIR --subprefix sub- --sesprefix ses-\n ')
    parser.add_argument('dicomsource',          help='The root folder containing the dicomsource/[sub/][ses/] dicomfiles or the DICOMDIR file')
    parser.add_argument('-i','--subprefix',     help='Provide a prefix string for recursive sorting of dicomsource/subject subfolders (e.g. "sub-")')
    parser.add_argument('-j','--sesprefix',     help='Provide a prefix string for recursive sorting of dicomsource/subject/session subfolders (e.g. "ses-")')
    parser.add_argument('-f','--folderscheme',  help='Naming scheme for the sorted DICOM Series subfolders. Follows the Python string formatting syntax with DICOM field names in curly bracers with an optional number of digits for numeric fields. Sorting in subfolders is skipped when an empty folderscheme is given (but note that renaming the filenames can still be performed)', default='{SeriesNumber:03d}-{SeriesDescription}')
    parser.add_argument('-n','--namescheme',    help='Optional naming scheme that can be provided to rename the DICOM files. Follows the Python string formatting syntax with DICOM field names in curly bracers with an optional number of digits for numeric fields. Use e.g. "{PatientName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d}.dcm" or "{InstanceNumber:05d}_{SOPInstanceUID}.IMA" for default names')
    parser.add_argument('-p','--pattern',       help='The regular expression pattern used in re.match(pattern, dicomfile) to select the dicom files', default='.*\.(IMA|dcm)$')
    parser.add_argument('--force',              help='Sort the DICOM data even the DICOM fields of the folder/name scheme are not in the data', action='store_true')
    parser.add_argument('-d','--dryrun',        help='Add this flag to just print the dicomsort commands without actually doing anything', action='store_true')
    args = parser.parse_args()

    # Set-up logging
    bidscoin.setup_logging()

    sortsessions(sourcefolder = args.dicomsource,
                 subprefix    = args.subprefix,
                 sesprefix    = args.sesprefix,
                 folderscheme = args.folderscheme,
                 namescheme   = args.namescheme,
                 pattern      = args.pattern,
                 force        = args.force,
                 dryrun       = args.dryrun)


if __name__ == "__main__":
    main()
