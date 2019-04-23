import sys
import os
import unittest
import json
import ruamel.yaml as yaml
import logging
import copy
import difflib

from bidscoin.bidsutils import (read_bidsmap, read_yaml_as_string, get_num_samples, read_sample, update_bidsmap, save_bidsmap)


logger = logging.getLogger()
logger.level = logging.DEBUG
logger.addHandler(logging.StreamHandler(sys.stdout))


class TestBidseditor(unittest.TestCase):

    def read_bidsmap(self):
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
        bidsmap_yaml = read_yaml_as_string(filename)
        bidsmap = read_bidsmap(bidsmap_yaml)

        with open(filename) as fp:
            test_bidsmap = fp.read()
            test_bidsmap_yaml = yaml.safe_load(test_bidsmap)

        self.assertEqual(bidsmap_yaml, test_bidsmap_yaml)
        self.assertEqual(bidsmap, test_bidsmap)

    def test_get_num_samples(self):
        """Determine the number of extra_data samples."""
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
        bidsmap_yaml = read_yaml_as_string(filename)
        bidsmap = read_bidsmap(bidsmap_yaml)

        modality = 'extra_data'
        num_samples = get_num_samples(bidsmap, modality)
        self.assertEqual(num_samples, 5)

    def test_read_sample_all(self):
        """Loop over all extra_data samples and read them. """
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
        bidsmap_yaml = read_yaml_as_string(filename)
        bidsmap = read_bidsmap(bidsmap_yaml)

        modality = 'extra_data'
        num_samples = get_num_samples(bidsmap, modality)
        self.assertEqual(num_samples, 5)

        for i in range(num_samples):
            sample = read_sample(bidsmap, modality, i)

    def test_read_sample_one(self):
        """Read the third extra_data sample (i.e. having index = 2). """
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
        bidsmap_yaml = read_yaml_as_string(filename)
        bidsmap = read_bidsmap(bidsmap_yaml)

        index = 2
        modality = 'extra_data'

        sample = read_sample(bidsmap, modality, index)
        sample_yaml = yaml.dump(sample, sys.stdout, default_flow_style=False)

        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new_sample2.yaml")
        with open(filename) as fp:
            test_sample_yaml = fp.read()
            test_sample = yaml.safe_load(test_sample_yaml)
        test_sample_yaml = yaml.dump(test_sample, sys.stdout, default_flow_style=False)

        self.assertEqual(test_sample_yaml, sample_yaml)

    def test_update_bidsmap(self):
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
        source_bidsmap_yaml = read_yaml_as_string(filename)
        source_bidsmap = read_bidsmap(source_bidsmap_yaml)

        source_modality = 'extra_data'
        source_index = 2
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new_sample2.yaml")
        with open(filename) as fp:
            test_sample_yaml = fp.read()
            test_sample = yaml.safe_load(test_sample_yaml)

        target_modality = 'anat'
        target_sample = copy.deepcopy(test_sample)
        target_sample['attributes']['test'] = 'test'

        target_bidsmap = update_bidsmap(source_bidsmap, source_modality, source_index, target_modality, target_sample)

        self.assertNotEqual(target_bidsmap, source_bidsmap)
        self.assertNotEqual(target_bidsmap['DICOM'][target_modality], source_bidsmap['DICOM'][target_modality])
        self.assertNotEqual(target_bidsmap['DICOM'][source_modality], source_bidsmap['DICOM'][source_modality])
        self.assertEqual(len(target_bidsmap['DICOM'][target_modality]), 1)
        self.assertEqual(len(target_bidsmap['DICOM'][source_modality]), 4)

        target_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_out.yaml")
        reference_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new_out.yaml")

        save_bidsmap(target_filename, target_bidsmap)
        text1 = open(target_filename).readlines()
        text2 = open(reference_filename).readlines()
        lines = list(difflib.unified_diff(text1, text2))
        logger.info(''.join(lines))
        self.assertEqual(len(lines), 0) # Difference must be zero


if __name__ == '__main__':
    unittest.main()
