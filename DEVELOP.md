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

# Run the tests

To run the tests and obtain the test coverage report:
```console
$ python setup.py test
```

# Install the package

Create a virtual environment

```console
$ pip install virtualenv
```

```console
$ virtualenv venv
```

In Linux:
```console
$ source venv/scripts/activate
```

In MS Windows:
```console
$ venv\\Scripts\\activate
```

Next, install BIDScoin with:
```console
$ python setup.py install
```