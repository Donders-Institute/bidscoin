import sys
import os
import unittest
import ruamel
import logging
import copy
import difflib

from bidscoin.bids import load_bidsmap, save_bidsmap
from bidscoin.bidseditor import get_anat_bids_modality_labels, update_bidsmap


LOGGER = logging.getLogger()
LOGGER.level = logging.DEBUG
LOGGER.addHandler(logging.StreamHandler(sys.stdout))


class TestBidseditor(unittest.TestCase):

    def test_get_bidsmap_modalities(self):
        pathname = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "heuristics")
        filename = os.path.join(pathname, "bidsmap_template.yaml")
        template_bidsmap = load_bidsmap(filename, pathname)

        reference_labels = [
            'T1w',
            'T2w',
            'T1rho',
            'T1map',
            'T2map',
            'T2star',
            'FLAIR',
            'FLASH',
            'PD',
            'PDmap',
            'PDT2',
            'inplaneT1',
            'inplaneT2',
            'angio',
            'defacemask',
            'SWImagandphase'
        ]

        bids_modality_labels = get_anat_bids_modality_labels(template_bidsmap)

        self.assertEqual(bids_modality_labels, reference_labels)

    def test_update_bidsmap(self):
        pathname = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata")
        filename = os.path.join(pathname, "bidsmap_example.yaml")
        source_bidsmap = load_bidsmap(filename, pathname)

        source_modality = 'extra_data'
        source_index = 2
        yaml = ruamel.yaml.YAML()
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_sample_example.yaml")
        with open(filename) as fp:
            test_sample_yaml = fp.read()
            test_sample = yaml.load(test_sample_yaml)

        target_modality = 'anat'
        target_sample = copy.deepcopy(test_sample)

        target_bidsmap = update_bidsmap(source_bidsmap, source_modality, source_index, target_modality, target_sample)

        self.assertNotEqual(target_bidsmap, source_bidsmap)
        self.assertNotEqual(target_bidsmap['DICOM'][target_modality], source_bidsmap['DICOM'][target_modality])
        self.assertNotEqual(target_bidsmap['DICOM'][source_modality], source_bidsmap['DICOM'][source_modality])
        self.assertEqual(len(target_bidsmap['DICOM'][target_modality]), 1)
        self.assertEqual(len(target_bidsmap['DICOM'][source_modality]), 4)

        target_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_out_temp.yaml")
        reference_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_out.yaml")

        save_bidsmap(target_filename, target_bidsmap)
        text1 = open(target_filename).readlines()
        text2 = open(reference_filename).readlines()
        lines = list(difflib.unified_diff(text1, text2))
        LOGGER.info(''.join(lines))
        self.assertEqual(len(lines), 0) # Difference must be zero


if __name__ == '__main__':
    unittest.main()
