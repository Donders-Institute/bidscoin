import unittest
import os

from bidscoin.bids import bidsversion, version, get_clean_dicomfile


class TestBids(unittest.TestCase):

    def test_version(self):
        v = version()
        v_from_file = 0.0
        with open('version.txt') as fp:
            v_from_file = float(fp.read())
        self.assertEqual(v, v_from_file)

    def test_bids_version(self):
        bids_v = bidsversion()
        bids_v_from_file = ''
        with open('bidsversion.txt') as fp:
            bids_v_from_file = fp.read()
        self.assertEqual(bids_v, bids_v_from_file)

    def test_clean_dicomfile(self):
        dicomfile = r'M:\bidscoin\raw\sub-P002\ses-mri01\02_localizer AANGEPAST 11 SLICES\M109.MR.WUR_BRAIN_ADHD.0002.0001.2018.03.01.13.05.10.140625.104357083.IMA'
        test_clean_dicomfile = r'M:\\bidscoin\\raw\\sub-P002\\ses-mri01\\02_localizer\ AANGEPAST\ 11\ SLICES\\M109.MR.WUR_BRAIN_ADHD.0002.0001.2018.03.01.13.05.10.140625.104357083.IMA'
        clean_dicomfile = get_clean_dicomfile(dicomfile)
        self.assertEqual(clean_dicomfile, test_clean_dicomfile)

        dicomfile = '/check/this/out/TEST.IMA'
        test_clean_dicomfile = '/check/this/out/TEST.IMA'
        clean_dicomfile = get_clean_dicomfile(dicomfile)
        self.assertEqual(clean_dicomfile, test_clean_dicomfile)


if __name__ == '__main__':
    unittest.main()
