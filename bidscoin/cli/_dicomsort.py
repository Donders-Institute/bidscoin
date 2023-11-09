"""
Sorts and/or renames DICOM files into local subfolders, e.g. with 3-digit SeriesNumber-SeriesDescription
folder names (i.e. following the same listing as on the scanner console)

Supports flat DICOM as well as multi-subject/session DICOMDIR file structures.
"""

# Imports from the standard library only (as these are imported during the cli/manpage build process)
import argparse
import textwrap


def get_parser():
    """Build an argument parser with input arguments for dicomsort.py"""

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass

    parser = argparse.ArgumentParser(prog='dicomsort',
                                     formatter_class=CustomFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  dicomsort raw/sub-011/ses-mri01\n'
                                            '  dicomsort raw --subprefix sub- --sesprefix ses-\n'
                                            '  dicomsort myproject/raw/DICOMDIR --subprefix pat^ --sesprefix\n'
                                            '  dicomsort sub-011/ses-mri01/DICOMDIR -n {AcquisitionNumber:05d}_{InstanceNumber:05d}.dcm\n ')
    parser.add_argument('dicomsource',          help='The root folder containing the dicomsource/[sub/][ses/] dicomfiles or the DICOMDIR file')
    parser.add_argument('-i','--subprefix',     help='Provide a prefix string to recursively sort dicomsource/subject subfolders (e.g. "sub-" or "S_")')
    parser.add_argument('-j','--sesprefix',     help='Provide a prefix string to recursively sort dicomsource/subject/session subfolders (e.g. "ses-" or "T_")')
    parser.add_argument('-f','--folderscheme',  help='Naming scheme for the sorted DICOM Series subfolders. Follows the Python string formatting syntax with DICOM field names in curly bracers with an optional number of digits for numeric fields. Sorting in subfolders is skipped when an empty folderscheme is given (but note that renaming the filenames can still be performed)', default='{SeriesNumber:03d}-{SeriesDescription}')
    parser.add_argument('-n','--namescheme',    help='Optional naming scheme that can be provided to rename the DICOM files. Follows the Python string formatting syntax with DICOM field names in curly bracers with an optional number of digits for numeric fields. Use e.g. "{PatientName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d}.dcm" or "{InstanceNumber:05d}_{SOPInstanceUID}.IMA" for default names')
    parser.add_argument('-p','--pattern',       help='The regular expression pattern used in re.match(pattern, dicomfile) to select the DICOM files', default=r'.*\.(IMA|dcm)$')
    parser.add_argument('--force',              help='Sort the DICOM data even the DICOM fields of the folder/name scheme are not in the data', action='store_true')
    parser.add_argument('-d','--dryrun',        help='Only print the dicomsort commands without actually doing anything', action='store_true')

    return parser
