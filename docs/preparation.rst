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

  The above organisation of one DICOMDIR file per subject or session is supported out of the box by the bidscoiner and bidsmapper. If you have a single multi-subject DICOMDIR file for your entire repository you can reorganize your data by running the `dicomsort <utilities.html#dicomsort>`__ utility beforehand.

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
   You can store your session data in any of the above data organizations as zipped (``.zip``) or tarzipped (e.g. ``.tar.gz``) archive files. BIDScoin `workflow tools <workflow.html>`__ will automatically unpack/unzip those archive files in a temporary folder and then process your session data from there. For flat/DICOMDIR data, BIDScoin tools (i.e. the bidsmapper and the bidscoiner) will automatically run `dicomsort <utilities.html#dicomsort>`__ in a temporary folder to sort them in seriesfolders. Depending on the data and file system, repeatedly unzipping data in the workflow may come with a significant processing speed penalty.

.. tip::
   BIDScoin will skip (Linux-style hidden) files and folders of which the name starts with a ``.`` (dot) character. You can use this feature to flexibly omit subjects, sessions or runs from your bids repository, for instance when you restarted an MRI scan because something went wrong with the stimulus presentation and you don't want that data to be converted and enumerated as ``run-1``, ``run-2``.

Recommended data acquisition conventions
----------------------------------------

BIDScoin can automatically recognize source datatypes on the basis of it's properties and attributes. Typically, in the DCCN users name their MR scan protocols in a meaningful way, which is therefore used as a basis for intelligent source datatype identification. For instance, if a functional fmri protocol is named "StopTask" or "fMRI_Stroop", the default bidsmap_dccn template will yield a positive 'func/bold' match, as it has the "task" and "fMRI" keywords in it's run-item regular expression: ``{ProtocolName: (?i).*(f.?MRI|task|BOLD|func|rest|RSN|CMRR.*_TR).*}``. Similarly, anatomical scans that have ``T1w`` or ``MPRAGE`` in their protocol name are identified as anat/T1w items, and fielmaps that have ``fmap``, ``fieldmap`` or ``B0map`` in their protocol name are identified as fieldmaps. On the other hand, if a functional scan is just named ``Stop``, the datatype cannot be correctly identified (at least not by the default template) and needs to be manually changed in the bidseditor from ``extra_data`` to ``func``. A robust way to acquire and convert your data is hence to use (BIDS-like) descriptive names for your protocols, or for any other attribute or property (such as filenames) that you may use to manage your data. For more details and keywords, see e.g. the `DCCN template bidsmap <https://github.com/Donders-Institute/bidscoin/blob/master/bidscoin/heuristics/bidsmap_dccn.yaml>`__.
