#!/usr/bin/env python3
"""
Sorts and / or renames DICOM files into local subdirectories with a (3-digit)
SeriesNumber-SeriesDescription directory name (i.e. following the same listing
as on the scanner console)
"""

import re
import logging
from pathlib import Path
import pydicom
import uuid
try:
    from bidscoin import bidscoin, bids
except ImportError:
    import bidscoin, bids         # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger(__name__)

def cleanup(name: str) -> str:
    """
    Removes illegal characters from file- or directory-name

    :param name: The file- or directory-name
    :return:     The cleaned file- or directory-name
    """

    special_characters = ('/', '\\', '*', '?', '"')        # These are the worst offenders, but there are many more

    for special in special_characters:
        name = name.strip().replace(special, '')

    return name


def sortsession(sessionfolder: Path, dicomfiles: list, dicomfield: str, rename: bool, rename_scheme: str, ext: str, nosort: bool, dryrun: bool) -> None:
    """
    Sorts dicomfiles into (3-digit) SeriesNumber-SeriesDescription subfolders (e.g. '003-T1MPRAGE')

    :param sessionfolder:   The name of the destination folder of the dicom files
    :param dicomfiles:      The list of dicomfiles to be sorted and/or renamed
    :param dicomfield:      The dicomfield that is used to construct the series folder name (e.g. SeriesDescription or ProtocolName, which are both used as fallback)
    :param rename:          Boolean to rename the DICOM files to a PatientName_SeriesNumber_SeriesDescription_AcquisitionNumber_InstanceNumber scheme
    :param rename_scheme:   The naming scheme for renaming. Follows the Python string formatting syntax with DICOM field names in curly bracers with {PatientName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d} as default.
    :param ext:             The file extension after sorting (empty value keeps original file extension)
    :param nosort:          Boolean to skip sorting of DICOM files into SeriesNumber-SeriesDescription directories (useful in combination with -r for renaming only)
    :param dryrun:          Boolean to just display the action
    :return:                Nothing
    """

    # Map all dicomfiles and move them to series folders
    LOGGER.info(f">> Sorting: {sessionfolder} ({len(dicomfiles)} files)")
    if not dryrun:
        sessionfolder.mkdir(parents=True, exist_ok=True)

    seriesdirs = []
    for dicomfile in dicomfiles:

        # Extract the SeriesDescription and SeriesNumber from the dicomfield
        seriesnr = bids.get_dicomfield('SeriesNumber', dicomfile)
        if not seriesnr:
            LOGGER.warning(f"No SeriesNumber found, skipping: {dicomfile}")          # This is not a normal DICOM file, better not do anything with it
            continue
        seriesdescr = bids.get_dicomfield(dicomfield, dicomfile)
        if not seriesdescr:
            seriesdescr = bids.get_dicomfield('SeriesDescription', dicomfile)
            if not seriesdescr:
                seriesdescr = bids.get_dicomfield('ProtocolName', dicomfile)
                if not seriesdescr:
                    seriesdescr = 'unknown_protocol'
                    LOGGER.warning(f"No {dicomfield}, SeriesDecription or ProtocolName found for: {dicomfile}")
        if rename:
            # Parse the naming scheme string and test if all attributes are present
            if not re.fullmatch('(({[a-zA-Z]+(:\\d+d)?})|([a-zA-Z0-9_.]+))*', rename_scheme):
                LOGGER.error('Bad naming scheme. Only alphanumeric characters could be used for the field names (with the optional number of digits afterwards, '
                             'e.g., \'{InstanceNumber:05d}\'), and only alphanumeric characters, dots, and underscores could be used as separators. ')
                rename = False
            else:
                fields = re.findall('(?<={)([a-zA-Z]+)(?::\\d+d)?(?=})', rename_scheme)
                field_alternatives = {'InstanceNumber': 'ImageNumber', # alternative field names based on the earlier versions of the Standard or other reasons
                                      'PatientName': 'PatientsName'}
                dicom_fields = {}
                for field in fields:
                    value = bids.get_dicomfield(field, dicomfile)
                    if not value:
                        if field in field_alternatives.keys() and bids.get_dicomfield(field_alternatives[field], dicomfile):
                            rename_scheme.replace('{'+field+'}','{'+field_alternatives[field]+'}')
                            dicom_fields[field_alternatives[field]] = value

                            LOGGER.info(f'{field} field is absent from the DICOM header, but {field_alternatives[field]} is present, using {field_alternatives[field]}')
                            continue

                        LOGGER.warning(f"Missing '{field}' DICOM field specified in the naming scheme, cannot safely rename {dicomfile}\n")
                        rename = False
                    else:
                        dicom_fields[field] = value
        if not ext:
            ext = Path(dicomfile).suffix()
        # Move and/or rename the dicomfile in(to) the (series sub)folder
        if rename:
            new_name = rename_scheme.format(**dicom_fields)+ext
            LOGGER.debug(f'Renaming {dicomfile.name} into {new_name}')
            filename = cleanup(new_name)
        else:
            filename = dicomfile.name

        if nosort:
            pathname = sessionfolder
        else:
            # Create the series subfolder
            seriesdir = cleanup(f"{seriesnr:03d}-{seriesdescr}")
            if seriesdir not in seriesdirs:  # We have a new series
                if not (sessionfolder/seriesdir).is_dir():
                    LOGGER.info(f"   Creating:  {sessionfolder/seriesdir}")
                    if not dryrun:
                        (sessionfolder/seriesdir).mkdir(parents=True)
                seriesdirs.append(seriesdir)
            pathname = sessionfolder/seriesdir
        if ext:
            newfilename = (pathname/filename).with_suffix(ext)
        else:
            newfilename = pathname/filename
        if newfilename.is_file():
            LOGGER.warning(f"File already exists: {dicomfile} -> {newfilename}")
            newfilename = newfilename.with_name(newfilename.stem + str(uuid.uuid4()) + newfilename.suffix)
            LOGGER.info(f"Using new file-name: {dicomfile} -> {newfilename}")
        if not dryrun:
          dicomfile.replace(newfilename)


def sortsessions(session: Path, subprefix: str='', sesprefix: str='', dicomfield: str='SeriesDescription', rename: bool=False,
                 rename_scheme: str="{PatientName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d}",
                 ext: str='', nosort: bool=False, pattern: str='.*\.(IMA|dcm)$', dryrun: bool=False) -> None:
    """

    :param session:         The root folder containing the source [sub/][ses/]dicomfiles or the DICOMDIR file
    :param subprefix:       The prefix for searching the sub folders in session
    :param sesprefix:       The prefix for searching the ses folders in sub folder
    :param dicomfield:      The dicomfield that is used to construct the series folder name (e.g. SeriesDescription or ProtocolName, which are both used as fallback)
    :param rename:          Boolean to rename the DICOM files to a PatientName_SeriesNumber_SeriesDescription_AcquisitionNumber_InstanceNumber scheme
    :param rename_scheme:   The naming scheme for renaming. Follows the Python string formatting syntax with DICOM field names in curly bracers with {PatientName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d} as default.
    :param ext:             The file extension after sorting (empty value keeps original file extension)
    :param nosort:          Boolean to skip sorting of DICOM files into SeriesNumber-SeriesDescription directories (useful in combination with -r for renaming only)
    :param pattern:         The regular expression pattern used in re.match() to select the dicom files
    :param dryrun:          Boolean to just display the action
    :return:                Nothing
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
                sortsessions(session=sessionfolder, dicomfield=dicomfield, rename=rename, rename_scheme=rename_scheme, ext=ext, nosort=nosort, pattern=pattern, dryrun=dryrun)

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
                sortsession(sessionfolder = sessionfolder, dicomfiles = dicomfiles, dicomfield =  dicomfield, rename = rename, rename_scheme = rename_scheme, ext = ext, nosort = nosort, dryrun = dryrun)

    else:

        dicomfiles = [dcmfile for dcmfile in session.iterdir() if dcmfile.is_file() and re.match(pattern, str(dcmfile))]
        sortsession(sessionfolder = session, dicomfiles = dicomfiles, dicomfield =  dicomfield, rename = rename, rename_scheme = rename_scheme, ext = ext, nosort = nosort, dryrun = dryrun)


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
                                            '  dicomsort /project/3022026.01/raw/sub-011/ses-mri01/DICOMDIR -r -e .dcm\n ')
    parser.add_argument('dicomsource',      help='The name of the root folder containing the dicomsource/[sub/][ses/]dicomfiles and / or the (single session/study) DICOMDIR file')
    parser.add_argument('-i','--subprefix', help='Provide a prefix string for recursive searching in dicomsource/subject subfolders (e.g. "sub")')
    parser.add_argument('-j','--sesprefix', help='Provide a prefix string for recursive searching in dicomsource/subject/session subfolders (e.g. "ses")')
    parser.add_argument('-f','--fieldname', help='The dicomfield that is used to construct the series folder name ("SeriesDescription" and "ProtocolName" are both used as fallback)', default='SeriesDescription')
    parser.add_argument('-r','--rename',    help='Flag to rename the DICOM files (recommended for DICOMDIR data)', action='store_true')
    parser.add_argument('-s','--scheme',    help='The naming scheme for renaming. Follows the Python string formatting syntax with DICOM field names in curly bracers with an optional number of digits for numeric fields. Use "{InstanceNumber:05d}_{SOPInstanceUID}" for the default names at DCCN.', default = '{PatientName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d}')
    parser.add_argument('-e','--ext',       help='The file extension after sorting (empty value keeps the original file extension), e.g. ".dcm"', default='')
    parser.add_argument('-n','--nosort',    help='Flag to skip sorting of DICOM files into SeriesNumber-SeriesDescription directories (useful in combination with -r for renaming only)', action='store_true')
    parser.add_argument('-p','--pattern',   help='The regular expression pattern used in re.match(pattern, dicomfile) to select the dicom files', default='.*\.(IMA|dcm)$')
    parser.add_argument('-d','--dryrun',    help='Add this flag to just print the dicomsort commands without actually doing anything', action='store_true')
    args = parser.parse_args()

    # Set-up logging
    bidscoin.setup_logging()

    sortsessions(session    = args.dicomsource,
                 subprefix  = args.subprefix,
                 sesprefix  = args.sesprefix,
                 dicomfield = args.fieldname,
                 rename     = args.rename,
                 rename_scheme = args.scheme,
                 ext        = args.ext,
                 nosort     = args.nosort,
                 pattern    = args.pattern,
                 dryrun     = args.dryrun)


if __name__ == "__main__":
    main()
