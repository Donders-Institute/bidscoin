Installation
============

BIDScoin can be installed and should work on Linux, MS Windows and on OS-X computers (this latter option has not been tested) that satisfy the system requirements:

-  dcm2niix
-  python 3.6 or higher

Dcm2niix installation
---------------------

BIDScoin relies on dcm2niix to convert DICOM and PAR/REC files to nifti. Please download and install `dcm2niix <https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage>`__ yourself according to the instructions. When done, make sure that the path to the dcm2niix binary / executable is set correctly in the BIDScoin `Options`_ in the ``[path_to_bidscoin]/heuristics/bidsmap_template.yaml`` file or in the `Site specific / customized template <advanced.html#site-specific-customized-template>`__ file.

Python 3 installation
---------------------

BIDScoin is a python package and therefore a python interpreter needs to be present on the system. On Linux this is usually already the case, but MS Windows users may need to install python themselves. See e.g. `this python 3 distribution <https://docs.anaconda.com/anaconda/install/windows/>`__ for instructions. They may also need to install the `MS Visual C++ <https://visualstudio.microsoft.com/downloads/>`__ build tools (sorry for this pain).

BIDScoin installation
---------------------

To install BIDScoin on your system run the following command in a command-terminal (institute users may want to activate a `virtual`_ / `conda`_ python environment first):

.. code-block:: console

   $ pip install bidscoin

This will give you the latest stable release of the software. To get the very latest (development) version of the software you can install the package directly from the github source code repository:

.. code-block:: console

   $ pip install git+https://github.com/Donders-Institute/bidscoin

If you do not have git (or any other version control system) installed you can `download`_ and unzip the code yourself in a directory named e.g. ``bidscoin`` and run:

.. code-block:: console

   $ pip install bidscoin

Updating BIDScoin
^^^^^^^^^^^^^^^^^

Run the pip command as before with the additional ``--upgrade`` option:

.. code-block:: console

   $ pip install --upgrade bidscoin

.. caution::
   - The bidsmaps are not garanteed to be compatible between different BIDScoin versions
   - After a succesful BIDScoin installation or upgrade, it may be needed to (re)do any adjustments that were done on the `Site specific / customized template <advanced.html#site-specific-customized-template>`__ file(s) (so make a back-up of these before you upgrade)

.. _Options: options.html
.. _virtual: https://docs.python.org/3.6/tutorial/venv.html
.. _conda: https://conda.io/docs/user-guide/tasks/manage-environments.html
.. _download: https://github.com/Donders-Institute/bidscoin

