# BIDScoiner installation

BIDScoiner can be installed and should work on linux, windows and, presumably, on OS-X computers (this latter option has not been tested)

## Requirements
- python 3
- A few additional python modules, see: [requirements.txt](../requirements.txt)
- [dcm2niix](https://github.com/rordenlab/dcm2niix)

## Installation
You can either download the code as a ZIP file or you can clone the code (recommended):

To download the code:

1. Go to the [BIDScoiner](https://github.com/Donders-Institute/bidscoin) repository on GitHub
2. Select 'Download ZIP' from the green 'Clone or download' button
3. Unzip the code in a bidscoin directory (e.g. in your python code directory)

To clone the code in a bidscoin direcory, go to your python code directory in your command shell and run the following commands (requires [git](https://git-scm.com/) to be installed):

    git clone https://github.com/Donders-Institute/bidscoin.git
    pip install ./bidscoin

Finally, edit the `Options : dcm2niix : path` value in the [bidsmap_template.yaml](../heuristics/bidsmap_template.yaml) file according to your system installation.