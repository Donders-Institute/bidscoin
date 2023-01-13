import unittest
import logging
import tempfile

import pytest
import ruamel
from pathlib import Path

try:
    from bidscoin import bidscoin, bids
    from bidscoin.plugins import dcm2niix4petbids
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))# This should work if bidscoin was not pip-installed
    sys.path.append(str(Path(__file__).parents[1]/'plugins'))# This should work if bidscoin was not pip-installed
    import bidscoin, bids
    from plugins import dcm2niix4petbids



# setup logger
LOGGER = logging.getLogger(__name__)
bidscoin.setup_logging()


@pytest.fixture()
def setup_bidsmaps():
    template_bidsmap_path = Path('../bidscoin/heuristics/bidsmap_dccn.yaml')
    bidsmap_path = Path('tests/test_data/bidsmap.yaml')
    full_bidsmap_path = Path(bidsmap_path.resolve())
    return {'template_bidsmap_path': template_bidsmap_path, 'full_bidsmap_path': full_bidsmap_path}


def test_template_bidsmap_is_valid(setup_bidsmaps):
    template_bidsmap, _ = bids.load_bidsmap(setup_bidsmaps['template_bidsmap_path'])
    is_valid = bids.check_bidsmap(template_bidsmap)
    for each in is_valid:
        assert each is None


def test_remove_duplicate_pet_runs(setup_bidsmaps):
    bidsmap, _ = bids.load_bidsmap(setup_bidsmaps['full_bidsmap_path'])
    to_be_deduplicated = bidsmap.copy()
    with tempfile.TemporaryDirectory() as tempdir:
        to_be_deduplicated_path = Path(tempdir)
        dcm2niix4petbids.deduplicate_pet_runs(to_be_deduplicated, to_be_deduplicated_path)

        # reload deduplicated bidsmap
        deduplicated, _ = bids.load_bidsmap(to_be_deduplicated_path / 'bidsmap.yaml')

        pet_runs = deduplicated.get('PET', None)
        assert type(pet_runs) == ruamel.yaml.comments.CommentedMap
        assert len(pet_runs['pet']) > 0

        other_data_formats = [fmt for fmt in bidsmap.keys() if fmt != 'Options' and fmt != 'PET']
        for pet_run in pet_runs['pet']:
            for other_format in other_data_formats:
                duplicate_pet_run = bids.find_run(
                    bidsmap=deduplicated,
                    provenance=pet_run['provenance'],
                    dataformat=other_format
                )
                assert duplicate_pet_run is None

# class Dcm2niix4petbidsPlugin(unittest.TestCase):
#
#     @classmethod
#     def setUpClass(cls):
#         cls.template_bidsmap_path = Path('../bidscoin/heuristics/bidsmap_dccn.yaml')
#         cls.bidsmap_path = Path('testdata/bidsmap.yaml')
#         cls.full_bidsmap_path = Path(cls.bidsmap_path.resolve())
#
#     def test_template_bidsmap_is_valid(self):
#         template_bidsmap, _ = bids.load_bidsmap(self.template_bidsmap_path)
#         is_valid = bids.check_bidsmap(template_bidsmap)
#         self.assertEqual(is_valid, [None, None, None])
#
#     def test_remove_duplicate_pet_runs(self):
#         bidsmap, _ = bids.load_bidsmap(self.full_bidsmap_path)
#         to_be_deduplicated = bidsmap.copy()
#         with tempfile.TemporaryDirectory() as tempdir:
#             to_be_deduplicated_path = Path(tempdir)
#             dcm2niix4petbids.deduplicate_pet_runs(to_be_deduplicated, to_be_deduplicated_path)
#
#             # reload deduplicated bidsmap
#             deduplicated, _ = bids.load_bidsmap(to_be_deduplicated_path / 'bidsmap.yaml')
#
#             pet_runs = deduplicated.get('PET', None)
#             self.assertEqual(type(pet_runs), ruamel.yaml.comments.CommentedMap)
#             self.assertGreater(len(pet_runs['pet']), 0)
#             other_data_formats = [fmt for fmt in bidsmap.keys() if fmt != 'Options' and fmt != 'PET']
#             for pet_run in pet_runs['pet']:
#                 for other_format in other_data_formats:
#                     duplicate_pet_run = find_run(
#                         bidsmap=deduplicated,
#                         provenance=pet_run['provenance'],
#                         dataformat=other_format
#                     )
#                     self.assertEqual(type(duplicate_pet_run), None)
#
# if __name__ == '__main__':
#     unittest.main()
