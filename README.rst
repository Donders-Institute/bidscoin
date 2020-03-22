BIDScoin: Coin your imaging data to BIDS
========================================

|PyPI version| |PyPI - Python Version|

.. image:: ./docs/_static/bidscoin_logo.png
   :height: 125
   :alt: A BIDS converter toolkit
   :align: right

BIDScoin is a user friendly
`open-source <https://github.com/Donders-Institute/bidscoin>`__ python
toolkit that converts ("coins") source-level (raw) neuroimaging
data-sets to `nifti <https://nifti.nimh.nih.gov/>`__ /
`json <https://www.json.org/>`__ /
`tsv <https://en.wikipedia.org/wiki/Tab-separated_values>`__ data-sets
that are organized following the Brain Imaging Data Structure, a.k.a.
`BIDS <http://bids.neuroimaging.io>`__ standard. Rather then depending
on complex or ambiguous programmatic logic for the identification of
imaging modalities, BIDScoin uses a direct mapping approach to identify
and convert the raw source data into BIDS data. The information sources
that can be used to map the source data to BIDS are:

1. Information in MRI header files (DICOM, PAR/REC or .7 format; e.g.
   SeriesDescription)
2. Information from nifti headers (e.g. image dimensionality)
3. Information in the file structure (file- and/or directory names, e.g.
   number of files)

    NB: Currently, the DICOM support (option 1) has been fully
    implemented, but the support for option 2 and 3 is planned for
    `future <#bidscoin-functionality--todo>`__ releases.

The mapping information is stored as key-value pairs in the human
readable and widely supported `YAML <http://yaml.org/>`__ files. The
nifti- and json-files are generated with
`dcm2niix <https://github.com/rordenlab/dcm2niix>`__. In addition, users
can provide custom written `plug-in
functions <#options-and-plug-in-functions>`__, e.g. for using additional
sources of information or e.g. for parsing of Presentation logfiles.

Because all the mapping information can be edited with a graphical user
interface, BIDScoin requires no programming knowledge in order to use
it.

For the the full documentation visit the `BIDScoin readthedocs page<https://bidscoin.readthedocs.io>`__.

.. |PyPI version| image:: https://badge.fury.io/py/bidscoin.svg
   :target: https://badge.fury.io/py/bidscoin
.. |PyPI - Python Version| image:: https://img.shields.io/pypi/pyversions/bidscoin.svg
