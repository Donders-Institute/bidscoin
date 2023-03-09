Installation
============

Python installation
-------------------

BIDScoin is a Python 3 package and can be installed on Linux, MS Windows and on OS-X computers, as long as a Python interpreter (v3.8 or higher) is available on the system. On Linux and OS-X this is usually already the case, but MS Windows users may need to first install Python themselves. See e.g. this `Python 3 distribution <https://docs.anaconda.com/anaconda/install/windows/>`__ for instructions.

BIDScoin installation
---------------------

To install BIDScoin on your system run one of the following commands in your command-line interface / shell (tip: you may want or need to install bidscoin in a `virtual`_ / `conda`_ Python environment):

.. code-block:: console

   $ pip install bidscoin                       # Use this when you want to convert conventional MR imaging data with the dcm2niix2bids plugin
   $ pip install bidscoin[spec2nii2bids]        # Use this when you want to convert MR spectroscopy data with the spec2nii2bids plugin
   $ pip install bidscoin[deface]               # Use this when you want to deface anatomical MRI scans. NB: Requires FSL to be installed on your system
   $ pip install bidscoin[deface,pet2bids]      # Use this when you want to deface anatomical MRI scans and convert PET data with the pet2bids plugin
   $ pip install bidscoin[all]                  # Use this to install all extra packages

These install commands can be run independently and will give you the latest stable release of BIDScoin and its `plugins <options.html#dcm2niix2bids-plugin>`__. Alternatively, if you need to use the very latest (development / unstable) version of the software, you can also install BIDScoin directly from the github source code repository:

.. code-block:: console

   $ pip install git+https://github.com/Donders-Institute/bidscoin

If you do not have git (or any other version control system) installed you can `download`_ and unzip the code yourself in a folder named e.g. 'bidscoin' and run:

.. code-block:: console

   $ pip install ./bidscoin

Updating BIDScoin
^^^^^^^^^^^^^^^^^

Run your pip install command as before with the additional ``--upgrade`` or ``--force-reinstall`` option, e.g.:

.. code-block:: console

   $ pip install --upgrade bidscoin                                                     # The latest stable release
   $ pip install --force-reinstall git+https://github.com/Donders-Institute/bidscoin    # The latest code (add ``--no-deps`` to only upgrade the bidscoin package)

.. caution::
   - The bidsmaps are not guaranteed to be compatible between different BIDScoin versions
   - After a successful BIDScoin installation or upgrade, it may be needed to (re)do any adjustments that were done on your `template bidsmap <bidsmap.html#building-your-own-template-bidsmap>`__ (so make a back-up of it before you upgrade)

.. _Options: options.html
.. _virtual: https://docs.python.org/3/tutorial/venv.html
.. _conda: https://conda.io/docs/user-guide/tasks/manage-environments.html
.. _download: https://github.com/Donders-Institute/bidscoin

Dcm2niix installation
---------------------

Unfortunately the pip installer can only install Python software and the default 'dcm2niix2bids' plugin relies on an external application named `dcm2niix <https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage>`__ to convert DICOM and PAR/REC source data to NIfTI. To make use of the dcm2niix2bids plugin you should therefore download and install dcm2niix yourself according to the instructions. When done, make sure that the dcm2niix executable is on your user or system path (Windows users can add the path permanently, e.g. by running: ``setx path "%path%;C:\Program Files\dcm2niix"``). Otherwise, make sure that the command to run the dcm2niix executable (exactly as if you would run it yourself in your command terminal) is set correctly in the `Options`_ section in your bidsmap. This can be done in two ways:

1. Open your template bidsmap with a text editor and adjust the settings as needed. The default template bidsmap is located in the [path_to_bidscoin]/heuristics subfolder -- see the output of ``bidscoin -p`` for the fullpath location on your system.
2. Go to the `Options`_ tab the first time the BIDScoin GUI is launched and adjust the settings as needed. Then click the [Set as default] button to save the settings to your default template bidsmap.

.. tip::

   Install the `pigz <https://zlib.net/pigz/>`__ tool to speed-up dcm2niix. An easy way to install both dcm2niix and pigz at once, is to install  `MRIcroGL <https://www.nitrc.org/projects/mricrogl/>`__

Testing BIDScoin
----------------

You can run the 'bidscoin' utility to test the installation of your BIDScoin installation and settings:

.. code-block:: console

   $ bidscoin -t                        # Test with the default template bidsmap
   $ bidscoin -t my_template_bidsmap    # Test with your custom template bidsmap

See also the `Troubleshooting guide <troubleshooting.html#installation>`__ for more information on potential installation issues.

Using an Apptainer (Singularity) container
------------------------------------------

An alternative for installing Python, BIDScoin and it's dependencies yourself is to execute BIDScoin commands using an `Apptainer <https://apptainer.org>`__ container. Executing BIDScoin commands via a container is less simple than running them directly on your host computer, read the `official documentation <https://apptainer.org/docs/user/latest>`__ for installation and usage instructions. NB: "Singularity" has been rebranded as "Apptainer", so Singularity users should replace ``apptainer`` for ``singularity`` in the commands given below.

The Apptainer current image includes:

* Debian Linux (see https://hub.docker.com/_/python)
* the latest version of `dcm2niix <https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage>`__
* the latest stable release of BIDScoin and its plugins

The current image does not include this (non-free) software needed for some bidsapps:

* FSL (needed for ``deface`` and ``slicereport``)
* Freesurfer/synthstrip (needed for ``skullstrip``)

Building the container image
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Download the Apptainer `definition file <https://github.com/Donders-Institute/bidscoin/blob/master/apptainer.def>`__ and execute the following command to build a BIDScoin container image:

.. code-block:: console

   $ sudo apptainer build bidscoin.sif apptainer.def

Alternatively, you can first build a Docker image (see instructions in the section below), save it to e.g. `bidscoin.tar` and then convert it into a Apptainer image using:

.. code-block:: console

   $ sudo apptainer build bidscoin.sif bidscoin.tar

Run BIDScoin tools in the container
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use the following command syntax to execute BIDScoin tools in the container:

.. code-block:: console

   $ apptainer exec bidscoin.sif <bidscoin_tool> <bidscoin_tool_args>

Where ``<bidscoin_tool>`` is a BIDScoin tool (e.g., ``bidsmapper``, ``bidscoiner``, ``dicomsort``) and ``<bidscoin_tool_args>`` are the tool's arguments. If your data doesn't reside in your home folder, then you need to add a ``--bind`` Apptainer argument which maps a folder from the host system to a folder inside the Apptainer container:

.. code-block:: console

   $ apptainer exec bidscoin.sif --bind <host_dir>:<container_dir> <bidscoin_tool> <bidscoin_tool_args>

So for instance, if you have source data in ``myhome/data/raw``, instead of running ``bidsmapper data/raw data/bids`` and then ``bidsmapper data/raw data/bids`` from your home directory, you now execute:

.. code-block:: console

   $ xhost +
   $ apptainer exec bidscoin.sif bidsmapper data/raw data/bids
   $ xhost -
   $ apptainer exec bidscoin.sif bidscoiner data/raw data/bids

The `xhost +` command allows Apptainer to open a graphical display on your computer and normally needs to be run once before launching a GUI application, i.e. is needed for running the bidseditor. If your data resides elsewhere, say in ``/myproject/data/raw`` then you should add ``--bind /myproject`` as an additional input argument (see the documentation for usage and setting environment variables to automatically bind your root paths for all containers).

Using a Docker container
------------------------

If the Apptainer container is not working for you, it is also possible to use a `Docker <https://docs.docker.com>`__ container. The Docker versus Apptainer image and container usage are very similar, and both have their pros and cons. A fundamental argument for using Apptainer is that it doesn't require root permission (admin rights), whereas a fundamental argument for using Docker is that it is not limited to Linux hosts.

The current Docker image includes the same as the Apptainer image:

* Debian Linux (see https://hub.docker.com/_/python)
* the latest version of `dcm2niix <https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage>`__
* the latest stable release of BIDScoin and its plugins

Likewise, the current image does not include this (non-free) software needed for some bidsapps:

* FSL (needed for ``deface`` and ``slicereport``)
* Freesurfer/synthstrip (needed for ``skullstrip``)

Building the container image
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Download the `Dockerfile <https://github.com/Donders-Institute/bidscoin/blob/master/Dockerfile>`__ and execute the following command to build a BIDScoin container image:

.. code-block:: console

   $ sudo docker build -t bidscoin .

Run BIDScoin tools in the container
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Executing BIDScoin commands via Docker is less simple than via Apptainer (and surely less simple than running them directly on your host computer). For instance, it is typically needed to bind-mount your data folder(s) in the container and, for the bidseditor, to bind-mount an x-server socket to display the GUI in your host computer. The syntax to run dockerized bidscoin tools is:

.. code-block:: console

   $ docker run --rm -v <bind_mount> bidscoin <bidscoin_tool> <bidscoin_tool_args>

If you have source data in ``/my/data/raw``, instead of running ``bidsmapper /my/data/raw /my/data/bids`` and then ``bidsmapper /my/data/raw /my/data/bids``, you now execute for instance:

.. code-block:: console

   $ xhost +
   $ sudo docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v /my/data:/mnt bidscoin bidsmapper /my/data/raw /my/data/bids
   $ xhost -
   $ sudo docker run --rm -v /my/data:/my/data bidscoin bidscoiner /my/data/raw /my/data/bids

As for Apptainer, the `xhost +` is normally needed to be launching a GUI application, but a few more arguments are now required, i.e. ``-e`` for setting the display number and ``-v`` for binding the data volume and for binding the x-server socket (see the documentation for usage and configuring bind propagation).
