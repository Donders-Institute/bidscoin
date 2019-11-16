#!/usr/bin/env python
"""
Maps out the values of a dicom field of all subjects in the sourcefolder, saves
the result in a mapper-file and, optionally, uses the dicom values to rename
the sub-/ses-id's of the subfolders. This latter option can be used, e.g.
when an alternative subject id was entered in the [Additional info] field
during subject registration (i.e. stored in the PatientComments dicom field)
"""

import re
import warnings
from pathlib import Path
try:
    from bidscoin import bids
except ImportError:
    import bids         # This should work if bidscoin was not pip-installed


def rawmapper(rawfolder, outfolder: Path=Path(), sessions: list=[], rename: bool=False, dicomfield: tuple=('PatientComments',), wildcard: str='*', subprefix: str='sub-', sesprefix: str='ses-', dryrun: bool=False) -> None:
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
    rawfolder = Path(rawfolder)
    if not outfolder:
        outfolder = rawfolder
        print(f"Outfolder: {outfolder}")
    outfolder = Path(outfolder)

    # Create or append the output to a mapper logfile
    mapperfile = outfolder/f"rawmapper_{'_'.join(dicomfield)}.tsv"
    if not dryrun:
        if rename:
            with mapperfile.open('a') as fid:
                fid.write('subid\tsesid\tnewsubid\tnewsesid\n')
        else:
            with mapperfile.open('x') as fid:
                fid.write('subid\tsesid\tseriesname\t{}\n'.format('\t'.join(dicomfield)))

    # Map the sessions in the sourcefolder
    if not sessions:
        sessions = list(rawfolder.glob(f"{subprefix}*/{sesprefix}*"))
        if not sessions:
            sessions = rawfolder.glob(f"{subprefix}*")      # Try without session-subfolders
    else:
        sessions = [sessionitem for session in sessions for sessionitem in rawfolder.rglob(session)]

    # Loop over the selected sessions in the sourcefolder
    for session in sessions:

        # Get the subject and session identifiers from the raw folder
        subid, sesid = bids.get_subid_sesid(session)

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
                warnings.warn(f"Skipping renaming because the dicom-field was empty for: {session}")
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
                    warnings.warn(f"Skipping renaming of {session} because the dicom-field '{dcmval}' could not be parsed into [subid, sesid]")
                    continue
                if newsesid==sesprefix or newsesid==subprefix+'None':
                    newsesid = sesid
                    warnings.warn(f"Could not rename {sesid} because the dicom-field was empty for: {session}")

            # Save the dicomfield / sub-ses mapping to disk and rename the session subfolder (but skip if it already exists)
            newsession = rawfolder/newsubid/newsesid
            print(f"{session} -> {newsession}")
            if newsession == session:
                continue
            if newsession.is_dir():
                warnings.warn(f"{newsession} already exists, skipping renaming of {session}")
            elif not dryrun:
                with mapperfile.open('a') as fid:
                    fid.write(f"{subid}\t{sesid}\t{newsubid}\t{newsesid}\n")
                session.rename(newsession)

        # Print & save the dicom values
        else:
            print('{}/{}/{}\t-> {}'.format(subid, sesid, series.name, '\t'.join(dcmval.split('/'))))
            if not dryrun:
                with mapperfile.open('a') as fid:
                    fid.write('{}\t{}\t{}\t{}\n'.format(subid, sesid, series.name, '\t'.join(dcmval.split('/'))))


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
