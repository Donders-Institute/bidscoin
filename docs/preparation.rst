Data preparation
================

Required source data structure
------------------------------

BIDScoin requires that the source data input folder is be organised 
according to a ``/sub-identifier/[ses-identifier]/seriesfolder/dicomfiles`` 
structure. This data organization is how users receive their data from the
(Siemens) scanners at the `DCCN <https://www.ru.nl/donders/>`__ (NB: the
``ses-identifier`` sub-folder is optional and can be left out).

Utilitities
-----------

-  If your data is not already organized in this way, you can use the
   handy `dicomsort <./bidscoin/dicomsort.py>`__ command-line utility to
   move your unordered or DICOMDIR ordered DICOM-files into a
   ``seriesfolder`` organization with the DICOM series-folders being
   named [SeriesNumber]-[SeriesDescription]. Series folders contain a
   single data type and are typically acquired in a single run.

-  Another command-line utility that can be helpful in organizing your
   source data is `rawmapper <./bidscoin/rawmapper.py>`__. This utility
   can show you the overview (map) of all the values of DICOM-fields of
   interest in your data-set and, optionally, use these fields to rename
   your source data sub-folders (this can be handy e.g. if you manually
   entered subject-identifiers as [Additional info] at the scanner
   console and you want to use these to rename your subject folders).

.. note::
   If these utilities do not satisfy your needs, then have a look at this
   `reorganize\_dicom\_files <https://github.com/robertoostenveld/bids-tools/blob/master/doc/reorganize_dicom_files.md>`__
   tool.

