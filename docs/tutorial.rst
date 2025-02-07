Tutorial
========

BIDS introduction and BIDScoin demo
-----------------------------------

A good starting point to learn more about BIDS and BIDScoin is to watch `this presentation <https://youtu.be/aRDK4Gj5qzE>`__ from the OpenMR Benelux 2020 meeting (`slides <https://osf.io/pm36z/>`__). The first 14 minutes Robert Oostenveld provides a general overview of the BIDS standard, after which Marcel Zwiers presents the design of BIDScoin and demonstrates hands-on how you can use it to convert a dataset to BIDS (the video is old but still somewhat useful).

BIDScoin tutorial
-----------------

The tutorial below was written with the DCCN user in mind that wants to convert DICOM MRI data to BIDS. Nevertheless, the main principles also apply to other datasets, and you are encouraged to try out the assignments

1. Setting up the environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Depending on how BIDScoin was installed, you may have to set your Python environment settings before you can run BIDScoin commands from your command-line interface/shell. This is already done for you when you run a `BIDScoin play <./play.html>`__ instance in the cloud. In the DCCN compute cluster example below it is assumed that an `environment module <https://modules.sourceforge.net/>`__ is used to load your Linux Anaconda Python installation and that BIDScoin is installed in a `conda environment <https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-with-commands>`__ named "bidscoin". Run or adjust these commands to your computer system if needed:

.. code-block:: console

   $ module add bidscoin                # Load the DCCN bidscoin module with the PATH settings and Anaconda environment
   $ source activate /opt/bidscoin      # Activate the Python virtual environment with the BIDScoin Python packages

Now you should be able to execute BIDScoin commands. Test this by running ``bidscoin`` to get a general workflow overview. Can you generate a list of all BIDScoin tools? What about the plugins? Test the bidscoin installation and make sure everything is OK

2. Data preparation
~~~~~~~~~~~~~~~~~~~

Create a tutorial playground folder by executing these shell commands:

.. code-block:: console

   $ bidscoin --download .              # Download the tutorial data (use a "." for the current folder or a pathname of choice to save it elsewhere)
   $ cd ./bidscointutorial              # Go to the downloaded data (replace "." with the full pathname if your data was saved elsewhere)

The new ``bidscointutorial`` folder contains a ``raw`` source-data folder and a ``bids_ref`` reference BIDS folder, i.e. the intended end product of this tutorial. In the raw folder you will find these DICOM Series folders (aka "runs")::

   bidscointutorial/raw/sub-001/ses-01/
   ├─ 001-localizer_32ch-head               A localizer scan that is not scientifically relevant and can be left out
   ├─ 002-AAHead_Scout_32ch-head            A localizer scan that is not scientifically relevant and can be left out
   ├─ 007-t1_mprage_sag_ipat2_1p0iso        An anatomical T1-weighted scan
   ├─ 047-cmrr_2p4iso_mb8_TR0700_SBRef      A single-band reference scan of the subsequent multi-band fMRI scan
   ├─ 048-cmrr_2p4iso_mb8_TR0700            A multi-band fMRI scan
   ├─ 049-field_map_2p4iso                  The field-map "magnitude1" images (intended for the previous fMRI scan)
   ├─ 050-field_map_2p4iso                  The field-map phase difference image
   ├─ 059-cmrr_2p5iso_mb3me3_TR1500_SBRef   A single-band reference scan of the subsequent multi-echo fMRI scan
   ├─ 060-cmrr_2p5iso_mb3me3_TR1500         A multi-band multi-echo fMRI scan
   ├─ 061-field_map_2p5iso                  Idem, the field-map "magnitude1" images (intended for the previous fMRI scan)
   ├─ 062-field_map_2p5iso                  Idem, the field-map phase difference image
   └─ behavioural                           NeuroBS Presentation log files

Let's begin with inspecting this new raw data collection:

- Are the DICOM files for all the ``bids/sub-*`` folders organized in series-subfolders (e.g. ``sub-001/ses-01/003-T1MPRAGE/0001.dcm`` etc)? Use `dicomsort <./utilities.html#dicomsort>`__ if this is not the case (hint: it's not the case). A help text for all BIDScoin tools is available by running the tool with the ``-h`` or ``--help`` flag (e.g. ``dicomsort -h``)
- Use the `rawmapper <./utilities.html#rawmapper>`__ command to print out the values of the "EchoTime", "PatientSex" and "AcquisitionDate" DICOM fields (see ``rawmapper -h``. Hint: use ``-f``) of the "cmrr" fMRI series in the ``raw`` folder (hint: also use ``-w``). You should find this result (NB: unfortunately in this tutorial sub-001 and sub-002 are identical phantoms)::

   subid    sesid   seriesname                        EchoTime  PatientSex  AcquisitionDate
   sub-001  ses-01  047-cmrr_2p4iso_mb8_TR0700_SBRef  39        O           20200428
   sub-002  ses-01  047-cmrr_2p4iso_mb8_TR0700_SBRef  39        O           20200428

3. BIDS mapping
~~~~~~~~~~~~~~~

Now we can make a study bidsmap, i.e. the mapping from DICOM source-files to BIDS target-files. To that end, scan all folders in the raw data collection by running the `bidsmapper <./workflow.html#step-1a-running-the-bidsmapper>`__ command:

.. code-block:: console

   $ bidsmapper raw bids

Mapping DICOM data
^^^^^^^^^^^^^^^^^^

In the first tab of the bidseditor window that now opened, you see a particpant table (top) and a samples table with a list of DICOM run-items being mapped to BIDS (bottom). Edit these tables as follows:

- By default, the participant label is parsed from the filepath with a regular expression pattern that extracts the substring between ``/raw/sub-`` and the first ``/`` character. Change the pattern to extract the substring between ``/raw/s`` and the first ``/`` character. Can you understand why the subject label is now ``sub-ub001`` instead of ``sub-001`` (if not, ask it to your favourite AI-assistant)? Go back to the original settings by clicking the reset button.
- We only have one session per subject, so in the main GUI that appears (when all raw data has been scanned), remove the ``session_id`` label. Note how the output names simplify, omitting the session subfolders and labels.
- Edit the "anat" sample and change the datatype to ``extra_data``. Hoover with your mouse over the orange filename to see what it means. No change the datatype to exclude the data to see what happens. Go back to the original settings by clicking the reset button. Now make the name of the T1 scan more user friendly, e.g. by naming the acquisition label simply ``acq-mprage``. Clcik OK to approve your edits and to go back to the main window.
- Next, edit the task and acquisition labels of the functional scans into something more readable, e.g. ``task-reward`` for the ``mb8`` scans and ``task-stop`` for the ``mb3me3`` scans. For the "reward" runs, add a tag of choice (e.g. "fmap1" or "fmap_reward") to the ``B0FieldSource`` field in the ``meta`` table. Likewise, add another tag to the "stop" runs (e.g. "fmap2" or "fmap_stop"). You also don't need the ``dir`` entity in the filenames, so remove these label values (and note how they disappear from the filename).
- Make the field map scans more user friendly, e.g. by simplifying the acquisition labels to ``acq-2p4iso`` and ``acq-2p5iso``. In both "2p4iso" fieldmap scans (magnitide and phasediff), add the same tag you used for the "reward" runs" to the ``B0FieldIdentifier`` field. If you like, you can also add a search pattern to the ``IntendedFor`` field such that it will select your ``reward`` runs (see the `field map notes <./bidsmap_features.html#field-maps>`__ for more details). Do the same for the "2p5iso" fieldmap scans, using the tag for the "stop" runs.
- Go back to the main window and check your edits by selecting all four "reward" func- and fmap-scans (use ctrl-or shift-click). Click with the right mouse button on a selected scan and choose ``Compare`` from the context menu that popped up. Are all your tags consistent?
- When all done, go to the ``Options`` tab and change the ``dcm2niix`` settings to get non-zipped NIfTI output data (i.e. ``*.nii`` instead of ``*.nii.gz``, see "dcm2niix -h" for help). Test the tool to see if it can run and, as a final step, save your bidsmap and close the editor. You can always go back later to change any of your edits by running the `bidseditor <./workflow.html#step-1b-running-the-bidseditor>`__ command-line tool directly. Try that.

Mapping Presentation log data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the second tab of the bidseditor window, you see a similar particpant table (top) and samples table with Presentation run-items. If you are not going to work with Presentation data, then you may skip the next paragraph.

.. dropdown:: Otherwise, click on the Presentation tab and continue as follows:

   - In the samples table you can see a "Flanker" run-item. Open it and change the data type to "func". In the meta table, write something meaningful in the ``TaskName`` field.
   - Clcik on the ``Edit`` button to tweak the events output data. You now get to see parsed input data on the left. Click on the ``Source`` button to inspect the raw text file. Scroll down and note that there are two tables in there -- the first one, which is the "events" table, is used as input (see the plugin `Options <./options.html#events2bids-plugin>`__). Close the inspection window.
   - In the middle panel, remove the ``trial_nr`` output column. Note that the column disappeared from the ``Events data`` table on the right. Click on the ``Reset`` button to undo any edits.
   - In ``Rows`` table of the middle panel, change the row condition ``Event_Type`` to include only "Picture" and "Response" rows, i.e. filter out the "Pulses": ``{'Event Type': '.*'}`` -> ``{'Event Type': 'Picture|Response'}``.
   - Add a new output collumn named "condition" that is "congruent" for the ``con_left`` and ``con_right`` input codes, and "incongruent" for the ``inc_left`` and ``inc_right`` input codes. To do so, in the bottom empty condition field, enter: ``{'Code': 'con.*'}`` and in the output field next to that enter: ``{'condition': 'congruent'}``. Note how a new output column has appeared. Now add the incongruent condition to the same new output collumn, i.e. enter ``{'Code': 'inc.*'}`` and ``{'condition': 'incongruent'}``.
   - In the timing table, set the clock to zero at the first scanner pulse, i.e. in the "start" field, change the value ``{'Code': 10}`` to ``{'Event Type': 'Pulse'}``. Did anything change in the output table? Why not? What if you change the value to ``{'Event Type': 'Response'}``?

4. BIDS coining
~~~~~~~~~~~~~~~

The next step—converting the source data into a BIDS collection—is straightforward and can be repeated whenever new data arrives. To do this, simply run the `bidscoiner <./workflow.html#step-2-running-the-bidscoiner>`__ command-line tool:

.. code-block:: console

   $ bidscoiner raw bids

- Check your ``bids/code/bidscoin/bidscoiner.log`` (the complete terminal output) and ``bids/code/bidscoin/bidscoiner.errors`` (the summary that is also printed at the end) files for any errors or warnings. You should not have any :-)
- Compare the results in your ``bids/sub-*`` subject folders with the in ``bids_ref`` reference result. Are the file and folder names the same (don't worry about missing individual echo images, they are combined/generated as described below)? Also check the json sidecar files of the field maps. Do they have the right ``EchoTime`` and ``B0FieldIdentifier``/``IntendedFor`` fields?
- What happens if you re-run the ``bidscoiner`` command? Are the same subjects processed again? Delete the ``bids/sub-001`` folder and re-run the ``bidscoiner`` command to recreate ``bids/sub-001``.

5. Finishing up
~~~~~~~~~~~~~~~

Now that you have converted the data to BIDS, you still need to do work to make it fully ready for data analysis and sharing. For instance:

- Combine the echos using the `echocombine <./bidsapps.html#multi-echo-combination>`__ tool (see ``echocombine --help`` examples), such that the echo-combined image is saved in the same func folder. Open the ``.bidsignore`` file in the bids directory and add a ``func/*_echo-*`` line. The individual echos will now be ignored by BIDS-apps that use func data.
- Deface the anatomical scans of ``sub-001`` using the `deface <./bidsapps.html#defacing>`__ tool (see ``deface --help``)). This will take a while, but will obviously not work well for our phantom dataset. Therefore store the 'defaced' output in the ``derivatives`` folder (instead of e.g. overwriting the existing images).
- Generate a QC report of the anatomical scans using the `slicereport <./bidsapps.html#quality-control>`__ tool (see ``slicereport -h``) and open the ``bids/derivatives/slicereport/index.html`` file in your browser.
- Inspect the ``bids/participants.tsv`` file and decide if it is OK.
- Update the ``dataset_description.json`` and ``README`` files in your ``bids`` folder
- As a final step, run the `bids-validator <https://bids-standard.github.io/bids-validator/>`__ on your ``bidscointutorial/bids`` folder. Are you completely ready now to share this dataset?
