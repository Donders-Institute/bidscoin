#!/usr/bin/env python
"""
Maps dicom fields in the rawfolder and, optionally, uses that info to rename the sub-/ses-id's of the subfolders
"""

import os
import sys
import warnings
sys.path.append(os.path.join('/opt/bidscoiner/1.1/bidscoiner'))
import bids


def rawmapper(rawfolder, outfolder=None, rename=False, dicomfield='PatientComments', dryrun=False):
    """
    :param str rawfolder:   The root folder-name of the sub/ses/data/file tree containing the source data files
    :param str outfolder:   The name of the folder where the mapping-file is saved (default = rawfolder)
    :param bool rename:     Flag for renaming the sub-subid folders to sub-dicomfield
    :param str dicomfield:  The name of the dicomfield that is mapped
    :param bool dryrun:     Flag for dry-running renaming the sub-subid folders
    :return:                Nothing
    :rtype: NoneType
    """

    # Input checking
    if not outfolder:
        outfolder = rawfolder
    rawfolder = os.path.abspath(os.path.expanduser(rawfolder))
    outfolder = os.path.abspath(os.path.expanduser(outfolder))

    # Create a output mapping-file
    mappingfile = os.path.join(outfolder, 'rawmapper_{}.tsv'.format(dicomfield))
    with open(mappingfile, 'x') as fid:
        if rename:
            fid.write('{}\t{}\t{}\t{}\n'.format('subid', 'sesid', 'newsubid', 'newsesid'))
        else:
            fid.write('{}\t{}\t{}\n'.format('subid', 'sesid', dicomfield))

    # Loop over all subjects and sessions and convert them using the bidsmap entries
    for subject in bids.lsdirs(rawfolder, 'sub-*'):

        sessions = bids.lsdirs(subject, 'ses-*')
        if not sessions: sessions = subject
        for session in sessions:

            # Get the subject and session identifiers from the raw folder
            subid = 'sub-' + session.rsplit('/sub-', 1)[1].split('/ses-', 1)[0]
            sesid = 'ses-' + session.rsplit('/ses-')[1]

            # Parse the new subject and session identifiers from the dicomfield
            dcmval = bids.get_dicomfield(dicomfield, bids.get_dicomfile(bids.lsdirs(session)[0]))   # TODO: test how newlines from the console work out
            if rename:
                if not dcmval:
                    warnings.warn('Skipping renaming because the dicom-field was empty for: ' + session)
                    newsubid = subid
                    newsesid = sesid
                else:
                    if '/' in dcmval:
                        delim = '/'
                    elif '\\' in dcmval:
                        delim = '\\'
                    else:
                        delim = '\n'
                    newsubsesid = dcmval.split(delim)
                    newsubid    = 'sub-' + newsubsesid[0].replace('sub-', '')
                    if len(newsubsesid)==1:
                        newsesid = sesid
                    elif len(newsubsesid)==2:
                        newsesid = 'ses-' + newsubsesid[1].replace('ses-', '')
                    else:
                        warnings.warn('Skipping renaming of {} because the dicom-field "{}" could not be parsed into [subid, sesid]'.format(session, dcmval))
                        newsubid = subid
                        newsesid = sesid

            # Save the dicomfield / sub-ses mapping to disk
            if rename:
                print('{}\{} -> \t{}\{}'.format(subid, sesid, newsubid, newsesid))
                with open(os.path.join(outfolder,mappingfile), 'a') as fid:
                    fid.write('{}\t{}\t{}\t{}\n'.format(subid, sesid, newsubid, newsesid))
            else:
                print('{}\{} -> \t{}'.format(subid, sesid, dcmval))
                with open(os.path.join(outfolder,mappingfile), 'a') as fid:
                    fid.write('{}\t{}\t{}\n'.format(subid, sesid, dcmval))

            # Rename the session subfolder in the rawfolder (but skip if it already exists)
            if rename:
                newsession = os.path.join(rawfolder, newsubid, newsesid)
                if session != newsession:
                    if os.path.isdir(newsession):
                        warnings.warn('{} already exists, skipping renaming of {}'.format(newsession, session))
                    elif not dryrun:
                        os.renames(session, newsession)


# Shell usage
if __name__ == "__main__":

    # Parse the input arguments and run the rawmapper(args)
    import argparse
    import textwrap
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n  rawmapper.py -r /project/3022026.01/raw\n  rawmapper.py -d AcquisitionDate /project/3022026.01/raw\n ')
    parser.add_argument('rawfolder',         help='The source folder with the raw data in sub-#/ses-#/series organisation')
    parser.add_argument('-r','--rename',     help='If this flag is given sub-subid/ses-sesid directories in the rawfolder will be renamed to sub-dcmval/ses-dcmval', action='store_true')
    parser.add_argument('-o','--outfolder',  help='The destination folder with the mapper-file is saved (default = rawfolder)')
    parser.add_argument('-d','--dicomfield', help='The name of the dicomfield that is mapped / used to rename the subid/sesid foldernames', default='PatientComments')
    parser.add_argument('-r','--rename',     help='If this flag is given sub-subid/ses-sesid directories in the rawfolder will be renamed to sub-dcmval/ses-dcmval', action='store_true')
    parser.add_argument('--dryrun',          help='Add this flag to dryrun (test) the renaming of the sub-subid/ses-sesid directories (i.e. directory names are not actually changed))', action='store_true')
    args = parser.parse_args()

    rawmapper(rawfolder=args.rawfolder, outfolder=args.outfolder, rename=args.rename, dicomfield=args.dicomfield)
