#!/usr/bin/env python
"""
Sorts and / or renames DICOM files into local subdirectories with a (3-digit) SeriesNumber-SeriesDescription directory name (i.e. following the same listing as on the scanner console)
"""

import os
import re
import warnings
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed


def cleanup(name: str) -> str:
    """
    Removes illegal characters from file- or directory-name

    :param name: The file- or directory-name
    :return:     The cleaned file- or directory-name
    """

    special_characters = (os.sep, '*', '?', '"')        # These are the worst offenders, but there are many more

    for special in special_characters:
        name = name.strip().replace(special, '')

    return name


def sortsession(sessionfolder: str, dicomfiles: list, rename: bool, ext: str, nosort: bool) -> None:
    """
    Sorts dicomfiles into (3-digit) SeriesNumber-SeriesDescription subfolders (e.g. '003-T1MPRAGE')

    :param sessionfolder:   The name of the destination folder of the dicom files
    :param dicomfiles:      The list of dicomfiles to be sorted and/or renamed
    :param rename:          Boolean to rename the DICOM files to a PatientName_SeriesNumber_SeriesDescription_AcquisitionNumber_InstanceNumber scheme
    :param ext:             The file extension after sorting (empty value keeps original file extension)
    :param nosort:          Boolean to skip sorting of DICOM files into SeriesNumber-SeriesDescription directories (useful in combination with -r for renaming only)
    :return:                Nothing
    """

    # Map all dicomfiles and move them to series folders
    print(f'>> Processing: {sessionfolder} ({len(dicomfiles)} files)')
    if not os.path.isdir(sessionfolder):
        os.makedirs(sessionfolder)

    seriesdirs = []
    for dicomfile in dicomfiles:

        # Extract the SeriesDescription and SeriesNumber from the dicomfield
        seriesnr    = bids.get_dicomfield('SeriesNumber', dicomfile)
        seriesdescr = bids.get_dicomfield('SeriesDescription', dicomfile)
        if not seriesnr:
            warnings.warn(f'No SeriesNumber found, skipping: {dicomfile}')          # This is not a normal DICOM file, better not do anything with it
            continue
        if not seriesdescr:
            seriesdescr = bids.get_dicomfield('ProtocolName', dicomfile)
            if not seriesdescr:
                seriesdescr = 'unknown_protocol'
                warnings.warn(f'No SeriesDecription or ProtocolName found for: {dicomfile}')
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
            warnings.warn(f'Missing one or more crucial DICOM-fields, cannot safely rename {dicomfile}\npatientname = {patientname}\nseriesnumber = {seriesnr}\nseriesdescription = {seriesdescr}\nacquisitionnr = {acquisitionnr}\ninstancenr = {instancenr}')
            filename = os.path.basename(dicomfile)
        elif rename:
            filename = cleanup(f'{patientname}_{seriesnr:03d}_{seriesdescr}_{acquisitionnr:05d}_{instancenr:05d}{ext}')
        else:
            filename = os.path.basename(dicomfile)
        if nosort:
            pathname = sessionfolder
        else:
            # Create the series subfolder
            seriesdir = cleanup(f'{seriesnr:03d}-{seriesdescr}')
            if seriesdir not in seriesdirs:  # We have a new series
                if not os.path.isdir(os.path.join(sessionfolder, seriesdir)):
                    print('   Creating:  ' + os.path.join(sessionfolder, seriesdir))
                    os.makedirs(os.path.join(sessionfolder, seriesdir))
                seriesdirs.append(seriesdir)
            pathname = os.path.join(sessionfolder, seriesdir)
        if ext:
            newfilename = os.path.join(pathname, os.path.splitext(filename)[0] + ext)
        else:
            newfilename = os.path.join(pathname, filename)
        if os.path.isfile(newfilename):
            warnings.warn(f'File already exists, cannot safely rename {dicomfile} -> {newfilename}')
        else:
            os.rename(dicomfile, newfilename)


def sortsessions(session: str, subjectid: str='', sessionid: str='', rename: bool=False, ext: str='', nosort: bool=False, pattern: str='.*\.(IMA|dcm)$') -> None:
    """

    :param session:     The root folder containing the source [sub/][ses/]dicomfiles or the DICOMDIR file
    :param subjectid:   The prefix of the sub folders in session
    :param sessionid:   The prefix of the ses folders in sub folder
    :param rename:      Boolean to rename the DICOM files to a PatientName_SeriesNumber_SeriesDescription_AcquisitionNumber_InstanceNumber scheme
    :param ext:         The file extension after sorting (empty value keeps original file extension)
    :param nosort:      Boolean to skip sorting of DICOM files into SeriesNumber-SeriesDescription directories (useful in combination with -r for renaming only)
    :param pattern:     The regular expression pattern used in re.match() to select the dicom files
    :return:            Nothing
    """

    # Input checking
    session = os.path.abspath(os.path.expanduser(session))

    # Define the sessionfolder, collect all DICOM files and run sortsession()
    if subjectid:   # Do a recursive search, assuming session is a foldername, not a DICOMDIR file

        for subfolder in bids.lsdirs(session, subjectid + '*'):
            if sessionid:
                sessionfolders = bids.lsdirs(subfolder, sessionid + '*')
            else:
                sessionfolders = [subfolder]

            for sessionfolder in sessionfolders:
                dicomfiles = [os.path.join(sessionfolder, dcmfile) for dcmfile in os.listdir(sessionfolder) if re.match(pattern, dcmfile)]
                sortsession(sessionfolder, dicomfiles, rename, ext, nosort)

    else:

        if os.path.basename(session) == 'DICOMDIR':

            from pydicom.filereader import read_dicomdir

            dicomdir = read_dicomdir(session)

            sessionfolder_ = os.path.dirname(session)
            for patient in dicomdir.patient_records:
                if len(dicomdir.patient_records) > 1:
                    sessionfolder = os.path.join(sessionfolder_, f'sub-{cleanup(str(patient.PatientName))}')

                for n, study in enumerate(patient.children, 1):
                    if len(patient.children) > 1:
                        sessionfolder = os.path.join(sessionfolder_, f'ses-{n:02}{cleanup(str(study.StudyDescription))}')    # TODO: Remove StudyDescrtiption?

                    dicomfiles = []
                    for series in study.children:
                        dicomfiles.extend([os.path.join(sessionfolder_, *image.ReferencedFileID) for image in series.children])
                    sortsession(sessionfolder, dicomfiles, rename, ext, nosort)

        else:

            sessionfolder = session
            dicomfiles    = [os.path.join(sessionfolder,dcmfile) for dcmfile in os.listdir(sessionfolder) if re.match(pattern, dcmfile)]
            sortsession(sessionfolder, dicomfiles, rename, ext, nosort)


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run the sortsessions(args)
    import argparse
    import textwrap

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(formatter_class=CustomFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  dicomsort.py /project/3022026.01/raw\n'
                                            '  dicomsort.py /project/3022026.01/raw --subjectid sub\n'
                                            '  dicomsort.py /project/3022026.01/raw --subjectid sub-01 --sessionid ses\n'
                                            '  dicomsort.py /project/3022026.01/raw/sub-011/ses-mri01/DICOMDIR -r -e .dcm\n')
    parser.add_argument('dicomsource',    help='The name of the root folder containing the dicomsource/[sub/][ses/]dicomfiles or the name of the (single session/study) DICOMDIR file')
    parser.add_argument('--subjectid',    help='The prefix string for recursive searching in dicomsource/subject subfolders (e.g. "sub")')
    parser.add_argument('--sessionid',    help='The prefix string for recursive searching in dicomsource/subject/session subfolders (e.g. "ses")')
    parser.add_argument('-r','--rename',  help='Flag to rename the DICOM files to a PatientName_SeriesNumber_SeriesDescription_AcquisitionNumber_InstanceNumber scheme', action='store_true')
    parser.add_argument('-e','--ext',     help='The file extension after sorting (empty value keeps the original file extension)', default='')
    parser.add_argument('-n','--nosort',  help='Flag to skip sorting of DICOM files into SeriesNumber-SeriesDescription directories (useful in combination with -r for renaming only)', action='store_true')
    parser.add_argument('-p','--pattern', help='The regular expression pattern used in re.match(pattern, dicomfile) to select the dicom files', default='.*\.(IMA|dcm)$')
    args = parser.parse_args()

    sortsessions(session    = args.dicomsource,
                 subjectid  = args.subjectid,
                 sessionid  = args.sessionid,
                 rename     = args.rename,
                 ext        = args.ext,
                 nosort     = args.nosort,
                 pattern    = args.pattern)
