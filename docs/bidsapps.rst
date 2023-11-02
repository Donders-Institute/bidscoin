BIDS-apps
=========

Multi-echo combination
----------------------

Before sharing or pre-processing their images, users may want to combine the separate the individual echos of multi-echo MRI acquisitions. The ``echcombine``-tool is a wrapper around ``mecombine`` that writes BIDS valid output.

::

    usage: echocombine [-h] [-p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]] [-o OUTPUT]
                       [-a {PAID,TE,average}] [-w [WEIGHTS ...]] [-f]
                       bidsfolder pattern

    A wrapper around the 'mecombine' multi-echo combination tool
    (https://github.com/Donders-Institute/multiecho).

    Except for BIDS inheritances, this wrapper is BIDS-aware (a 'bidsapp') and writes BIDS
    compliant output

    positional arguments:
      bidsfolder            The bids-directory with the (multi-echo) subject data
      pattern               Globlike recursive search pattern (relative to the subject/session folder) to
                            select the first echo of the images that need to be combined, e.g.
                            '*task-*echo-1*'

    options:
      -h, --help            show this help message and exit
      -p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...], --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub-prefix can
                            be left out). If not specified then all sub-folders in the bidsfolder will be
                            processed (default: None)
      -o OUTPUT, --output OUTPUT
                            A string that determines where the output is saved. It can be the name of a
                            BIDS datatype folder, such as 'func', or of the derivatives folder, i.e.
                            'derivatives'. If output = [the name of the input datatype folder] then the
                            original echo images are replaced by one combined image. If output is left
                            empty then the combined image is saved in the input datatype folder and the
                            original echo images are moved to the 'extra_data' folder (default: )
      -a {PAID,TE,average}, --algorithm {PAID,TE,average}
                            Combination algorithm (default: TE)
      -w [WEIGHTS ...], --weights [WEIGHTS ...]
                            Weights for each echo (default: None)
      -f, --force           Process all images, regardless whether target images already exist. Otherwise
                            the echo-combination will be skipped (default: False)

    examples:
      echocombine myproject/bids func/*task-stroop*echo-1*
      echocombine myproject/bids *task-stroop*echo-1* -p 001 003
      echocombine myproject/bids func/*task-*echo-1* -o func
      echocombine myproject/bids func/*task-*echo-1* -o derivatives -w 13 26 39 52
      echocombine myproject/bids func/*task-*echo-1* -a PAID

Defacing
--------

Before sharing or pre-processing their images, users may want to deface their anatomical MRI acquisitions to protect the privacy of their subjects. The ``deface``-tool is a wrapper around `pydeface <https://github.com/poldracklab/pydeface>`__ that writes BIDS valid output. NB: pydeface requires `FSL <https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation>`__ to be installed on the system.

::

    usage: deface [-h] [-p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]] [-o OUTPUT] [-c] [-n NATIVESPEC]
                  [-a ARGS] [-f]
                  bidsfolder pattern

    A wrapper around the 'pydeface' defacing tool (https://github.com/poldracklab/pydeface).

    Except for BIDS inheritances and IntendedFor usage, this wrapper is BIDS-aware (a 'bidsapp')
    and writes BIDS compliant output

    Linux users can distribute the computations to their HPC compute cluster if the DRMAA
    libraries are installed and the DRMAA_LIBRARY_PATH environment variable set

    For multi-echo data see `medeface`

    positional arguments:
      bidsfolder            The bids-directory with the subject data
      pattern               Globlike search pattern (relative to the subject/session folder) to select
                            the images that need to be defaced, e.g. 'anat/*_T1w*'

    options:
      -h, --help            show this help message and exit
      -p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...], --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub-prefix can
                            be left out). If not specified then all sub-folders in the bidsfolder will be
                            processed (default: None)
      -o OUTPUT, --output OUTPUT
                            A string that determines where the defaced images are saved. It can be the
                            name of a BIDS datatype folder, such as 'anat', or of the derivatives folder,
                            i.e. 'derivatives'. If output is left empty then the original images are
                            replaced by the defaced images (default: None)
      -c, --cluster         Use the DRMAA library to submit the deface jobs to a high-performance compute
                            (HPC) cluster (default: False)
      -n NATIVESPEC, --nativespec NATIVESPEC
                            DRMAA native specifications for submitting deface jobs to the HPC cluster
                            (default: -l walltime=00:30:00,mem=2gb)
      -a ARGS, --args ARGS  Additional arguments (in dict/json-style) that are passed to pydeface. See
                            examples for usage (default: {})
      -f, --force           Deface all images, regardless if they have already been defaced (i.e. if
                            {"Defaced": True} in the json sidecar file) (default: False)

    examples:
      deface myproject/bids anat/*_T1w*
      deface myproject/bids anat/*_T1w* -p 001 003 -o derivatives
      deface myproject/bids anat/*_T1w* -c -n "-l walltime=00:60:00,mem=4gb"
      deface myproject/bids anat/*_T1w* -a '{"cost": "corratio", "verbose": ""}'

Multi-echo defacing
-------------------

This utility is very similar to the `deface <#defacing>`__ utility above, except that it can handle multi-echo data.

::

    usage: medeface [-h] [-m MASKPATTERN] [-p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]] [-o OUTPUT] [-c]
                    [-n NATIVESPEC] [-a ARGS] [-f]
                    bidsfolder pattern

    A wrapper around the 'pydeface' defacing tool (https://github.com/poldracklab/pydeface) that
    computes a defacing mask on a (temporary) echo-combined image and then applies it to each
    individual echo-image.

    Except for BIDS inheritances and IntendedFor usage, this wrapper is BIDS-aware (a 'bidsapp')
    and writes BIDS compliant output

    Linux users can distribute the computations to their HPC compute cluster if the DRMAA
    libraries are installed and the DRMAA_LIBRARY_PATH environment variable set

    For single-echo data see `deface`

    positional arguments:
      bidsfolder            The bids-directory with the (multi-echo) subject data
      pattern               Globlike search pattern (relative to the subject/session folder) to select
                            the images that need to be defaced, e.g. 'anat/*_T2starw*'

    options:
      -h, --help            show this help message and exit
      -m MASKPATTERN, --maskpattern MASKPATTERN
                            Globlike search pattern (relative to the subject/session folder) to select
                            the images from which the defacemask is computed, e.g. 'anat/*_part-
                            mag_*_T2starw*'. If not given then 'pattern' is used (default: None)
      -p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...], --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub-prefix can
                            be left out). If not specified then all sub-folders in the bidsfolder will be
                            processed (default: None)
      -o OUTPUT, --output OUTPUT
                            A string that determines where the defaced images are saved. It can be the
                            name of a BIDS datatype folder, such as 'anat', or of the derivatives folder,
                            i.e. 'derivatives'. If output is left empty then the original images are
                            replaced by the defaced images (default: None)
      -c, --cluster         Use the DRMAA library to submit the deface jobs to a high-performance compute
                            (HPC) cluster (default: False)
      -n NATIVESPEC, --nativespec NATIVESPEC
                            DRMAA native specifications for submitting deface jobs to the HPC cluster
                            (default: -l walltime=00:30:00,mem=2gb)
      -a ARGS, --args ARGS  Additional arguments (in dict/json-style) that are passed to pydeface. See
                            examples for usage (default: {})
      -f, --force           Process all images, regardless if images have already been defaced (i.e. if
                            {"Defaced": True} in the json sidecar file) (default: False)

    examples:
      medeface myproject/bids anat/*_T1w*
      medeface myproject/bids anat/*_T1w* -p 001 003 -o derivatives
      medeface myproject/bids anat/*_T1w* -c -n "-l walltime=00:60:00,mem=4gb"
      medeface myproject/bids anat/*acq-GRE* -m anat/*acq-GRE*magnitude*"
      medeface myproject/bids anat/*_FLAIR* -a '{"cost": "corratio", "verbose": ""}'

Skull-stripping
---------------

The ``skullstrip``-tool is a wrapper around the synthstrip tool that writes BIDS valid output

::

    usage: skullstrip [-h] [-p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]] [-m MASKED]
                      [-o OUTPUT [OUTPUT ...]] [-f] [-a ARGS] [-c]
                      bidsfolder pattern

    A wrapper around FreeSurfer's 'synthstrip' skull stripping tool
    (https://surfer.nmr.mgh.harvard.edu/docs/synthstrip). Except for BIDS inheritances,
    this wrapper is BIDS-aware (a 'bidsapp') and writes BIDS compliant output

    The corresponding brain mask is saved in the bids/derivatives/synthstrip folder

    Assumes the installation of FreeSurfer v7.3.2 or higher

    positional arguments:
      bidsfolder            The bids-directory with the subject data
      pattern               Globlike search pattern (relative to the subject/session folder) to select
                            the (3D) images that need to be skullstripped, e.g. 'anat/*_T1w*'

    options:
      -h, --help            show this help message and exit
      -p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...], --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub-prefix can
                            be left out). If not specified then all sub-folders in the bidsfolder will be
                            processed (default: None)
      -m MASKED, --masked MASKED
                            Globlike search pattern (relative to the subject/session folder) to select
                            additional (3D/4D) images from the same space that need to be masked with the
                            same mask, e.g. 'fmap/*_phasediff'. NB: This option can only be used if
                            pattern yields a single file per session (default: None)
      -o OUTPUT [OUTPUT ...], --output OUTPUT [OUTPUT ...]
                            One or two output strings that determine where the skullstripped + additional
                            masked images are saved. Each output string can be the name of a BIDS
                            datatype folder, such as 'anat', or of the derivatives folder, i.e.
                            'derivatives' (default). If the output string is the same as the datatype
                            then the original images are replaced by the skullstripped images (default:
                            None)
      -f, --force           Process images, regardless whether images have already been skullstripped
                            (i.e. if {'SkullStripped': True} in the json sidecar file) (default: False)
      -a ARGS, --args ARGS  Additional arguments that are passed to synthstrip (NB: Use quotes and a
                            leading space to prevent unintended argument parsing) (default: )
      -c {torque,slurm}, --cluster {torque,slurm}
                            Use `torque` or `slurm` to submit the skullstrip jobs to a high-performance
                            compute (HPC) cluster. Can only be used if `--masked` is left empty (default:
                            None)

    examples:
      skullstrip myproject/bids anat/*_T1w*
      skullstrip myproject/bids anat/*_T1w* -p 001 003 -a ' --no-csf'
      skullstrip myproject/bids fmap/*_magnitude1* -m fmap/*_phasediff* -o extra_data fmap
      skullstrip myproject/bids fmap/*_acq-mylabel*_magnitude1* -m fmap/*_acq-mylabel_* -o fmap

Quality control
---------------

``Slicereport`` is a very flexible QC report generator for doing visual inspections on your BIDS data.

::

    usage: slicereport [-h] [-o OUTLINEPATTERN] [-i OUTLINEIMAGE]
                       [-p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]] [-r REPORTFOLDER]
                       [-x XLINKFOLDER [XLINKFOLDER ...]] [-q QCSCORES [QCSCORES ...]]
                       [-c {torque,slurm}] [--options OPTIONS [OPTIONS ...]]
                       [--outputs OUTPUTS [OUTPUTS ...]] [--suboptions SUBOPTIONS [SUBOPTIONS ...]]
                       [--suboutputs SUBOUTPUTS [SUBOUTPUTS ...]]
                       bidsfolder pattern

    A wrapper around the 'slicer' imaging tool (https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Miscvis)
    to generate a web page with a row of image slices for each subject in the BIDS repository, as
    well as individual sub-pages displaying more detailed information. The input images are
    selectable using wildcards, and the output images are configurable via various user options,
    allowing you to quickly create a custom 'slicer' report to do visual quality control on any
    3D/4D imagetype in your repository.

    Requires an existing installation of FSL/slicer

    positional arguments:
      bidsfolder            The bids-directory with the subject data
      pattern               Globlike search pattern to select the images in bidsfolder to be reported,
                            e.g. 'anat/*_T2starw*'

    options:
      -h, --help            show this help message and exit
      -o OUTLINEPATTERN, --outlinepattern OUTLINEPATTERN
                            Globlike search pattern to select red outline images that are projected on
                            top of the reported images (i.e. 'outlinepattern' must yield the same number
                            of images as 'pattern'. Prepend `outlinedir:` if your outline images are in
                            `outlinedir` instead of `bidsdir` (see examples below)`
      -i OUTLINEIMAGE, --outlineimage OUTLINEIMAGE
                            A common red-outline image that is projected on top of all images
      -p PARTICIPANT_LABEL [PARTICIPANT_LABEL ...], --participant_label PARTICIPANT_LABEL [PARTICIPANT_LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub-prefix can
                            be left out). If not specified then all sub-folders in the bidsfolder will be
                            processed
      -r REPORTFOLDER, --reportfolder REPORTFOLDER
                            The folder where the report is saved (default:
                            bidsfolder/derivatives/slicereport)
      -x XLINKFOLDER [XLINKFOLDER ...], --xlinkfolder XLINKFOLDER [XLINKFOLDER ...]
                            A (list of) QC report folder(s) with cross-linkable sub-reports, e.g.
                            bidsfolder/derivatives/mriqc
      -q QCSCORES [QCSCORES ...], --qcscores QCSCORES [QCSCORES ...]
                            Column names for creating an accompanying tsv-file to store QC-rating scores
                            (default: rating_overall)
      -c {torque,slurm}, --cluster {torque,slurm}
                            Use `torque` or `slurm` to submit the slicereport jobs to a high-performance
                            compute (HPC) cluster
      --options OPTIONS [OPTIONS ...]
                            Main options of slicer (see below). (default: "s 1")
      --outputs OUTPUTS [OUTPUTS ...]
                            Output options of slicer (see below). (default: "x 0.4 x 0.5 x 0.6 y 0.4 y 0.5
                            y 0.6 z 0.4 z 0.5 z 0.6")
      --suboptions SUBOPTIONS [SUBOPTIONS ...]
                            Main options of slicer for creating the sub-reports (same as OPTIONS, see
                            below). (default: OPTIONS)
      --suboutputs SUBOUTPUTS [SUBOUTPUTS ...]
                            Output options of slicer for creating the sub-reports (same as OUTPUTS, see
                            below). (default: "S 4 1600")

    OPTIONS:
      L                  : Label slices with slice number.
      l [LUT]            : Use a different colour map from that specified in the header.
      i [MIN] [MAX]      : Specify intensity min and max for display range.
      e [THR]            : Use the specified threshold for edges (if > 0 use this proportion of max-min,
                           if < 0, use the absolute value)
      t                  : Produce semi-transparent (dithered) edges.
      n                  : Use nearest-neighbour interpolation for output.
      u                  : Do not put left-right labels in output.
      s                  : Size scaling factor
      c                  : Add a red dot marker to top right of image

    OUTPUTS:
      x/y/z [SLICE] [..] : Output sagittal, coronal or axial slice (if SLICE > 0 it is a fraction of
                           image dimension, if < 0, it is an absolute slice number)
      a                  : Output mid-sagittal, -coronal and -axial slices into one image
      A [WIDTH]          : Output _all_ axial slices into one image of _max_ width WIDTH
      S [SAMPLE] [WIDTH] : As `A` but only include every SAMPLE'th slice
      LF                 : Start a new line (i.e. works like a row break)

    examples:
      slicereport myproject/bids anat/*_T1w*
      slicereport myproject/bids anat/*_T2w* -r myproject/QC/slicereport_T2 -x myproject/QC/slicereport_T1
      slicereport myproject/bids fmap/*_phasediff* -o fmap/*_magnitude1*
      slicereport myproject/bids/derivatives/fmriprep func/*desc-preproc_bold*
      slicereport myproject/bids/derivatives/fmriprep anat/*desc-preproc_T1w* -o anat/*label-GM*
      slicereport myproject/bids/derivatives/deface anat/*_T1w* -o myproject/bids:anat/*_T1w* --options L e 0.05
      slicereport myproject/bids anat/*_T1w* --outputs x 0.3 x 0.4 x 0.5 x 0.6 x 0.7 LF z 0.3 z 0.4 z 0.5 z 0.6 z 0.7

.. figure:: ./_static/slicereport_skullstrip.png

   Snippet of a ``slicereport`` for doing quality control on ``skullstrip`` output images (see above). The
   background image shows the skull-stripped image in the `extra_data` folder, and the red outline image
   on top shows the contours of the original image in the `anat` folder. Users can click on an image to
   navigate to the individual (more detailed) slicereport of that subject. This example can be generated
   from scratch with just two commands:

.. code-block:: console

   $ skullstrip bids anat/*run-1_T1w* -o extra_data
   $ slicereport bids extra_data/*run-1_T1w* -o anat/*run-1_T1w*
