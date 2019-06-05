# BIDScoin

[![PyPI version](https://badge.fury.io/py/bidscoin.svg)](https://badge.fury.io/py/bidscoin)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bidscoin.svg)

- [The BIDScoin workflow](#the-bidscoin-workflow)
- [The BIDScoin tools](#the-bidscoin-tools)
  * [Running the bidsmapper](#running-the-bidsmapper)
  * [Running the bidseditor](#running-the-bidseditor)
  * [Running the bidscoiner](#running-the-bidscoiner)
- [The bidsmap files](#the-bidsmap-files)
  * [Tips and tricks](#tips-and-tricks)
    + [Attribute list](#attribute-list)
    + [Dynamic values](#dynamic-values)
    + [Field maps: IntendedFor](#field-maps-intendedfor)
    + [Plug-in functions](#plug-in-functions)
- [BIDScoin functionality / TODO](#bidscoin-functionality--todo)
- [BIDScoin tutorial](#bidscoin-tutorial)

BIDScoin is a user friendly [open-source](https://github.com/Donders-Institute/bidscoin) python toolkit that converts ("coins") source-level (raw) neuroimaging data-sets to [nifti](https://nifti.nimh.nih.gov/) / [json](https://www.json.org/) / [tsv](https://en.wikipedia.org/wiki/Tab-separated_values) data-sets that are organized following the Brain Imaging Data Structure, a.k.a. [BIDS](http://bids.neuroimaging.io) standard. Rather then depending on complex or ambiguous programmatic logic for the identification of imaging modalities, BIDScoin uses a direct mapping approach to identify and convert the raw source data into BIDS data. To information sources that can be used to map the source data to BIDS are:

 1. Information in MRI header files (DICOM, PAR/REC or .7 format; e.g. SeriesDescription)
 2. Information from nifti headers (e.g. image dimensionality)
 3. Information in the file structure (file- and/or directory names, e.g. number of files)

> NB: Currently, the DICOM support (option 1) has been fully implemented, but the support for option 2 and 3 is planned for [future](#bidscoin-functionality--todo) releases.

The mapping information is stored as key-value pairs in the human readable and widely supported [YAML](http://yaml.org/) files. The nifti- and json-files are generated with [dcm2niix](https://github.com/rordenlab/dcm2niix). In addition, users can provide custom written [plug-in functions](#plug-in-functions), e.g. for using additional sources of information or e.g. for parsing of Presentation logfiles.

Because all the mapping information can be edited with a graphical user interface, BIDScoin requires no programming knowledge in order to use it.

For information on the BIDScoin installation and requirements, see the [installation guide](./docs/installation.md).
 
## The BIDScoin workflow

### Required source data structure
BIDScoin will take your (raw) source data as well as a YAML file with the key-value mapping (dictionary) information as input, and returns a BIDS folder as output. The source data input folder should be organised according to a `/sub-identifier/[ses-identifier]/seriesfolder/dicomfile` structure. This data organization is how users receive their data from the (Siemens) scanners at the [DCCN](https://www.ru.nl/donders/) (NB: the `ses-identifier` sub-folder is optional and can be left out).

- If your data is not already organized in this way, you can use the [dicomsort.py](./bidscoin/dicomsort.py) command-line utility to move your unordered or DICOMDIR ordered DICOM-files into a `seriesfolder` organization with the DICOM series-folders being named [SeriesNumber]-[SeriesDescription]. Series folders contain a single data type and are typically acquired in a single run.
 
- Another command-line utility that can be helpful in organizing your source data is [rawmapper.py](.bidscoin/rawmapper.py). This utility can show you the overview (map) of all the values of DICOM-fields of interest in your data-set and, optionally, use these fields to rename your source data sub-folders (this can be handy e.g. if you manually entered subject-identifiers as [Additional info] at the scanner console and you want to use these to rename your subject folders).
 
> If these utilities do not satisfy your needs, then have a look at this [reorganize_dicom_files](https://github.com/robertoostenveld/bids-tools/blob/master/doc/reorganize_dicom_files.md) tool.

### Coining your source data to BIDS
Having an organized source data folder, the actual data-set conversion to BIDS can be performed fully automatically by simply running the `bidsmapper.py`, the `bidseditor.py` and the `bidscoiner.py` command-line tools after another:

#### Step 1: Running the bidsmapper

    usage: bidsmapper.py [-h] [-b BIDSMAP] [-n SUBPREFIX] [-m SESPREFIX]
                         sourcefolder bidsfolder
    
    Creates a bidsmap.yaml YAML file that maps the information from all raw source data to
    the BIDS labels (see also [bidsmap_template.yaml] and [bidstrainer.py]). You can check
    and edit the bidsmap.yaml file before passing it to [bidscoiner.py]
    
    positional arguments:
      sourcefolder          The source folder containing the raw data in
                            sub-#/ses-#/series format (or see below for different
                            prefixes)
      bidsfolder            The destination folder with the (future) bids data and
                            the default bidsfolder/code/bidsmap.yaml file
    
    optional arguments:
      -h, --help            show this help message and exit
      -b BIDSMAP, --bidsmap BIDSMAP
                            The non-default / site-specific bidsmap YAML-file with
                            the BIDS heuristics
      -n SUBPREFIX, --subprefix SUBPREFIX
                            The prefix common for all the source subject-folders.
                            Default: 'sub-'
      -m SESPREFIX, --sesprefix SESPREFIX
                            The prefix common for all the source session-folders.
                            Default: 'ses-'
    
    examples:
      bidsmapper.py /project/foo/raw /project/foo/bids
      bidsmapper.py /project/foo/raw /project/foo/bids -b bidsmap_dccn

The `bidsmapper.py` tool scans all source data folders of your dataset and saves the known and unknown key-value mappings in a [bidsmap file](#the-bidsmap-files). You can consider it as a dry-run for how exactly the [bidscoiner](#running-the-bidscoiner) will convert the source data into BIDS folders. It gives you the opportunity to inspect the resulting `bidsmap.yaml` file to see if all data types / runs were recognized correctly with proper BIDS labels before doing the actual conversion to BIDS. Unexpected mappings or poor BIDS labels can be found if your bidstraining or the bidsmap file that was provided to you was incomplete. In that case you should either get an updated bidsmap file or redo the bidstraining with new sample files, rerun the bidstrainer and bidsmapper until you have a suitable `bidsmap.yaml` file. You can of course also directly edit the `bidsmap.yaml` file yourself, for instance by changing some of the automatically generated BIDS labels to your needs (e.g. "task_label").

#### Step 2: Running the bidseditor

    usage: bidstrainer.py [-h] bidsfolder [samplefolder] [bidsmap]
    
    Takes example files from the samples folder as training data and creates a key-value
    mapping, i.e. a bidsmap_sample.yaml file, by associating the file attributes with the
    file's BIDS-semantic pathname
    
    positional arguments:
      bidsfolder    The destination folder with the bids data structure
      samplefolder  The root folder of the directory tree containing the sample
                    files / training data. Optional argument, if left empty,
                    bidsfolder/code/samples is used or such an empty directory
                    tree is created
      bidsmap       The bidsmap YAML-file with the BIDS heuristics (optional
                    argument, default: ./heuristics/bidsmap_template.yaml)
    
    optional arguments:
      -h, --help    show this help message and exit
    
    examples:
      bidstrainer.py /project/foo/bids
      bidstrainer.py /project/foo/bids /project/foo/samples bidsmap_custom

The core idea of the bidstrainer is that you know your own scan protocol and can therefore point out which files should go where in the BIDS. In order to do so, you have to place raw sample files for each of the BIDS data types / runs in your scan protocol (e.g. T1, fMRI, etc) in the appropriate folder of a semantic folder tree (named `samples`, see the [bidstrainer example](#bidstrainer-example)). If you run `bidstrainer.py` with just the name of your bidsfolder, bidstrainer will create this semantic folder tree for you in the `code` subfolder (if it is not already there). Generally, when placing your sample files, it will be fairly straightforward to find your way in this semantic folder tree, but in doubt you should have a look at the [BIDS specification](http://bids.neuroimaging.io/bids_spec.pdf). Note that the deepest foldername in the tree denotes the BIDS suffix (e.g. "T1w"). You do not need to place samples from your non-BIDS data types / runs (such as localizer or spectroscopy scans) in the folder tree, these data types will automatically go into the "extra_data" folder.

If all sample files have been put in the appropriate location, you can (re)run the bidstrainer to create a bidsmap file for your study. How this works is that, on one hand, the bidstrainer will read a predefined set of (e.g. key DICOM) attributes from each sample file and, on the other hand, take the path-names of the sample files to infer the associated BIDS modality. In this way, a list of unique key-value mappings between sets of (DICOM) attributes and sets of BIDS-labels is defined, the so-called [bidsmap](#the-bidsmap-files), that can be used as input for the [bidsmapper tool](#running-the-bidsmapper). If the predefined set of attributes does not uniquely identify your particular scan sequences (not likely but possible), or if you simply prefer to use more or other attributes, you can (copy and) edit the [bidsmap_template.yaml](./heuristics/bidsmap_template.yaml) file in the heuristics folder and re-run the bidstrainer with this customized template as an input argument.

<a name="bidstrainer-example">![Bidstrainer example](./docs/sample_tree.png)</a>
*Bidstrainer example. The red arrow depicts a raw data sample (left file browser) that is put (copied over) to the appropriate location in the semantic folder tree (right file browser)*

#### Step 3: Running the bidscoiner

    usage: bidscoiner.py [-h] [-p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]] [-f]
                         [-s] [-b BIDSMAP] [-n SUBPREFIX] [-m SESPREFIX] [-v]
                         sourcefolder bidsfolder
    
    Converts ("coins") datasets in the sourcefolder to nifti / json / tsv datasets in the
    bidsfolder according to the BIDS standard. Check and edit the bidsmap.yaml file to
    your needs before running this function. Provenance, warnings and error messages are
    stored in the ../bidsfolder/code/bidscoiner.log file
    
    positional arguments:
      sourcefolder          The source folder containing the raw data in
                            sub-#/ses-#/series format
      bidsfolder            The destination / output folder with the bids data
    
    optional arguments:
      -h, --help            show this help message and exit
      -p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...], --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                            Space seperated list of selected sub-# names / folders
                            to be processed (the sub- prefix can be removed).
                            Otherwise all subjects in the sourcefolder will be
                            selected
      -f, --force           If this flag is given subjects will be processed,
                            regardless of existing folders in the bidsfolder.
                            Otherwise existing folders will be skipped
      -s, --skip_participants
                            If this flag is given those subjects that are in
                            particpants.tsv will not be processed (also when the
                            --force flag is given). Otherwise the participants.tsv
                            table is ignored
      -b BIDSMAP, --bidsmap BIDSMAP
                            The bidsmap YAML-file with the study heuristics. If
                            the bidsmap filename is relative (i.e. no "/" in the
                            name) then it is assumed to be located in
                            bidsfolder/code/. Default: bidsmap.yaml
      -n SUBPREFIX, --subprefix SUBPREFIX
                            The prefix common for all the source subject-folders.
                            Default: 'sub-'
      -m SESPREFIX, --sesprefix SESPREFIX
                            The prefix common for all the source session-folders.
                            Default: 'ses-'
      -v, --version         Show the BIDS and BIDScoin version
    
    examples:
      bidscoiner.py /project/raw /project/bids
      bidscoiner.py -f /project/raw /project/bids -p sub-009 sub-030

The `bidscoiner.py` tool is the workhorse of the toolkit that will fully automatically convert your source-level (raw) MRI data-sets to BIDS organized data-sets. In order to do so, it needs a [bidsmap file](#the-bidsmap-files), which is typically created by running the [bidsmapper](#running-the-bidsmapper) tool. You can run `bidscoiner.py` after all data is collected, or whenever new data has been added to the raw folder (presuming the scan protocol hasn't changed).

After a successful run of `bidscoiner.py`, the work to convert your data in a fully compliant BIDS dataset is unfortunately not yet fully over and, depending on the complexity of your data-set, additional tools may need to be run and meta-data may need to be entered manually (not everything can be automated). For instance, you should update the content of the `dataset_description.json` and `README` files in your bids folder and you may need to provide e.g. additional `*_scans.tsv`,`*_sessions.tsv` or `participants.json` files (see the [BIDS specification](http://bids.neuroimaging.io/bids_spec.pdf) for more information). Moreover, if you have behavioural log-files you will find that BIDScoin does not (yet) [support](#bidscoin-functionality--todo) converting these into BIDS compliant `*_events.tsv/json` files (advanced users are encouraged to use the `bidscoiner.py` [plug-in](#plug-in-functions) possibility and write their own log-file parser).  

If all of the above work is done, you can (and should) run the web-based [bidsvalidator](https://bids-standard.github.io/bids-validator/) to check for inconsistencies or missing files in your bids data-set (NB: the bidsvalidator also exists as a [command-line tool](https://github.com/bids-standard/bids-validator)).

NB: The provenance of the produced BIDS data-sets is stored in the `bids/code/bidscoiner.log` file. This file is also very useful for debugging / tracking down bidsmapping issues.

## The bidsmap files

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

### Tips and tricks

#### Attribute list
The attribute value can also be a list, in which case a (DICOM) series is positively identified if its attribute value is in this list. If the attribute value is empty it is not used to identify the series

#### Dynamic values
The BIDS labels can be static, in which case the value is just a normal string, or dynamic, when the string is enclosed with pointy brackets like \<attribute name> or \<\<argument1>\<argument2>> (see the [example](#bidsmap-sample) above). In case of single pointy brackets the value will be replaced during bidsmapper and bidscoiner runtime by the value of the attribute with that name. In case of double pointy brackets, the value will be updated for each subject/session during bidscoiner runtime (e.g. the \<\<runindex>> value will be increased if a file with the same runindex already exists in that directory).
 
#### Field maps: IntendedFor
You can use the "IntendedFor" field to indicate for which runs (DICOM series) a fieldmap was intended. The dynamic value of the "IntendedFor" field can be a list of string patterns that is used to include those runs that have that string pattern in their nifti pathname (e.g. \<\<task>> to include all functional runs or \<\<Stop\*Go>\<Reward>> to include "Stop1Go"-, "Stop2Go"- and "Reward"-runs).

#### Plug-in functions
BIDScoin provides the possibility for researchers to write custom python functions that will be executed at bidsmapper.py and bidscoiner.py runtime. To use this functionality, enter the name of the module (default location is the plugins-folder; otherwise the full path must be provided) in the bidsmap dictionary file to import the plugin functions. The functions in the module should be named "bidsmapper_plugin" for bidsmapper.py and "bidscoiner_plugin" for bidscoiner.py. See [README.py](./bidscoin/plugins/README.py) for more details and placeholder code.

## BIDScoin functionality / TODO
- [x] DICOM source data
- [ ] PAR / REC source data
- [ ] P7 source data
- [ ] Nifti source data
- [x] Fieldmaps
- [x] Multi-echo data
- [x] Multi-coil data
- [x] PET data
- [ ] Stimulus / behavioural logfiles

Are you a python programmer with an interest in BIDS who knows all about GE and / or Philips data? Are you experienced with parsing stimulus presentation log-files? Or do you have ideas to improve the this toolkit or its documentation? Have you come across bugs? Then you are highly encouraged to provide feedback or contribute to this project on [https://github.com/Donders-Institute/bidscoin](https://github.com/Donders-Institute/bidscoin).

## BIDScoin tutorial
This tutorial is specific for researchers from the DCCN and makes use of data-sets stored on its central file-system. However, it should not be difficult to use (at least part of) this tutorial for other data-sets as well.
 
1. **Preparation.** Activate the bidscoin environment and create a tutorial playground folder in your home directory by executing these bash commands (see also `module help bidscoin`):  
   ```
   module add bidscoin  
   source activate /opt/bidscoin  
   cp -r /opt/bidscoin/tutorial ~
   ```
   The new `tutorial` folder contains a `raw` source-data folder and a `bids_ref` reference BIDS folder, i.e. the end product of this tutorial.
   
   Let's begin with inspecting this new raw data collection: 
   - Are the DICOM files for all the sub-*/ses-# folders organised in series-subfolders (e.g. sub-001/ses-01/003-T1MPRAGE/0001.dcm etc)? Use `dicomsort.py` if not
   - Use the `rawmapper.py` command to print out the DICOM values of the "EchoTime", "Sex" and "AcquisitionDate" of the fMRI series in the `raw` folder

2. **BIDS training.** Now that we have some source data and have inspected its properties, we are ready to start with the actual BIDS coining  process. The first step is to perform [training](#running-the-bidstrainer) on a few raw data samples:
   - Put files (training data) in the right subfolders in this `samples` tree
   - Create a `bids\code\samples` foldertree in your `tutorial` folder with this bash command:  
   ```
   cd ~/tutorial
   bidstrainer.py bids
   ```
   - Create a `bids/code/bidsmap_sample.yaml` bidsmap file by re-running the above `bidstrainer.py bids` command
   - Inspect the newly created bidsmap file. Can you recognise the key-value mappings? Which fields are going to end up in the filenames of the final BIDS datasets?
   
3. **BIDS mapping.** Scan all folders in the raw data collection for unknown data by running the [bidsmapper](#running-the-bidsmapper) bash command:  
   ```
   bidsmapper.py raw bids
   ```
   - Open the `bids/code/bidsmap.yaml` file and check the "extra_data" section for images that should go in the BIDS sections (e.g. T1, fMRI or DWI data). If so, add the missing training samples (check the messages in the command shell) to the `samples` folder tree and rerun the `bidstrainer.py bids` command.
   - In the `bids/code/bidsmap.yaml` file, rename the "task_label" of the functional scans into something more readable, e.g. "Reward" and "Stop"
   - Add a search pattern to the [IntendedFor](#field-maps-intendedfor) field such that it will select your fMRI runs
   - Change the options such that you will get non-zipped nifti data (i.e. `*.nii `instead of `*.nii.gz`) in your BIDS data collection
   
4. **BIDS coining.** Convert your raw data collection into a BIDS collection by running the bidscoiner bash command (note that the input is the same as for the bidsmapper):  
   ```
   bidscoiner.py raw bids
   ```
   - Check your `bids/code/bidscoiner.log` file for any errors or warnings 
   - Compare the results in your `bids/sub-#` subject folders with the  in `bids_ref` reference result. Are the file and foldernames the same? Also check the json sidecar files of the fieldmaps. Do they have the right "EchoTime" and "IntendedFor" fields?
   - What happens if you re-run the `bidscoiner.py` command? Are the same subjects processed again? Re-run "sub-001".
   - Inspect the `bids/participants.tsv` file and decide if it is ok.
   - Update the `dataset_description.json` and `README` files in your `bids` folder
   - As a final step, run the [bids-validator](https://github.com/bids-standard/bids-validator) on your `~/bids_tutorial` folder. Are you completely ready now to share this dataset?
