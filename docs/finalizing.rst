Finishing up
============

After a successful run of bidscoiner, the work to convert your data in a fully compliant BIDS dataset is usually not fully over and, depending on the complexity of your data-set, additional tools may need to be run to post-process (e.g. deface) your data or convert datatypes not supported by the standard BIDScoin plugins (e.g. EEG data). Below you can find some tips and additional BIDScoin tools that may help you finishing up.

Adding more meta-data
---------------------
To make your dataset reproducable and shareable, you should add study-level meta-data in the modality agnostic BIDS files (BIDScoin saves stub versions of them). For instance, you should update the content of the ``dataset_description.json`` and ``README`` files in your bids folder and you may need to provide e.g. additional ``*_sessions.tsv`` or ``participants.json`` files (see the `BIDS specification <https://bids-specification.readthedocs.io/en/stable/03-modality-agnostic-files.html>`__ for more information). Moreover, if you have behavioural log-files you will find that BIDScoin does not (yet) support converting these into BIDS compliant ``*_events.tsv/json`` files (advanced users are encouraged to use the bidscoiner `plug-in <advanced.html#plugins>`__ option and write their own log-file parser).

Data sharing utilities
----------------------

Multi-echo combination
^^^^^^^^^^^^^^^^^^^^^^

Before sharing or pre-processing their images, users may want to combine the separate the individual echos of multi-echo MRI acquisitions. The ``echcombine``-tool is a wrapper around ``mecombine`` that writes BIDS valid output.

::

    usage: echocombine [-h] [-p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]] [-o OUTPUT] [-a {PAID,TE,average}]
                       [-w [WEIGHTS [WEIGHTS ...]]] [-f]
                       bidsfolder pattern

    A wrapper around the 'mecombine' multi-echo combination tool (https://github.com/Donders-Institute/multiecho).

    This wrapper is fully BIDS-aware (a 'bidsapp') and writes BIDS compliant output

    positional arguments:
      bidsfolder            The bids-directory with the (multi-echo) subject data
      pattern               Globlike recursive search pattern (relative to the subject/session folder) to select
                            the first echo of the images that need to be combined, e.g. '*task-*echo-1*'

    optional arguments:
      -h, --help            show this help message and exit
      -p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...], --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub- prefix can be
                            left out). If not specified then all sub-folders in the bidsfolder will be processed
                            (default: None)
      -o OUTPUT, --output OUTPUT
                            A string that determines where the output is saved. It can be the name of a BIDS
                            datatype folder, such as 'func', or of the derivatives folder, i.e. 'derivatives'.
                            If output = [the name of the input datatype folder] then the original echo images
                            are replaced by one combined image. If output is left empty then the combined image
                            is saved in the input datatype folder and the original echo images are moved to the
                            extra_data folder (default: )
      -a {PAID,TE,average}, --algorithm {PAID,TE,average}
                            Combination algorithm (default: TE)
      -w [WEIGHTS [WEIGHTS ...]], --weights [WEIGHTS [WEIGHTS ...]]
                            Weights for each echo (default: None)
      -f, --force           If this flag is given subjects will be processed, regardless of existing target
                            files already exist. Otherwise the echo-combination will be skipped (default: False)

    examples:
      echocombine /project/3017065.01/bids func/*task-stroop*echo-1*
      echocombine /project/3017065.01/bids *task-stroop*echo-1* -p 001 003
      echocombine /project/3017065.01/bids func/*task-*echo-1* -o func
      echocombine /project/3017065.01/bids func/*task-*echo-1* -o derivatives -w 13 26 39 52
      echocombine /project/3017065.01/bids func/*task-*echo-1* -a PAID

Defacing
^^^^^^^^

Before sharing or pre-processing their images, users may want to deface their anatomical MRI acquisitions to protect the privacy of their subjects. The ``deface``-tool is a wrapper around `pydeface <https://github.com/poldracklab/pydeface>`__ that writes BIDS valid output. NB: pydeface requires `FSL <https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation>`__ to be installed on the system.

::

    usage: deface [-h] [-p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]] [-o OUTPUT] [-c] [-n NATIVESPEC] [-a ARGS]
                  bidsfolder pattern

    A wrapper around the 'pydeface' defacing tool (https://github.com/poldracklab/pydeface).

    This wrapper is fully BIDS-aware (a 'bidsapp') and writes BIDS compliant output

    For multi-echo data see `medeface`

    positional arguments:
      bidsfolder            The bids-directory with the subject data
      pattern               Globlike search pattern (relative to the subject/session folder) to select the
                            images that need to be defaced, e.g. 'anat/*_T1w*'

    optional arguments:
      -h, --help            show this help message and exit
      -p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...], --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub- prefix can be
                            left out). If not specified then all sub-folders in the bidsfolder will be processed
                            (default: None)
      -o OUTPUT, --output OUTPUT
                            A string that determines where the defaced images are saved. It can be the name of a
                            BIDS datatype folder, such as 'anat', or of the derivatives folder, i.e.
                            'derivatives'. If output is left empty then the original images are replaced by the
                            defaced images (default: None)
      -c, --cluster         Flag to submit the deface jobs to the high-performance compute (HPC) cluster
                            (default: False)
      -n NATIVESPEC, --nativespec NATIVESPEC
                            DRMAA native specifications for submitting deface jobs to the HPC cluster (default:
                            -l walltime=00:30:00,mem=2gb)
      -a ARGS, --args ARGS  Additional arguments (in dict/json-style) that are passed to pydeface. See examples
                            for usage (default: {})

    examples:
      deface /project/3017065.01/bids anat/*_T1w*
      deface /project/3017065.01/bids anat/*_T1w* -p 001 003 -o derivatives
      deface /project/3017065.01/bids anat/*_T1w* -c -n "-l walltime=00:60:00,mem=4gb"
      deface /project/3017065.01/bids anat/*_T1w* -a '{"cost": "corratio", "verbose": ""}'

Multi-echo defacing
^^^^^^^^^^^^^^^^^^^

This utility is very similar to the `deface <#defacing>`__ utility above, except that it can handle multi-echo data.

::

    usage: medeface [-h] [-m MASKPATTERN] [-p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]] [-o OUTPUT] [-c]
                    [-n NATIVESPEC] [-a ARGS]
                    bidsfolder pattern

    A wrapper around the 'pydeface' defacing tool (https://github.com/poldracklab/pydeface) that computes
    a defacing mask on a (temporary) echo-combined image and then applies it to each individual echo-image.

    This wrapper is fully BIDS-aware (a 'bidsapp') and writes BIDS compliant output

    For single-echo data see `deface`

    positional arguments:
      bidsfolder            The bids-directory with the (multi-echo) subject data
      pattern               Globlike search pattern (relative to the subject/session folder) to select the
                            images that need to be defaced, e.g. 'anat/*_T2starw*'

    optional arguments:
      -h, --help            show this help message and exit
      -m MASKPATTERN, --maskpattern MASKPATTERN
                            Globlike search pattern (relative to the subject/session folder) to select the
                            images from which the defacemask is computed, e.g. 'anat/*_part-mag_*_T2starw*'. If
                            not given then 'pattern' is used (default: None)
      -p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...], --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub- prefix can be
                            left out). If not specified then all sub-folders in the bidsfolder will be processed
                            (default: None)
      -o OUTPUT, --output OUTPUT
                            A string that determines where the defaced images are saved. It can be the name of a
                            BIDS datatype folder, such as 'anat', or of the derivatives folder, i.e.
                            'derivatives'. If output is left empty then the original images are replaced by the
                            defaced images (default: None)
      -c, --cluster         Flag to submit the deface jobs to the high-performance compute (HPC) cluster
                            (default: False)
      -n NATIVESPEC, --nativespec NATIVESPEC
                            DRMAA native specifications for submitting deface jobs to the HPC cluster (default:
                            -l walltime=00:30:00,mem=2gb)
      -a ARGS, --args ARGS  Additional arguments (in dict/json-style) that are passed to pydeface. See examples
                            for usage (default: {})

    examples:
      medeface /project/3017065.01/bids anat/*_T1w*
      medeface /project/3017065.01/bids anat/*_T1w* -p 001 003 -o derivatives
      medeface /project/3017065.01/bids anat/*_T1w* -c -n "-l walltime=00:60:00,mem=4gb"
      medeface /project/3017065.01/bids anat/*acq-GRE* -m anat/*acq-GRE*magnitude*"
      medeface /project/3017065.01/bids anat/*_FLAIR* -a '{"cost": "corratio", "verbose": ""}'

BIDS validation
---------------

If all of the above work is done, you can (and should) run the web-based `bidsvalidator <https://bids-standard.github.io/bids-validator/>`__ to check for inconsistencies or missing files in your bids data-set (NB: the bidsvalidator also exists as a `command-line tool <https://github.com/bids-standard/bids-validator>`__).

.. note::
   Privacy-sensitive source data samples may be stored in ``[bidsfolder]/code/bidscoin/provenance`` (see the ``-s`` option in the `bidsmapper <workflow.html#step-1a-running-the-bidsmapper>`__).
