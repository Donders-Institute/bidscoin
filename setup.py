from pathlib import Path
from setuptools import setup, find_packages

version       = (Path(__file__).parent/'bidscoin'/'version.txt').read_text().strip()
readme        = (Path(__file__).parent/'README.rst').read_text()
requirements  = (Path(__file__).parent/'requirements.txt').read_text().splitlines()
spec2nii2bids = ['spec2nii']
deface        = ['pydeface', 'drmaa']
pet2bids      = ['pypet2bids>=1.0.12']
phys2bidscoin = ['bioread>=1.0.5', 'pymatreader>=0.0.24', 'duecredit', 'phys2bids>=2.0.0,<3.0.0']
all_extras    = spec2nii2bids + deface + pet2bids # + phys2bidscoin

setup(name                           = 'bidscoin',          # Required
      version                        = version,             # Required
      packages                       = find_packages(),     # Required
      install_requires               = requirements,
      python_requires                = '>=3.8',
      extras_require                 = {'all':           all_extras,
                                        'phys2bidscoin': phys2bidscoin,
                                        'spec2nii2bids': spec2nii2bids,
                                        'deface':        deface,
                                        'pet2bids':      'pet2bids>=1.1.0'},
      package_data                   = {'': ['*version.txt', '*VERSION', '*.yaml', 'bidscoin_logo.png', 'bidscoin.ico', 'rightarrow.png']},
      entry_points                   = {'console_scripts': ['bidscoin         = bidscoin.bidscoin:main',
                                                            'bidseditor       = bidscoin.bidseditor:main',
                                                            'bidsmapper       = bidscoin.bidsmapper:main',
                                                            'bidscoiner       = bidscoin.bidscoiner:main',
                                                            'echocombine      = bidscoin.bidsapps.echocombine:main',
                                                            'deface           = bidscoin.bidsapps.deface:main',
                                                            'medeface         = bidscoin.bidsapps.medeface:main',
                                                            'skullstrip       = bidscoin.bidsapps.skullstrip:main',
                                                            'slicereport      = bidscoin.bidsapps.slicereport:main',
                                                            'dicomsort        = bidscoin.utilities.dicomsort:main',
                                                            'bidsparticipants = bidscoin.utilities.bidsparticipants:main',
                                                            'rawmapper        = bidscoin.utilities.rawmapper:main',
                                                            'physio2tsv       = bidscoin.utilities.physio2tsv:main',
                                                            'plotphysio       = bidscoin.utilities.plotphysio:main']},
      classifiers                    = ['Programming Language :: Python :: 3.8',
                                        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
                                        'Operating System :: OS Independent'],
      keywords                       = 'bids mri imaging neuroimaging dicom par rec nifti defacing echo-combination skull-stripping',
      description                    = 'Converts and organises raw MRI data-sets according to the Brain Imaging Data Structure (BIDS)',
      long_description               = readme,
      long_description_content_type  = 'text/x-rst',
      author                         = 'Marcel Zwiers',
      author_email                   = 'm.zwiers@donders.ru.nl',
      url                            = 'https://github.com/Donders-Institute/bidscoin')
