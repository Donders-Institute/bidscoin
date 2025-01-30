BIDS-apps
=========

BIDScoin comes with a set of command-line applications that can read and write BIDS compliant datasets. These applications can be qualified as `bidsapps <https://bids-apps.neuroimaging.io/>`__, except that they don't strictly adhere to the ``app_name bids_dir output_dir analysis_level`` API and that the bidsapps are all bundled into a single BIDScoin container. Hence, that means that for example a BIDScoin bidsapp command such as:

.. code-block:: console

   $ app_name bids_dir pattern --example option

Could be translated into a Docker command like this:

.. code-block:: console

   $ sudo docker run --rm -v /home/me/bidsfolder:/bidsfolder \
    marcelzwiers/bidscoin:<version> app_name bids_dir pattern --example option

See the `installation instructions <https://bidscoin.readthedocs.io/en/stable/installation.html#using-an-apptainer-singularity-container>`__ for more information on how to use a BIDScoin container and below for more information on the individual bidsapps.

Metadata editing
----------------
If you have a previously converted BIDS data repository and you would like to retrospectively change or replace one or more metadata fields in the json sidecar files you can use ``fixmeta``. Fixmeta is more powerful than conventional find-and-replace tools in that fixmeta can leverage BIDScoin's `special bidsmap features <./bidsmap_features.html>`__::

    usage: fixmeta [-h] [-p LABEL [LABEL ...]] [-b NAME] bidsfolder pattern metadata

    A bidsapp that can change or add metadata in BIDS data repositories. The fixmeta app supports the use
    of special bidsmap features, such as dynamic values to use source data attributes or properties, or to
    populate `IntendedFor` and `B0FieldIdentifier` metadata values

    positional arguments:
      bidsfolder            The BIDS root directory that needs fixing (in place)
      pattern               Globlike recursive search pattern (relative to the subject/session folder) to
                            select the json sidecar targets that need to be fixed, e.g. '*task-*echo-1*'
      metadata              Dictionary with key-value pairs of metadata that need to be fixed. If value
                            is a string, then this metadata is written to the sidecars as is, but if it
                            is a list of `old`/`new` strings, i.e. `[old1, new1, old2, new2, ..]`, then
                            the existing metadata is re-written, with all occurrences of substring `old`
                            replaced by `new`

    options:
      -h, --help            show this help message and exit
      -p LABEL [LABEL ...], --participant LABEL [LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub-prefix can
                            be left out). If not specified then all participants will be processed
      -b NAME, --bidsmap NAME
                            Selects a custom study bidsmap file for extracting source data properties and
                            attributes. If the bidsmap filename is just the base name (i.e. no "/" in the
                            name) then it is assumed to be located in the current directory or in
                            bidsfolder/code/bidscoin. Default: bidsmap.yaml or else the template bidsmap

    examples:
      fixmeta myproject/bids func/*task-reward1* '{"TaskName": "Monetary reward paradigm 1"}'
      fixmeta myproject/bids *acq-reward1* '{"B0FieldIdentifier": ["<<", "_", ">>", ""], "B0FieldSource": ["<<", "_", ">>", ""]}'
      fixmeta myproject/bids fmap/*run-2* '{"IntendedFor": "<<task/*run-2*_bold*>>"}' -p 001 003

Multi-echo combination
----------------------

Before sharing or pre-processing their images, you may want to combine the separate the individual echos of multi-echo MRI acquisitions. The ``echcombine``-tool is a wrapper around ``mecombine`` that writes BIDS valid echo-combined output data::

    usage: echocombine [-h] [-p LABEL [LABEL ...]] [-o DESTINATION] [-a {PAID,TE,average}]
                       [-w [WEIGHT ...]] [-f]
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
      -p LABEL [LABEL ...], --participant LABEL [LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub-prefix can
                            be left out). If not specified then all participants will be processed
                            (default: None)
      -o DESTINATION, --output DESTINATION
                            A string that determines where the output is saved. It can be the name of a
                            BIDS datatype folder, such as 'func', or of the derivatives folder, i.e.
                            'derivatives'. If output is left empty then the combined image is saved in
                            the input datatype folder and the original echo images are moved to the
                            'extra_data' folder (default: )
      -a {PAID,TE,average}, --algorithm {PAID,TE,average}
                            Combination algorithm (default: TE)
      -w [WEIGHT ...], --weights [WEIGHT ...]
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

Before sharing or pre-processing your data, you may want to deface your anatomical MRI scans to protect the privacy of your participants. The ``deface``-tool is a wrapper around `pydeface <https://github.com/poldracklab/pydeface>`__ that writes BIDS valid defaced output images (NB: pydeface requires `FSL <https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation>`__ to be installed on the system)::

    usage: deface [-h] [-p LABEL [LABEL ...]] [-o DESTINATION] [-c [SPECS]] [-a DICT] [-f]
                  bidsfolder pattern

    A wrapper around the 'pydeface' defacing tool (https://github.com/poldracklab/pydeface). Pydeface
    requires an existing installation of FSL flirt

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
      -p LABEL [LABEL ...], --participant LABEL [LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub-prefix can
                            be left out). If not specified then all participants will be processed
                            (default: None)
      -o DESTINATION, --output DESTINATION
                            A string that determines where the defaced images are saved. It can be the
                            name of a BIDS datatype folder, such as 'anat', or of the derivatives folder,
                            i.e. 'derivatives'. If output is left empty then the original images are
                            replaced by the defaced images (default: None)
      -c [SPECS], --cluster [SPECS]
                            Use the DRMAA library to submit the deface jobs to a high-performance compute
                            (HPC) cluster. You can add an opaque DRMAA argument with native
                            specifications for your HPC resource manager (NB: Use quotes and include at
                            least one space character to prevent premature parsing -- see examples)
                            (default: None)
      -a DICT, --args DICT  Additional arguments (in dict/json-style) that are passed to pydeface (NB:
                            Use quotes). See examples for usage (default: {})
      -f, --force           Deface all images, regardless if they have already been defaced (i.e. if
                            {"Defaced": True} in the json sidecar file) (default: False)

    examples:
      deface myproject/bids anat/*_T1w*
      deface myproject/bids anat/*_T1w* -p 001 003 -o derivatives
      deface myproject/bids anat/*_T1w* -c -n "-l walltime=00:60:00,mem=4gb"
      deface myproject/bids anat/*_T1w* -a '{"cost": "corratio", "verbose": ""}'

Multi-echo defacing
-------------------

This utility is very similar to the `deface <#defacing>`__ utility above, except that it can handle multi-echo data::

    usage: medeface [-h] [-m PATTERN] [-p LABEL [LABEL ...]] [-o DESTINATION] [-c [SPECS]] [-a DICT] [-f]
                    bidsfolder pattern

    A wrapper around the 'pydeface' defacing tool (https://github.com/poldracklab/pydeface) that
    computes a defacing mask on a (temporary) echo-combined image and then applies it to each
    individual echo-image. Pydeface requires an existing installation of FSL flirt

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
      -m PATTERN, --maskpattern PATTERN
                            Globlike search pattern (relative to the subject/session folder) to select
                            the images from which the defacemask is computed, e.g. 'anat/*_part-
                            mag_*_T2starw*'. If not given then 'pattern' is used (default: None)
      -p LABEL [LABEL ...], --participant LABEL [LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub-prefix can
                            be left out). If not specified then all participants will be processed
                            (default: None)
      -o DESTINATION, --output DESTINATION
                            A string that determines where the defaced images are saved. It can be the
                            name of a BIDS datatype folder, such as 'anat', or of the derivatives folder,
                            i.e. 'derivatives'. If output is left empty then the original images are
                            replaced by the defaced images (default: None)
      -c [SPECS], --cluster [SPECS]
                            Use the DRMAA library to submit the deface jobs to a high-performance compute
                            (HPC) cluster. You can add an opaque DRMAA argument with native
                            specifications for your HPC resource manager (NB: Use quotes and include at
                            least one space character to prevent premature parsing -- see examples)
                            (default: None)
      -a DICT, --args DICT  Additional arguments (in dict/json-style) that are passed to pydeface (NB:
                            Use quotes). See examples for usage (default: {})
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

The ``skullstrip``-tool is a wrapper around the synthstrip tool that writes BIDS valid brain extracted output data::

    usage: skullstrip [-h] [-p LABEL [LABEL ...]] [-m PATTERN] [-o DESTINATION [DESTINATION ...]] [-f]
                      [-a ARGS] [-c [SPECS]]
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
      -p LABEL [LABEL ...], --participant LABEL [LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub-prefix can
                            be left out). If not specified then all participants will be processed
                            (default: None)
      -m PATTERN, --masked PATTERN
                            Globlike search pattern (relative to the subject/session folder) to select
                            additional (3D/4D) images from the same space that need to be masked with the
                            same mask, e.g. 'fmap/*_phasediff'. NB: This option can only be used if
                            pattern yields a single file per session (default: None)
      -o DESTINATION [DESTINATION ...], --output DESTINATION [DESTINATION ...]
                            One or two output strings that determine where the skullstripped + additional
                            masked images are saved. Each output string can be the name of a BIDS
                            datatype folder, such as 'anat', or of the derivatives folder, i.e.
                            'derivatives' (default). If the output string is the same as the datatype
                            then the original images are replaced by the skullstripped images (default:
                            None)
      -f, --force           Process images, regardless whether images have already been skullstripped
                            (i.e. if {'SkullStripped': True} in the json sidecar file) (default: False)
      -a ARGS, --args ARGS  Additional arguments that are passed to synthstrip (NB: Use quotes and
                            include at least one space character to prevent premature parsing) (default:
                            )
      -c [SPECS], --cluster [SPECS]
                            Use the DRMAA library to submit the skullstrip jobs to a high-performance
                            compute (HPC) cluster. You can add an opaque DRMAA argument with native
                            specifications for your HPC resource manager (NB: Use quotes and include at
                            least one space character to prevent premature parsing -- see examples)
                            (default: None)

    examples:
      skullstrip myproject/bids anat/*_T1w*
      skullstrip myproject/bids anat/*_T1w* -p 001 003 -a " --no-csf"
      skullstrip myproject/bids fmap/*_magnitude1* -m fmap/*_phasediff* -o extra_data fmap
      skullstrip myproject/bids fmap/*_acq-mylabel*_magnitude1* -m fmap/*_acq-mylabel_* -o fmap

Quality control
---------------

``Slicereport`` is a very flexible QC report generator for doing visual inspections on your BIDS data::

    usage: slicereport [-h] [-o PATTERN] [-i FILENAME] [-p LABEL [LABEL ...]] [-r FOLDER]
                       [-x FOLDER [FOLDER ...]] [-q NAME [NAME ...]] [-c [SPECS]]
                       [--operations OPERATIONS] [--suboperations OPERATIONS]
                       [--options OPTIONS [OPTIONS ...]] [--outputs OUTPUTS [OUTPUTS ...]]
                       [--suboptions OPTIONS [OPTIONS ...]] [--suboutputs OUTPUTS [OUTPUTS ...]]
                       bidsfolder pattern

    A wrapper around the 'fslmaths' (https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Fslutils) and 'slicer'
    imaging tools (https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/Miscvis) to generate a web page with a
    row of image slices for each subject in the BIDS repository, as well as individual sub-pages
    displaying more detailed information. The input images are selectable using wildcards (all
    nibabel image formats are supported), and the output images are configurable via various user
    options, allowing you to quickly create a custom 'slicer' report to do visual quality control
    on any 3D/4D imagetype in your repository.

    Requires an existing installation of FSL tools (i.e. fsl-libvis, fsl-avwutils and fsl-flirt)

    Set the environment variable BIDSCOIN_DEBUG=TRUE to save intermediate data

    positional arguments:
      bidsfolder            The bids-directory with the subject data
      pattern               Globlike search pattern to select the images in bidsfolder to be reported,
                            e.g. 'anat/*_T2starw*'

    options:
      -h, --help            show this help message and exit
      -o PATTERN, --outlinepattern PATTERN
                            Globlike search pattern to select red outline images that are projected on
                            top of the reported images (i.e. 'outlinepattern' must yield the same number
                            of images as 'pattern'. Prepend `outlinedir:` if your outline images are in
                            `outlinedir` instead of `bidsdir` (see examples below)`
      -i FILENAME, --outlineimage FILENAME
                            A common red-outline image that is projected on top of all images
      -p LABEL [LABEL ...], --participant LABEL [LABEL ...]
                            Space separated list of sub-# identifiers to be processed (the sub-prefix can
                            be left out). If not specified then all participants will be processed
      -r FOLDER, --reportfolder FOLDER
                            The folder where the report is saved (default:
                            bidsfolder/derivatives/slicereport)
      -x FOLDER [FOLDER ...], --xlinkfolder FOLDER [FOLDER ...]
                            A (list of) QC report folder(s) with cross-linkable sub-reports, e.g.
                            bidsfolder/derivatives/mriqc
      -q NAME [NAME ...], --qcscores NAME [NAME ...]
                            Column names for creating an accompanying tsv-file to store QC-rating scores
                            (default: rating_overall)
      -c [SPECS], --cluster [SPECS]
                            Use the DRMAA library to submit the slicereport jobs to a high-performance
                            compute (HPC) cluster. You can add an opaque DRMAA argument with native
                            specifications for your HPC resource manager (NB: Use quotes and include at
                            least one space character to prevent premature parsing -- see examples)
      --operations OPERATIONS
                            One or more fslmaths operations that are performed on the input image (before
                            slicing it for the report). OPERATIONS is opaquely passed as is: `fslmaths
                            inputimage OPERATIONS reportimage`. NB: Use quotes and include at least one
                            space character to prevent premature parsing, e.g. " -Tmean" or "-Tstd -s 3"
                            (default: -Tmean)
      --suboperations OPERATIONS
                            The same as OPERATIONS but then for the sub-report instead of the main
                            report: `fslmaths inputimage SUBOPERATIONS subreportimage` (default: -Tmean)
      --options OPTIONS [OPTIONS ...]
                            Main options of slicer (see below). (default: "s 1")
      --outputs OUTPUTS [OUTPUTS ...]
                            Output options of slicer (see below). (default: "x 0.4 x 0.5 x 0.6 y 0.4 y
                            0.5 y 0.6 z 0.4 z 0.5 z 0.6")
      --suboptions OPTIONS [OPTIONS ...]
                            Main options of slicer for creating the sub-reports (same as OPTIONS, see
                            below). (default: OPTIONS)
      --suboutputs OUTPUTS [OUTPUTS ...]
                            Output options of slicer for creating the sub-reports (same as OUTPUTS, see
                            below). (default: "S 4 1600")

    OPTIONS:
      L                  : Label slices with slice number.
      l [LUT]            : Use a different colour map from that specified in the header (see $FSLDIR/etc/luts)
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
      slicereport bids anat/*_T1w*
      slicereport bids anat/*_T2w* -r QC/slicereport_T2 -x QC/slicereport_T1
      slicereport bids fmap/*_phasediff* -o fmap/*_magnitude1* -c "--time=00:10:00 --mem=2000"
      slicereport bids/derivatives/fmriprep func/*desc-preproc_bold* --suboperations " -Tstd"
      slicereport bids/derivatives/fmriprep anat/*desc-preproc_T1w* -o anat/*label-GM* -x bids/derivatives/fmriprep
      slicereport bids/derivatives/deface anat/*_T1w* -o bids:anat/*_T1w* --options L e 0.05
      slicereport bids anat/*_T1w* --outputs x 0.3 x 0.4 x 0.5 x 0.6 x 0.7 LF z 0.3 z 0.4 z 0.5 z 0.6 z 0.7

.. figure:: ./_static/slicereport_skullstrip.png

   Snippet of a ``slicereport`` for doing quality control on ``skullstrip`` output images (see above). The
   background image shows the skull-stripped image in the `extra_data` folder, and the red outline image
   on top shows the contours of the original image in the `anat` folder. Users can click on an image to
   navigate to the individual (more detailed) slicereport of that subject. This example can be generated
   from scratch with just two commands:

.. code-block:: console

   $ skullstrip bids anat/*run-1_T1w* -o extra_data
   $ slicereport bids extra_data/*run-1_T1w* -o anat/*run-1_T1w*

Click `here <_static/slicereport/index.html>`__ to view a sample slicereport
