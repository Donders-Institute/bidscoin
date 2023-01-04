Troubleshooting
===============

Installation
------------
A first step when encountering execution errors is to test whether your installation is working correctly. An easy way to test the working of various BIDScoin components is to run ``bidscoin -t`` in your terminal. Some commonly seen messages are:

The "dcm2niix" command is not recognized
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This is an `installation <installation.html#dcm2niix>`__ problem and means that bidscoin can't find your dcm2niix executable (just carefully follow the installation instructions)

Could not load the Qt platform plugin "xcb"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This error message may occur on certain Linux platforms when opening the bidseditor. This is an `installation <installation.html#bidscoin>`__ issue that may be solved by downgrading your PyQt5 library, e.g. by running ``pip install --upgrade pyqt5==5.14`` in your terminal environment

My singularity container fails
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
When running singularity on on systems with an older Linux kernel (e.g. older than 3.15) you may get errors such as ``ImportError: libQt5Core.so.5: cannot open shared object file: No such file or directory``. A working fix may be to add the following line at the end of ``%post`` section of  the `singularity.def <installation.html#using-a-singularity-container>`__ file.

.. code-block:: console

   strip --remove-section=.note.ABI-tag /usr/lib/x86_64-linux-gnu/libQt5Core.so.5

The fix comes from these resources:

* (Answer #3) https://answers.launchpad.net/yade/+question/696260/
* https://github.com/wkhtmltopdf/wkhtmltopdf/issues/4497
* https://stackoverflow.com/questions/58912268/singularity-container-python-pytorch-why-does-import-torch-work-on-arch-l

Workflow
--------
The first step in troubleshooting is to look at the warnings and messages printed out in the terminal (they are also save to disk in the ``bidsfolder/code/bidscoin`` output folder). Make sure you are ok with the warnings (they are meaningful and not to be ignored) and do not continue with a next step until all errors are resolved.

My bidsmap is empty
^^^^^^^^^^^^^^^^^^^
After running the bidsmapper, the bidseditor shows an empty bidsmap (i.e no data samples). The most likely cause is that the structure of your raw data repository is not understood by BIDScoin (see `data preparation <peparation.html>`__ for more info). Another likely cause is that the sub-/ses- prefixes need to be adjusted to your foldernames (e.g. when your ). Install and/or add the plugin

My subject/session labels are wrong
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Everything seems to work but the ``sub-``/``ses-`` BIDS labels are not what I want. In the bidseditor main window, play around with the ``subject`` regular expressions

Unexpected postfix / file conversion result
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This message means that the source data was not properly recognised / converted by the plugin. Please search and/or report it on `Github issue <https://github.com/Donders-Institute/bidscoin/issues?q=>`__ to resolve it

More help
---------
If this guide doesn't help to solve your problem, then you can `search on github <https://github.com/Donders-Institute/bidscoin/issues?q=>`__ for open and/or closed issues to see if anyone else has encountered similar problems before. If not, feel free to help yourself and others by opening a new github issue.
