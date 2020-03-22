BIDScoin: Coin your imaging data to BIDS
========================================

.. image:: ./_static/bidscoin_logo.png
  :height: 325px
  :align: right
  :alt: Full documentation: https://bidscoin.readthedocs.io
  :target: https://bidscoin.readthedocs.io

.. raw:: html

   <img name="bidscoin-logo" src="./docs/_static/bidscoin_logo.png" height="325px" align="right" alt=" " src="https://bidscoin.readthedocs.io">

|PyPI version| |PyPI - Python Version|

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

BIDScoin functionality / TODO
-----------------------------

-  [x] DICOM source data
-  [x] PAR / REC source data
-  [ ] P7 source data
-  [ ] Nifti source data
-  [x] Fieldmaps\*
-  [x] Multi-echo data\*
-  [x] Multi-coil data\*
-  [x] PET data\*
-  [ ] Stimulus / behavioural logfiles

   ``* = Only for DICOM source data``

::

    Are you a python programmer with an interest in BIDS who knows all about GE and / or Philips data?
    Are you experienced with parsing stimulus presentation log-files? Or do you have ideas to improve
    the this toolkit or its documentation? Have you come across bugs? Then you are highly encouraged to
    provide feedback or contribute to this project on https://github.com/Donders-Institute/bidscoin.

Note:

|   **The full BIDScoin documentation is hosted at** `Read the Docs <https://bidscoin.readthedocs.io>`__
|   **Issues can be reported at** `github <https://github.com/Donders-Institute/bidscoin/issues>`__

.. |PyPI version| image:: https://badge.fury.io/py/bidscoin.svg
   :target: https://badge.fury.io/py/bidscoin
.. |PyPI - Python Version| image:: https://img.shields.io/pypi/pyversions/bidscoin.svg
