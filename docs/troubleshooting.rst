Troubleshooting
===============

Installation
------------
A first step when encountering execution errors is to test whether your installation is working correctly. An easy way to test the working of various BIDScoin components is to run ``bidscoin -t`` in your terminal. Some commonly seen messages are:

The "dcm2niix" command is not recognized
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This is an `installation <./installation.html#dcm2niix-installation>`__ problem and means that bidscoin can't find your dcm2niix executable (just carefully follow the installation instructions)

Could not load the Qt platform plugin "xcb"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This error message may occur on certain Linux platforms when opening the bidseditor. This is an `installation <./installation.html#bidscoin-installation>`__ issue that may occur if you have installed the ``+qt5`` build of BIDScoin (e.g. because your system does not support Qt6). Sometimes this error can be solved by downgrading your PyQt5 library, e.g. by running ``pip install --upgrade pyqt5==5.14`` in your terminal environment. Another solution might be to use your Linux package manager to install PyQt5, e.g. like this: ``apt install python3-pyqt5 python3-pyqt5.qtx11extras``

ImportError: libEGL.so.1: cannot open shared object file: No such file or directory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This may error message may be reported on Linux systems that do not support Qt6 out of the box. On Debian/Ubuntu systems this may be solved by running:

.. code-block:: console

   sudo apt install qt6-base
   sudo apt install qt6-base-dev     # If the above package cannot be located
   sudo apt install python3-pyqt6    # If the above commands do not solve the issue

An alternative solution may be to install the ``+qt5`` build of BIDScoin (see `installation <./installation.html#bidscoin-installation>`__)

My Apptainer/Singularity container fails
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
When running apptainer/singularity on on systems with an older Linux kernel (e.g. older than 3.15) you may get errors such as ``ImportError: libQt5Core.so.5: cannot open shared object file: No such file or directory``. A working fix may be to add the following line at the end of ``%post`` section of  the `singularity.def <./installation.html#using-a-singularity-container>`__ file.

.. code-block:: console

   strip --remove-section=.note.ABI-tag /usr/lib/x86_64-linux-gnu/libQt5Core.so.5

The fix comes from these resources:

* https://answers.launchpad.net/yade/+question/696260/ (Answer #3)
* https://github.com/wkhtmltopdf/wkhtmltopdf/issues/4497
* https://stackoverflow.com/questions/58912268/singularity-container-python-pytorch-why-does-import-torch-work-on-arch-l

Workflow
--------
The first step in troubleshooting is to look at the warnings and messages printed out in the terminal (they are also save to disk in the ``bidsfolder/code/bidscoin`` output folder). Make sure you are OK with the warnings (they are meaningful and not to be ignored) and do not continue with a next step until all errors are resolved.

My bidsmap is empty
^^^^^^^^^^^^^^^^^^^
After running the bidsmapper, the bidseditor shows an empty bidsmap (i.e no data samples). The most likely cause is that the structure of your raw data repository is not understood by BIDScoin (see `data preparation <./preparation.html>`__ for more info). Another likely cause is that the sub-/ses- prefixes need to be adjusted to your folder names (e.g. when your ). Install and/or add the plugin.

My bidsmap list is much longer than the number of scan types
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Normally the list of items in the bidsmap is a shortlist that represents the different scan types in the dataset. Each scan type is characterized by unique properties and/or attributes specific for that scan type. If your list is much longer then one or more of the properties or attributes in the bidsmap are varying between different acquisitions of the same scan type (which causes bidscoin to classify them as different scan types that are all added to the list). For instance, it sometimes happens that manufacturers write a value for TR or TE in the DICOM header that reflects the measured TR or TE, instead of the values from the protocol (the measured values typically jitter a tiny bit). If you found out which attributes and/or properties it concerns, you can open the template bidsmap with an editor and remove them for the long-listed scan type(s) (but be careful, this may make the item(s) to generic, yielding false positive matches). An alternative solution is to open your study bidsmap with an editor, delete all the long-listed items except one, and add a custom regular expression for the varying properties and/or attributes (e.g. to catch the jitter)

I have duplicate run-items in my bidsmap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Exact duplicates should not exist, i.e. there is probably a small difference in the properties or attributes that identify your run-items. To investigate this, you can compare these run-items by selecting their BIDS output names (use shift-/control-click), then right-click them and choose ``compare`` from the context menu (see `here <./screenshots.html>`__ for an example)

My subject/session labels are wrong
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Everything seems to work but the ``sub-``/``ses-`` BIDS labels are not what I want. In the bidseditor main window, play around with the ``subject`` regular expressions.

As an example, let's break down the regular expression `pattern <https://docs.python.org/3/library/re.html#re.findall>`__ ``/source_data/sub-.*?/ses-(.*?)/`` step by step:

1. ``/source_data/sub-``: This part of the pattern matches the literal string “/source_data/sub-”.
2. ``.*?``: This is a non-greedy (or lazy) match for any character zero or more times. The ``.*`` part means “match any character (``.``) zero or more times (``*``)”, and the ``?`` makes the quantifier non-greedy, which means it will match as few characters as possible.
3. ``/ses-``: This matches the literal string “/ses-”.
4. ``(.*?)``: This is another non-greedy match for any character zero or more times, but this time it is inside parentheses, which means it captures the matched characters into a group. The non-greedy quantifier ensures that this group will match as few characters as possible.
5. ``/``: This matches the literal character “/”.

Summary
.......

The regular expression ``/source_data/sub-.*?/ses-(.*?)/`` is designed to:

- Match the literal path starting with “/source_data/sub-”.
- Use a non-greedy match to skip over characters until it finds “/ses-”.
- Capture the segment following “/ses-” up to the next “/”.

*Example Matches*

Here are a few example strings and how they would be matched by the regular expression::

    /project/source_data/sub-123/ses-456/some_string
        Captured group 1: 456

    /project/source_data/sub-abcd/ses-efgh/another_string
        Captured group 1: efgh

Could not parse required sub-/ses- label
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You may get the error "Could not parse required sub- label from [..]". This error can have multiple causes, the most probable ones are:

1) Your subject source folders are named in an inconsistent way, i.e. the filepath is not parsable by your ``subject`` regular expression. The best remedy is to open the bidsmap in the bidseditor and update the path in the ``subject`` and/or ``session`` regular expression(s). If that is not working out, then you should rename your subject/session source folders and make them all consistent
2) Your source data moved to a different location. The solution is to either move the data back to the original location or to open the bidsmap in the bidseditor and update the path in the ``subject`` and/or ``session`` field(s). Alternatively, to avoid this specific issue, you can use bidsmapper's ``--no-update`` option (the first time you run it on the raw folder). The downside of this (non-default) approach is that the subject/session label parsing may be less robust (especially if you have no or a very short subject/session prefix)

I got an "Unexpected postfix / file conversion result"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This bidscoiner warning message means that the source data was not properly recognized/converted by the plugin. Please search and/or report it on `Github issue <https://github.com/Donders-Institute/bidscoin/issues?q=>`__ to resolve it.

I only see "_magnitude1" or "_magnitude2" run-items in my bidsmap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Siemens (and perhaps other manufacturers too) stores all field-map Series in a single Series folder. Hence, when BIDScoin takes a sample from that folder it only sees one of these Series. You don't need to worry about this, because the dcm2niix plugin will accommodate for this and will look-up the other samples during bidscoiner runtime.

My source-files can no longer be found
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You may get the warning "Cannot reliably change the data type and/or suffix because the source file '..' can no longer be found". This warning is generated when (1) your source data moved to a different location, or (2) your data is zipped or in DICOMDIR format. This warning can be ignored if you do not need to change the data type of your run-items anymore (in the bidseditor), because in that case BIDScoin may need access to the source data (to read new properties or attributes). To restore data access for (1), move the data to it's original location and for (2) use the ``--store`` option of bidsmapper to store local copies of the source data samples in the bids output folder.

I have duplicated field maps because of an interrupted session
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
It may happen that due to irregularities during data acquisition you had to reacquire your field-map for part of your data. In that case the ``IntendedFor`` and ``B0FieldIdentifier``/``B0FieldSource`` semantics become ambiguous. To handle this situation, you can use json sidecar files to extend the source attributes (see below) or use the limited ``IntendedFor`` search as described `here <./bidsmap.html#intendedfor>`__ and `here <https://github.com/Donders-Institute/bidscoin/issues/123>`__.

The bidscoiner says that the IntendedFor search gave no results
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Even if you have specified the IntendedFor value in the bidseditor, you still get `"Empty 'IntendedFor' field map value in {..}: the search for {..} gave no results"`. This may be because you hardcoded the IntendedFor value instead of providing a search pattern. Or it may be that you provided a correct search pattern but that for some subjects the target images were not acquired or could not be found (e.g. due to irregularities in the acquisition). Check out the BIDS output session(s) mentioned in the warning(s) and see if and how you should update your IntendedFor search pattern accordingly.

The bidscoiner says that I need to check my scan.tsv files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This may occur when you use a dynamic run-index (e.g. ``<<>>`` or ``<<1>>``) and the folder names of your DICOM Series do not start with the DICOM SeriesNumber (this is default on Siemens). The solution would be to rename your Series folder to alphabetical order (in many cases this can be done with ``disomsort``), or to use another dynamic value, e.g. ``<<SeriesNumber>>`` (the latter will yield properly ordered run-indices, albeit with a variable step, e.g. yielding ``run-2`` + ``run-5`` instead of ``run-1`` + ``run-2``

I use dynamic run-indices and now have 'orphan' run-indices in my BIDS directory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
BIDScoin automatically increments the run-index based on existing files in the same directory. In rare cases, this procedure can fail, leading to 'orphan' run-indices, e.g. a ``run-2`` file without an accompanying ``run-1`` file. Most likely this is caused by underspecified run-items in the bidsmap, for instance when you have a magnitude as well as a phase item, but you left the ``part`` entity empty (instead of specifying ``part-mag`` and ``part-phase``), i.e. you gave them the same output name (which BIDScoin then has to fix post-hoc). In rare cases you cannot avoid this problem and then it is advised to use the more robust ``<<1>>`` index, instead of ``<<>>``

The data of some subjects need to be treated (mapped) differently
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Sometimes you may have irregularities in your data that make that you would like make exceptions for run-items of certain subjects. There are different ways to do this but most likely the best way to do this is to add a json sidecar file to the source data of those run-items. In the json sidecar file you can store an attribute key-value pair to `overrule or extend the original attribute value of the source data <./bidsmap.html#structure-and-content>`__. For instance, if your fMRI run was acquired with the wrong task presentation, e.g. ``task2`` instead of ``task1``, you can add ``SeriesDescription: task2`` to the sidecar file to overrule ``SeriesDescription: task1`` in the DICOM header (to make a more specific exception that shows up as a new run-item in the bidsmap you can change it to e.g. ``task1_exception``).

I want to rename files or change some data in my existing BIDS directory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You can simply use the ``bidseditor`` to make changes to your bidsmap, delete all subject folders in your BIDS output folder and then re-run ``bidscoiner``. However, sometimes you may no longer have access to your source data, or you may have downloaded a publicly shared BIDS dataset (without source data). In that case you can use ``bidscoiner`` in combination with the ``nibabel2bids`` plugin and the ``bidsmap_bids2bids`` bidsmap to create a new BIDS dataset, i.e. like this:

.. code-block:: console

   $ bidsmapper bidsfolder bidsfolder_new -p nibabel2bids -t bidsmap_bids2bids
   $ bidscoiner bidsfolder bidsfolder_new

More help
---------
If this guide does not help to solve your problem, then you can `search on github <https://github.com/Donders-Institute/bidscoin/issues?q=>`__ for open and/or closed issues to see if anyone else has encountered similar problems before. If not, feel free to help yourself and others by opening a new github issue.
