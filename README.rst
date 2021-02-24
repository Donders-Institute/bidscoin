========================================
BIDScoin: Coin your imaging data to BIDS
========================================

.. image:: ./_static/bidscoin_logo.png
   :height: 260px
   :align: right
   :alt: Full documentation: https://bidscoin.readthedocs.io
   :target: https://bidscoin.readthedocs.io

.. raw:: html

   <img name="bidscoin-logo" src="./docs/_static/bidscoin_logo.png" height="340px" align="right" alt=" " src="https://bidscoin.readthedocs.io">

|PyPI version| |BIDS| |PyPI - Python Version| |GPLv3| |RTD|

BIDScoin is a user friendly `open-source <https://github.com/Donders-Institute/bidscoin>`__ python toolkit that converts ("coins") source-level (raw) neuroimaging data-sets to `nifti <https://nifti.nimh.nih.gov/>`__ / `json <https://www.json.org/>`__ / `tsv <https://en.wikipedia.org/wiki/Tab-separated_values>`__ data-sets that are organized following the Brain Imaging Data Structure, a.k.a. the `BIDS <http://bids.neuroimaging.io>`__ standard. Rather then depending on complex or ambiguous programmatic logic for the identification of imaging modalities, BIDScoin uses a direct mapping approach to identify and convert the raw source data into BIDS data. Different runs of source data are identified by reading information from MRI header files (DICOM or PAR/REC; e.g. 'ProtocolName') and the mapping information about how these different runs should be named in BIDS can be specified a priori as well as interactively by the researcher -- bringing in the missing knowledge that often exists only in his or her head!

Because all the mapping information can be easily edited with a Graphical User Interface (GUI), BIDScoin requires no programming knowledge in order to use it.

BIDScoin is developed at the `Donders Institute <https://www.ru.nl/donders/>`__ of the `Radboud University <https://www.ru.nl/english/>`__.

BIDScoin functionality
----------------------

-  [x] DICOM source data
-  [x] PAR / REC source data (Philips)
-  [ ] P7 source data (GE)
-  [ ] Nifti source data
-  [x] Fieldmaps\*
-  [x] Multi-echo data\*
-  [x] Multi-coil data\*
-  [x] PET data\*
-  [ ] Stimulus / behavioural logfiles
-  [x] Physiological data\*
-  [x] Plug-ins
-  [x] Defacing
-  [x] Multi-echo combination

   ``* = DICOM source data (tested for Siemens)``

::

   Are you a python programmer with an interest in BIDS who knows all about GE and / or Philips data?
   Are you experienced with parsing stimulus presentation log-files? Or do you have ideas to improve
   the this toolkit or its documentation? Have you come across bugs? Then you are highly encouraged to
   provide feedback or contribute to this project on https://github.com/Donders-Institute/bidscoin.

Note:
-----

   **The full BIDScoin documentation is hosted at** `Read the Docs <https://bidscoin.readthedocs.io>`__

   **Issues can be reported at** `Github <https://github.com/Donders-Institute/bidscoin/issues>`__

.. |PyPI version| image:: https://badge.fury.io/py/bidscoin.svg
   :target: https://badge.fury.io/py/bidscoin
.. |PyPI - Python Version| image:: https://img.shields.io/pypi/pyversions/bidscoin.svg
.. |GPLv3| image:: https://img.shields.io/badge/License-GPLv3-blue.svg
   :target: https://www.gnu.org/licenses/gpl-3.0
.. |RTD| image:: https://readthedocs.org/projects/bidscoin/badge/?version=latest
   :target: http://bidscoin.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status
.. |BIDS| image:: https://img.shields.io/badge/BIDS-v1.5.0-blue
   :target: https://bids-specification.readthedocs.io/en/v1.5.0/
   :alt: BIDS
