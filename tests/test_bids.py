import unittest
import os
import logging
import tempfile
import shutil
from pathlib import Path
from bidscoin import bidscoin

from bidscoin.bids import get_run, append_run, delete_run, update_bidsmap, \
    match_runvalue, exist_run, get_matching_run, find_run, save_bidsmap, load_bidsmap

LOGGER = logging.getLogger(__name__)
bidscoin.setup_logging()

class TestBidsMappingFunctions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bidsmap_path = Path('testdata/bidsmap.yaml')
        cls.full_bidsmap_path = Path(cls.bidsmap_path.resolve())

    def test_load_bidsmap(self):
        # test loading with recommended arguments for load_bidsmap
        full_arguments_map, return_path = load_bidsmap(Path(self.full_bidsmap_path.name), self.full_bidsmap_path.parent)
        self.assertIsInstance(full_arguments_map, dict)
        self.assertTrue(full_arguments_map)

        # test loading with no input folder0, should load default from heuristics folder
        no_input_folder_map, _ = load_bidsmap(self.bidsmap_path)
        self.assertIsInstance(no_input_folder_map, dict)
        self.assertTrue(no_input_folder_map)

        # test loading with full path to only bidsmap file
        full_path_to_bidsmap_map, _ = load_bidsmap(self.full_bidsmap_path)
        self.assertIsInstance(full_path_to_bidsmap_map, dict)
        self.assertTrue(no_input_folder_map)

    def test_find_run(self):
        # load bidsmap

        bidsmap, _ = load_bidsmap(self.full_bidsmap_path)
        # collect provenance from bidsmap for anat, pet, and func
        anat_provenance = bidsmap['DICOM']['anat'][0]['provenance']
        func_provenance = bidsmap['DICOM']['func'][0]['provenance']

        # find run with partial provenance
        not_found_run = find_run(bidsmap=bidsmap, provenance='sub-001', dataformat='DICOM')
        self.assertFalse(not_found_run)

        # find run with full provenance
        found_run = find_run(bidsmap=bidsmap, provenance=anat_provenance)

        # create a duplicate provenance but in a different datatype
        bidsmap['PET'] = bidsmap['DICOM']
        # mark the entry in the PET section to make sure we're getting the right one
        tag = 123456789
        bidsmap['PET']['anat'][0]['properties']['nrfiles'] = tag
        # locate PET datatype run
        pet_run = find_run(bidsmap, provenance=anat_provenance, dataformat='PET')
        self.assertEqual(
            pet_run['properties']['nrfiles'], tag
        )

    def test_delete_run(self):
        # create a capy of the bidsmap
        with tempfile.TemporaryDirectory() as tempdir:
            temp_bidsmap = Path(tempdir) / Path(self.full_bidsmap_path.name)
            shutil.copy(self.full_bidsmap_path, temp_bidsmap)
            bidsmap, _ = load_bidsmap(temp_bidsmap)
            anat_provenance = bidsmap['DICOM']['anat'][0]['provenance']
            # now delete it from the bidsmap
            delete_run(bidsmap, anat_provenance)
            self.assertEqual(len(bidsmap['DICOM']['anat']), 0)
            # verify this gets deleted when rewritten
            save_bidsmap(_, bidsmap)
            written_bidsmap, _ = load_bidsmap(_)
            deleted_run = find_run(written_bidsmap, anat_provenance)
            self.assertFalse(deleted_run)


# class TestBids(unittest.TestCase):
#
#     def test_version(self):
#         v = version()
#         with open('version.txt') as fp:
#             v_from_file = fp.read().strip()
#         self.assertEqual(v, v_from_file)
#
#     def test_bids_version(self):
#         bids_v = bidsversion()
#         with open('bidsversion.txt') as fp:
#             bids_v_from_file = fp.read().strip()
#         self.assertEqual(bids_v, bids_v_from_file)


if __name__ == '__main__':
    unittest.main()
