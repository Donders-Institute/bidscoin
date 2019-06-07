# BIDScoin developer instructions

# Obtain the source code

To obtain the latest version of BIDScoin:
```console
$ git clone https://github.com/Donders-Institute/bidscoin.git
```

Go into the directory:
```console
$ cd bidscoin
```

# Install the package in an Anaconda environment on Linux

To setup the virtual environment

```console
$ conda create -n venv
$ source activate venv
$ conda install pip
$ ~/.conda/envs/venv/bin/pip install -r requirements.txt
$ source deactivate
```

To start a session
```console
$ source activate venv
```

To close this session
```console
$ source deactivate
```

If you want to remove the virtual environment at a later stage:

```console
$ conda remove -n venv -all
```

# Install the package on Windows

Prerequisites:
* Python for windows
* Git for windows
* Install `dcm2nixx`

Create a virtual environment

```console
$ pip install virtualenv
```

```console
$ virtualenv venv
```

```console
$ venv\Scripts\activate
```

Next, install BIDScoin with:
```console
$ pip install git+https://github.com/Donders-Institute/bidscoin
```

For example, then run 
```console
$ venv\Scripts\bidsmapper.py -h
```
