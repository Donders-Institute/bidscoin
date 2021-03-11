The BIDScoin workflow
=====================

With a sufficiently `organized source data folder <preparation.html>`__, the data conversion to BIDS can be performed by running the `(1a) <#step-1a-running-the-bidsmapper>`__ the ``bidsmapper``, `(1b) <#step-1b-running-the-bidseditor>`__ the ``bidseditor`` and `(2) <#step-2-running-the-bidscoiner>`__ the ``bidscoiner`` command-line tools. The ``bidsmapper`` starts by making a map of the different kind of datatypes (scans) in your source dataset, which you can then edit with the ``bidseditor``. The ``bidscoiner`` reads this so-called study bidsmap, which tells it how exactly to convert the source data into BIDS.

.. figure:: ./_static/bidsmap_flow.png

   Creation and application of a study bidsmap

By default (but see the ``-i`` option of the bidsmapper below), step 1a automatically launches step 1b, so in it's simplest form, all you need to do to convert your raw source data into BIDS is to run two simple commands, e.g.:

.. code-block:: console

    $ bidsmapper sourcefolder bidsfolder
    $ bidscoiner sourcefolder bidsfolder

If you add new subjects all you need to do is re-run the ``bidscoiner`` -- unless the scan protocol was changed, then you also need to first re-run the ``bidsmapper`` to add the new samples to the study bidsmap.

Step 1a: Running the bidsmapper
-------------------------------

::

    usage: bidsmapper [-h] [-b BIDSMAP] [-t TEMPLATE] [-n SUBPREFIX]
                      [-m SESPREFIX] [-i {0,1,2}] [-v]
                      sourcefolder bidsfolder

    Creates a bidsmap.yaml YAML file in the bidsfolder/code/bidscoin that maps the
    information from all raw source data to the BIDS labels. You can check and edit
    the bidsmap file with the bidseditor (but also with any text-editor) before
    passing it to the bidscoiner. See the bidseditor help for more information and
    useful tips for running the bidsmapper in interactive mode (the default).

    positional arguments:
      sourcefolder          The study root folder containing the raw data in
                            sub-#/[ses-#/]data subfolders (or specify --subprefix
                            and --sesprefix for different prefixes)
      bidsfolder            The destination folder with the (future) bids data and
                            the bidsfolder/code/bidscoin/bidsmap.yaml output file

    optional arguments:
      -h, --help            show this help message and exit
      -b BIDSMAP, --bidsmap BIDSMAP
                            The bidsmap YAML-file with the study heuristics. If
                            the bidsmap filename is relative (i.e. no "/" in the
                            name) then it is assumed to be located in
                            bidsfolder/code/bidscoin. Default: bidsmap.yaml
      -t TEMPLATE, --template TEMPLATE
                            The bidsmap template with the default heuristics (this
                            could be provided by your institute). If the bidsmap
                            filename is relative (i.e. no "/" in the name) then it
                            is assumed to be located in bidsfolder/code/bidscoin.
                            Default: bidsmap_dccn.yaml
      -n SUBPREFIX, --subprefix SUBPREFIX
                            The prefix common for all the source subject-folders.
                            Default: 'sub-'
      -m SESPREFIX, --sesprefix SESPREFIX
                            The prefix common for all the source session-folders.
                            Default: 'ses-'
      -s, --store           Flag to store the provenance data samples in the
                            bidsfolder/'code'/'provenance' folder
      -i {0,1,2}, --interactive {0,1,2}
                            {0}: The sourcefolder is scanned for different kinds
                            of scans without any user interaction. {1}: The
                            sourcefolder is scanned for different kinds of scans
                            and, when finished, the resulting bidsmap is opened
                            using the bidseditor. {2}: As {1}, except that already
                            during scanning the user is asked for help if a new
                            and unknown run is encountered. This option is most
                            useful when re-running the bidsmapper (e.g. when the
                            scan protocol was changed since last running the
                            bidsmapper). Default: 1
      -v, --version         Show the BIDS and BIDScoin version

    examples:
      bidsmapper /project/foo/raw /project/foo/bids
      bidsmapper /project/foo/raw /project/foo/bids -t bidsmap_template

After the source data has been scanned, the bidsmapper will automatically launch `step 1b <#step-1b-running-the-bidseditor>`__. For a fully automated workflow users can skip this interactive step using the ``-i`` option (see above).

.. tip::
   The default template bidsmap (``-t bidsmap_dccn``) is customized for acquisitions at the DCCN. If this bidsmap is not working well for you, consider `adapting it to your needs <advanced.html#site-specific-customized-template>`__ so that the bidsmapper can recognize more of your scans and map them to BIDS the way you prefer.

Step 1b: Running the bidseditor
-------------------------------

::

    usage: bidseditor [-h] [-b BIDSMAP] [-t TEMPLATE] [-d DATAFORMAT]
                      [-n SUBPREFIX] [-m SESPREFIX]
                      bidsfolder

    This tool launches a graphical user interface for editing the bidsmap.yaml file
    that is produced by the bidsmapper. The user can fill in or change the BIDS labels
    for entries that are unidentified or sub-optimal, such that meaningful and nicely
    readable BIDS output names will be generated. The saved bidsmap.yaml output file
    will be used by the bidscoiner to actually convert the source data to BIDS.

    You can hoover with your mouse over items to get help text (pop-up tooltips).

    positional arguments:
      bidsfolder        The destination folder with the (future) bids data

    optional arguments:
      -h, --help        show this help message and exit
      -b BIDSMAP, --bidsmap BIDSMAP
                        The bidsmap YAML-file with the study heuristics. If
                        the bidsmap filename is relative (i.e. no "/" in the
                        name) then it is assumed to be located in
                        bidsfolder/code/bidscoin. Default: bidsmap.yaml
      -t TEMPLATE, --template TEMPLATE
                        The bidsmap template with the default heuristics (this
                        could be provided by your institute). If the bidsmap
                        filename is relative (i.e. no "/" in the name) then it
                        is assumed to be located in bidsfolder/code/bidscoin.
                        Default: bidsmap_dccn.yaml
      -d DATAFORMAT, --dataformat DATAFORMAT
                        The format of the source data, e.g. DICOM or PAR.
                        Default: DICOM
      -n SUBPREFIX, --subprefix SUBPREFIX
                        The prefix common for all the source subject-folders.
                        Default: 'sub-'
      -m SESPREFIX, --sesprefix SESPREFIX
                        The prefix common for all the source session-folders.
                        Default: 'ses-'

    examples:
      bidseditor /project/foo/bids
      bidseditor /project/foo/bids -t bidsmap_template.yaml
      bidseditor /project/foo/bids -b my/custom/bidsmap.yaml

As shown below, the main window of the bidseditor opens with the ``BIDS map`` tab that contains a list of ``input samples`` that uniquely represents all the different files that are present in the source folder, together with the associated ``BIDS output name``. The path in the ``BIDS output name`` is shown in red if the modality is not part of the BIDS standard, striked-out gray when the runs will be ignored in the conversion to BIDS, otherwise it is colored green. Double clicking the sample (DICOM) filename opens an inspection window with the full header information (double clicking sample filenames works throughout the GUI).

\ |Bidseditor main window|\

The user can click the ``Edit`` button for each list item to open a new edit window, as show below. In this interface, the right BIDS ``Modality`` (drop down menu) and the ``suffix`` label (drop down menu) can set correctly, after which the associated BIDS ``Labels`` can be edited (double click black items). As a result, the new BIDS ``Output name`` is then shown in the bottom text field. This is a preview of the BIDS output data, if that looks satisfactory (NB: green text indicates that  BIDS valid), the user can store this mapping to the bidsmap and return to the main window by clicking the ``OK`` button. Editing the source attributes of a study bidsmap is usually not necessary and adviced against. See `The bidsmap explained <bidsmap.html#special-features>`__ for more explanation about the special bidsmap feautures.

\ |Bidseditor edit window|\

Finally, if all BIDS output names in the main window are fine, the user can click on the ``Save`` button and proceed with running the bidscoiner tool. Note that the bidsmapper and bidseditor don't do anything except reading from and writing to the ``bidsmap.yaml`` file.

Fieldmaps
^^^^^^^^^

The way fieldmaps are acquired and stored varies considerably between sequences and manufacturers, and may therefore require special treatment. For instance, it could be that you have ``magnitude1`` and ``magnitude2`` data in one series-folder (which is what Siemens can do). In that case you should select the ``magnitude1`` suffix and let bidscoiner automatically pick up the other magnitude image during runtime. The same holds for ``phase1`` and ``phase2`` data. The suffix ``magnitude`` can be selected for sequences that save fielmaps directly. See the `BIDS specification <https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data>`__ for more details on fieldmap suffixes.

Fieldmaps are typically acquired to be applied to specific other scans from the same session. If this is the case then you should indicate this in the ``IntendedFor`` field, either using a single search string or multiple `dynamic strings <bidsmap.html#special-features>`__ to select the runs that have that string pattern in their BIDS file name. For instance you can use ``task`` to select all functional runs or use ``<<Stop*Go><Reward>>`` to select "Stop1Go"-, "Stop2Go"- and "Reward"-runs. NB: bidsapps may not use the fieldmap at all if this field is left empty!

Step 2: Running the bidscoiner
------------------------------

::

    usage: bidscoiner [-h] [-p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]] [-f]
                      [-s] [-b BIDSMAP] [-n SUBPREFIX] [-m SESPREFIX] [-v]
                      sourcefolder bidsfolder

    Converts ("coins") datasets in the sourcefolder to nifti / json / tsv datasets in the
    bidsfolder according to the BIDS standard. Check and edit the bidsmap.yaml file to
    your needs using the bidseditor tool before running this function. You can run
    bidscoiner after all data is collected, or run / re-run it whenever new data has
    been added to the source folder (presuming the scan protocol hasn't changed). If you
    delete a (subject/) session folder from the bidsfolder, it will be re-created from the
    sourcefolder the next time you run the bidscoiner. Image tags indicating properties
    such as echo-number or complex data can be appended to the "acq" value if the BIDS
    datatype does not provide for this (e.g. "sub-01_acq-MEMPRAGE_T1w.nii" becomes
    "sub-01_acq-MEMPRAGEe1_T1w.nii")

    Provenance information, warnings and error messages are stored in the
    bidsfolder/code/bidscoin/bidscoiner.log file.

    positional arguments:
      sourcefolder          The source folder containing the raw data in
                            sub-#/[ses-#]/data format (or specify --subprefix and
                            --sesprefix for different prefixes)
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
                            bidsfolder/code/bidscoin. Default: bidsmap.yaml
      -n SUBPREFIX, --subprefix SUBPREFIX
                            The prefix common for all the source subject-folders.
                            Default: 'sub-'
      -m SESPREFIX, --sesprefix SESPREFIX
                            The prefix common for all the source session-folders.
                            Default: 'ses-'
      -v, --version         Show the BIDS and BIDScoin version

    examples:
      bidscoiner /project/foo/raw /project/foo/bids
      bidscoiner -f /project/foo/raw /project/foo/bids -p sub-009 sub-030

.. tip::
   Check your json sidecar files of your fieldmaps, in particular see if they have the expected ``IntendedFor`` values.

.. note::
   The provenance of the produced BIDS data-sets is stored in the ``[bidsfolder]/code/bidscoin/bidscoiner.log`` file. This file is also very useful for debugging / tracking down bidscoin issues.

.. |Bidseditor main window| image:: ./_static/bidseditor_main.png
.. |Bidseditor edit window| image:: ./_static/bidseditor_edit.png
