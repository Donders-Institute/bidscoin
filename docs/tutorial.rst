Tutorial
========

BIDS introduction and BIDScoin demo
-----------------------------------

A good starting point to learn more about BIDS and BIDScoin is to watch `this presentation <https://youtu.be/aRDK4Gj5qzE>`__ from the OpenMR Benelux 2020 meeting (`slides <https://osf.io/pm36z/>`__). The first 14 minutes Robert Oostenveld provides a general overview of the BIDS standard, after which Marcel Zwiers presents the design of BIDScoin and demonstrates hands-on how you can use it to convert a dataset to BIDS.

BIDScoin tutorial
-----------------

The tutorial below was written with the DCCN user in mind that wants to convert DICOM MRI data to BIDS. Nevertheless, the main principles also apply to other datasets, and you are encouraged to try out the assignments

1. Setting up the environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Depending on how BIDScoin was installed, you may have to set your Python environment settings before you can run BIDScoin commands from your command-line interface / shell. In the DCCN compute cluster example below it is assumed that an `environment module <https://modules.sourceforge.net/>`__ is used to load your Linux Anaconda Python installation and that BIDScoin is installed in a `conda environment <https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-with-commands>`__ named "bidscoin". Run or adjust these commands to your computer system if needed:

.. code-block:: console

   $ module add bidscoin                # Load the DCCN bidscoin module with the PATH settings and Anaconda environment
   $ source activate /opt/bidscoin      # Activate the Python virtual environment with the BIDScoin Python packages

Now you should be able to execute BIDScoin commands. Test this by running ``bidscoin`` to get a general workflow overview. Can you generate a list of all BIDScoin tools? What about the plugins? Test the bidscoin installation and make sure everything is ok

2. Data preparation
~~~~~~~~~~~~~~~~~~~

Create a tutorial playground folder by executing these shell commands:

.. code-block:: console

   $ bidscoin --download .              # Download the tutorial data (use a "." for the current folder or a pathname of choice to save it elsewhere)
   $ cd ./bidscointutorial              # Go to the downloaded data (replace "." with the full pathname if your data was saved elsewhere)

The new ``bidscointutorial`` folder contains a ``raw`` source-data folder and a ``bids_ref`` reference BIDS folder, i.e. the intended end product of this tutorial. In the raw folder you will find these DICOM series (aka "runs")::

   001-localizer_32ch-head                  A localizer scan that is not scientifically relevant and can be left out of the BIDS dataset
   002-AAHead_Scout_32ch-head               A localizer scan that is not scientifically relevant and can be left out of the BIDS dataset
   007-t1_mprage_sag_ipat2_1p0iso           An anatomical T1-weighted scan
   047-cmrr_2p4iso_mb8_TR0700_SBRef         A single-band reference scan of the subsequent multi-band functional MRI scan
   048-cmrr_2p4iso_mb8_TR0700               A multi-band functional MRI scan
   049-field_map_2p4iso                     The field-map magnitude images of the first and second echo. Set as "magnitude1", bidscoiner will recognize the format. This field map is intended for the previous functional MRI scan
   050-field_map_2p4iso                     The field-map phase difference image of the first and second echo
   059-cmrr_2p5iso_mb3me3_TR1500_SBRef      A single-band reference scan of the subsequent multi-echo functional MRI scan
   060-cmrr_2p5iso_mb3me3_TR1500            A multi-band multi-echo functional MRI scan
   061-field_map_2p5iso                     Idem, the field-map magnitude images of the first and second echo, intended for the previous functional MRI scan
   062-field_map_2p5iso                     Idem, the field-map phase difference image of the first and second echo

Let's begin with inspecting this new raw data collection:

- Are the DICOM files for all the ``bids/sub-*`` folders organized in series-subfolders (e.g. ``sub-001/ses-01/003-T1MPRAGE/0001.dcm`` etc)? Use `dicomsort <utilities.html#dicomsort>`__ if this is not the case (hint: it's not the case). A help text for all BIDScoin tools is available by running the tool with the ``-h`` or ``--help`` flag (e.g. ``rawmapper -h``)
- Use the `rawmapper <utilities.html#rawmapper>`__ command to print out the values of the "EchoTime", "PatientSex" and "AcquisitionDate" DICOM fields (hint: use ``-f``) of the fMRI series in the ``raw`` folder (hint: use ``-w``). You should find this result (NB: unfortunately in this tutorial sub-001 and sub-002 are identical phantoms)::

   subid    sesid   seriesname                        EchoTime  PatientSex  AcquisitionDate
   sub-001  ses-01  047-cmrr_2p4iso_mb8_TR0700_SBRef  39        O           20200428
   sub-002  ses-01  047-cmrr_2p4iso_mb8_TR0700_SBRef  39        O           20200428

3. BIDS mapping
~~~~~~~~~~~~~~~

Now we can make a study bidsmap, i.e. the mapping from DICOM source-files to BIDS target-files. To that end, scan all folders in the raw data collection by running the `bidsmapper <workflow.html#step-1a-running-the-bidsmapper>`__ command:

.. code-block:: console

   $ bidsmapper raw bids

- We only have one session per subject, so in the main GUI that appears (when all raw data has been scanned), remove the session label (and note how the output names simplify, omitting the session subfolders and labels)
- Edit the task and acquisition labels of the functional scans into something more readable, e.g. ``task-Reward`` for the ``mb8`` scans and ``task-Stop`` for the ``mb3me3`` scans. Also make the name of the T1 scan more user friendly, e.g. by naming the acquisition label simply ``acq-mprage``.
- Make the fieldmap scans more user friendly, e.g. by naming the acquisition label simply ``acq-2p4iso`` and ``acq-2p5iso``, and add a search pattern to the ``IntendedFor`` field such that the first field map will select your ``Reward`` runs and the second field map your ``Stop`` runs (see the `bidseditor <workflow.html#step-1b-running-the-bidseditor>`__ field map notes for more details)
- When all done, go to the ``Options`` tab and change the ``dcm2niix`` settings to get non-zipped NIfTI output data (i.e. ``*.nii`` instead of ``*.nii.gz``). Test the tool to see if it can run and, as a final step, save your bidsmap. You can always go back later to change any of your edits by running the `bidseditor <workflow.html#step-1b-running-the-bidseditor>`__ command line tool directly. Try that.

4. BIDS coining
~~~~~~~~~~~~~~~

The next step, converting the source data into a BIDS collection, is very simple to do (and can be repeated whenever new data has come in). To do this run the `bidscoiner <workflow.html#step-2-running-the-bidscoiner>`__ command-line tool (note that the input is the same as for the bidsmapper):

.. code-block:: console

   $ bidscoiner raw bids

- Check your ``bids/code/bidscoin/bidscoiner.log`` (the complete terminal output) and ``bids/code/bidscoin/bidscoiner.errors`` (the summary that is also printed at the end) files for any errors or warnings. You shouldn't have any :-)
- Compare the results in your ``bids/sub-*`` subject folders with the in ``bids_ref`` reference result. Are the file and folder names the same (don't worry about missing individual echo images, they are combined/generated as described below)? Also check the json sidecar files of the field maps. Do they have the right ``EchoTime`` and ``IntendedFor`` fields?
- What happens if you re-run the ``bidscoiner`` command? Are the same subjects processed again? Delete the ``bids/sub-001`` folder and re-run the ``bidscoiner`` command to recreate ``bids/sub-001``.

5. Finishing up
~~~~~~~~~~~~~~~

Now that you have converted the data to BIDS, you still need to do work to make it fully ready for data analysis and sharing. For instance:

- Combine the echos using the `echocombine <bidsapps.html#multi-echo-combination>`__ tool (see ``echocombine --help`` examples), such that the individual echo images are **replaced** by the echo-combined image
- Deface the anatomical scans of ``sub-001`` using the `deface <bidsapps.html#defacing>`__ tool. This will take a while, but will obviously not work well for our phantom dataset. Therefore store the 'defaced' output in the ``derivatives`` folder (instead of e.g. overwriting the existing images)
- Generate a QC report of the anatomical scans using the `slicereport <bidsapps.html#quality-control>`__ tool and open the ``bids/derivatives/slicereport/index.html`` file in your browser.
- Inspect the ``bids/participants.tsv`` file and decide if it is ok.
- Update the ``dataset_description.json`` and ``README`` files in your ``bids`` folder
- As a final step, run the `bids-validator <https://bids-standard.github.io/bids-validator/>`__ on your ``bidscointutorial/bids`` folder. Are you completely ready now to share this dataset?
