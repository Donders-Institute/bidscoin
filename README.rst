========================================
BIDScoin: Coin your imaging data to BIDS
========================================

.. image:: ../bidscoin/bidscoin_logo.png
   :height: 260px
   :align: right
   :alt: Full documentation: https://bidscoin.readthedocs.io
   :target: https://bidscoin.readthedocs.io

.. raw:: html

   <img name="bidscoin-logo" src="./bidscoin/bidscoin_logo.png" height="340px" align="right" alt=" " src="https://bidscoin.readthedocs.io">

|PyPI version| |BIDS| |PyPI - Python Version| |GPLv3| |RTD|

BIDScoin is a user friendly `open-source <https://github.com/Donders-Institute/bidscoin>`__ python toolkit that converts ("coins") source-level (raw) neuroimaging data-sets to `nifti <https://nifti.nimh.nih.gov/>`__ / `json <https://www.json.org/>`__ / `tsv <https://en.wikipedia.org/wiki/Tab-separated_values>`__ data-sets that are organized following the Brain Imaging Data Structure, a.k.a. the `BIDS <http://bids.neuroimaging.io>`__ standard. Rather then depending on complex or ambiguous programmatic logic for source data-type identification, BIDScoin uses a mapping approach to identify and convert the raw source data types into BIDS data. Different runs of source data are identified by way of file system properties (e.g. file size) and/or from file attributes (e.g. ``ProtocolName`` from the DICOM header). The mapping information about how these runs should be converted to BIDS can be pre-specified (e.g. per site), which should provide for a good first automatic data-typing and mapping, using all information available on disk. Then the researcher can interactively check and edit this mapping -- bringing in the missing knowledge that often exists only in his or her head!

Because all the mapping information can be easily edited with the `Graphical User Interface (GUI) <screenshots.html>`__, BIDScoin requires no programming knowledge in order to use it.

BIDScoin is developed at the `Donders Institute <https://www.ru.nl/donders/>`__ of the `Radboud University <https://www.ru.nl/english/>`__.

BIDScoin functionality
----------------------

-  [x] DICOM source data
-  [x] PAR / REC source data (Philips)
-  [x] Physiological logging data\*
-  [x] Fieldmaps\*
-  [x] Multi-echo data\*
-  [x] Multi-coil data\*
-  [x] PET data\*
-  [ ] Stimulus / behavioural logfiles
-  [x] Plug-ins
-  [x] Defacing
-  [x] Multi-echo combination

   ``* = Only DICOM source data / tested for Siemens``

::

   Are you a python programmer with an interest in BIDS who knows all about GE and / or Philips data?
   Are you experienced with parsing stimulus presentation log-files? Or do you have ideas to improve
   the this toolkit or its documentation? Have you come across bugs? Then you are highly encouraged to
   provide feedback or contribute to this project on https://github.com/Donders-Institute/bidscoin.

Note:
-----

   **The full BIDScoin documentation is hosted at** `Read the Docs <https://bidscoin.readthedocs.io>`__

   **Issues can be reported at** `Github <https://github.com/Donders-Institute/bidscoin/issues>`__

.. |PyPI version| image:: https://img.shields.io/pypi/v/bidscoin?color=success
   :target: https://pypi.org/project/bidscoin
.. |PyPI - Python Version| image:: https://img.shields.io/pypi/pyversions/bidscoin.svg
.. |GPLv3| image:: https://img.shields.io/badge/License-GPLv3-blue.svg
   :target: https://www.gnu.org/licenses/gpl-3.0
.. |RTD| image:: https://readthedocs.org/projects/bidscoin/badge/?version=latest
   :target: http://bidscoin.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status
.. |BIDS| image:: https://img.shields.io/badge/BIDS-v1.5.0-blue
   :target: https://bids-specification.readthedocs.io/en/v1.5.0/
   :alt: BIDS
