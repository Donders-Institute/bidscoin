Tutorial
========

This tutorial is specific for researchers from the DCCN and makes use of data-sets stored on its central file-system. However, it should not be difficult to use (at least part of) this tutorial for other data-sets as well.

1. **Preparation.** Activate the bidscoin environment and create a tutorial playground folder in your home directory by executing these bash commands (see also ``module help bidscoin``)::

   $ module add bidscoin
   $ source activate /opt/bidscoin
   $ cp -r /opt/bidscoin/tutorial ~

   The new ``tutorial`` folder contains a ``raw`` source-data folder and a ``bids_ref`` reference BIDS folder, i.e. the end product of this tutorial.

Let's begin with inspecting this new raw data collection: - Are the DICOM files for all the sub-\ */ses-* folders organised in series-subfolders (e.g. sub-001/ses-01/003-T1MPRAGE/0001.dcm etc)? Use ``dicomsort`` if not - Use the ``rawmapper`` command to print out the DICOM values of the "EchoTime", "Sex" and "AcquisitionDate" of the fMRI series in the ``raw`` folder

2. **BIDS mapping.** Scan all folders in the raw data collection for unknown data by running the `bidsmapper <#step-1a-running-the-bidsmapper>`__ bash command::

   $ bidsmapper raw bids

-  Rename the "task\_label" of the functional scans into something more readable, e.g. "Reward" and "Stop"
-  Add a search pattern to the IntendedFor field such that it will select your fMRI runs (see the `bidseditor <#step-1b-running-the-bidseditor>`__ ``fieldmap`` section for more details)
-  When all done, (re)open the ``bidsmap.yaml`` file and change the options such that you will get non-zipped nifti data (i.e. ``*.nii``\ instead of ``*.nii.gz``) in your BIDS data collection. You can use a text editor or, much better, run the `bidseditor <#step-1b-running-the-bidseditor>`__ command line tool.

3. **BIDS coining.** Convert your raw data collection into a BIDS collection by running the `bidscoiner <#step-2-running-the-bidscoiner>`__ commandline tool (note that the input is the same as for the bidsmapper)::

   $ bidscoiner raw bids

-  Check your ``bids/code/bidscoin/bidscoiner.log`` and ``bids/code/bidscoin/bidscoiner.errors`` files for any errors or warnings
-  Compare the results in your ``bids/sub-*`` subject folders with the in ``bids_ref`` reference result. Are the file and foldernames the same? Also check the json sidecar files of the fieldmaps. Do they have the right "EchoTime" and "IntendedFor" fields?
-  What happens if you re-run the ``bidscoiner`` command? Are the same subjects processed again? Re-run "sub-001".
-  Inspect the ``bids/participants.tsv`` file and decide if it is ok.
-  Update the ``dataset_description.json`` and ``README`` files in your ``bids`` folder
-  As a final step, run the `bids-validator <https://github.com/bids-standard/bids-validator>`__ on your ``~/bids_tutorial`` folder. Are you completely ready now to share this dataset?

