import sys
import os
import unittest
import json
import ruamel
import logging
import copy
import difflib

from bidscoin.bidsutils import (read_bidsmap, read_yaml_as_string, get_num_samples,
                                read_sample, update_bidsmap, save_bidsmap, get_bids_name,
                                get_bids_name_array, get_bids_attributes, show_label,
                                get_list_summary, MODALITIES)


logger = logging.getLogger()
logger.level = logging.DEBUG
logger.addHandler(logging.StreamHandler(sys.stdout))


class TestBidsUtils(unittest.TestCase):

    def test_read_bidsmap(self):
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
        bidsmap_yaml = read_yaml_as_string(filename)
        bidsmap = read_bidsmap(bidsmap_yaml)

        yaml = ruamel.yaml.YAML()
        with open(filename) as fp:
            test_bidsmap_yaml = fp.read()
            test_bidsmap = yaml.load(test_bidsmap_yaml)

        self.assertEqual(bidsmap_yaml, test_bidsmap_yaml)
        self.assertEqual(bidsmap, test_bidsmap)

    def test_show_label(self):
        self.assertEqual(show_label(None), False)
        self.assertEqual(show_label(""), False)
        self.assertEqual(show_label("test"), True)

    def test_get_bids_name(self):
        bids_name = get_bids_name([])
        self.assertEqual(bids_name, "")

        bids_name_array = get_bids_name_array("", "", "extra_data", {}, "")
        bids_name = get_bids_name(bids_name_array)
        self.assertEqual(bids_name, "sub-_acq-")

    def test_get_bids_name_array(self):
        test_bids_name_array_anat = [
            {
                "prefix": "sub-",
                "label": "",
                "show": True
            },
            {
                "prefix": "ses-",
                "label": "",
                "show": False
            },
            {
                "prefix": "acq-",
                "label": "",
                "show": False
            },
            {
                "prefix": "ce-",
                "label": "",
                "show": False
            },
            {
                "prefix": "rec-",
                "label": "",
                "show": False
            },
            {
                "prefix": "run-",
                "label": "",
                "show": False
            },
            {
                "prefix": "mod-",
                "label": "",
                "show": False
            },
            {
                "prefix": "",
                "label": "",
                "show": True
            }
        ]
        for modality in MODALITIES:
            bids_name_array = get_bids_name_array("", "", modality, {}, "")
            if modality == 'anat':
                self.assertEqual(bids_name_array, test_bids_name_array_anat)


    def test_get_bids_attributes(self):
        source_bids_attributes = {}
        for modality in MODALITIES:
            bids_attributes = get_bids_attributes(modality, source_bids_attributes)


    def test_get_list_summary(self):
        test_list_summary = [
            {
                "modality": "extra_data",
                "provenance_file": "M109.MR.WUR_BRAIN_ADHD.0002.0001.2018.03.01.13.05.10.140625.104357083.IMA",
                "provenance_path": "M:\\bidscoin\\raw\\sub-P002\\ses-mri01\\02_localizer AANGEPAST 11 SLICES",
                "bids_name": "sub-*_ses-*_acq-localizerAANGEPAST11SLICES_run-<<1>>"
            },
            {
                "modality": "extra_data",
                "provenance_file": "M109.MR.WUR_BRAIN_ADHD.0003.0001.2018.03.01.13.05.10.140625.104359017.IMA",
                "provenance_path": "M:\\bidscoin\\raw\\sub-P002\\ses-mri01\\03_Stoptaak_ep2d_bold_nomoco",
                "bids_name": "sub-*_ses-*_acq-Stoptaakep2dboldnomoco_run-<<1>>"
            },
            {
                "modality": "extra_data",
                "provenance_file": "M109.MR.WUR_BRAIN_ADHD.0004.0001.2018.03.01.13.05.10.140625.104364139.IMA",
                "provenance_path": "M:\\bidscoin\\raw\\sub-P002\\ses-mri01\\04_t1_mpr_sag_p2_iso_1",
                "bids_name": "sub-*_ses-*_acq-t1mprsagp2iso1_run-<<1>>"
            },
            {
                "modality": "extra_data",
                "provenance_file": "M109.MR.WUR_BRAIN_ADHD.0005.0001.2018.03.01.13.05.10.140625.104368237.IMA",
                "provenance_path": "M:\\bidscoin\\raw\\sub-P002\\ses-mri01\\05_Flanker_ep2d_bold_nomoco",
                "bids_name": "sub-*_ses-*_acq-Flankerep2dboldnomoco_run-<<1>>"
            },
            {
                "modality": "extra_data",
                "provenance_file": "M005.MR.WUR_BRAIN_ADHD.0007.0001.2018.04.12.13.00.48.734375.108749947.IMA",
                "provenance_path": "M:\\bidscoin\\raw\\sub-P002\\ses-mri02\\07_t1_fl3d_sag_p3_iso_1",
                "bids_name": "sub-*_ses-*_acq-t1fl3dsagp3iso1_run-<<1>>"
            }
        ]

        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
        bidsmap_yaml = read_yaml_as_string(filename)
        bidsmap = read_bidsmap(bidsmap_yaml)
        list_summary = get_list_summary(bidsmap)

        self.assertEqual(list_summary, test_list_summary)

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

        yaml = ruamel.yaml.YAML()
        sample = read_sample(bidsmap, modality, index)
        sample_yaml = yaml.dump(sample, sys.stdout)

        yaml = ruamel.yaml.YAML()
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new_sample2.yaml")
        with open(filename) as fp:
            test_sample_yaml = fp.read()
            test_sample = yaml.load(test_sample_yaml)
        test_sample_yaml = yaml.dump(test_sample, sys.stdout)

        self.assertEqual(test_sample_yaml, sample_yaml)

    def test_update_bidsmap(self):
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
        source_bidsmap_yaml = read_yaml_as_string(filename)
        source_bidsmap = read_bidsmap(source_bidsmap_yaml)

        source_modality = 'extra_data'
        source_index = 2
        yaml = ruamel.yaml.YAML()
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new_sample2.yaml")
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
