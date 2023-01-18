Troubleshooting
===============

Installation
------------
A first step when encountering execution errors is to test whether your installation is working correctly. An easy way to test the working of various BIDScoin components is to run ``bidscoin -t`` in your terminal. Some commonly seen messages are:

The "dcm2niix" command is not recognized
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This is an `installation <installation.html#dcm2niix-installation>`__ problem and means that bidscoin can't find your dcm2niix executable (just carefully follow the installation instructions)

Could not load the Qt platform plugin "xcb"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This error message may occur on certain Linux platforms when opening the bidseditor. This is an `installation <installation.html#bidscoin-installation>`__ issue that may be solved by downgrading your PyQt5 library, e.g. by running ``pip install --upgrade pyqt5==5.14`` in your terminal environment

My singularity container fails
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
When running singularity on on systems with an older Linux kernel (e.g. older than 3.15) you may get errors such as ``ImportError: libQt5Core.so.5: cannot open shared object file: No such file or directory``. A working fix may be to add the following line at the end of ``%post`` section of  the `singularity.def <installation.html#using-a-singularity-container>`__ file.

.. code-block:: console

   strip --remove-section=.note.ABI-tag /usr/lib/x86_64-linux-gnu/libQt5Core.so.5

The fix comes from these resources:

* https://answers.launchpad.net/yade/+question/696260/ (Answer #3)
* https://github.com/wkhtmltopdf/wkhtmltopdf/issues/4497
* https://stackoverflow.com/questions/58912268/singularity-container-python-pytorch-why-does-import-torch-work-on-arch-l

Workflow
--------
The first step in troubleshooting is to look at the warnings and messages printed out in the terminal (they are also save to disk in the ``bidsfolder/code/bidscoin`` output folder). Make sure you are ok with the warnings (they are meaningful and not to be ignored) and do not continue with a next step until all errors are resolved.

My bidsmap is empty
^^^^^^^^^^^^^^^^^^^
After running the bidsmapper, the bidseditor shows an empty bidsmap (i.e no data samples). The most likely cause is that the structure of your raw data repository is not understood by BIDScoin (see `data preparation <preparation.html>`__ for more info). Another likely cause is that the sub-/ses- prefixes need to be adjusted to your foldernames (e.g. when your ). Install and/or add the plugin.

My subject/session labels are wrong
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Everything seems to work but the ``sub-``/``ses-`` BIDS labels are not what I want. In the bidseditor main window, play around with the ``subject`` regular expressions.

I got an "Unexpected postfix / file conversion result"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This bidscoiner warning message means that the source data was not properly recognised / converted by the plugin. Please search and/or report it on `Github issue <https://github.com/Donders-Institute/bidscoin/issues?q=>`__ to resolve it.

I only see "_magnitude1" or "_magnitude2" run-items in my bidsmap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Siemens (and perhaps other manufacturers too) stores all fieldmap Series in a single Series folder. Hence, when BIDScoin takes a sample from that folder it only sees one of these Series. You don't need to worry about this, because the dcm2niix plugin will accomodate for this and will look-up the other samples during bidscoiner runtime.

My sourcefile can no longer be found
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
You may get the warning "Cannot reliably change the datatype and/or suffix because the source file '..' can no longer be found". This warning is generated when (1) your source data moved to a different location, or (2) your data is zipped or in DICOMDIR format. This warning can be ignored if you do not need to change the datatype of your run-items anymore (in the bidseditor), because in that case BIDScoin may need access to the source data (to read new properties or attributes). To restore data access for (1), move the data to it's original location and for (2) use the `--store` option of bidsmapper to store local copies of the source data samples in the bids output folder.

I have duplicated fieldmaps because of an interrupted session
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
It may happen that due to irregularities during data acquisition you had to reacquire your fieldmap for part of your data. In that case the `IntendedFor` and `B0FieldIdentifier`/'B0FieldSource` semantics become ambiguous. To handle this situation, you can use json sidecar files (see below) or use the limited `IntendedFor` search as described `here <bidsmap.html#intendedfor>`__ and `here <https://github.com/Donders-Institute/bidscoin/issues/123>`__.

The data of some subjects need to be treated (mapped) differently
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Sometimes you may have irregularities in your data that make that you would like make exceptions for run-items of certain subjects. There are different ways to do this but most likely the best way to do this is to add a json sidecar file to the source data of those run-items. In the json sidecar file you can store an attribute key-value pair to `overrule the original attribute value of the source data <bidsmap.html#structure-and-content>`__. For instance, if your fmri run was acquired with the wrong task presentation, e.g. `task2` instead of `task1`, you can add `SeriesDescription: task2` to the sidecar file to overrule `SeriesDescription: task1` in the DICOM header (to make a more specific exception that shows up as a new run-item in the bidsmap you can change it to e.g. `task1_exception`).

More help
---------
If this guide doesn't help to solve your problem, then you can `search on github <https://github.com/Donders-Institute/bidscoin/issues?q=>`__ for open and/or closed issues to see if anyone else has encountered similar problems before. If not, feel free to help yourself and others by opening a new github issue.
