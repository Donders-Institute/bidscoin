# BIDScoin installation

BIDScoin can be installed and should work on linux, windows and, presumably, on OS-X computers (this latter option has not been tested)

## Requirements
- python 3
- A few common python modules, see: [requirements.txt](../requirements.txt)
- [dcm2niix](https://github.com/rordenlab/dcm2niix)

## Installation
Run the following command in your command-shell (institute users may want to activate a [virtual](https://docs.python.org/3.6/tutorial/venv.html) / [conda](https://conda.io/docs/user-guide/tasks/manage-environments.html) environments first):

    pip install git+https://github.com/Donders-Institute/bidscoin

If you are a developper who wants to edit the code or who wants to contribute back to the project, you can use the `-e` option of `pip` or clone the code and do a local install:

    git clone https://github.com/Donders-Institute/bidscoin
    pip install -e bidscoin

After a succesful installation, edit the `Options : dcm2niix : path` value in the [bidsmap_template.yaml](../heuristics/bidsmap_template.yaml) file according to your system configuration.