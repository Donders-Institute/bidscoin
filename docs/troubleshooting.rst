Troubleshooting
===============

Installation
------------
A first step when encountering execution errors is to test whether your installation is working correctly. An easy way to test the working of various BIDScoin components is to run ``bidscoin -t`` in your terminal. Some commonly seen messages are:

* **The "dcm2niix" command is not recognized**. This is an `installation <installation.html#dcm2niix>`__ problem and means that bidscoin can't find your dcm2niix executable (see the link).
* **Could not load the Qt plugin "xcb"**. This is an `installation <installation.html#bidscoin>`__ problem that occurs on certain Linux platforms (see the "Tip" in the link).
* **My singularity container**. This

Workflow
--------
The first step in troubleshooting is to look at the warnings and messages printed out in the terminal (they are also save to disk in the ``bidsfolder/code/bidscoin`` output folder). Make sure you are ok with the warnings (they are meaningful and not to be ignored) and do not continue with a next step until all errors are resolved.

* **My bidsmap is empty**. After running the bidsmapper, the bidseditor shows an empty bidsmap (i.e no data samples). The most likely cause is that the structure of your raw data repository is not understood by BIDScoin (see `data preparation <peparation.html>`__ for more info). Another likely cause is that the sub-/ses- prefixes need to be adjusted to your foldernames (e.g. when your ). Install and/or add the plugin
* **My subject/session labels are wrong**. Everything seems to work but the ``sub-``/``ses-`` BIDS labels are not what I want. In the bidseditor main window, play around with the ``subject`` regular expressions

More help
---------
If this guide doesn't help to solve your problem, then you can `search on github <https://github.com/Donders-Institute/bidscoin/issues?q=>`__ for open and/or closed issues to see if anyone else has encountered similar problems before. If not, feel free to help yourself and others by opening a new github issue.
