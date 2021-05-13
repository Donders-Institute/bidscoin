Options
=======

BIDScoin has different options and settings (see below) that can be adjusted per study bidsmap or, when you want to customize the default, edited in the `template bidsmap <bidsmap.html>`__. There are seperate settings for BIDScoin and for the individual plugins that can be edited by double clicking. Installed plugins can be removed or added to extend BIDScoin's functionality.

.. figure:: ./_static/bidseditor_options.png
   :scale: 75%

   The bidseditor options window with the different BIDScoin settings

BIDScoin
--------

These setting can be used by all the BIDScoin tools:

- ``version``: Used to check for version conflicts (should correspond with the version in ../bidscoin/version.txt)
- ``bidsignore``: Semicolon-separated list of datatypes that you want to include but that do not pass a BIDS `validation test <https://github.com/bids-standard/bids-validator#bidsignore>`__. Example: ``bidsignore: extra_data/;rTMS/;myfile.txt;yourfile.csv``

dcm2bidsmap - plugin
--------------------

The default bidsmapper plugin that builds a bidsmap from DICOM and PAR/REC source data. There are no settings for this plugin

dcm2niix2bids - plugin
----------------------

The default bidscoiner plugin that converts DICOM and PAR/REC source data to BIDS-valid nifti- and json sidecar files. This plugin relies on `dcm2niix <https://github.com/rordenlab/dcm2niix>`__, for which you can set the following options:

- ``path``: A string that is prepended to the dcm2niix command to make sure it can be found by the operating system. You can leave it empty if dcm2niix is already on your shell path and callable from the command-line, otherwise you could use e.g.:

  - ``module add dcm2niix/v1.0.20210317;`` (note the semi-colon at the end)
  - ``PATH=/opt/dcm2niix/bin:$PATH;`` (note the semi-colon at the end)
  - ``/opt/dcm2niix/bin/`` (note the slash at the end)
  - ``'\"C:\\Program Files\\dcm2niix\"'`` (note the quotes to deal with the whitespace)

- ``args``: Argument string that is passed to dcm2niix, e.g. ``-b y -z n -i n``. Click [Test] and see the terminal output for usage

.. tip::
   - Put your custom dcm2niix path-setting in your template so that you don't have to set it anymore for every new study
   - SPM users may want to use '-z n', which produces unzipped nifti's
