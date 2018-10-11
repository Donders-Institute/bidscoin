# BIDScoiner installation

BIDScoiner can be installed on linux, windows and, presumably, on OS-X computers (this latter option has not been tested)

## Requirements
- python 3
- A few additional python modules, see: [requirements.txt](../requirements.txt)
- [dcm2niix](https://github.com/rordenlab/dcm2niix)

## Installation
First create a bidscoiner directory where you want the python code to be saved.
You can either download the code as a ZIP file or you can clone the code:

To download the code:

1. Go to the [BIDScoiner](https://github.com/Donders-Institute/bidscoiner) repository on GitHub
2. Select 'Download ZIP' from the green 'Clone or download' button
3. Unzip the code in the bidscoiner directory

To clone the code, run the following command in your command shell (requires Git to be installed):

    git clone https://github.com/Donders-Institute/bidscoiner.git
    git clone git@github.com:Donders-Institute/bidscoiner.git

In your command shell, go to the bidscoiner code directory and run either of the following commands to install required python modules (optionally, first activate your [virtual](https://virtualenv.pypa.io/en/stable/)/[conda](https://conda.io/docs/user-guide/tasks/manage-environments.html#) environment):

    pip install -r requirements.txt
    conda install --yes --file requirements.txt

Finally, edit the `Options : dcm2niix : path` value in the [bidsmap_template.yaml](../heuristics/bidsmap_template.yaml) file according to your system installation.