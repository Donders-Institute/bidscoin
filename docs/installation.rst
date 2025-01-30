Installation
============

BIDScoin can be installed directly on your operating system, or in a so-called container. Direct installation is arguably simpler and lighter, but containerized installations are better guaranteed to always work and be reproducible. Below you find instructions for direct installation, followed by instructions for installation in a container. Alternatively, if you like to use a container but don't like the complexity of its overhead, you can install `Neurodesk <https://www.neurodesk.org/>`__ and use its pre-installed transparent BIDScoin container without needing to know anything about containers.

Python installation
-------------------

BIDScoin is a Python 3 package and can be installed on Linux, MS Windows and on OS-X computers, as long as a Python interpreter (v3.8 or higher) is available on the system. On Linux and OS-X this is usually already the case, but MS Windows users may need to first install Python themselves. The easiest solution is to use the official `Python installer <https://www.python.org/downloads/windows/>`__ and tick the "Add Python 3.# to PATH" checkbox during the installation process.

If you have a working Python installation, then you can install BIDScoin directly on your system, but this is not recommended. Instead, it is best practice to isolate apps such as BIDScoin, and install them in a so-called `virtual <https://docs.python.org/3/tutorial/venv.html>`__ environment, e.g. by opening a command terminal execute (Linux example):

.. code-block:: console

   $ python -m venv bidscoin        # This will create an environment for BIDScoin
   $ source bidscoin/bin/activate   # This activates the environment so you can use it

BIDScoin installation
---------------------

To install BIDScoin on your system / activated virtual environment (see above) run one of the following commands in your command-line interface/shell:

.. code-block:: console

   $ pip install bidscoin                       # Use this to install the BIDScoin-framework only and independently install the software dependencies of the plugin(s) (such as dcm2niix)
   $ pip install bidscoin[dcm2niix2bids]        # Use this when you want to convert conventional MR imaging data with the dcm2niix2bids plugin and would like to have dcm2niix pip-installed
   $ pip install bidscoin[spec2nii2bids]        # Use this when you want to convert MR spectroscopy data with the spec2nii2bids plugin
   $ pip install bidscoin[deface]               # Use this when you want to deface anatomical MRI scans. NB: Requires FSL (but see the Apptainer file for doing a minimal install)
   $ pip install bidscoin[deface,spec2nii2bids] # Use this when you want to deface anatomical MRI scans and convert MRS data with the spec2nii2bids plugin
   $ pip install bidscoin[all]                  # Use this to install all extra packages

These install commands can be run independently and will give you the latest stable release of BIDScoin and its `plugins <./options.html#dcm2niix2bids-plugin>`__. Alternatively, if you need to use the very latest (development/unstable) version of the software, you can also install BIDScoin directly from the github source code repository, e.g. like this:

.. code-block:: console

   $ pip install git+https://github.com/Donders-Institute/bidscoin                          # The BIDScoin-framework only
   $ pip install bidscoin[dcm2niix2bids]@git+https://github.com/Donders-Institute/bidscoin  # The BIDScoin-framework + dcm2niix2bids plugin

If you do not have git (or any other version control system) installed you can `download <https://github.com/Donders-Institute/bidscoin>`__ and unzip the code yourself in a folder named e.g. 'bidscoin' and run:

.. code-block:: console

   $ pip install ./bidscoin[dcm2niix2bids]

If you are installing BIDScoin on an older system and you are getting Qt6 errors, you can try to install an older ``+qt5`` build, e.g. for version 4.3.3 (the last Qt5 build):

.. code-block:: console

   $ pip install bidscoin[dcm2niix2bids]@git+https://github.com/Donders-Institute/bidscoin@v4.3.3+qt5

Updating BIDScoin
^^^^^^^^^^^^^^^^^

Run your pip install command as before with the additional ``--upgrade`` or ``--force-reinstall`` option, e.g.:

.. code-block:: console

   $ pip install --upgrade bidscoin                                                     # The latest stable release
   $ pip install --force-reinstall git+https://github.com/Donders-Institute/bidscoin    # The latest code (add ``--no-deps`` to only upgrade the bidscoin package)

.. caution::
   - The bidsmaps are not guaranteed to be compatible between different BIDScoin versions
   - After a successful BIDScoin installation or upgrade, it may be needed to (re)do any adjustments that were done on your `template bidsmap <./bidsmap_indepth.html#building-your-own-template-bidsmap>`__
   - The code on GitHub does not always have a unique version number. Therefore, if you install the latest code from github, and then later re-install a newer BIDScoin with the same version number (e.g. the stable version from PyPi), then you need to actively delete your old user configuration. You can do this most easily by running ``bidscoin --reset``

Dcm2niix installation
---------------------

The default 'dcm2niix2bids' plugin relies on an external application named `dcm2niix <https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage>`__ for converting DICOM and PAR/REC source data to NIfTI. To use the plugin you must pip-install dcm2niix when installing BIDScoin or install it yourself (e.g. when pip-installing dcm2niix does not work for your platform) as explained in the `dcm2niix installation instructions <https://github.com/rordenlab/dcm2niix#install>`__. When done, make sure that the dcm2niix executable is on your user or system path (Windows users can add the path permanently, e.g. by running: ``setx path "%path%;C:\Program Files\dcm2niix"``). Otherwise (for instance when you want to use the Linux module system or fixate the software version), make sure that the command to run the dcm2niix executable (exactly as if you would run it yourself in your command terminal) is set correctly in the `Options <options.html>`__ section in your bidsmap. This can be done in two ways:

1. Open your template bidsmap with a text editor and adjust the settings as needed. The default template bidsmap is located in your ``[home]/.bidscoin/[version]/templates`` folder (see the output of ``bidscoin -p`` for the fullpath location on your system).
2. Go to the `Options <options.html>`__ tab the first time the BIDScoin GUI is launched and adjust the settings as needed. Then click the [Set as default] button to save the settings to your default template bidsmap.

.. tip::

   Install the `pigz <https://zlib.net/pigz/>`__ tool to speed-up dcm2niix. An easy way to install both dcm2niix and pigz at once, is to install  `MRIcroGL <https://www.nitrc.org/projects/mricrogl/>`__

Testing BIDScoin
----------------

You can run the 'bidscoin' utility to test the installation of your BIDScoin installation and settings:

.. code-block:: console

   $ bidscoin -t                        # Test with the default template bidsmap
   $ bidscoin -t my_template_bidsmap    # Test with your custom template bidsmap

See also the `Troubleshooting guide <./troubleshooting.html#installation>`__ for more information on potential installation issues.

Using an Apptainer (Singularity) container
------------------------------------------

An alternative for installing Python, BIDScoin and it's dependencies yourself is to execute BIDScoin commands using an `Apptainer <https://apptainer.org>`__ container. Executing BIDScoin commands via a container is less simple than running them directly on your host computer, read the `official documentation <https://apptainer.org/docs/user/latest>`__ for installation and usage instructions. NB: "Singularity" has been rebranded as "Apptainer", so Singularity users should replace ``apptainer`` for ``singularity`` in the commands given below.

The current Apptainer image includes:

* Debian stable,
* The latest stable release of BIDScoin
* The latest versions of dcm2niix, pydeface, spec2nii

This image does not include FreeSurfer/synthstrip (needed for ``skullstrip``)

Building the container image
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Download the Apptainer `definition file <https://github.com/Donders-Institute/bidscoin/blob/master/apptainer.def>`__ and execute the following command to build a BIDScoin container image:

.. code-block:: console

   $ sudo apptainer build bidscoin.sif apptainer.def

Alternatively, you can pull a BIDScoin Docker image and convert it into an Apptainer image using:

.. code-block:: console

   $ sudo apptainer build bidscoin.sif docker://marcelzwiers/bidscoin:<version>

Run BIDScoin tools in the container
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use the following command syntax to execute BIDScoin tools in the container:

.. code-block:: console

   $ apptainer exec bidscoin.sif <bidscoin_tool> <bidscoin_tool_args>

Where ``<bidscoin_tool>`` is a BIDScoin tool (e.g., ``bidsmapper``, ``bidscoiner``, ``dicomsort``) and ``<bidscoin_tool_args>`` are the tool's arguments. So for instance, if you have source data in ``myhome/data/raw``, instead of running ``bidsmapper data/raw data/bids`` and then ``bidsmapper data/raw data/bids`` from your home directory, you now execute:

.. code-block:: console

   $ xhost +
   $ apptainer exec bidscoin.sif bidsmapper data/raw data/bids
   $ xhost -
   $ apptainer exec bidscoin.sif bidscoiner data/raw data/bids

The ``xhost +`` command allows Apptainer to open a graphical display on your computer and normally needs to be run once before launching any GUI application (so this is needed for the bidseditor).

If your data does not reside in your home folder, then you need to add a ``--bind <host_dir>:<container_dir>`` Apptainer argument which maps a folder from the host system to a folder inside the Apptainer container. So if your data is in ``/myproject/raw``, you run:

.. code-block:: console

   $ apptainer exec bidscoin.sif --bind /myproject <bidscoin_tool> <bidscoin_tool_args>

See the documentation for usage and setting environment variables to automatically bind your root paths for all containers.

Using a Docker container
------------------------

If the Apptainer container is not working for you, it is also possible to use a `Docker <https://docs.docker.com>`__ container. The Docker versus Apptainer image and container usage are very similar, and both have their pros and cons. A fundamental argument for using Apptainer is that it does not require root permission (admin rights), whereas a fundamental argument for using Docker is that it is not limited to Linux hosts.

The current Docker image includes the same as the Apptainer image:

* Debian stable,
* The latest stable release of BIDScoin
* The latest versions of dcm2niix, pydeface, spec2nii and some FSL tools

Likewise, the current image does not include FreeSurfer/synthstrip (needed for ``skullstrip``)

Building the container image
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Download the `Dockerfile <https://github.com/Donders-Institute/bidscoin/blob/master/Dockerfile>`__ and execute the following command to build a BIDScoin container image:

.. code-block:: console

   $ sudo docker build -t bidscoin .

Alternatively, you can pull a pre-build image from `Docker Hub <https://hub.docker.com/repository/docker/marcelzwiers/bidscoin/>`__

.. code-block:: console

   $ sudo docker pull marcelzwiers/bidscoin:<version>

Run BIDScoin tools in the container
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Executing BIDScoin commands via Docker is less simple than via Apptainer (and surely less simple than running them directly on your host computer). For instance, it is typically needed to bind-mount your data folder(s) in the container and, for the bidseditor, to bind-mount an x-server socket to display the GUI in your host computer. The syntax to run dockerized bidscoin tools is:

.. code-block:: console

   $ docker run --rm -v <bind_mount> bidscoin <bidscoin_tool> <bidscoin_tool_args>                          # If you built the image from the Dockerfile
   $ docker run --rm -v <bind_mount> marcelzwiers/bidscoin:<version> <bidscoin_tool> <bidscoin_tool_args>   # If you pulled the image from Docker Hub

If you have source data in ``/my/data/raw``, instead of running ``bidsmapper /my/data/raw /my/data/bids`` and then ``bidsmapper /my/data/raw /my/data/bids``, you now execute for instance:

.. code-block:: console

   $ xhost +
   $ sudo docker run --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix -v /my/data:/mnt bidscoin bidsmapper /my/data/raw /my/data/bids
   $ xhost -
   $ sudo docker run --rm -v /my/data:/my/data bidscoin bidscoiner /my/data/raw /my/data/bids

As for Apptainer, the `xhost +` is normally needed to be launching a GUI application, but a few more arguments are now required, i.e. ``-e`` for setting the display number and ``-v`` for binding the data volume and for binding the x-server socket (see the documentation for usage and configuring bind propagation).
