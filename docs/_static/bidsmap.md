# The bidsmap files

A bidsmap file contains a collection of key-value dictionaries that define unique mappings between different types of raw data files (e.g. DICOM series) and their corresponding BIDS labels. As bidsmap files are both inputs as well as outputs for the different BIDScoin tools (except for `bidscoiner.py`, which has BIDS data as output; see the [BIDScoin workflow](#bidscoin-workflow)), they are derivatives of eachother and, as such, share the same basic structure. The [bidsmap_template.yaml](./heuristics/bidsmap_template.yaml) file is relatively empty and defines only which attributes (but not their values) are mapped to which BIDS-labels. The [bidsmap_[sample/site].yaml](#bidsmap-sample) file contains actual attribute values (e.g. from training samples from a certain study or site) and their associated BIDS-values. The final [bidsmap.yaml](./heuristics) file contains the attribute and associated BIDS values for all types of data found in entire raw data collection.

A bidsmap file consists of help-text, followed by several mapping sections, i.e. `Options`, `DICOM`, `PAR`, `P7`, `Nifti`, `FileSystem` and `Plugin`. Within each of these sections there different sub-sections for the different BIDS modalities, i.e. for `anat`, `func`, `dwi`, `fmap`, `pet` and `beh`. There are a few additional sub-sections, i.e. `participant_label`, `session_label` and `extra_data`. Schematically, a bidsmap file has the following structure:

 - **Options** *(A list of general options that can be passed to the bidscoiner and its plug-ins)*
 - **DICOM**
   - participant_label [a DICOM field]
   - session_label [a DICOM field]
   - anat
     - attributes
       - [a DICOM field]
       - [another DICOM field]
       - [..]
     - acq_label
     - rec_label
     - run_index
     - mod_label
     - modality_label
     - ce_label
   - func
     - attributes
       - [a DICOM field]
       - [another DICOM field]
       - [..]
     - task_label
     - acq_label
     - [..]
   - dwi
     - [..]
   - fmap
     - [..]
   - beh
     - [..]
   - pet
     - [..]
   - extra_data *(all non-BIDS data)*
     - [..]
 - **PAR**.
 - **P7**.
 - **Nifti**.
 - **FileSystem**.
 - **PlugIn**. Name of the python plug-in function. Supported but this is an experimental (untested) feature

Inside each BIDS modality, there can be multiple key-value mappings that map (e.g. DICOM) modality [attributes] to the BIDS [labels] (e.g. `task_label`), as indicated below:

<img name="bidsmap-sample" src="./docs/bidsmap_sample.png" alt="bidsmap_sample example" width="700">

*Bidsmap_sample example. As indicated by the solid arrowline, the set of DICOM values (suitable to uniquely identify the DICOM series) are used here a key-set that maps onto the set of BIDS labels. Note that certain BIDS labels are enclosed by pointy brackets, marking their [dynamic value](#dynamic-values). In this bidsmap, as indicated by the dashed arrowline, that means that \<ProtocolName> will be replaced in a later stage by "t1_mprage_sag_p2_iso_1.0". Also note that in this bidsmap there was only one T1-image, but there were two different fMRI runs (here because of multi-echo, but multiple tasks could also be listed)*

The `participant_label` and `session_label` sub-sections can be used to set the subject/session-labels using DICOM values instead of the subject/session-labels from the sourcefolder (e.g. when the subject- and/or session-label was entered at the scanner console). The `extra_data` sub-section will contain all series that were not identified otherwise.
