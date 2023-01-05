import unittest
import logging
import tempfile
import ruamel
from pathlib import Path
from bidscoin import bidscoin
from bidscoin.bids import load_bidsmap, find_run, check_bidsmap
from bidscoin.plugins import dcm2niix4petbids

# setup logger
LOGGER = logging.getLogger(__name__)
bidscoin.setup_logging()

class Dcm2niix4petbidsPlugin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.template_bidsmap_path = Path('../bidscoin/heuristics/bidsmap_dccn.yaml')
        cls.bidsmap_path = Path('testdata/bidsmap.yaml')
        cls.full_bidsmap_path = Path(cls.bidsmap_path.resolve())

    def test_template_bidsmap_is_valid(self):
        template_bidsmap, _ = load_bidsmap(self.template_bidsmap_path)
        is_valid = check_bidsmap(template_bidsmap)
        self.assertEqual(is_valid, [None, None, None])

    def test_remove_duplicate_pet_runs(self):
        bidsmap, _ = load_bidsmap(self.full_bidsmap_path)
        to_be_deduplicated = bidsmap.copy()
        with tempfile.TemporaryDirectory() as tempdir:
            to_be_deduplicated_path = Path(tempdir)
            dcm2niix4petbids.deduplicate_pet_runs(to_be_deduplicated, to_be_deduplicated_path)

            # reload deduplicated bidsmap
            deduplicated, _ = load_bidsmap(to_be_deduplicated_path / 'bidsmap.yaml')

            pet_runs = deduplicated.get('PET', None)
            self.assertEqual(type(pet_runs), ruamel.yaml.comments.CommentedMap)
            self.assertGreater(len(pet_runs['pet']), 0)
            other_data_formats = [fmt for fmt in bidsmap.keys() if fmt != 'Options' and fmt != 'PET']
            for pet_run in pet_runs['pet']:
                for other_format in other_data_formats:
                    duplicate_pet_run = find_run(
                        bidsmap=deduplicated,
                        provenance=pet_run['provenance'],
                        dataformat=other_format
                    )
                    self.assertEqual(duplicate_pet_run, None)

            bidsmap_validity = check_bidsmap(deduplicated)
            self.assertEqual(bidsmap_validity, [None, None, None])


if __name__ == '__main__':
    unittest.main()
