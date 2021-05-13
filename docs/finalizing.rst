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

    usage: mecombine [-h] [-o OUTPUTNAME] [-a {PAID,TE,average}] [-w [WEIGHTS [WEIGHTS ...]]] [-s] [-v VOLUMES]
                     pattern

    Combine multi-echo echoes.

    Tools to combine multiple echoes from an fMRI acquisition.
    It expects input files saved as NIfTIs, preferably organised
    according to the BIDS standard.

    Currently three different combination algorithms are supported, implementing
    the following weighting schemes:

    1. PAID => TE * SNR
    2. TE => TE
    3. Simple Average => 1

    positional arguments:
      pattern               Globlike search pattern with path to select the echo images that need to be combined.
                            Because of the search, be sure to check that not too many files are being read

    optional arguments:
      -h, --help            show this help message and exit
      -o OUTPUTNAME, --outputname OUTPUTNAME
                            File output name. If not a fullpath name, then the output will be stored in the same
                            folder as the input. If empty, the output filename will be the filename of the first
                            echo appended with a '_combined' suffix (default: )
      -a {PAID,TE,average}, --algorithm {PAID,TE,average}
                            Combination algorithm. Default: TE (default: TE)
      -w [WEIGHTS [WEIGHTS ...]], --weights [WEIGHTS [WEIGHTS ...]]
                            Weights (e.g. = echo times) for all echoes (default: None)
      -s, --saveweights     If passed and algorithm is PAID, save weights (default: False)
      -v VOLUMES, --volumes VOLUMES
                            Number of volumes that is used to compute the weights if algorithm is PAID (default:
                            100)

    examples:
      mecombine '/project/number/bids/sub-001/func/*_task-motor_*echo-*.nii.gz'
      mecombine '/project/number/bids/sub-001/func/*_task-rest_*echo-*.nii.gz' -a PAID
      mecombine '/project/number/bids/sub-001/func/*_acq-MBME_*run-01*.nii.gz' -w 11 22 33 -o sub-001_task-stroop_acq-mecombined_run-01_bold.nii.gz


Defacing
^^^^^^^^

Before sharing or pre-processing their images, users may want to deface their anatomical MRI acquisitions to protect the privacy of their subjects. The ``deface``-tool is a wrapper around `pydeface <https://github.com/poldracklab/pydeface>`__ that writes BIDS valid output. NB: pydeface requires `FSL <https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation>`__ to be installed on the system.

::

    usage: deface.py [-h] [-p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]]
                     [-o {fmap,anat,func,perf,dwi,meg,eeg,ieeg,beh,pet,extra_data,derivatives}] [-c]
                     [-n NATIVESPEC] [-a ARGS]
                     bidsfolder pattern

    A wrapper around the 'pydeface' defacing tool (https://github.com/poldracklab/pydeface).

    This wrapper is fully BIDS-aware (a 'bidsapp') and writes BIDS compliant output

    positional arguments:
      bidsfolder            The bids-directory with the (multi-echo) subject data
      pattern               Globlike search pattern (relative to the subject/session folder) to select the images
                            that need to be defaced, e.g. 'anat/*_T1w*'

    optional arguments:
      -h, --help            show this help message and exit
      -p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...], --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub- prefix can be left
                            out). If not specified then all sub-folders in the bidsfolder will be processed
                            (default: None)
      -o {fmap,anat,func,perf,dwi,meg,eeg,ieeg,beh,pet,extra_data,derivatives}, --output {fmap,anat,func,perf,dwi,meg,eeg,ieeg,beh,pet,extra_data,derivatives}
                            A string that determines where the defaced images are saved. It can be the name of a
                            BIDS datatype folder, such as 'anat', or of the derivatives folder, i.e.
                            'derivatives'. If output is left empty then the original images are replaced by the
                            defaced images (default: None)
      -c, --cluster         Flag to submit the deface jobs to the high-performance compute (HPC) cluster (default:
                            False)
      -n NATIVESPEC, --nativespec NATIVESPEC
                            DRMAA native specifications for submitting deface jobs to the HPC cluster (default: -l
                            walltime=00:30:00,mem=2gb)
      -a ARGS, --args ARGS  Additional arguments (in dict/json-style) that are passed to pydeface. See examples
                            for usage (default: {})

    examples:
      deface /project/3017065.01/bids anat/*_T1w*
      deface /project/3017065.01/bids anat/*_T1w* -p 001 003 -o derivatives
      deface /project/3017065.01/bids anat/*_T1w* -c -n "-l walltime=00:60:00,mem=4gb"
      deface /project/3017065.01/bids anat/*_T1w* -a '{"cost": "corratio", "verbose": ""}'

BIDS validation
---------------

If all of the above work is done, you can (and should) run the web-based `bidsvalidator <https://bids-standard.github.io/bids-validator/>`__ to check for inconsistencies or missing files in your bids data-set (NB: the bidsvalidator also exists as a `command-line tool <https://github.com/bids-standard/bids-validator>`__).

.. note::
   Privacy-sensitive source data samples may be stored in ``[bidsfolder]/code/bidscoin/provenance`` (see the ``-s`` option in the ``bidsmapper <workflow.html#step-1a-running-the-bidsmapper>``__).
