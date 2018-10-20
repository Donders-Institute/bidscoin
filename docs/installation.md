# BIDScoin installation

BIDScoin can be installed and should work on linux, windows and, presumably, on OS-X computers (this latter option has not been tested) that satisfy the [system requirements](#system-requirements)

## System requirements
- python 3
- [dcm2niix](https://github.com/rordenlab/dcm2niix)

## Installation
Run the following command in your command-shell (institute users may want to activate a [virtual](https://docs.python.org/3.6/tutorial/venv.html) / [conda](https://conda.io/docs/user-guide/tasks/manage-environments.html) environments first):

    pip install git+https://github.com/Donders-Institute/bidscoin

If you are a developper who wants to edit the code or who wants to contribute back to the project, you can use the `-e` option:

    pip install -e git+https://github.com/Donders-Institute/bidscoin#egg=bidscoin
    
If you do not have git (or any other version control system) installed you can download the code and unzip the code yourself in a directory named e.g. `bidscoin` and run (again, with or without the `-e` option):

    pip install -e bidscoin

If the installation somehow failed, you can have a look at the packages in [requirements.txt](../requirements.txt) and try to find another way to install them beforehand

After a succesful installation, if needed, edit the `Options : dcm2niix : path` value in the [bidsmap_template.yaml](../heuristics/bidsmap_template.yaml) file according to your system configuration (you may want to use the `-e` install option for this).
