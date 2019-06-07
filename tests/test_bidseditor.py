import sys
import os
import unittest
import ruamel
import logging
import copy
import difflib

from bidscoin.bids import load_bidsmap, save_bidsmap, unknownmodality
from bidscoin.bidseditor import get_allowed_suffixes, get_bids_attributes, update_bidsmap


LOGGER = logging.getLogger()
LOGGER.level = logging.DEBUG
LOGGER.addHandler(logging.StreamHandler(sys.stdout))


class TestBidseditor(unittest.TestCase):

    def test_get_allowed_suffices(self):
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "heuristics")
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "heuristics", "bidsmap_template.yaml")
        template_bidsmap = load_bidsmap(filename, path)
        allowed_suffixes = get_allowed_suffixes(template_bidsmap)

        reference_allowed_suffixes = {
            "anat": [
                "FLAIR",
                "FLASH",
                "PD",
                "PDT2",
                "PDmap",
                "SWImagandphase",
                "T1map",
                "T1rho",
                "T1w",
                "T2map",
                "T2star",
                "T2w",
                "angio",
                "defacemask",
                "inplaneT1",
                "inplaneT2"
            ],
            "func": [
                "bold",
                "events",
                "physio",
                "sbref",
                "stim"
            ],
            "dwi": [
                "dwi",
                "sbref"
            ],
            "fmap": [
                "epi",
                "fieldmap",
                "magnitude",
                "magnitude1",
                "magnitude2",
                "phase1",
                "phase2",
                "phasediff"
            ],
            "beh": [
                "beh",
                "events",
                "physio",
                "stim"
            ],
            "pet": [
                "pet"
            ],
            "extra_data": []
        }

        self.assertEqual(allowed_suffixes, reference_allowed_suffixes)

    def test_get_allowed_suffixes(self):
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "heuristics")
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "heuristics",
                                "bidsmap_template.yaml")
        template_bidsmap = load_bidsmap(filename, path)
        allowed_suffixes = get_allowed_suffixes(template_bidsmap)

        source_bids_attributes = {
            "acq_label": "localizerAANGEPAST11SLICES",
            "rec_label": None,
            "ce_label": None,
            "task_label": None,
            "echo_index": None,
            "dir_label": None,
            "run_index": "<<1>>",
            "suffix": None,
            "mod_label": None
        }

        # test anat
        bids_attributes = get_bids_attributes(template_bidsmap,
                                              allowed_suffixes,
                                              'anat',
                                              source_bids_attributes)

        reference_bids_attributes = {
            "acq_label": "localizerAANGEPAST11SLICES",
            "rec_label": "",
            "run_index": "<<1>>",
            "mod_label": "",
            "suffix": "T1w",
            "ce_label": ""
        }

        self.assertEqual(bids_attributes, reference_bids_attributes)

        # test extra_data
        bids_attributes = get_bids_attributes(template_bidsmap,
                                              allowed_suffixes,
                                              unknownmodality,
                                              source_bids_attributes)

        reference_bids_attributes = {
            "acq_label": "localizerAANGEPAST11SLICES",
            "rec_label": "",
            "ce_label": "",
            "task_label": "",
            "echo_index": "",
            "dir_label": "",
            "run_index": "<<1>>",
            "suffix": "",
            "mod_label": ""
        }

        self.assertEqual(bids_attributes, reference_bids_attributes)

    def test_update_bidsmap(self):
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata")
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata",
                                "bidsmap_example.yaml")
        source_bidsmap = load_bidsmap(filename, path)

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
