#!/usr/bin/env python3
"""
Sorts and / or renames DICOM files into local subfodlers with a (3-digit)
SeriesNumber-SeriesDescription folder name (i.e. following the same listing
as on the scanner console)
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
    import bidscoin, bids         # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger(__name__)


def construct_name(scheme: str, dicomfile: Path) -> str:
    """
    Check the renaming scheme for presence in the DICOM file and use an alternative if available. Then construct the new
    name by replacing the DICOM keys for their values, and applying the formatted string

    :param scheme:      The renaming scheme
    :param dicomfile:   The DICOM file that should be renamed
    :return:            The new name constructed from the scheme
    """

    # Alternative field names based on earlier DICOM versions or on other reasons
    alternatives = {'PatientName':'PatientsName', 'SeriesDescription':'ProtocolName', 'InstanceNumber':'ImageNumber',
                    'PatientsName':'PatientName', 'ProtocolName':'SeriesDescription', 'ImageNumber':'InstanceNumber'}

    schemedata = {}
    for field in re.findall('(?<={)([a-zA-Z]+)(?::\\d+d)?(?=})', scheme):
        value = cleanup(bids.get_dicomfield(field, dicomfile))
        if not value and field in alternatives.keys():
            value = cleanup(bids.get_dicomfield(alternatives[field], dicomfile))
        if not value:
            LOGGER.warning(f"Missing '{field}' DICOM field specified in the '{scheme}' naming scheme, cannot find a safe name for: {dicomfile}\n")
            return ''

        schemedata[field] = value

    return scheme.format(**schemedata) if schemedata else ''


def validscheme(scheme: str) -> bool:
    """
    Parse the naming scheme string and test if all attributes are present

    :param scheme: The renaming scheme
    :return:
    """
    if re.fullmatch('(({[a-zA-Z]+(:\\d+d)?})|([a-zA-Z0-9_.]+))*', scheme):
        LOGGER.error(f"Bad naming scheme: {scheme}. Only alphanumeric characters could be used for the field names (with the optional number of digits afterwards,"
                      "e.g. '{InstanceNumber:05d}'), and only alphanumeric characters, dots, and underscores could be used as separators.")
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
        name = name.strip().replace(special, '')

    return name


def sortsession(sessionfolder: Path, dicomfiles: List[Path], folderscheme: str, namescheme: str, dryrun: bool) -> None:
    """
    Sorts dicomfiles into subfolders (e.g. a 3-digit SeriesNumber-SeriesDescription subfolder, such as '003-T1MPRAGE')

    :param sessionfolder:   The name of the destination folder of the dicom files
    :param dicomfiles:      The list of dicomfiles to be sorted and/or renamed
    :param folderscheme:    Optional naming scheme for the sorted (e.g. Series) subfolders. Follows the Python string formatting syntax with DICOM field names in curly bracers with an optional number of digits for numeric fields, e.g. {SeriesNumber:03d}_{SeriesDescription}
    :param namescheme:      Optional naming scheme for renaming the files. Follows the Python string formatting syntax with DICOM field names in curly bracers, e.g. {PatientName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d}.IMA
    :param dryrun:          Boolean to just display the action
    :return:                Nothing
    """

    # Map all dicomfiles and move them to series folders
    LOGGER.info(f">> Sorting: {sessionfolder} ({len(dicomfiles)} files)")
    if not dryrun:
        sessionfolder.mkdir(parents=True, exist_ok=True)

    subfolders = []
    for dicomfile in dicomfiles:

        # Create a (e.g. DICOM Series) sorting subfolder if needed
        if not folderscheme:
            pathname = sessionfolder
        else:
            subfolder = construct_name(folderscheme, dicomfile)
            if not validscheme(folderscheme) or not subfolder:
                LOGGER.error('Cannot create subfolders, aborting dicomsort()...')
                return
            pathname = sessionfolder/subfolder
            if subfolder not in subfolders:
                subfolders.append(subfolder)
                if not pathname.is_dir():
                    LOGGER.info(f"   Creating:  {pathname}")
                    if not dryrun:
                        pathname.mkdir(parents=True)

        # Move and/or rename the dicomfiles in(to) the (sub)folder
        if namescheme and validscheme(namescheme):
            newfilename = pathname/construct_name(namescheme, dicomfile)
        else:
            newfilename = pathname/dicomfile.name
        if newfilename.is_file():
            LOGGER.warning(f"File already exists: {dicomfile} -> {newfilename}")
            newfilename = newfilename.with_name(newfilename.stem + str(uuid.uuid4()) + newfilename.suffix)
            LOGGER.info(f"Using new file-name: {dicomfile} -> {newfilename}")
        if not dryrun:
            dicomfile.replace(newfilename)


def sortsessions(session: Path, subprefix: str='', sesprefix: str='', folderscheme: str='{SeriesNumber:03d}_{SeriesDescription}',
                 namescheme: str='', pattern: str='.*\.(IMA|dcm)$', dryrun: bool=False) -> None:
    """
    Wrapper around sortsession() to loop over subjects and sessions and index the session DICOM files

    :param session:      The root folder containing the source [sub/][ses/]dicomfiles or the DICOMDIR file
    :param subprefix:    The prefix for searching the sub folders in session
    :param sesprefix:    The prefix for searching the ses folders in sub folder
    :param folderscheme: Optional naming scheme for the sorted (e.g. Series) subfolders. Follows the Python string formatting syntax with DICOM field names in curly bracers with an optional number of digits for numeric fields', default='{SeriesNumber:03d}_{SeriesDescription}'
    :param namescheme:   Optional naming scheme for renaming the files. Follows the Python string formatting syntax with DICOM field names in curly bracers, e.g. {PatientName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d}.IMA
    :param pattern:      The regular expression pattern used in re.match() to select the dicom files
    :param dryrun:       Boolean to just display the action
    :return:             Nothing
    """

    # Input checking
    session = Path(session)

    # Do a recursive call if subprefix is given
    if subprefix:

        for subfolder in bidscoin.lsdirs(session, subprefix + '*'):
            if sesprefix:
                sessionfolders = bidscoin.lsdirs(subfolder, sesprefix + '*')
            else:
                sessionfolders = [subfolder]

            for sessionfolder in sessionfolders:
                sortsessions(sessionfolder, folderscheme=folderscheme, namescheme=namescheme, pattern=pattern, dryrun=dryrun)

    # Use the DICOMDIR file if it is there
    if (session/'DICOMDIR').is_file():

        dicomdir = pydicom.dcmread(str(session/'DICOMDIR'))

        sessionfolder = session
        for patient in dicomdir.patient_records:
            if len(dicomdir.patient_records) > 1:
                sessionfolder = session/f"sub-{cleanup(patient.PatientName)}"

            for n, study in enumerate(patient.children, 1):                                    # TODO: Check order
                if len(patient.children) > 1:
                    sessionfolder = session/f"ses-{n:02}{cleanup(study.StudyDescription)}"     # TODO: Leave out StudyDescription? Include PatientName/StudiesDescription?
                    LOGGER.warning(f"The session index-number '{n:02}' is not necessarily meaningful: {sessionfolder}")

                dicomfiles = [session.joinpath(*image.ReferencedFileID) for series in study.children for image in series.children]
                sortsession(sessionfolder, dicomfiles, folderscheme, namescheme, dryrun)

    else:

        dicomfiles = [dcmfile for dcmfile in session.iterdir() if dcmfile.is_file() and re.match(pattern, str(dcmfile))]
        sortsession(session, dicomfiles, folderscheme, namescheme, dryrun)


def main():
    """Console script usage"""

    # Parse the input arguments and run the sortsessions(args)
    import argparse
    import textwrap

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass

    parser = argparse.ArgumentParser(formatter_class=CustomFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  dicomsort /project/3022026.01/raw\n'
                                            '  dicomsort /project/3022026.01/raw --subprefix sub\n'
                                            '  dicomsort /project/3022026.01/raw --subprefix sub-01 --sesprefix ses\n'
                                            '  dicomsort /project/3022026.01/raw/sub-011/ses-mri01/DICOMDIR -r {AcquisitionNumber:05d}_{InstanceNumber:05d}.dcm\n ')
    parser.add_argument('dicomsource',          help='The name of the root folder containing the dicomsource/[sub/][ses/]dicomfiles and / or the (single session/study) DICOMDIR file')
    parser.add_argument('-i','--subprefix',     help='Provide a prefix string for recursive searching in dicomsource/subject subfolders (e.g. "sub-")')
    parser.add_argument('-j','--sesprefix',     help='Provide a prefix string for recursive searching in dicomsource/subject/session subfolders (e.g. "ses-")')
    parser.add_argument('-f','--folderscheme',  help='Naming scheme for the sorted DICOM Series subfolders. Follows the Python string formatting syntax with DICOM field names in curly bracers with an optional number of digits for numeric fields. Sorting in subfolders is skipped when an empty folderscheme is given (but note that renaming the filenames can still be performed)', default='{SeriesNumber:03d}_{SeriesDescription}')
    parser.add_argument('-n','--namescheme',    help='Optional naming scheme that can be provided to rename the DICOM files. Follows the Python string formatting syntax with DICOM field names in curly bracers with an optional number of digits for numeric fields. Use "{PatientName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d}.IMA" for the default names at DCCN')
    parser.add_argument('-p','--pattern',       help='The regular expression pattern used in re.match(pattern, dicomfile) to select the dicom files', default='.*\.(IMA|dcm)$')
    parser.add_argument('-d','--dryrun',        help='Add this flag to just print the dicomsort commands without actually doing anything', action='store_true')
    args = parser.parse_args()

    # Set-up logging
    bidscoin.setup_logging()

    sortsessions(session      = args.dicomsource,
                 subprefix    = args.subprefix,
                 sesprefix    = args.sesprefix,
                 folderscheme = args.folderscheme,
                 namescheme   = args.namescheme,
                 pattern      = args.pattern,
                 dryrun       = args.dryrun)


if __name__ == "__main__":
    main()
