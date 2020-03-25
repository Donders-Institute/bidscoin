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

BIDScoin relies on dcm2niix to convert the source imaging data to nifti. Please download and install `dcm2niix <https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage>`__ yourself according to the instructions. When done, make sure that the path to the dcm2niix binary / executable is set correctly in the BIDScoin `options <./options.html#dcm2niix>`__ (see also below)

Python 3 installation
"""""""""""""""""""""

BIDScoin is a python package and therefore a python interpreter needs to be present on the system. On Linux this is usually already the case, but MS Windows users may need to install python themselves. See e.g. `this python 3 distribution <https://docs.anaconda.com/anaconda/install/windows/>`__ for instructions. They may also need to install the `MS Visual C++ <https://visualstudio.microsoft.com/downloads/>`__ (sorry for this pain).

BIDScoin installation
^^^^^^^^^^^^^^^^^^^^^

To install bidscoin run the following command in your command-shell (institute users may want to activate a `virtual`_ / `conda`_ python environment first):

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

After a succesful installation, if needed, edit the ``Options : dcm2niix : path`` value in the ``[path_to_bidscoin]/heuristics/bidsmap_template.yaml`` file according to your system configuration (you may want to use the ``-e`` install option for this). You can best do this using a plain text editor.

Updating BIDScoin
^^^^^^^^^^^^^^^^^

Run the pip command as before with the additional ``--upgrade`` option:

::

   $ pip install --upgrade bidscoin

.. note::
   - The bidsmap-files are not garanteed to be compatible between different BIDScoin versions, so after upgrading it may be necessary to re-run the ``bidsmapper.py`` command before using ``bidscoiner.py``.
   - After upgrading, redo any edits you made to your ``bidsmap_template.yaml`` file.

2. Docker installation
----------------------

A Docker image of BIDScoin is available on `dockerhub <https://hub.docker.com/r/kasbohm/bidscoin>`__. Follow `these instructions <https://docs.docker.com/get-started>`__ to download, install and run a Docker container. **NB: This is currently still an outdated version, but new versions will be uploaded soon.**

.. _dcm2niix: https://github.com/rordenlab/dcm2niix
.. _virtual: https://docs.python.org/3.6/tutorial/venv.html
.. _conda: https://conda.io/docs/user-guide/tasks/manage-environments.html
.. _download: https://github.com/Donders-Institute/bidscoin
