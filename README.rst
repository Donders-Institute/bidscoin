BIDScoin
========

.. raw:: html

   <img name="bidscoin-logo" src="./docs/bidscoin_logo.png" alt="A BIDS converter toolkit" height="325" align="right">

|PyPI version| |PyPI - Python Version|

-  `The BIDScoin workflow`_

   -  `Required source data structure`_
   -  `Coining your source data to BIDS`_

      -  `Step 1a: Running the bidsmapper`_
      -  `Step 1b: Running the bidseditor`_
      -  `Step 2: Running the bidscoiner`_

   -  `Finishing up`_

-  `Plug-in functions`_
-  `BIDScoin functionality / TODO`_
-  `BIDScoin tutorial`_

BIDScoin is a user friendly `open-source`_ python toolkit that converts
("coins") source-level (raw) neuroimaging data-sets to `nifti`_ /
`json`_ / `tsv`_ data-sets that are organized following the Brain
Imaging Data Structure, a.k.a. `BIDS`_ standard. Rather then depending
on complex or ambiguous programmatic logic for the identification of
imaging modalities, BIDScoin uses a direct mapping approach to identify
and convert the raw source data into BIDS data. The information sources
that can be used to map the source data to BIDS are:

1. Information in MRI header files (DICOM, PAR/REC or .7 format; e.g.
   SeriesDescription)
2. Information from nifti headers (e.g. image dimensionality)
3. Information in the file structure (file- and/or directory names, e.g.
   number of files)

..

   NB: Currently, the DICOM support (option 1) has been fully
   implemented, but the support for option 2 and 3 is planned for
   `future`_ releases.

The mapping information is stored as key-value pairs in the human
readable and widely supported `YAML`_ files. The nifti- and json-files
are generated with `dcm2niix`_. In addition, users can provide custom
written `plug-in functions`_, e.g. for using additional sources of
information or e.g. for parsing of Presentation logfiles.

Because all the mapping information can be edited with a graphical user
interface, BIDScoin requires no programming knowledge in order to use
it.

For information on the BIDScoin installation and requirements, see the
`installation guide`_.

The BIDScoin workflow
---------------------

Required source data structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

BIDScoin will take your (raw) source data as well as a YAML file with
the key-value mapping (dictionary) information as input, and returns a
BIDS folder as output. The source data input folder should be organised

.. _The BIDScoin workflow: #the-bidscoin-workflow
.. _Required source data structure: #required-source-data-structure
.. _Coining your source data to BIDS: #coining-your-source-data-to-bids
.. _`Step 1a: Running the bidsmapper`: #step-1a-running-the-bidsmapper
.. _`Step 1b: Running the bidseditor`: #step-1b-running-the-bidseditor
.. _`Step 2: Running the bidscoiner`: #step-2-running-the-bidscoiner
.. _Finishing up: #finishing-up
.. _Plug-in functions: #options-and-plug-in-functions
.. _BIDScoin functionality / TODO: #bidscoin-functionality--todo
.. _BIDScoin tutorial: #bidscoin-tutorial
.. _open-source: https://github.com/Donders-Institute/bidscoin
.. _nifti: https://nifti.nimh.nih.gov/
.. _json: https://www.json.org/
.. _tsv: https://en.wikipedia.org/wiki/Tab-separated_values
.. _BIDS: http://bids.neuroimaging.io
.. _future: #bidscoin-functionality--todo
.. _YAML: http://yaml.org/
.. _dcm2niix: https://github.com/rordenlab/dcm2niix
.. _plug-in functions: #options-and-plug-in-functions
.. _installation guide: ./docs/installation.md

.. |PyPI version| image:: https://badge.fury.io/py/bidscoin.svg
   :target: https://badge.fury.io/py/bidscoin
.. |PyPI - Python Version| image:: https://img.shields.io/pypi/pyversions/bidscoin.svg