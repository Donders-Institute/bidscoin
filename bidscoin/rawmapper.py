#!/usr/bin/env python
"""
Maps out the values of a dicom field of all subjects in the sourcefolder, saves
the result in a mapper-file and, optionally, uses the dicom values to rename
the sub-/ses-id's of the subfolders. This latter option can be used, e.g.
when an alternative subject id was entered in the [Additional info] field
during subject registration (i.e. stored in the PatientComments dicom field)
"""

import os
import re
import glob
import warnings
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed


def rawmapper(rawfolder: str, outfolder: str='', sessions: list=[], rename: bool=False, dicomfield: tuple=('PatientComments',), wildcard: str='*', subprefix: str='sub-', sesprefix: str='ses-', dryrun: bool=False) -> None:
    """
    :param rawfolder:   The root folder-name of the sub/ses/data/file tree containing the source data files
    :param outfolder:   The name of the folder where the mapping-file is saved (default = sourcefolder)
    :param sessions:    Space separated list of selected sub-#/ses-# names / folders to be processed. Otherwise all sessions in the bidsfolder will be selected
    :param rename:      Flag for renaming the sub-subid folders to sub-dicomfield
    :param dicomfield:  The names of the dicomfields that are mapped (/ renamed to sub-dcmval/ses-dcmval)
    :param wildcard:    The Unix style pathname pattern expansion that is used by glob to select the series from which the dicomfield is being mapped
    :param subprefix:   The prefix common for all source subject-folders
    :param sesprefix:   The prefix common for all source session-folders
    :param dryrun:      Flag for dry-running renaming the sub-subid folders
    :return:            Nothing
    """

    # Input checking
    if not outfolder:
        outfolder = rawfolder
    rawfolder = os.path.abspath(os.path.expanduser(rawfolder))
    outfolder = os.path.abspath(os.path.expanduser(outfolder))

    # Create or append the output to a mapper logfile
    if not dryrun:
        mapperfile = os.path.join(outfolder, 'rawmapper_{}.tsv'.format('_'.join(dicomfield)))
        if rename:
            with open(mapperfile, 'a') as fid:
                fid.write('{}\t{}\t{}\t{}\n'.format('subid', 'sesid', 'newsubid', 'newsesid'))
        else:
            with open(mapperfile, 'x') as fid:
                fid.write('{}\t{}\t{}\t{}\n'.format('subid', 'sesid', 'seriesname', '\t'.join(dicomfield)))

    # Map the sessions in the sourcefolder
    if not sessions:
        sessions = glob.glob(os.path.join(rawfolder, f'{subprefix}*{os.sep}{sesprefix}*'))
        if not sessions:
            sessions = glob.glob(os.path.join(rawfolder, f'{subprefix}*'))      # Try without session-subfolders
    else:
        sessions = [sessionitem for session in sessions for sessionitem in glob.glob(os.path.join(rawfolder, session), recursive=True)]

    # Loop over the selected sessions in the sourcefolder
    for session in sessions:

        # Get the subject and session identifiers from the raw folder
        subid = subprefix + session.rsplit(os.sep+subprefix, 1)[1].split(os.sep+sesprefix, 1)[0]
        sesid = sesprefix + session.rsplit(os.sep+sesprefix)[1]                                         # TODO: Fix crashing on session-less datasets

        # Parse the new subject and session identifiers from the dicomfield
        series = bids.lsdirs(session, wildcard)
        if not series:
            series = ''
            dcmval = ''
        else:
            series = series[0]                                                                          # TODO: loop over series?
            dcmval = ''
            for dcmfield in dicomfield:
                dcmval = dcmval + '/' + str(bids.get_dicomfield(dcmfield, bids.get_dicomfile(series)))
            dcmval = dcmval[1:]

        # Rename the session subfolder in the sourcefolder and print & save this info
        if rename:

            # Get the new subid and sesid
            if not dcmval or dcmval=='None':
                warnings.warn('Skipping renaming because the dicom-field was empty for: ' + session)
                continue
            else:
                if '/' in dcmval:               # Allow for different sub/ses delimiters that could be entered at the console (i.e. in PatientComments)
                    delim = '/'
                elif '\\' in dcmval:
                    delim = '\\'
                else:
                    delim = '\r\n'
                newsubsesid = [val for val in dcmval.split(delim) if val]   # Skip empty lines / entries
                newsubid    = subprefix + bids.cleanup_value(re.sub(f'^{subprefix}', '', newsubsesid[0]))
                if newsubid==subprefix or newsubid==subprefix+'None':
                    newsubid = subid
                    warnings.warn('Could not rename {} because the dicom-field was empty for: {}'.format(subid, session))
                if len(newsubsesid)==1:
                    newsesid = sesid
                elif len(newsubsesid)==2:
                    newsesid = sesprefix + bids.cleanup_value(re.sub(f'^{sesprefix}', '', newsubsesid[1]))
                else:
                    warnings.warn('Skipping renaming of {} because the dicom-field "{}" could not be parsed into [subid, sesid]'.format(session, dcmval))
                    continue
                if newsesid==sesprefix or newsesid==subprefix+'None':
                    newsesid = sesid
                    warnings.warn('Could not rename {} because the dicom-field was empty for: {}'.format(sesid, session))

            # Save the dicomfield / sub-ses mapping to disk and rename the session subfolder (but skip if it already exists)
            newsession = os.path.join(rawfolder, newsubid, newsesid)
            print(session + ' -> ' + newsession)
            if newsession == session:
                continue
            if os.path.isdir(newsession):
                warnings.warn('{} already exists, skipping renaming of {}'.format(newsession, session))
            elif not dryrun:
                with open(os.path.join(outfolder, mapperfile), 'a') as fid:
                    fid.write('{}\t{}\t{}\t{}\n'.format(subid, sesid, newsubid, newsesid))
                os.renames(session, newsession)

        # Print & save the dicom values
        else:
            print('{}{}{}\t-> {}'.format(subid+os.sep, sesid+os.sep, os.path.basename(series), '\t'.join(dcmval.split('/'))))
            if not dryrun:
                with open(os.path.join(outfolder, mapperfile), 'a') as fid:
                    fid.write('{}\t{}\t{}\t{}\n'.format(subid, sesid, os.path.basename(series), '\t'.join(dcmval.split('/'))))


def main():
    """Console script usage"""

    # Parse the input arguments and run the rawmapper(args)
    import argparse
    import textwrap

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(formatter_class=CustomFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n' 
                                            '  rawmapper /project/3022026.01/raw/\n'
                                            '  rawmapper /project/3022026.01/raw -d AcquisitionDate\n' 
                                            '  rawmapper /project/3022026.01/raw -s sub-100/ses-mri01 sub-126/ses-mri01\n'
                                            '  rawmapper /project/3022026.01/raw -r -d ManufacturerModelName AcquisitionDate --dryrun\n' 
                                            '  rawmapper raw/ -r -s sub-1*/* sub-2*/ses-mri01 --dryrun\n'
                                            '  rawmapper -d EchoTime -w *fMRI* /project/3022026.01/raw\n ')
    parser.add_argument('sourcefolder',      help='The source folder with the raw data in sub-#/ses-#/series organisation')
    parser.add_argument('-s','--sessions',   help='Space separated list of selected sub-#/ses-# names / folders to be processed. Otherwise all sessions in the bidsfolder will be selected', nargs='+')
    parser.add_argument('-d','--dicomfield', help='The name of the dicomfield that is mapped / used to rename the subid/sesid foldernames', default=['PatientComments'], nargs='+')
    parser.add_argument('-w','--wildcard',   help='The Unix style pathname pattern expansion that is used to select the series from which the dicomfield is being mapped (can contain wildcards)', default='*')
    parser.add_argument('-o','--outfolder',  help='The mapper-file is normally saved in sourcefolder or, when using this option, in outfolder')
    parser.add_argument('-r','--rename',     help='If this flag is given sub-subid/ses-sesid directories in the sourcefolder will be renamed to sub-dcmval/ses-dcmval', action='store_true')
    parser.add_argument('-n','--subprefix',  help='The prefix common for all the source subject-folders', default='sub-')
    parser.add_argument('-m','--sesprefix',  help='The prefix common for all the source session-folders', default='ses-')
    parser.add_argument('--dryrun',          help='Add this flag to dryrun (test) the mapping or renaming of the sub-subid/ses-sesid directories (i.e. nothing is stored on disk and directory names are not actually changed))', action='store_true')
    args = parser.parse_args()

    rawmapper(rawfolder  = args.sourcefolder,
              outfolder  = args.outfolder,
              sessions   = args.sessions,
              rename     = args.rename,
              dicomfield = args.dicomfield,
              wildcard   = args.wildcard,
              subprefix  = args.subprefix,
              sesprefix  = args.sesprefix,
              dryrun     = args.dryrun)


if __name__ == "__main__":
    main()
