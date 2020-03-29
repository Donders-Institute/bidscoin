Installation
============

There are two ways to install BIDScoin:

1. A direct (bare metal) installation
2. A docker container installation (experimental)

1. Direct installation
----------------------

System requirements
^^^^^^^^^^^^^^^^^^^

BIDScoin can be installed and should work on Linux, MS Windows and on OS-X computers (this latter option has not been tested) that satisfy the system requirements:

-  dcm2niix
-  python 3

Dcm2niix installation
"""""""""""""""""""""

BIDScoin relies on dcm2niix to convert the source imaging data to nifti. Please download and install `dcm2niix <https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage>`__ yourself according to the instructions. When done, make sure that the path to the dcm2niix binary / executable is set correctly in the BIDScoin `Options`_ in the ``[path_to_bidscoin]/heuristics/bidsmap_template.yaml`` file or in the `Site specific / customized template`_ file.

Python 3 installation
"""""""""""""""""""""

BIDScoin is a python package and therefore a python interpreter needs to be present on the system. On Linux this is usually already the case, but MS Windows users may need to install python themselves. See e.g. `this python 3 distribution <https://docs.anaconda.com/anaconda/install/windows/>`__ for instructions. They may also need to install the `MS Visual C++ <https://visualstudio.microsoft.com/downloads/>`__ (sorry for this pain).

BIDScoin installation
^^^^^^^^^^^^^^^^^^^^^

To install BIDScoin run the following command in your command-shell (institute users may want to activate a `virtual`_ / `conda`_ python environment first):

::

   $ pip install bidscoin

This will give you the latest stable release of the software. To get the very latest (development) version of the software you can install the package directly from the github source code repository:

::

   $ pip install git+https://github.com/Donders-Institute/bidscoin

If you want to edit the code or want to contribute back to the project, you can use the ``-e`` option:

::

   $ pip install -e git+https://github.com/Donders-Institute/bidscoin#egg=bidscoin

If you do not have git (or any other version control system) installed you can `download`_ the code and unzip the code yourself in a directory named e.g. ``bidscoin`` and run (again, with or without the ``-e`` option):

::

   $ pip install -e bidscoin

Updating BIDScoin
^^^^^^^^^^^^^^^^^

Run the pip command as before with the additional ``--upgrade`` option:

::

   $ pip install --upgrade bidscoin

.. note::
   - The bidsmap-files are not garanteed to be compatible between different BIDScoin versions, so after upgrading it may be necessary to re-run the ``bidsmapper`` command before using ``bidscoiner``.
   - After a succesful BIDScoin installation or upgrade, it may be needed to (re)do any adjustments that were done on the ``[path_to_bidscoin]/heuristics/bidsmap_template.yaml`` or `Site specific / customized template`_ file.

2. Docker installation
----------------------

A Docker image of BIDScoin is available on `dockerhub <https://hub.docker.com/r/kasbohm/bidscoin>`__. Follow `these instructions <https://docs.docker.com/get-started>`__ to download, install and run a Docker container. **NB: This is currently still an outdated version, but new versions will be uploaded soon.**

Site specific / customized template
-----------------------------------

If you want to convert many studies with similar acquisition protocols then you may *consider* creating your own customized bidsmap template. This template can then be passed to the `bidsmapper <workflow.html#bidsmapper>`__ tool to automatically recognize the different scans in your protocol and map these to the correct BIDS modality. As a start, you can try adapting the ``[path_to_bidscoin]/heuristics/bidsmap_dccn.yaml`` file to your needs. Editing bidsmap templates requires more indepth knowledge of `YAML <http://yaml.org/>`__ and of how BIDScoin identifies different acquisitions in a protocol given a bidsmap (NB: a bidsmap template is just a void bidsmap).

Generally speaking, a bidsmap file contains a collection of key-value dictionaries that define unique mappings between different types (runs) of source data and BIDS outcome data. For each run in the bidsmap there is a ``provenance`` item, i.e. the pathname of a representative data sample of that run. Each run also contains a source data ``attributes`` item, i.e. a key-value dictionary with keys and values that are extracted from the provenance data sample, as well as a ``bids`` item, i.e. a key-value dictionary that determines the filename of the BIDS output file. The different keys in the ``attributes`` dictionary represent properties of the source data and should uniquely identify the different runs in a session. But they should not vary between sessions, making the length of the bidsmap only dependent on the acquisition protocol and not on the number of subjects and sessions in the data collection. The difference between a bidsmap template and the study bidsmap that comes out of the ``bidsmapper`` is that the template contains / defines the keys that will be used by the bidsmapper and that the template contains all possible runs. The study bidsmap contains only runs that were encountered in the study, with dictionary values that are specific for that study. A bidsmap has different sections for different source data modalities, i.e.  ``DICOM``, ``PAR``, ``P7``, ``Nifti``, ``FileSystem``, as well as a section for the BIDScoin ``Options``. Within each source data section there sub-sections for the different BIDS modalities, i.e. for ``anat``, ``func``, ``dwi``, ``fmap``, ``pet``, ``beh`` and `` extra_data``, and for the ``participant_label`` and ``session_label``. An example bidsmap can be seen below:

.. figure:: ./_static/bidsmap_sample.png

   A study bidsmap
   
.. _Options: options.html
.. _virtual: https://docs.python.org/3.6/tutorial/venv.html
.. _conda: https://conda.io/docs/user-guide/tasks/manage-environments.html
.. _download: https://github.com/Donders-Institute/bidscoin
