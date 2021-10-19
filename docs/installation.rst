Installation
============

Python 3 installation
---------------------

BIDScoin is a Python package and can be installed on Linux, MS Windows and on OS-X computers that can run a Python interpreter (v3.8 or higher). On Linux and OS-X this is usually already the case, but MS Windows users may need to first install Python themselves. See e.g. this `Python 3 distribution <https://docs.anaconda.com/anaconda/install/windows/>`__ for instructions.

BIDScoin installation
---------------------

To install BIDScoin on your system run one of the following commands in a command-terminal (tip: you may want or need to install bidscoin in a `virtual`_ / `conda`_ Python environment):

.. code-block:: console

   $ pip install bidscoin                           # Use this when you want to convert conventional MR imaging data with the dcm2niix2bids plugin
   $ pip install bidscoin[spec2nii2bids]            # Use this when you want to convert MR spectroscopy data with the spec2nii2bids plugin
   $ pip install bidscoin[phys2bidscoin]            # Use this when you want to convert physiological data with the phys2bidscoin plugin
   $ pip install bidscoin[deface]                   # Use this when you want to deface anatomical MRI scans. NB: Requires FSL to be installed on your system
   $ pip install bidscoin[deface,phys2bidscoin]     # Use this to install two extra packages
   $ pip install bidscoin[all]                      # Use this to install all extra packages

These install commands can be run independently and will give you the latest stable release of BIDScoin and its `plugins <options.html#dcm2niix2bids-plugin>`__. Alternatively, if you need to use the very latest (development / unstable) version of the software, you can also install BIDScoin directly from the github source code repository:

.. code-block:: console

   $ pip install --upgrade git+https://github.com/Donders-Institute/bidscoin

If you do not have git (or any other version control system) installed you can `download`_ and unzip the code yourself in a directory named e.g. 'bidscoin' and run:

.. code-block:: console

   $ pip install ./bidscoin

Dcm2niix installation
---------------------

The default 'dcm2niix2bids' plugin relies on dcm2niix to convert DICOM and PAR/REC source data to nifti. To make use of dcm2niix, please download and install `dcm2niix <https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage>`__ yourself according to the instructions. When done, make sure that the path to the dcm2niix executable is set correctly in the `Options`_ section in your bidsmap. This can be done in two ways:

1. Open your template bidsmap with a text editor and adjust the settings as needed. The default template bidsmap is located in the [path_to_bidscoin]/heuristics subfolder -- see the output of ``bidscoin -t`` for the fullpath location on your system.
2. Go to the `Options`_ tab the first time the BIDScoin GUI is launched and adjust the settings as needed. Then click the [Set as default] button to save the settings to your default template bidsmap.

Testing BIDScoin
^^^^^^^^^^^^^^^^

You can run the 'bidscoin' utility to test the installation of your BIDScoin tools and settings:

.. code-block:: console

   $ bidscoin -t

Updating BIDScoin
^^^^^^^^^^^^^^^^^

Run the pip command as before with the additional ``--upgrade`` option, e.g.:

.. code-block:: console

   $ pip install --upgrade bidscoin

.. caution::
   - The bidsmaps are not garanteed to be compatible between different BIDScoin versions
   - After a succesful BIDScoin installation or upgrade, it may be needed to (re)do any adjustments that were done on your `template bidsmap <advanced.html#customized-template-bidsmap>`__ (so make a back-up of it before you upgrade)

.. _Options: options.html
.. _virtual: https://docs.python.org/3.6/tutorial/venv.html
.. _conda: https://conda.io/docs/user-guide/tasks/manage-environments.html
.. _download: https://github.com/Donders-Institute/bidscoin

Singularity
-----------

BIDScoin can be executed using a `Singularity <https://singularity.hpcng.org/>`__ image. Read `Singularity documentation <https://singularity.hpcng.org/user-docs/master/>`__ for installation and usage instructions.

The current image includes:

* Debian stable,
* the latest version of `dcm2niix <https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage>`__,
* the latest stable release of BIDScoin.

Dependencies:

* Debian (or Debian-like, e.g., Ubuntu) host system,
* `debootstrap <https://packages.debian.org/bullseye/debootstrap>`__ package.

Building the image
^^^^^^^^^^^^^^^^^^

Execute the following command to build the BIDScoin image.

.. code-block:: console

   $ sudo singularity build bidscoin.sif singularity.def

Run BIDScoin tools from the image
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Execute BIDScoin tool using the following command:

.. code-block:: console

   $ singularity exec bidscoin.sif <bidscoin_tool> <bidscoin_tool_args>

Where ``<bidscoin_tool>`` is a BIDScoin tool (e.g., ``bidsmapper``, ``bidscoiner``, ``dicomsort``) and ``<bidscoin_tool_args>`` are the tool's arguments.

If your data doesn't reside in home directory, add ``--bind`` Singularity argument which maps a directory from the host system to one inside the Singularity container.

.. code-block:: console

   $ singularity exec bidscoin.sif --bind <host_dir>:<container_dir> <bidscoin_tool> <bidscoin_tool_args>

For example:

.. code-block:: console

   $ singularity exec --bind /my/data:/mnt bidscoin.sif bidscoiner /my/data/source /my/data/bids

.. tip::

   Since there is no fixed entry point to the container, you can also use it to execute dcm2niix.

Latest develop release
^^^^^^^^^^^^^^^^^^^^^^

To install the latest develop realease of BIDScoin, substitute

.. code-block:: console

   pip3 install bidscoin --no-deps

with

.. code-block:: console

   pip3 install --upgrade git+https://github.com/Donders-Institute/bidscoin

in the definition ``singularity.def`` file.

Speed up building the image
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To speed up building the Singularity image, you can change the ``apt`` servers to download the packages from a location closer to you. Add the following line as the first command in the ``%post`` section of  ``singularity.def`` file.

.. code-block:: console

   echo 'deb http://ftp.at.debian.org/debian stable main' > /etc/apt/sources.list

Troubleshooting
^^^^^^^^^^^^^^^

The image didn't work after copying it to a CentOS 7 host system. The problem was kernel version older than 3.15. A working fix is to add the following line at the end of ``%post`` section of  ``singularity.def`` file.

.. code-block:: console

   strip --remove-section=.note.ABI-tag /usr/lib/x86_64-linux-gnu/libQt5Core.so.5

The fix comes from these resources:

* (Answer #3) https://answers.launchpad.net/yade/+question/696260/
* https://github.com/wkhtmltopdf/wkhtmltopdf/issues/4497
* https://stackoverflow.com/questions/58912268/singularity-container-python-pytorch-why-does-import-torch-work-on-arch-l
