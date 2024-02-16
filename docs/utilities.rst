Utilities
=========

bidscoin
--------

The bidscoin command-line utility serves as a central starting point to test and manage your BIDScoin installation

::

    usage: bidscoin [-h] [-l] [-p] [-i INSTALL [INSTALL ...]] [-u UNINSTALL [UNINSTALL ...]]
                    [-d DOWNLOAD] [-t [TEST]] [-b BIDSMAPTEST] [-c CREDITS [CREDITS ...]]
                    [--tracking {yes,no,show}] [-v]

    BIDScoin is a toolkit to convert raw data-sets according to the Brain Imaging Data Structure (BIDS)

    The basic workflow is to run these two tools:

      $ bidsmapper sourcefolder bidsfolder     # This produces a study bidsmap and launches a GUI
      $ bidscoiner sourcefolder bidsfolder     # This converts your data to BIDS according to the study bidsmap

    Default settings and template bidsmaps are stored in the `.bidscoin` folder in your home directory
    (you can modify the configuration files to your needs with any plain text editor)

    Set the environment variable `BIDSCOIN_DEBUG=TRUE` to run BIDScoin in a more verbose logging mode and
    `BIDSCOIN_CONFIGDIR=/writable/path/to/configdir` for using a different configuration (root) directory.
    Citation reports can be generated with the help of duecredit (https://github.com/duecredit/duecredit)

    For more documentation see: https://bidscoin.readthedocs.io

    options:
      -h, --help            show this help message and exit
      -l, --list            List all executables (i.e. the apps, bidsapps and utilities)
      -p, --plugins         List all installed plugins and template bidsmaps
      -i INSTALL [INSTALL ...], --install INSTALL [INSTALL ...]
                            A list of template bidsmaps and/or bidscoin plugins to install
      -u UNINSTALL [UNINSTALL ...], --uninstall UNINSTALL [UNINSTALL ...]
                            A list of template bidsmaps and/or bidscoin plugins to uninstall
      -d DOWNLOAD, --download DOWNLOAD
                            Download tutorial MRI data to the DOWNLOAD folder
      -t [TEST], --test [TEST]
                            Test the bidscoin installation and template bidsmap
      -b BIDSMAPTEST, --bidsmaptest BIDSMAPTEST
                            Test the run-items and their bidsnames of all normal runs in the study
                            bidsmap. Provide the bids-folder or the bidsmap filepath
      -c CREDITS [CREDITS ...], --credits CREDITS [CREDITS ...]
                            Show duecredit citations for your BIDS repository. You can also add duecredit
                            summary arguments (without dashes), e.g. `style {apa,harvard1}` or `format
                            {text,bibtex}`.
      --tracking {yes,no,show}
                            Show the usage tracking info {show}, or set usage tracking to {yes} or {no}
      -v, --version         Show the installed version and check for updates

    examples:
      bidscoin -l
      bidscoin -d data/bidscoin_tutorial
      bidscoin -t
      bidscoin -t my_template_bidsmap
      bidscoin -b my_study_bidsmap
      bidscoin -i data/my_template_bidsmap.yaml downloads/my_plugin.py
      bidscoin -c myproject/bids
      bidscoin -c myproject/bids format bibtex
      bidscoin --tracking show

dicomsort
---------

The ``dicomsort`` command-line tool is a utility to move your flat- or DICOMDIR-organized files (see `above <#required-source-data-structure>`__) into a 'seriesfolder' organization. This can be useful to organize your source data in a more convenient and human readable way (DICOMDIR or flat DICOM directories can often be hard to comprehend). The BIDScoin tools will run dicomsort in a temporary folder if your data is not already organized in series-folders, so in principle you don't really need to run it yourself (unless when you have a single multi-subject DICOMDIR file for your entire repository). Running dicomsort beforehand does, however, give you more flexibility in handling special cases that are not handled properly and it can also give you a speed benefit. If dicomsort do not satisfy your needs, then have a look at this `DICOM reorganize <https://github.com/robertoostenveld/bids-tools/blob/master/doc/reorganize_dicom_files.md>`__ tool.

::

    usage: dicomsort [-h] [-i SUBPREFIX] [-j SESPREFIX] [-f FOLDERSCHEME] [-n NAMESCHEME] [-p PATTERN]
                     [--force] [-d]
                     dicomsource

    Sorts and/or renames DICOM files into local subfolders, e.g. with 3-digit SeriesNumber-SeriesDescription
    folder names (i.e. following the same listing as on the scanner console)

    Supports flat DICOM as well as multi-subject/session DICOMDIR file structures.

    positional arguments:
      dicomsource           The root folder containing the dicomsource/[sub/][ses/] dicomfiles or the
                            DICOMDIR file

    options:
      -h, --help            show this help message and exit
      -i SUBPREFIX, --subprefix SUBPREFIX
                            Provide a prefix string to recursively sort dicomsource/subject subfolders
                            (e.g. "sub-" or "S_") (default: None)
      -j SESPREFIX, --sesprefix SESPREFIX
                            Provide a prefix string to recursively sort dicomsource/subject/session
                            subfolders (e.g. "ses-" or "T_") (default: None)
      -f FOLDERSCHEME, --folderscheme FOLDERSCHEME
                            Naming scheme for the sorted DICOM Series subfolders. Follows the Python
                            string formatting syntax with DICOM field names in curly bracers with an
                            optional number of digits for numeric fields. Sorting in subfolders is
                            skipped when an empty folderscheme is given (but note that renaming the
                            filenames can still be performed) (default:
                            {SeriesNumber:03d}-{SeriesDescription})
      -n NAMESCHEME, --namescheme NAMESCHEME
                            Optional naming scheme that can be provided to rename the DICOM files.
                            Follows the Python string formatting syntax with DICOM field names in curly
                            bracers with an optional number of digits for numeric fields. Use e.g. "{Pati
                            entName}_{SeriesNumber:03d}_{SeriesDescription}_{AcquisitionNumber:05d}_{Inst
                            anceNumber:05d}.dcm" or "{InstanceNumber:05d}_{SOPInstanceUID}.IMA" for
                            default names (default: None)
      -p PATTERN, --pattern PATTERN
                            The regular expression pattern used in re.match(pattern, dicomfile) to select
                            the DICOM files (default: .*\.(IMA|dcm)$)
      --force               Sort the DICOM data even the DICOM fields of the folder/name scheme are not
                            in the data (default: False)
      -d, --dryrun          Only print the dicomsort commands without actually doing anything (default:
                            False)

    examples:
      dicomsort raw/sub-011/ses-mri01
      dicomsort raw --subprefix sub- --sesprefix ses-
      dicomsort myproject/raw/DICOMDIR --subprefix pat^ --sesprefix
      dicomsort sub-011/ses-mri01/DICOMDIR -n {AcquisitionNumber:05d}_{InstanceNumber:05d}.dcm

rawmapper
---------

Another command-line utility that can be helpful in organizing your source data is ``rawmapper``. This utility can show you an overview (map) of all the values of DICOM-attributes of interest in your data-set and, optionally, used to rename your source data sub-folders. The latter option can be handy e.g. if you manually entered subject-identifiers as [Additional info] at the scanner console and you want to use these to rename your subject folders.

::

    usage: rawmapper [-h] [-s SESSIONS [SESSIONS ...]] [-f FIELD [FIELD ...]] [-w WILDCARD]
                     [-o OUTFOLDER] [-r] [-c] [-n SUBPREFIX] [-m [SESPREFIX]] [-d]
                     sourcefolder

    Maps out the values of a DICOM attribute of all subjects in the sourcefolder, saves the result
    in a mapper-file and, optionally, uses the DICOM values to rename the sub-/ses-id's of the
    subfolders. This latter option can be used, e.g. when an alternative subject id was entered in
    the [Additional info] field during subject registration at the scanner console (i.e. this data
    is stored in the DICOM attribute named 'PatientComments')

    positional arguments:
      sourcefolder          The source folder with the raw data in sub-#/ses-#/series organization

    options:
      -h, --help            show this help message and exit
      -s SESSIONS [SESSIONS ...], --sessions SESSIONS [SESSIONS ...]
                            Space separated list of selected sub-#/ses-# names / folders to be processed.
                            Otherwise all sessions in the bidsfolder will be selected (default: None)
      -f FIELD [FIELD ...], --field FIELD [FIELD ...]
                            The fieldname(s) of the DICOM attribute(s) used to rename or map the
                            subid/sesid foldernames (default: ['PatientComments', 'ImageComments'])
      -w WILDCARD, --wildcard WILDCARD
                            The Unix style pathname pattern expansion that is used to select the series
                            from which the dicomfield is being mapped (can contain wildcards) (default:
                            *)
      -o OUTFOLDER, --outfolder OUTFOLDER
                            The mapper-file is normally saved in sourcefolder or, when using this option,
                            in outfolder (default: None)
      -r, --rename          Rename sub-subid/ses-sesid directories in the sourcefolder to sub-dcmval/ses-
                            dcmval (default: False)
      -c, --clobber         Rename the sub/ses directories, even if the target-directory already exists
                            (default: False)
      -n SUBPREFIX, --subprefix SUBPREFIX
                            The prefix common for all the source subject-folders. Use a '*' wildcard if
                            there is no prefix (default: sub-)
      -m [SESPREFIX], --sesprefix [SESPREFIX]
                            The prefix common for all the source session-folders. Use a '*' wildcard if
                            there is no prefix or an empty value if there are no sessions (default: ses-)
      -d, --dryrun          Dryrun (test) the mapping or renaming of the sub-subid/ses-sesid directories
                            (i.e. nothing is stored on disk and directory names are not actually
                            changed)) (default: False)

    examples:
      rawmapper myproject/raw
      rawmapper myproject/raw -f AcquisitionDate
      rawmapper myproject/raw -s sub-100/ses-mri01 sub-126/ses-mri01
      rawmapper myproject/raw -r -f ManufacturerModelName AcquisitionDate --dryrun
      rawmapper myproject/raw -r -s sub-1*/* sub-2*/ses-mri01 --dryrun
      rawmapper -f EchoTime -w *fMRI* myproject/raw

bidsparticipants
----------------

The bidsparticipants tool is useful for (re-)generating a participants.tsv file from your source data (without having to run bidscoiner)

::

    usage: bidsparticipants [-h] [-k KEYS [KEYS ...]] [-d] [-b BIDSMAP] sourcefolder bidsfolder

    (Re)scans data sets in the source folder for subject metadata to populate the participants.tsv
    file in the bids directory, e.g. after you renamed (be careful there!), added or deleted data
    in the bids folder yourself.

    Provenance information, warnings and error messages are stored in the
    bidsfolder/code/bidscoin/bidsparticipants.log file.

    positional arguments:
      sourcefolder          The study root folder containing the raw source data folders
      bidsfolder            The destination / output folder with the bids data

    options:
      -h, --help            show this help message and exit
      -k KEYS [KEYS ...], --keys KEYS [KEYS ...]
                            Space separated list of the participants.tsv columns. Default: 'session_id'
                            'age' 'sex' 'size' 'weight'
      -d, --dryrun          Do not save anything, only print the participants info on screen
      -b BIDSMAP, --bidsmap BIDSMAP
                            The study bidsmap file with the mapping heuristics. If the bidsmap filename
                            is just the basename (i.e. no "/" in the name) then it is assumed to be
                            located in the current directory or in bidsfolder/code/bidscoin. Default:
                            bidsmap.yaml

    examples:
      bidsparticipants myproject/raw myproject/bids
      bidsparticipants myproject/raw myproject/bids -k participant_id age sex
