#!/usr/bin/env python
"""
Sorts and / or renames DICOM files into local subdirectories with a (3-digit) SeriesNumber-SeriesDescription directory name (i.e. following the same listing as on the scanner console)
"""

import re
import logging
from pathlib import Path
from pydicom.filereader import read_dicomdir
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger('bidscoin')


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


def sortsession(sessionfolder: Path, dicomfiles: list, dicomfield: str, rename: bool, ext: str, nosort: bool, dryrun: bool) -> None:
    """
    Sorts dicomfiles into (3-digit) SeriesNumber-SeriesDescription subfolders (e.g. '003-T1MPRAGE')

    :param sessionfolder:   The name of the destination folder of the dicom files
    :param dicomfiles:      The list of dicomfiles to be sorted and/or renamed
    :param dicomfield:      The dicomfield that is used to construct the series folder name (e.g. SeriesDescription or ProtocolName, which are both used as fallback)
    :param rename:          Boolean to rename the DICOM files to a PatientName_SeriesNumber_SeriesDescription_AcquisitionNumber_InstanceNumber scheme
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
            acquisitionnr = bids.get_dicomfield('AcquisitionNumber', dicomfile)
            instancenr    = bids.get_dicomfield('InstanceNumber', dicomfile)
            if not instancenr:
                instancenr = bids.get_dicomfield('ImageNumber', dicomfile)          # This Attribute was named Image Number in earlier versions of this Standard
            patientname    = bids.get_dicomfield('PatientName', dicomfile)
            if not patientname:
                patientname = bids.get_dicomfield('PatientsName', dicomfile)        # This Attribute was/is sometimes called PatientsName?

        # Move and/or rename the dicomfile in(to) the (series sub)folder
        if rename and not (patientname and seriesnr and seriesdescr and acquisitionnr and instancenr):
            LOGGER.warning(f"Missing one or more essential DICOM-fields, cannot safely rename {dicomfile}\n"
                          f"patientname = {patientname}\n"
                          f"seriesnumber = {seriesnr}\n"
                          f"{dicomfield} = {seriesdescr}\n"
                          f"acquisitionnr = {acquisitionnr}\n"
                          f"instancenr = {instancenr}")
            filename = dicomfile.name
        elif rename:
            filename = cleanup(f"{patientname}_{seriesnr:03d}_{seriesdescr}_{acquisitionnr:05d}_{instancenr:05d}{ext}")
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
            LOGGER.warning(f"File already exists, cannot safely rename {dicomfile} -> {newfilename}")
        elif not dryrun:
            dicomfile.replace(newfilename)


def sortsessions(session: Path, subprefix: str='', sesprefix: str='', dicomfield: str='SeriesDescription', rename: bool=False, ext: str='', nosort: bool=False, pattern: str='.*\.(IMA|dcm)$', dryrun: bool=False) -> None:
    """

    :param session:     The root folder containing the source [sub/][ses/]dicomfiles or the DICOMDIR file
    :param subprefix:   The prefix for searching the sub folders in session
    :param sesprefix:   The prefix for searching the ses folders in sub folder
    :param dicomfield:  The dicomfield that is used to construct the series folder name (e.g. SeriesDescription or ProtocolName, which are both used as fallback)
    :param rename:      Boolean to rename the DICOM files to a PatientName_SeriesNumber_SeriesDescription_AcquisitionNumber_InstanceNumber scheme
    :param ext:         The file extension after sorting (empty value keeps original file extension)
    :param nosort:      Boolean to skip sorting of DICOM files into SeriesNumber-SeriesDescription directories (useful in combination with -r for renaming only)
    :param pattern:     The regular expression pattern used in re.match() to select the dicom files
    :param dryrun:      Boolean to just display the action
    :return:            Nothing
    """

    # Input checking
    session = Path(session)

    # Start logging
    bids.setup_logging()

    # Do a recursive call if subprefix is given
    if subprefix:

        for subfolder in bids.lsdirs(session, subprefix + '*'):
            if sesprefix:
                sessionfolders = bids.lsdirs(subfolder, sesprefix + '*')
            else:
                sessionfolders = [subfolder]

            for sessionfolder in sessionfolders:
                sortsessions(session=sessionfolder, dicomfield=dicomfield, rename=rename, ext=ext, nosort=nosort, pattern=pattern, dryrun=dryrun)

    # Use the DICOMDIR file if it is there
    if (session/'DICOMDIR').is_file():

        dicomdir = read_dicomdir(str(session/'DICOMDIR'))

        sessionfolder = session
        for patient in dicomdir.patient_records:
            if len(dicomdir.patient_records) > 1:
                sessionfolder = session/f"sub-{cleanup(patient.PatientName)}"

            for n, study in enumerate(patient.children, 1):                                    # TODO: Check order
                if len(patient.children) > 1:
                    sessionfolder = session/f"ses-{n:02}{cleanup(study.StudyDescription)}"     # TODO: Leave out StudyDescrtiption? Include PatientName/StudiesDescription?
                    LOGGER.warning(f"The session index-number '{n:02}' is not necessarily meaningful: {sessionfolder}")

                dicomfiles = []
                for series in study.children:
                    dicomfiles.extend([session.joinpath(*image.ReferencedFileID) for image in series.children])
                sortsession(sessionfolder, dicomfiles, dicomfield, rename, ext, nosort, dryrun)

    else:

        dicomfiles = [dcmfile for dcmfile in session.iterdir() if dcmfile.is_file() and re.match(pattern, str(dcmfile))]
        sortsession(session, dicomfiles, dicomfield, rename, ext, nosort, dryrun)


def main():
    """Console script usage"""

    # Parse the input arguments and run the sortsessions(args)
    import argparse
    import textwrap

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

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
    parser.add_argument('-r','--rename',    help='Flag to rename the DICOM files to a PatientName_SeriesNumber_SeriesDescription_AcquisitionNumber_InstanceNumber scheme (recommended for DICOMDIR data)', action='store_true')
    parser.add_argument('-e','--ext',       help='The file extension after sorting (empty value keeps the original file extension), e.g. ".dcm"', default='')
    parser.add_argument('-n','--nosort',    help='Flag to skip sorting of DICOM files into SeriesNumber-SeriesDescription directories (useful in combination with -r for renaming only)', action='store_true')
    parser.add_argument('-p','--pattern',   help='The regular expression pattern used in re.match(pattern, dicomfile) to select the dicom files', default='.*\.(IMA|dcm)$')
    parser.add_argument('-d','--dryrun',    help='Add this flag to just print the dicomsort commands without actually doing anything', action='store_true')
    args = parser.parse_args()

    sortsessions(session    = args.dicomsource,
                 subprefix  = args.subprefix,
                 sesprefix  = args.sesprefix,
                 dicomfield = args.fieldname,
                 rename     = args.rename,
                 ext        = args.ext,
                 nosort     = args.nosort,
                 pattern    = args.pattern,
                 dryrun     = args.dryrun)


if __name__ == "__main__":
    main()
