Utilities
=========

dicomsort
---------

The ``dicomsort`` command-line tool is a utility to move your flat- or DICOMDIR-organized files (see `above <#required-source-data-structure>`__) into a 'seriesfolder' organization. This can be useful to organise your source data in a more convenient and human readable way (DICOMDIR or flat DICOM directories can often be hard to comprehend). The BIDScoin tools will run dicomsort in a temporary folder if your data is not already organised in series-folders, so in principle you don't really need to run it yourself (unless when you have a single multi-subject DICOMDIR file for your entire repository). Running dicomsort beforehand does, however, give you more flexibility in handling special cases that are not handled properly and it can also give you a speed benefit.

::

    usage: dicomsort.py [-h] [-i SUBPREFIX] [-j SESPREFIX] [-f FOLDERSCHEME] [-n NAMESCHEME] [-p PATTERN] [-d]
                        dicomsource

    Sorts and / or renames DICOM files into local subfolders, e.g. with 3-digit SeriesNumber-SeriesDescription
    folder names (i.e. following the same listing as on the scanner console)

    positional arguments:
      dicomsource           The root folder containing the dicomsource/[sub/][ses/] dicomfiles or the
                            DICOMDIR file

    optional arguments:
      -h, --help            show this help message and exit
      -i SUBPREFIX, --subprefix SUBPREFIX
                            Provide a prefix string for recursive sorting of dicomsource/subject
                            subfolders (e.g. "sub-") (default: None)
      -j SESPREFIX, --sesprefix SESPREFIX
                            Provide a prefix string for recursive sorting of dicomsource/subject/session
                            subfolders (e.g. "ses-") (default: None)
      -f FOLDERSCHEME, --folderscheme FOLDERSCHEME
                            Naming scheme for the sorted DICOM Series subfolders. Follows the Python string
                            formatting syntax with DICOM field names in curly bracers with an optional
                            number of digits for numeric fields. Sorting in subfolders is skipped when an
                            empty folderscheme is given (but note that renaming the filenames can still be
                            performed) (default: {SeriesNumber:03d}-{SeriesDescription})
      -n NAMESCHEME, --namescheme NAMESCHEME
                            Optional naming scheme that can be provided to rename the DICOM files. Follows
                            the Python string formatting syntax with DICOM field names in curly bracers with
                            an optional number of digits for numeric fields. Use e.g. "{PatientName}_{Series
                            Number:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{InstanceNumber:05d}.dcm"
                            or "{InstanceNumber:05d}_{SOPInstanceUID}.IMA" for default names (default: None)
      -p PATTERN, --pattern PATTERN
                            The regular expression pattern used in re.match(pattern, dicomfile) to select
                            the dicom files (default: .*\.(IMA|dcm)$)
      -d, --dryrun          Add this flag to just print the dicomsort commands without actually doing
                            anything (default: False)

    examples:
      dicomsort sub-011/ses-mri01
      dicomsort sub-011/ses-mri01/DICOMDIR -n {AcquisitionNumber:05d}_{InstanceNumber:05d}.dcm
      dicomsort /project/3022026.01/raw/DICOMDIR --subprefix sub- --sesprefix ses-

rawmapper
---------

Another command-line utility that can be helpful in organizing your source data is ``rawmapper``. This utility can show you an overview (map) of all the values of DICOM-attributes of interest in your data-set and, optionally, used to rename your source data sub-folders. The latter option can be handy e.g. if you manually entered subject-identifiers as [Additional info] at the scanner console and you want to use these to rename your subject folders.

::

    usage: rawmapper.py [-h] [-s SESSIONS [SESSIONS ...]] [-f FIELD [FIELD ...]] [-w WILDCARD]
                        [-o OUTFOLDER] [-r] [-n SUBPREFIX] [-m SESPREFIX] [-d]
                        sourcefolder

    Maps out the values of a dicom attribute of all subjects in the sourcefolder, saves the result in a
    mapper-file and, optionally, uses the dicom values to rename the sub-/ses-id's of the subfolders. This
    latter option can be used, e.g. when an alternative subject id was entered in the [Additional info]
    field during subject registration at the scanner console (i.e. this data is stored in the dicom
    attribute named 'PatientComments')

    positional arguments:
      sourcefolder          The source folder with the raw data in sub-#/ses-#/series organisation

    optional arguments:
      -h, --help            show this help message and exit
      -s SESSIONS [SESSIONS ...], --sessions SESSIONS [SESSIONS ...]
                            Space separated list of selected sub-#/ses-# names / folders to be processed.
                            Otherwise all sessions in the bidsfolder will be selected (default: None)
      -f FIELD [FIELD ...], --field FIELD [FIELD ...]
                            The fieldname(s) of the dicom attribute(s) used to rename or map the
                            subid/sesid foldernames (default: ['PatientComments'])
      -w WILDCARD, --wildcard WILDCARD
                            The Unix style pathname pattern expansion that is used to select the series
                            from which the dicomfield is being mapped (can contain wildcards) (default: *)
      -o OUTFOLDER, --outfolder OUTFOLDER
                            The mapper-file is normally saved in sourcefolder or, when using this option,
                            in outfolder (default: None)
      -r, --rename          If this flag is given sub-subid/ses-sesid directories in the sourcefolder will
                            be renamed to sub-dcmval/ses-dcmval (default: False)
      -n SUBPREFIX, --subprefix SUBPREFIX
                            The prefix common for all the source subject-folders (default: sub-)
      -m SESPREFIX, --sesprefix SESPREFIX
                            The prefix common for all the source session-folders (default: ses-)
      -d, --dryrun          Add this flag to dryrun (test) the mapping or renaming of the sub-subid/ses-
                            sesid directories (i.e. nothing is stored on disk and directory names are not
                            actually changed)) (default: False)

    examples:
      rawmapper /project/3022026.01/raw/
      rawmapper /project/3022026.01/raw -d AcquisitionDate
      rawmapper /project/3022026.01/raw -s sub-100/ses-mri01 sub-126/ses-mri01
      rawmapper /project/3022026.01/raw -r -d ManufacturerModelName AcquisitionDate --dryrun
      rawmapper raw/ -r -s sub-1*/* sub-2*/ses-mri01 --dryrun
      rawmapper -d EchoTime -w *fMRI* /project/3022026.01/raw

.. note::
   If these data management utilities do not satisfy your needs, then have a look at this `reorganize\_dicom\_files <https://github.com/robertoostenveld/bids-tools/blob/master/doc/reorganize_dicom_files.md>`__ tool.
