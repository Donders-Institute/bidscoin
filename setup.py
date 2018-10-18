#!/usr/bin/env python

from setuptools import setup
from os import path
from importlib import import_module

# Read the version from bids.py
bids    = import_module(name='bids', package=path.join(__file__,'bidscoiner','bids.py'))
version = str(bids.version)

# Read the contents of the README file
with open(path.join(path.abspath(path.dirname(__file__)), 'README.md'), encoding='utf-8') as fid:
    long_description = fid.read()

# Read the contents of the requirements file
with open(path.join(path.abspath(path.dirname(__file__)), 'requirements.txt')) as fid:
    requirements = fid.read().splitlines()

setup(name                           = 'bidscoiner',                        # Required
      version                        = version,                             # Required
      keywords                       = 'bids mri neuroimaging dicom nifti',
      description                    = 'Converts and organises raw MRI data-sets according to the Brain Imaging Data Standard (BIDS)',
      long_description               = long_description,
      long_description_content_type  = 'text/markdown',
      url                            = 'https://github.com/Donders-Institute/bidscoiner',
      python_requires                = '>=3',
      install_requires               = requirements,
      packages                       = find_packages(),                     # Required
      classifiers                    = ['Programming Language :: Python :: 3',
                                       'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
                                       'Operating System :: OS Independent'])
