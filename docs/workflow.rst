The BIDScoin workflow
=====================

Having an organized source data folder, the actual data-set conversion
to BIDS is performed by the `(1a) <#step-1a-running-the-bidsmapper>`__
the ``bidsmapper``, `(1b) <#step-1b-running-the-bidseditor>`__ the
``bidseditor`` and `(2) <#step-2-running-the-bidscoiner>`__ the
``bidscoiner`` command-line tools. The ``bidsmapper`` makes a map of the
different kind of datatypes in your source dataset, with the
``bidseditor`` you can edit this map, and the ``bidscoiner`` does the
actual work to convert the source data into BIDS. By default (but see
the ``-i`` option of the bidsmapper below), step 1a automatically
launches step 1b, so in it's simplest form, all you need to do to
convert your raw source data into BIDS is to run two simple commands,
e.g.:

::

    bidsmapper sourcefolder bidsfolder
    bidscoiner sourcefolder bidsfolder

Step 1a: Running the bidsmapper
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    usage: bidsmapper.py [-h] [-b BIDSMAP] [-t TEMPLATE] [-n SUBPREFIX]
                         [-m SESPREFIX] [-i {0,1,2}] [-v]
                         sourcefolder bidsfolder

    Creates a bidsmap.yaml YAML file in the bidsfolder/code/bidscoin that maps the information
    from all raw source data to the BIDS labels. You can check and edit the bidsmap file with
    the bidseditor (but also with any text-editor) before passing it to the bidscoiner. See the
    bidseditor help for more information and useful tips for running the bidsmapper in interactive
    mode (which is the default).

    N.B.: Institute users may want to use a site-customized template bidsmap (see the
    --template option). The bidsmap_dccn template from the Donders Institute can serve as
    an example (or may even mostly work for other institutes out of the box).

    positional arguments:
      sourcefolder          The study root folder containing the raw data in
                            sub-#/[ses-#/]run subfolders (or specify --subprefix
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
                            Default: bidsmap_template.yaml
      -n SUBPREFIX, --subprefix SUBPREFIX
                            The prefix common for all the source subject-folders.
                            Default: 'sub-'
      -m SESPREFIX, --sesprefix SESPREFIX
                            The prefix common for all the source session-folders.
                            Default: 'ses-'
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
      bidsmapper /project/foo/raw /project/foo/bids -t bidsmap_dccn

The bidsmapper will scan your ``sourcefolder`` to look for different
runs (scan-types) to create a mapping for each run to a bids output name
(a.k.a. the 'bidsmap'). By default (but see the ``-i`` option above),
when finished the bidsmapper will automatically launch `step
1b <#step-1b-running-the-bidseditor>`__, as described in the next
section (but step 1b can also always be run separately by directly
running the bidseditor).

    Tip: use the ``-t bidsmap_dccn`` option and see if it works for you.
    If not, consider opening it with a text editor and adapt it to your
    needs.

Step 1b: Running the bidseditor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    usage: bidseditor [-h] [-s SOURCEFOLDER] [-b BIDSMAP] [-t TEMPLATE]
                      [-n SUBPREFIX] [-m SESPREFIX]
                      bidsfolder

    This tool launches a graphical user interface for editing the bidsmap.yaml file
    that is e.g. produced by the bidsmapper or by this bidseditor itself. The user can
    fill in or change the BIDS labels for entries that are unidentified or sub-optimal,
    such that meaningful BIDS output names will be generated from these labels. The saved
    bidsmap.yaml output file can be used for converting the source data to BIDS using
    the bidscoiner.

    positional arguments:
      bidsfolder            The destination folder with the (future) bids data

    optional arguments:
      -h, --help            show this help message and exit
      -s SOURCEFOLDER, --sourcefolder SOURCEFOLDER
                            The source folder containing the raw data. If empty,
                            it is derived from the bidsmap provenance information
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
                            Default: bidsmap_template.yaml
      -n SUBPREFIX, --subprefix SUBPREFIX
                            The prefix common for all the source subject-folders.
                            Default: 'sub-'
      -m SESPREFIX, --sesprefix SESPREFIX
                            The prefix common for all the source session-folders.
                            Default: 'ses-'

    examples:
      bidseditor /project/foo/bids
      bidseditor /project/foo/bids -t bidsmap_dccn.yaml
      bidseditor /project/foo/bids -b my/custom/bidsmap.yaml

    Here are a few tips & tricks:
    -----------------------------

    DICOM Attributes
      An (DICOM) attribute label can also be a list, in which case the BIDS labels / mapping
      are applies if a (DICOM) attribute value is in this list. If the attribute value is
      empty it is not used to identify the run. Wildcards can also be given, either as a single
      '*', or enclosed by '*'. Examples:
           SequenceName: '*'
           SequenceName: '*epfid*'
           SequenceName: ['epfid2d1rs', 'fm2d2r']
           SequenceName: ['*epfid*', 'fm2d2r']
       NB: Editing the DICOM attributes is normally not necessary and adviced against

    Dynamic BIDS labels
      The BIDS labels can be static, in which case the label is just a normal string, or dynamic,
      when the string is enclosed with pointy brackets like `<attribute name>` or
      `<<argument1><argument2>>`. In case of single pointy brackets the label will be replaced
      during bidsmapper, bidseditor and bidscoiner runtime by the value of the (DICOM) attribute
      with that name. In case of double pointy brackets, the label will be updated for each
      subject/session during bidscoiner runtime. For instance, then the `run` label `<<1>>` in
      the bids name will be replaced with `1` or increased to `2` if a file with runindex `1`
      already exists in that directory.

    Fieldmaps: suffix
      Select 'magnitude1' if you have 'magnitude1' and 'magnitude2' data in one series-folder
      (this is what Siemens does) -- the bidscoiner will automatically pick up the 'magnitude2'
      data during runtime. The same holds for 'phase1' and 'phase2' data. See the BIDS
      specification for more details on fieldmap suffixes

    Fieldmaps: IntendedFor
      You can use the `IntendedFor` field to indicate for which runs (DICOM series) a fieldmap
      was intended. The dynamic label of the `IntendedFor` field can be a list of string patterns
      that is used to include all runs in a session that have that string pattern in their BIDS
      file name. Example: use `<<task>>` to include all functional runs or `<<Stop*Go><Reward>>`
      to include "Stop1Go"-, "Stop2Go"- and "Reward"-runs.
      NB: The fieldmap might not be used at all if this field is left empty!

    Manual editing / inspection of the bidsmap
      You can of course also directly edit or inspect the `bidsmap.yaml` file yourself with any
      text editor. For instance to merge a set of runs that by adding a wildcard to a DICOM
      attribute in one run item and then remove the other runs in the set. See ./docs/bidsmap.md
      and ./heuristics/bidsmap_dccn.yaml for more information.

As shown below, the main window of the bidseditor opens with the
``BIDS map`` tab that contains a list of ``input samples`` that uniquely
represents all the different files that are present in the source
folder, together with the associated ``BIDS output name``. The path in
the ``BIDS output name`` is shown in red if the modality is not part of
the BIDS standard, striked-out gray when the runs will be ignored in the
conversion to BIDS, otherwise it is colored green. Double clicking the
sample (DICOM) filename opens an inspection window with the full header
information (double clicking sample filenames works throughout the GUI).

\ |Bidseditor main window|\ 

The user can click the ``Edit`` button for each list item to open a new
edit window, as show below. In this interface, the right BIDS
``Modality`` (drop down menu) and the ``suffix`` label (drop down menu)
can set correctly, after which the associated BIDS ``Labels`` can be
edited (double click black items). As a result, the new BIDS
``Output name`` is then shown in the bottom text field. This is how the
BIDS output data will look like and, if this looks all fine, the user
can store this mapping to the bidsmap and return to the main window by
clicking the ``OK`` button.

\ |Bidseditor edit window|\ 

Finally, if all BIDS output names in the main window are fine, the user
can click on the ``Save`` button and proceed with running the bidscoiner
tool.

Step 2: Running the bidscoiner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
    sourcefolder the next time you run the bidscoiner.

    Provenance information, warnings and error messages are stored in the
    bidsfolder/code/bidscoin/bidscoiner.log file.

    positional arguments:
      sourcefolder          The source folder containing the raw data in
                            sub-#/[ses-#]/run format (or specify --subprefix and
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

.. |Bidseditor main window| image:: ./_static/bidseditor_main.png
.. |Bidseditor edit window| image:: ./_static/bidseditor_edit.png
