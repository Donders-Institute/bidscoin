Options
=======

BIDScoin has different options and settings (see below) that can be adjusted per study bidsmap or, when you want to customize the default, set as default in the `template bidsmap <bidsmap.html>`__. There are separate settings for BIDScoin and for the individual plugins that can be edited by double clicking the corresponding fields. Installed plugins can be removed or added to extend BIDScoin's functionality.

.. figure:: ./_static/bidseditor_options.png
   :scale: 75%

   The bidseditor options window with the different settings for BIDScoin and its plugins. The user can manage the plugins that will be used with the [Add] and [Remove] buttons, and save the current options to the template bidsmap by using the [Set as default] button.

BIDScoin
--------

These setting can be used by all the BIDScoin tools:

- ``version``: Used to check for version conflicts between the installed version (see ../bidscoin/version.txt) and the version that was used to create the bidsmap, or between the installed version and the latest online version.
- ``bidsignore``: Semicolon-separated list of (non-BIDS) datatypes that you want to include but that do not pass a BIDS `validation test <https://github.com/bids-standard/bids-validator#bidsignore>`__. These files are added to the `.bidsignore` file. Example: ``bidsignore: extra_data/;rTMS/;myfile.txt;yourfile.csv``
- ``subprefix``: The prefix before the subject label in the source data folder, e.g. 'patient-' if the source data is in ``raw/patient-001/ses-01/..``
- ``sesprefix``: Idem for the session label
- ``datatypes``: Datatypes that are converted to BIDS
- ``unknowntypes``: Datatypes that are not part of BIDS but that are converted to a BIDS-like entries in the BIDS folder
- ``ignoretypes``: Datatypes that are excluded / not converted"""

The core working of BIDScoin can be tested by clicking the [Test] button and inspection of the terminal output.

dcm2niix2bids - plugin
----------------------

The dcm2niix2bids plugin is the default bidscoiner plugin that converts DICOM and PAR/REC source data to BIDS-valid nifti- and json sidecar files. This plugin relies on `dcm2niix <https://github.com/rordenlab/dcm2niix>`__, for which you can set the following options:

- ``path``: A string that is prepended to the dcm2niix command such that it can be found by the operating system. You can leave it empty if dcm2niix is already on your shell path and callable from the command-line, otherwise you could use e.g.:

  - ``module add dcm2niix/v1.0.20210317;`` (note the semi-colon at the end)
  - ``PATH=/opt/dcm2niix/bin:$PATH;`` (note the semi-colon at the end)
  - ``/opt/dcm2niix/bin/`` (note the slash at the end)
  - ``"C:\Program Files\dcm2niix\"`` (note the quotes to deal with the whitespace in the path)

- ``args``: Argument string that is passed as input to dcm2niix to customize its behavior, e.g. ``-z n -i y`` for ignoring derived data and having uncompressed output data.
- ``anon``: Set this anonymization flag to 'y' to round off age and to discard acquisition date from the meta data

To test the proper working of dcm2niix click [Test] and see the terminal output for more helptext on its input arguments

spec2nii2bids - plugin
----------------------

The spec2nii2bids plugin is a bidscoiner plugin that converts Twix, SPAR/SDAT and P-file spectroscopy source data to BIDS-valid nifti- and json sidecar files. This plugin relies on `spec2nii <https://github.com/wexeee/spec2nii>`__, for which you can set the following options:

- ``path``: A string that is prepended to the spec2nii command such that it can be found by the operating system. You can leave it empty if spec2nii is already on your shell path (default) and callable from the command-line
- ``args``: Argument string that is passed as input to spec2nii to customize its behavior
- ``anon``: Set this anonymization flag to 'y' to round off age and to discard acquisition date from the meta data

To test the proper working of spec2nii click [Test] and see the terminal output for more helptext on its input arguments

.. tip::
   - Use the [Set as default] button to put your custom dcm2niix path-setting in your template bidsmap so that you don't have to adjust it anymore for every new study
   - SPM users may want to use '-z n', which produces unzipped nifti's
