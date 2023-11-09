"""
Maps out the values of a DICOM attribute of all subjects in the sourcefolder, saves the result
in a mapper-file and, optionally, uses the DICOM values to rename the sub-/ses-id's of the
subfolders. This latter option can be used, e.g. when an alternative subject id was entered in
the [Additional info] field during subject registration at the scanner console (i.e. this data
is stored in the DICOM attribute named 'PatientComments')
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse
import textwrap


def get_parser():
    """Build an argument parser with input arguments for rawmapper.py"""

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass

    parser = argparse.ArgumentParser(prog='rawmapper',
                                     formatter_class=CustomFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n' 
                                            '  rawmapper myproject/raw\n'
                                            '  rawmapper myproject/raw -f AcquisitionDate\n' 
                                            '  rawmapper myproject/raw -s sub-100/ses-mri01 sub-126/ses-mri01\n'
                                            '  rawmapper myproject/raw -r -f ManufacturerModelName AcquisitionDate --dryrun\n' 
                                            '  rawmapper myproject/raw -r -s sub-1*/* sub-2*/ses-mri01 --dryrun\n'
                                            '  rawmapper -f EchoTime -w *fMRI* myproject/raw\n ')
    parser.add_argument('sourcefolder',     help='The source folder with the raw data in sub-#/ses-#/series organization')
    parser.add_argument('-s','--sessions',  help='Space separated list of selected sub-#/ses-# names / folders to be processed. Otherwise all sessions in the bidsfolder will be selected', nargs='+')
    parser.add_argument('-f','--field',     help='The fieldname(s) of the DICOM attribute(s) used to rename or map the subid/sesid foldernames', default=['PatientComments', 'ImageComments'], nargs='+')
    parser.add_argument('-w','--wildcard',  help='The Unix style pathname pattern expansion that is used to select the series from which the dicomfield is being mapped (can contain wildcards)', default='*')
    parser.add_argument('-o','--outfolder', help='The mapper-file is normally saved in sourcefolder or, when using this option, in outfolder')
    parser.add_argument('-r','--rename',    help='Rename sub-subid/ses-sesid directories in the sourcefolder to sub-dcmval/ses-dcmval', action='store_true')
    parser.add_argument('-c','--clobber',   help='Rename the sub/ses directories, even if the target-directory already exists', action='store_true')
    parser.add_argument('-n','--subprefix', help="The prefix common for all the source subject-folders. Use a '*' wildcard if there is no prefix", default='sub-')
    parser.add_argument('-m','--sesprefix', help="The prefix common for all the source session-folders. Use a '*' wildcard if there is no prefix or an empty value if there are no sessions", nargs='?', default='ses-')
    parser.add_argument('-d','--dryrun',    help='Dryrun (test) the mapping or renaming of the sub-subid/ses-sesid directories (i.e. nothing is stored on disk and directory names are not actually changed))', action='store_true')

    return parser
