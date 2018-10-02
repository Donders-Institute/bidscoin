#!/usr/bin/env python
"""
Sorts DICOM files into local subdirectories with a (3-digit) SeriesNumber-SeriesDescription directory name (i.e. following the same listing as on the scanner console)
"""

import os
import re
import bids
import warnings


def sortsession(sessionfolder, pattern):
    """
    Sorts dicomfiles into (3-digit) SeriesNumber-SeriesDescription subfolders (e.g. '003-T1MPRAGE')

    :param str sessionfolder:   The name of the folder that contains the dicom files
    :param str pattern:         The regular expression pattern used in re.match(pattern, dicomfile) to select the dicom files
    :return:                    Nothing
    :rtype: NoneType
    """

    # Input checking
    sessionfolder = os.path.abspath(os.path.expanduser(sessionfolder))
    seriesdirs    = []
    print('> Sorting: ' + sessionfolder)

    # Map all dicomfiles and move them to series folders
    for dicomfile in [os.path.join(sessionfolder,dcmfile) for dcmfile in os.listdir(sessionfolder) if re.match(pattern, dcmfile)]:

        # Extract the SeriesDescription and SeriesNumber from the dicomfield
        seriesnr    = bids.get_dicomfield('SeriesNumber', dicomfile)
        seriesdescr = bids.get_dicomfield('SeriesDescription', dicomfile)
        if not seriesdescr:
            seriesdescr = bids.get_dicomfield('ProtocolName', dicomfile)
            if not seriesdescr:
                seriesdescr = 'unknown_protocol'
                warnings.warn('No SeriesDecription or ProtocolName found for: ' + dicomfile)

        # Create the series subfolder
        seriesdir = '{:03d}-{}'.format(seriesnr, seriesdescr)
        if seriesdir not in seriesdirs:                 # We have a new series
            if not os.path.isdir(os.path.join(sessionfolder, seriesdir)):
                print('Creating:  ' + os.path.join(sessionfolder, seriesdir))
                os.makedirs(os.path.join(sessionfolder, seriesdir))
            seriesdirs.append(seriesdir)

        # Move the dicomfile to the series subfolder
        os.rename(dicomfile, os.path.join(sessionfolder, seriesdir, os.path.basename(dicomfile)))


def sortsessions(rawfolder, subjectid='', sessionid='', pattern='.*\.(IMA|dcm)$'):
    """

    :param rawfolder:   The root folder containing the source [sub/][ses/]dicomfiles
    :param subjectid:   The prefix of the sub folders in rawfolder
    :param sessionid:   The prefix of the ses folders in sub folder
    :param pattern:     The regular expression pattern used in re.match() to select the dicom files
    :return:            Nothing
    :rtype: NoneType
    """

    if subjectid:
        for subfolder in bids.lsdirs(rawfolder, subjectid + '*'):
            if sessionid:
                for sesfolder in bids.lsdirs(subfolder, sessionid + '*'):
                    sortsession(sesfolder, pattern)
            else:
                sortsession(subfolder, pattern)
    else:
        sortsession(rawfolder, pattern)


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run the sortsessions(args)
    import argparse
    import textwrap

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(formatter_class=CustomFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n  dicomsort.py /project/3022026.01/raw\n  dicomsort.py /project/3022026.01/raw --subjectid sub\n  dicomsort.py /project/3022026.01/raw --subjectid sub --sessionid ses')
    parser.add_argument('rawfolder',   help='The root folder containing the source [sub/][ses/]dicomfiles')
    parser.add_argument('--subjectid', help='The prefix of the subject folders in rawfolder to search in (e.g. "sub")')
    parser.add_argument('--sessionid', help='The prefix of the session folders in the subject folder to search in (e.g. "ses")')
    parser.add_argument('--pattern',   help='The regular expression pattern used in re.match(pattern, dicomfile) to select the dicom files', default='.*\.(IMA|dcm)$')
    args = parser.parse_args()

    sortsessions(rawfolder=args.rawfolder, subjectid=args.subjectid, sessionid=args.sessionid, pattern=args.pattern)
