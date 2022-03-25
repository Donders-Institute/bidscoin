Data preparation
================

Required source data structure
------------------------------

Out of the box, BIDScoin requires that the source data repository is organized according to a ``subject/[session]/data`` structure (the ``session`` subfolder is optional). The data folder can be structured in various ways, as illustrated by the following examples:

1. **A 'seriesfolder' organization**. The data folder is organised in multiple series subfolders, each of which that contains a single data type that is typically acquired in a single run -- a.k.a 'Series' in DICOM speak. This is how users receive their data from the (Siemens) scanners at the `DCCN <https://www.ru.nl/donders/>`__::

    sourcedata
    |-- sub-001
    |   |-- ses-mri01
    |   |   |-- 001-localizer
    |   |   |   |-- 00001_1.3.12.2.1107.5.2.19.45416.2017121914582956872274162.IMA
    |   |   |   |-- 00002_1.3.12.2.1107.5.2.19.45416.2017121914583757650874172.IMA
    |   |   |   `-- 00003_1.3.12.2.1107.5.2.19.45416.2017121914583358068374167.IMA
    |   |   |
    |   |   |-- 002-t1_mprage_sag_p2_iso_1.0
    |   |   |   |-- 00002_1.3.12.2.1107.5.2.19.45416.2017121915051526005675150.IMA
    |   |   |   |-- 00003_1.3.12.2.1107.5.2.19.45416.2017121915051520026075138.IMA
    |   |   |   |-- 00004_1.3.12.2.1107.5.2.19.45416.2017121915051515689275130.IMA
    |   |   |   [..]
    |   |   [..]
    |   |
    |   `-- ses-mri02
    |       |-- 001-localizer
    |       |   |-- 00001_1.3.12.2.1107.5.2.19.45416.2017121914582956872274162.IMA
    |       |   |-- 00002_1.3.12.2.1107.5.2.19.45416.2017121914583757650874172.IMA
    |       |   `-- 00003_1.3.12.2.1107.5.2.19.45416.2017121914583358068374167.IMA
    |       [..]
    |
    |-- sub-002
    |   `-- ses-mri01
    |       |-- 001-localizer
    |       |   |-- 00001_1.3.12.2.1107.5.2.19.45416.2017121914582956872274162.IMA
    |       |   |-- 00002_1.3.12.2.1107.5.2.19.45416.2017121914583757650874172.IMA
    |       |   `-- 00003_1.3.12.2.1107.5.2.19.45416.2017121914583358068374167.IMA
    |       [..]
    [..]

2. **A 'DICOMDIR' organization**. The data folder contains a DICOMDIR file and multiple subfolders. A DICOMDIR is dictionary-file that indicates the various places where the DICOM files are stored. DICOMDIRs are often used in clinical settings and may look like::

    sourcedata
    |-- sub-001
    |   |-- DICOM
    |   |   `-- 00001EE9
    |   |       `-- AAFC99B8
    |   |           `-- AA547EAB
    |   |               |-- 00000025
    |   |               |   |-- EE008C45
    |   |               |   |-- EE027F55
    |   |               |   |-- EE03D17C
    |   |               |   [..]
    |   |               |
    |   |               |-- 000000B4
    |   |               |   |-- EE07CCDA
    |   |               |   |-- EE0E0701
    |   |               |   |-- EE0E200A
    |   |               |   [..]
    |   |               [..]
    |   `-- DICOMDIR
    |
    |-- sub-002
    |   [..]
    [..]

  The above organisation of one DICOMDIR file per subject or session is supported out of the box by the bidscoiner and bidsmapper. If you have a single multi-subject DICOMDIR file for your entire repository you can reorganize your data by running the `dicomsort <#dicomsort>`__ utility beforehand.

3. **A flat DICOM organization**. In a flat DICOM organization the data folder contains all the DICOM files of all the different Series without any subfolders. This organization is sometimes used when exporting data in clinical settings (the session sub-folder is optional)::

    sourcedata
    |-- sub-001
    |   `-- ses-mri01
    |       |-- IM_0001.dcm
    |       |-- IM_0002.dcm
    |       |-- IM_0003.dcm
    |       [..]
    |
    |-- sub-002
    |   `-- ses-mri01
    |       |-- IM_0001.dcm
    |       |-- IM_0002.dcm
    |       |-- IM_0003.dcm
    |       [..]
    [..]

4. **A PAR/REC organization**. All PAR/REC(/XML) files of all the different Series are contained in the data folder (without subfolders). This organization is how users often export their data from Philips scanners in research settings (the session sub-folder is optional)::

    sourcedata
    |-- sub-001
    |   `-- ses-mri01
    |       |-- TCHC_066_1_WIP_Hanneke_Block_2_SENSE_4_1.PAR
    |       |-- TCHC_066_1_WIP_Hanneke_Block_2_SENSE_4_1.REC
    |       |-- TCHC_066_1_WIP_IDED_SENSE_6_1.PAR
    |       |-- TCHC_066_1_WIP_IDED_SENSE_6_1.REC
    |       |-- TCHC_066_1_WIP_Localizer_CLEAR_1_1.PAR
    |       |-- TCHC_066_1_WIP_Localizer_CLEAR_1_1.REC
    |       [..]
    |
    |-- sub-002
    |   `-- ses-mri01
    |       |-- TCHC_066_1_WIP_Hanneke_Block_2_SENSE_4_1.PAR
    |       |-- TCHC_066_1_WIP_Hanneke_Block_2_SENSE_4_1.REC
    |       |-- TCHC_066_1_WIP_IDED_SENSE_6_1.PAR
    |       |-- TCHC_066_1_WIP_IDED_SENSE_6_1.REC
    |       |-- TCHC_066_1_WIP_Localizer_CLEAR_1_1.PAR
    |       |-- TCHC_066_1_WIP_Localizer_CLEAR_1_1.REC
    |       [..]
    [..]

.. note::
   You can store your session data in any of the above data organizations as zipped (``.zip``) or tarzipped (e.g. ``.tar.gz``) archive files. BIDScoin `workflow tools <workflow.html>`__ will automatically unpack/unzip those archive files in a temporary folder and then process your session data from there. For flat/DICOMDIR data, BIDScoin tools (i.e. the bidsmapper and the bidscoiner) will automatically run `dicomsort <#dicomsort>`__ in a temporary folder to sort them in seriesfolders. Depending on the data and file system, repeatedly unzipping data in the workflow may come with a significant processing speed penalty.

.. tip::
   BIDScoin will skip (linux-style hidden) files and folders starting with a `.` (dot) character. You can use this feature to flexibly omit subjects, sessions or runs from your bids repository, for instance when you restarted a MRI scan because something went wrong with the stimulus presentation and you don't want that data to be converted and enumerated as `run-1`, `run-2`.

Data management utilities
-------------------------

dicomsort
^^^^^^^^^

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
^^^^^^^^^

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
