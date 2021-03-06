Demo and tutorial
=================

BIDS introduction and BIDScoin demo
-----------------------------------

A good starting point to learn more about BIDS and BIDScoin is to watch `this presentation <https://youtu.be/aRDK4Gj5qzE>`__ from the OpenMR Benelux 2020 meeting (`slides <https://osf.io/pm36z/>`__). The first 14 minutes `Robert Oostenveld <https://openmrbenelux.github.io/page-speakers/#robert>`__ provides a general overview of the BIDS standard, after which `Marcel Zwiers <https://www.linkedin.com/in/mzwiers>`__ presents the design of BIDScoin and demonstrates hands-on how you can use it to convert a dataset to BIDS.

Hands-on tutorial
-----------------

The following tutorial is somewhat tailored to the dataflow in the DCCN (e.g. using the module system to set the BIDScoin shell environment), but should nevertheless make the basic parts of the BIDScoin workflow clear for everyone.

1. **Preparation.** Activate the bidscoin environment and create a tutorial playground folder in your home directory by executing these bash commands (see also ``module help bidscoin``):

.. code-block:: console

   $ module add bidscoin
   $ source activate /opt/bidscoin
   $ pulltutorialdata
   $ cd bidscointutorial

The new ``bidscointutorial`` folder contains a ``raw`` source-data folder and a ``bids_ref`` reference BIDS folder, i.e. the intended end product of this tutorial. In the ``raw`` folder you will find these DICOM series:

::

   001-localizer_32ch-head                  A localizer scan that is not scientifically relevant and can be left out of the BIDS dataset
   002-AAHead_Scout_32ch-head               A localizer scan that is not scientifically relevant and can be left out of the BIDS dataset
   007-t1_mprage_sag_ipat2_1p0iso           An anatomical T1-weighted scan
   047-cmrr_2p4iso_mb8_TR0700_SBRef         A single-band reference scan of the subsequent multi-band functional MRI scan
   048-cmrr_2p4iso_mb8_TR0700               A multi-band functional MRI scan
   049-field_map_2p4iso                     The fieldmap magnitude images of the first and second echo. Set as "magnitude1", bidscoiner will recognize the format. This fieldmap is intended for the previous functional MRI scan
   050-field_map_2p4iso                     The fieldmap phase difference image of the first and second echo
   059-cmrr_2p5iso_mb3me3_TR1500_SBRef      A single-band reference scan of the subsequent multi-echo functional MRI scan
   060-cmrr_2p5iso_mb3me3_TR1500            A multi-band multi-echo functional MRI scan
   061-field_map_2p5iso                     Idem, the fieldmap magnitude images of the first and second echo, intended for the previous functional MRI scan
   062-field_map_2p5iso                     Idem, the fieldmap phase difference image of the first and second echo

Let's begin with inspecting this new raw data collection:

- Are the DICOM files for all the ``bids/sub-*`` folders organised in series-subfolders (e.g. ``sub-001/ses-01/003-T1MPRAGE/0001.dcm`` etc)? Use `dicomsort <preparation.html#dicomsort>`__ if this is not the case. A help text for all BIDScoin tools is available by running the tool with the ``-h`` flag (e.g. ``rawmapper -h``)
- Use the `rawmapper <preparation.html#rawmapper>`__ command to print out the DICOM values of the "EchoTime", "Sex" and "AcquisitionDate" of the fMRI series in the ``raw`` folder

2. **BIDS mapping.** Now we can make a ``bidsmap``, i.e. the mapping from DICOM source-files to BIDS target-files. To that end, scan all folders in the raw data collection by running the `bidsmapper <workflow.html#step-1a-running-the-bidsmapper>`__ command:

.. code-block:: console

   $ bidsmapper raw bids

-  In the GUI that appears, rename the task and acquisition label of the functional scans into something more readable, e.g. ``task-Reward`` for the ``acq-mb8`` scans and "task-Stop" for the ``acq-mb3me3 scans``. Also make the name of the T1 scan more pleasant, e.g. by naming the aquisition label simply ``acq-mprage``.
-  Add a search pattern to the IntendedFor field such that it will select your fMRI runs correctly (see the `bidseditor <workflow.html#step-1b-running-the-bidseditor>`__ ``fieldmap`` section for more details)
-  Since for this dataset we only have one session per subject, remove the session label (and note how the output names simplify, omitting the session subfolders and labels)
-  When all done, (re)open the ``bidsmap.yaml`` file and change the options such that you will get non-zipped nifti data (i.e. ``*.nii`` instead of ``*.nii.gz``) in your BIDS data collection. You can use a text editor or, much better, run the `bidseditor <workflow.html#step-1b-running-the-bidseditor>`__ command line tool.

3. **BIDS coining.** The next step is very simple (and can be repeated when new data comes in) and just applies the previously made bidsmap when converting the source data into a BIDS collection. To do this run the `bidscoiner <workflow.html#step-2-running-the-bidscoiner>`__ commandline tool (note that the input is the same as for the bidsmapper):

.. code-block:: console

   $ bidscoiner raw bids

-  Check your ``bids/code/bidscoin/bidscoiner.log`` (the complete terminal output) and ``bids/code/bidscoin/bidscoiner.errors`` (the summary that is also printed at the end) files for any errors or warnings. You shouldn't have any :-)
-  Compare the results in your ``bids/sub-*`` subject folders with the in ``bids_ref`` reference result. Are the file and foldernames the same (don't worry about the multi-echo images and the ``extra_data`` images, they are combined/generated as described below)? Also check the json sidecar files of the fieldmaps. Do they have the right "EchoTime" and "IntendedFor" fields?
-  What happens if you re-run the `bidscoiner <workflow.html#step-2-running-the-bidscoiner>`__ command? Are the same subjects processed again? Re-run "sub-001".

4. **Finishing up.** Now that you have converted the data to BIDS, you still need to do some manual work to make it fully ready for data analysis and sharing

-  Combine the echos using the `echocombine <finalizing.html#multi-echo-combination>`__ tool, such that the individual echo images are replaced by the ech-combined image
-  Deface the anatomical scans using the `echocombine <finalizing.html#multi-echo-combination>`__ tool. This will take a while, but will obviously not work well for our phantom dataset. Therefore store the 'defaced' output in the ``extra_data`` folder (instead of e.g. overwriting the existing images)
-  Inspect the ``bids/participants.tsv`` file and decide if it is ok.
-  Update the ``dataset_description.json`` and ``README`` files in your ``bids`` folder
-  As a final step, run the `bids-validator <https://bids-standard.github.io/bids-validator/>`__ on your ``~/bids_tutorial`` folder. Are you completely ready now to share this dataset?
