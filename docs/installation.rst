BIDScoin installation
=====================

BIDScoin can be installed and should work on linux, windows and,
presumably, on OS-X computers (this latter option has not been tested)
that satisfy the `system requirements`_

System requirements
-------------------

-  python 3
-  `dcm2niix`_

Installation
------------

Run the following command in your command-shell (institute users may
want to activate a `virtual`_ / `conda`_ environments first):

::

   pip install bidscoin

This will give you the latest stable release of the software. To get the
very latest version of the software you can install the package directly
from the github source code repository:

::

   pip install git+https://github.com/Donders-Institute/bidscoin

If you want to edit the code or want to contribute back to the project,
you can use the ``-e`` option:

::

   pip install -e git+https://github.com/Donders-Institute/bidscoin#egg=bidscoin

If you do not have git (or any other version control system) installed
you can `download`_ the code and unzip the code yourself in a directory
named e.g. ``bidscoin`` and run (again, with or without the ``-e``
option):

::

   pip install -e bidscoin

If the installation somehow failed, you can have a look at the packages
in `requirements.txt`_ and try to find another way to install them
beforehand

After a succesful installation, if needed, edit the
``Options : dcm2niix : path`` value in the
`[bidscoin]/heuristics/bidsmap_template.yaml`_ file according to your
system configuration (you may want to use the ``-e`` install option for
this).

Updating
--------

Run the pip command as before with the additional ``--upgrade`` option
and redo any edits you made to your ``bidsmap_template.yaml`` file. The
`bidsmap-files`_ are not garanteed to be compatible between different
version, so it may be necessary to re-run the ``bidstrainer.py`` and the
``bidsmapper.py`` commands before using ``bidscoiner.py``.

.. _system requirements: #system-requirements
.. _dcm2niix: https://github.com/rordenlab/dcm2niix
.. _virtual: https://docs.python.org/3.6/tutorial/venv.html
.. _conda: https://conda.io/docs/user-guide/tasks/manage-environments.html
.. _download: https://github.com/Donders-Institute/bidscoin
.. _requirements.txt: ../requirements.txt
.. _[bidscoin]/heuristics/bidsmap_template.yaml: ../heuristics/bidsmap_template.yaml
.. _bidsmap-files: #the-bidsmap-files
