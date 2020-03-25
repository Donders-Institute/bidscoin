Data preparation
================

Required source data structure
------------------------------

BIDScoin requires that the source data input folder is be organised according to a ``/sub-identifier/[ses-identifier]/seriesfolder/dicomfiles`` structure. This data organization is how users receive their data from the (Siemens) scanners at the `DCCN <https://www.ru.nl/donders/>`__ (NB: the ``ses-identifier`` sub-folder is optional and can be left out).

Data management utilitities
---------------------------

dicomsort
^^^^^^^^^

The ``dicomsort`` command-line tool is a utility to move your unordered or DICOMDIR ordered DICOM-files into a 'seriesfolder' organization (series folders contain a single data type and are typically acquired in a single run). This can be useful to organise your source data in a more convenient and human readable way, as DICOMDIR or flat DICOM directories can often be hard to comprehend. The BIDScoin tools will run ``dicomsort`` in a temporary folder if your data is not already organised in series-folders, so in principle you don't really need to run it yourself. Running ``dicomsort`` by yourself, does, however, give you more flexibility in handling special cases that are not handled properly and it can also give you a speed benefit.

::

    usage: dicomsort [-h] [-i SUBPREFIX] [-j SESPREFIX] [-f FIELDNAME] [-r]
                     [-e EXT] [-n] [-p PATTERN] [-d]
                     dicomsource
    
    Sorts and / or renames DICOM files into local subdirectories with a (3-digit) SeriesNumber-SeriesDescription directory name (i.e. following the same listing as on the scanner console)
    
    positional arguments:
      dicomsource           The name of the root folder containing the
                            dicomsource/[sub/][ses/]dicomfiles and / or the
                            (single session/study) DICOMDIR file
    
    optional arguments:
      -h, --help            show this help message and exit
      -i SUBPREFIX, --subprefix SUBPREFIX
                            Provide a prefix string for recursive searching in
                            dicomsource/subject subfolders (e.g. "sub") (default:
                            None)
      -j SESPREFIX, --sesprefix SESPREFIX
                            Provide a prefix string for recursive searching in
                            dicomsource/subject/session subfolders (e.g. "ses")
                            (default: None)
      -f FIELDNAME, --fieldname FIELDNAME
                            The dicomfield that is used to construct the series
                            folder name ("SeriesDescription" and "ProtocolName"
                            are both used as fallback) (default:
                            SeriesDescription)
      -r, --rename          Flag to rename the DICOM files to a PatientName_Series
                            Number_SeriesDescription_AcquisitionNumber_InstanceNum
                            ber scheme (recommended for DICOMDIR data) (default:
                            False)
      -e EXT, --ext EXT     The file extension after sorting (empty value keeps
                            the original file extension), e.g. ".dcm" (default: )
      -n, --nosort          Flag to skip sorting of DICOM files into SeriesNumber-
                            SeriesDescription directories (useful in combination
                            with -r for renaming only) (default: False)
      -p PATTERN, --pattern PATTERN
                            The regular expression pattern used in
                            re.match(pattern, dicomfile) to select the dicom files
                            (default: .*\.(IMA|dcm)$)
      -d, --dryrun          Add this flag to just print the dicomsort commands
                            without actually doing anything (default: False)
    
    examples:
      dicomsort /project/3022026.01/raw
      dicomsort /project/3022026.01/raw --subprefix sub
      dicomsort /project/3022026.01/raw --subprefix sub-01 --sesprefix ses
      dicomsort /project/3022026.01/raw/sub-011/ses-mri01/DICOMDIR -r -e .dcm

rawmapper
^^^^^^^^^

Another command-line utility that can be helpful in organizing your source data is ``rawmapper``. This utility can show you the overview (map) of all the values of DICOM-fields of interest in your data-set and, optionally, use these fields to rename your source data sub-folders (this can be handy e.g. if you manually entered subject-identifiers as [Additional info] at the scanner console and you want to use these to rename your subject folders).

::

    usage: rawmapper [-h] [-s SESSIONS [SESSIONS ...]]
                     [-d DICOMFIELD [DICOMFIELD ...]] [-w WILDCARD]
                     [-o OUTFOLDER] [-r] [-n SUBPREFIX] [-m SESPREFIX]
                     [--dryrun]
                     sourcefolder

    Maps out the values of a dicom field of all subjects in the sourcefolder, saves
    the result in a mapper-file and, optionally, uses the dicom values to rename
    the sub-/ses-id's of the subfolders. This latter option can be used, e.g.
    when an alternative subject id was entered in the [Additional info] field
    during subject registration (i.e. stored in the PatientComments dicom field)

    positional arguments:
      sourcefolder          The source folder with the raw data in
                        sub-#/ses-#/series organisation

    optional arguments:
      -h, --help            show this help message and exit
      -s SESSIONS [SESSIONS ...], --sessions SESSIONS [SESSIONS ...]
                        Space separated list of selected sub-#/ses-# names /
                        folders to be processed. Otherwise all sessions in the
                        bidsfolder will be selected (default: None)
      -d DICOMFIELD [DICOMFIELD ...], --dicomfield DICOMFIELD [DICOMFIELD ...]
                        The name of the dicomfield that is mapped / used to
                        rename the subid/sesid foldernames (default:
                        ['PatientComments'])
      -w WILDCARD, --wildcard WILDCARD
                        The Unix style pathname pattern expansion that is used
                        to select the series from which the dicomfield is
                        being mapped (can contain wildcards) (default: *)
      -o OUTFOLDER, --outfolder OUTFOLDER
                        The mapper-file is normally saved in sourcefolder or,
                        when using this option, in outfolder (default: None)
      -r, --rename          If this flag is given sub-subid/ses-sesid directories
                        in the sourcefolder will be renamed to sub-dcmval/ses-
                        dcmval (default: False)
      -n SUBPREFIX, --subprefix SUBPREFIX
                        The prefix common for all the source subject-folders
                        (default: sub-)
      -m SESPREFIX, --sesprefix SESPREFIX
                        The prefix common for all the source session-folders
                        (default: ses-)
      --dryrun              Add this flag to dryrun (test) the mapping or renaming
                        of the sub-subid/ses-sesid directories (i.e. nothing
                        is stored on disk and directory names are not actually
                        changed)) (default: False)

    examples:
      rawmapper /project/3022026.01/raw/
      rawmapper /project/3022026.01/raw -d AcquisitionDate
      rawmapper /project/3022026.01/raw -s sub-100/ses-mri01 sub-126/ses-mri01
      rawmapper /project/3022026.01/raw -r -d ManufacturerModelName AcquisitionDate --dryrun
      rawmapper raw/ -r -s sub-1*/* sub-2*/ses-mri01 --dryrun
      rawmapper -d EchoTime -w *fMRI* /project/3022026.01/raw

.. note::
   If these data management utilities do not satisfy your needs, then have a look at this `reorganize\_dicom\_files <https://github.com/robertoostenveld/bids-tools/blob/master/doc/reorganize_dicom_files.md>`__ tool.

