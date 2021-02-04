#!/usr/bin/env python3
"""
Utility to download a tutorial dataset

@author: Marcel Zwiers
"""

import tarfile
import argparse
import urllib.request
import shutil
import ssl
from pathlib import Path

tutorialurl = 'https://surfdrive.surf.nl/files/index.php/s/HTxdUbykBZm2cYM/download'


def getdata(tutorialfolder) -> None:
    """
    Download and unzip tutorial.tar.gz file

    :param tutorialfolder:  The full pathname of the target folder in which the tutorial data will be downloaded
    :return:
    """

    tutorialfolder = Path(tutorialfolder).resolve()
    tutorialtargz  = tutorialfolder/'bidscointutorial.tar.gz'
    tutorialfolder.mkdir(parents=True, exist_ok=True)

    # Download the data, avoiding ssl certificate issues
    print(f"Downloading the tutorial dataset...")
    with urllib.request.urlopen(tutorialurl, context=ssl.SSLContext()) as data, open(tutorialtargz, 'wb') as targz_fid:
        shutil.copyfileobj(data, targz_fid)

    # Unzip the data in the target folder
    print(f"Unzipping the downloaded data in: {tutorialfolder}")
    with tarfile.open(tutorialtargz, 'r') as targz_fid:
        targz_fid.extractall(tutorialfolder)
    tutorialtargz.unlink()


def main():
    """Console script usage"""

    class CustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass

    parser = argparse.ArgumentParser(formatter_class=CustomFormatter,
                                     description=__doc__,
                                     epilog='example:\n'
                                            '  tutorialdata -t tmp/bidscointutorial\n')
    parser.add_argument('-t','--tutorialfolder', type=str, default='.',
                        help='The directory in which the toturial data will be downloaded')
    args = parser.parse_args()

    getdata(tutorialfolder = args.tutorialfolder)


if __name__ == '__main__':
    main()
