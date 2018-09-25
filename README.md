# BIDScoiner

BIDScoiner is a python toolkit that converts source-level (raw) MRI data-sets to nifti data-sets that are organized according to the Brain Imaging Data Standard, a.k.a. [BIDS](bids.neuroimaging.io). Rather then depending on logic, BIDScoiner uses a straightforward key-value approach to map the source data onto BIDS. The key values that can be used in BIDScoiner to map ("coin") the data are:

 1. Information in the MRI header files (DICOM, PAR/REC or .7 format, e.g. SeriesDescription)
 2. Information from nifti headers (e.g. image dimensionality)
 3. Information in the file structure (file- and/or directory names, e.g. number of files)

Currently, BIDScoiner is fully functional, although only option (1) has been implemented. (NB: Options (2) and (3) are planned for future versions, such that (3) takes precedence over (2), which in turn takes precedence over (1)).

BIDScoiner is a command-line tool that requires no programming knowledge in order to use it, just some basic file handling and, possibly, minor text editing.

## The BIDScoiner workflow

BIDScoiner will take your raw data as well as a [YAML](http://yaml.org/) file with the key-value mapping information as input, and returns a BIDS folder as output. Here is how to prepare the BIDScoiner inputs:

 1. **A minimally organised raw data folder**, following a  
 /raw/sub-[identifier]/ses-[identifier]/[seriesfolder]/[dicomfile]  
 structure. This data organization is how users receive their data from the (Siemens) scanners at the DCCN (NB: the ses-[identifier] sub-folder is optional and can be left out). 

    If your data is not already organized in this way, you can use the *dicomsort.py* command-line utility to move your unordered dicom-files into a [seriesfolder] organization with the series folders being named [SeriesNumber]-[SeriesDescription].
 
    Another command-line utility that can be helpful in organizing your raw data is *rawmapper.py*. This utility can show you the overview (map) of all the values of dicom-fields of interest in your data-set and, optionally, use these fields to rename your raw data sub-folders (this can be handy e.g. if you manually entered subject-identifiers at the scanner console and you want to use these to rename your subject folders).
 
    If the previous utilities do not satisfy your needs, then have a look at this more elaborate [reorganize_dicom_files](https://github.com/robertoostenveld/bids-tools/blob/master/doc/reorganize_dicom_files.md) tool.

 2. **A YAML file with the key-value mapping information**, i.e. a bidsmap.  There are two ways to create such a bidsmap.

    The first is if you are a new user and are working from scratch. In this case you would start with the *bidstrainer.py* tool (see *the bidstrainer* section below).

    If you have run the bidstrainer or, e.g. if you work in an institute where someone else (i.e. your MR physicist ;-)) has already performed the training procedure, you can use the training data to map all the files in your data-set with the *bidsmapper.py* tool (see *the bidsmapper* section below).

    The output of the bidsmapper is the desired bidsmap that you can inspect to see if your raw data will be correctly mapped onto BIDS. If this is not the case you can go back to the training procedure and change or add new samples, and rerun the bidsmapper until you have a correct bidsmap. Alternatively, or in addition to, you can directly edit the bidsmap yourself (this requires more expert knowledge but can also be more powerful). 
      
Having an organized raw data folder and a correct bidsmap, the actual data-set conversion to BIDS can now be performed fully automatically by running the *bidscoiner.py* tool (see the workflow diagram and *the bidscoiner* section below).

> TODO: insert workflow diagram here
> bidsmapper.yaml -> bidstrainer.py  -> bidsmapper_sample.yaml (from template to a first mapping)
> bidsmapper_sample.yaml -> bidsmapper.py -> bidsmap.yaml (user editable mapping)
> bidsmap.yaml    -> bidscoiner.py  -> the nifti-converted BIDS datastructure (runs fully automatic)

## The BIDScoiner tools

### The bidstrainer

    usage: bidstrainer.py [-h] bidsfolder [samplefolder] [bidsmapper]
    
    Takes example files from the samples folder to create a bidsmapper config file
    
    positional arguments:
      bidsfolder    The destination folder with the bids data structure
      samplefolder  The root folder of the directory tree containing the sample
                    files / training data. Optional argument, if left empty,
                    bidsfolder/code/samples is used or such an empty directory
                    tree is created
      bidsmapper    The bidsmapper yaml-file with the BIDS heuristics (optional
                    argument, default: ./heuristics/bidsmapper.yaml)
    
    optional arguments:
      -h, --help    show this help message and exit
    
    example:
      bidsmapper.py /project/foo/bids
      bidsmapper.py /project/foo/bids /project/foo/samples bidsmapper_dccn

The bidstrainer reads attributes from sample files that are placed by the user at the right location in a hierarchical folder structure. The full pathname is indicative for the BIDS modality and the lowest foldername signifies the BIDS suffix. Which attributes are read can be defined in a bidsmapper yaml file that serves as a template for the final bidsmap. In this way, a unique key-value mapping can be defined for each of the sample files.
      
### The bidsmapper

    usage: bidsmapper.py [-h] [-a] rawfolder bidsfolder [bidsmapper]
    
    Creates a bidsmap.yaml config file that maps the information from the data to the
    BIDS modalities and BIDS labels (see also [bidsmapper.yaml] and [bidsmapper.py]).
    You can edit the bidsmap file before passing it to [bidscoiner.py] which uses it
    to cast the datasets into the BIDS folder structure
    
    positional arguments:
      rawfolder        The source folder containing the raw data in
                       sub-#/ses-#/series format
      bidsfolder       The destination folder with the bids data structure
      bidsmapper       The bidsmapper yaml-file with the BIDS heuristics (optional
                       argument, default: bidsfolder/code/bidsmapper_sample.yaml)
    
    optional arguments:
      -h, --help       show this help message and exit
      -a, --automatic  If this flag is given the user will not be asked for help
                       if an unknown series is encountered
    
    example:
      bidsmapper.py /project/foo/raw /project/foo/bids
      bidsmapper.py /project/foo/raw /project/foo/bids bidsmapper_dccn

### The bidscoiner

    usage: bidscoiner.py [-h] [-s [SUBJECTS [SUBJECTS ...]]] [-f] [-p]
                         [-b BIDSMAP]
                         rawfolder bidsfolder
    
    Converts datasets in the rawfolder to nifti datasets in the bidsfolder according to the BIDS standard
    
    positional arguments:
      rawfolder             The source folder containing the raw data in
                            sub-#/ses-#/series format
      bidsfolder            The destination folder with the bids data structure
    
    optional arguments:
      -h, --help            show this help message and exit
      -s [SUBJECTS [SUBJECTS ...]], --subjects [SUBJECTS [SUBJECTS ...]]
                            Space seperated list of selected sub-# names / folders
                            to be processed. Otherwise all subjects in the
                            rawfolder will be selected
      -f, --force           If this flag is given subjects will be processed,
                            regardless of existing folders in the bidsfolder.
                            Otherwise existing folders will be skipped
      -p, --participants    If this flag is given those subjects that are in
                            particpants.tsv will not be processed (also when the
                            --force flag is given). Otherwise the participants.tsv
                            table is ignored
      -b BIDSMAP, --bidsmap BIDSMAP
                            The bidsmap yaml-file with the study heuristics. If
                            the bidsmapfile is relative (i.e. no "/" in the name)
                            then it is assumed to be located in bidsfolder/code/.
                            Default: bidsmap.yaml
    
    examples:
      bidscoiner.py /project/raw /project/bids
      bidscoiner.py -f /project/raw /project/bids -s sub-009 sub-030

## The BIDScoiner bidsmap
