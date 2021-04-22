from pathlib import Path
from setuptools import setup, find_packages

# Read the version from file
with (Path(__file__).parent/'bidscoin'/'version.txt').open('r') as fid:
    version = fid.read().strip()

# Read the contents of the README file
with (Path(__file__).parent/'README.rst').open('r') as fid:
    readme = fid.read()

# Read the contents of the requirements file
with (Path(__file__).parent/'requirements.txt').open('r') as fid:
    requirements = fid.read().splitlines()

setup(name                           = 'bidscoin',          # Required
      version                        = version,             # Required
      packages                       = find_packages(),     # Required
      install_requires               = requirements,
      python_requires                = '>=3.8',
      setup_requires                 = ["pytest-runner"],
      tests_require                  = ["pytest", "pytest-cov", "coverage"],
      package_data                   = {'': ['*version.txt', '*.yaml', 'bidscoin_logo.png', 'bidscoin.ico', 'rightarrow.png']},
      entry_points                   = {'console_scripts': ['bidscoin         = bidscoin.bidscoin:main',
                                                            'bidseditor       = bidscoin.bidseditor:main',
                                                            'bidsmapper       = bidscoin.bidsmapper:main',
                                                            'bidscoiner       = bidscoin.bidscoiner:main',
                                                            'rawmapper        = bidscoin.rawmapper:main',
                                                            'dicomsort        = bidscoin.dicomsort:main',
                                                            'echocombine      = bidscoin.echocombine:main',
                                                            'deface           = bidscoin.deface:main',
                                                            'bidsparticipants = bidscoin.bidsparticipants:main',
                                                            'physio2tsv       = bidscoin.physio2tsv:main',
                                                            'plotphysio       = bidscoin.plotphysio:main']},
      classifiers                    = ['Programming Language :: Python :: 3',
                                        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
                                        'Operating System :: OS Independent'],
      keywords                       = 'bids mri imaging neuroimaging dicom par rec nifti pet defacing echo-combination',
      description                    = 'Converts and organises raw MRI data-sets according to the Brain Imaging Data Structure (BIDS)',
      long_description               = readme,
      long_description_content_type  = 'text/x-rst',
      author                         = 'Marcel Zwiers',
      author_email                   = 'm.zwiers@donders.ru.nl',
      url                            = 'https://github.com/Donders-Institute/bidscoin')
