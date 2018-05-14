# bidscoiner
Maps source-level neuroimaging data onto a BIDS data structure

BIDScoiner maps the data in your [raw] data folder to a [sourcedata] BIDS data folder. The key-value mapping is based (in opposite order) on:

1) Information in the MRI header files (DICOM, PAR/REC or .7 format)
2) Information from nifti headers (e.g. image dimensionality)
3) Information in the file structure (file- and/or directory names)

So, key-value mapping from the file structure takes precedence over key-value mapping from the nifti headers, which takes precedence over key-value mapping from the MRI headers.

The mapping to map the (currently only DICOM header) attributes to the BIDS labels can be built using the following pipeline:
1) bidsmap.yaml    -> bidstrainer.py  -> bidsmapper.yaml (from template to a first mapping)
2) bidsmapper yaml -> bidsmapper.py -> bidsmap.yaml (user editable mapping)
3) bidsmap.yaml    -> bidscoiner.py  -> the nifti-converted BIDS datastructure (runs fully automatic)
