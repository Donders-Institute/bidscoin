import sys
import os
import unittest
import ruamel
import logging
import copy
import difflib

from bidscoin.bids import load_bidsmap, save_bidsmap, bidsmodalities, unknownmodality, update_bidsmap
from bidscoin.bidseditor import SOURCE, get_allowed_suffixes, get_bids_attributes, get_index_mapping


LOGGER = logging.getLogger()
LOGGER.level = logging.DEBUG
LOGGER.addHandler(logging.StreamHandler(sys.stdout))


class TestBidseditor(unittest.TestCase):

    def test_get_allowed_suffices(self):
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "heuristics")
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "heuristics", "bidsmap_template.yaml")
        template_bidsmap, _ = load_bidsmap(filename, path)
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
        template_bidsmap, _ = load_bidsmap(filename, path)
        allowed_suffixes = get_allowed_suffixes(template_bidsmap)

        SOURCE = 'DICOM'
        source_series = template_bidsmap[SOURCE][unknownmodality][0]

        # test extra_data
        bids_attributes = get_bids_attributes(template_bidsmap,
                                              allowed_suffixes,
                                              unknownmodality,
                                              source_series)

        reference_bids_attributes = {
            "acq": "<SeriesDescription>",
            "rec": "",
            "ce": "",
            "task": "",
            "echo": "",
            "dir": "",
            "run": "<<1>>",
            "suffix": "",
            "mod": ""
        }

        self.assertEqual(bids_attributes, reference_bids_attributes)

    def test_update_bidsmap(self):
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata")
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata",
                                "bidsmap_example.yaml")
        source_bidsmap, _ = load_bidsmap(filename, path)

        source_modality = 'extra_data'
        source_index = 2
        yaml = ruamel.yaml.YAML()
        filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata",
                                "bidsmap_sample_example.yaml")
        with open(filename) as fp:
            test_sample_yaml = fp.read()
            test_sample = yaml.load(test_sample_yaml)

        target_bidsmap = copy.deepcopy(source_bidsmap)
        target_modality = 'pet'
        target_sample = copy.deepcopy(test_sample)

        target_bidsmap = update_bidsmap(source_bidsmap, target_bidsmap, source_modality, source_index,
                                        target_modality, target_sample)

        self.assertNotEqual(target_bidsmap, source_bidsmap)
        self.assertNotEqual(target_bidsmap['DICOM'][target_modality], source_bidsmap['DICOM'][target_modality])
        self.assertNotEqual(target_bidsmap['DICOM'][source_modality], source_bidsmap['DICOM'][source_modality])
        self.assertEqual(len(target_bidsmap['DICOM'][target_modality]), 1)
        self.assertEqual(len(target_bidsmap['DICOM'][source_modality]), 3)

        target_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_out_temp.yaml")
        reference_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_out.yaml")

        save_bidsmap(target_filename, target_bidsmap)
        text1 = open(target_filename).readlines()
        text2 = open(reference_filename).readlines()
        lines = list(difflib.unified_diff(text1, text2))
        LOGGER.info(''.join(lines))
        self.assertEqual(len(lines), 0) # Difference must be zero


    def test_index_mapping(self):
        bidsmap = {}
        bidsmap[SOURCE] = {}
        for modality in bidsmodalities + (unknownmodality,):
            bidsmap[SOURCE][modality] = []

        series1 = {'test': '1'}
        series2 = {'test': '2'}
        series3 = {'test': '3'}
        series4 = {'test': '4'}

        bidsmap[SOURCE]['func'].append(series1)
        bidsmap[SOURCE]['func'].append(series2)
        bidsmap[SOURCE]['extra_data'].append(series3)
        bidsmap[SOURCE]['extra_data'].append(series4)

        index_mapping = get_index_mapping(bidsmap)
        index_mapping_ref = {
            'anat': {},
            'func': {0: 0, 1: 1},
            'dwi': {},
            'fmap': {},
            'beh': {},
            'pet': {},
            'extra_data': {2: 0, 3: 1}
        }
        self.assertEqual(index_mapping, index_mapping_ref)

        bidsmap[SOURCE]['func'].append(series3)
        del bidsmap[SOURCE]['extra_data'][0]

        index_mapping = get_index_mapping(bidsmap)

        index_mapping_ref = {
            'anat': {},
            'func': {0: 0, 1: 1, 2: 2},
            'dwi': {},
            'fmap': {},
            'beh': {},
            'pet': {},
            'extra_data': {3: 0}
        }
        self.assertEqual(index_mapping, index_mapping_ref)


if __name__ == '__main__':
    unittest.main()
