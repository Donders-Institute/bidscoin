# bidscoiner
Maps source-level neuroimaging data onto a BIDS data structure

BIDScoiner maps the data in your [raw] data folder to a [sourcedata] BIDS data folder. The key-value mapping is based (in opposite order) on:

1) Information in the MRI header files (DICOM, PAR/REC or .7 format)
2) Information from nifti headers (e.g. image dimensionality)
3) Information in the file structure (file- and/or directory names)

So, key-value mapping from the file structure takes precedence over key-value mapping from the nifti headers, which takes precedence over key-value mapping from the MRI headers.

The mapping to map the (currently only DICOM header) attributes to the BIDS labels can be built using the following pipeline:
1) bidsmapper.yaml -> bidstrainer.py  -> bidsmapper_sample.yaml (from template to a first mapping)
2) bidsmapper_sample.yaml -> bidsmapper.py -> bidsmap.yaml (user editable mapping)
3) bidsmap.yaml    -> bidscoiner.py  -> the nifti-converted BIDS datastructure (runs fully automatic)

Step 1 would only be needed when starting from scratch. When you have built up a large bidsmapper file (e.g. by adding many different bidsmapper_sample files into a large bidsmapper_site.yaml) you can run step 2 and step 3 fully automatically. It would always be good to inspect the bidsmapper (i.e. after step 2) before feeding it into step 3.
