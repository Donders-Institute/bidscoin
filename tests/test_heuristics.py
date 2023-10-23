import jsonschema
import json
from bidscoin import bcoin, bidscoinfolder
from ruamel.yaml import YAML
yaml = YAML()

bcoin.setup_logging()


def test_validate_bidsmaps():

    # Use the schema to validate the bidsmap
    with (bidscoinfolder/'heuristics'/'schema.json').open('r') as stream:
        schema = json.load(stream)
    for template in (bidscoinfolder/'heuristics').glob('*.yaml'):
        with template.open('r') as stream:
            bidsmap = yaml.load(stream)
        jsonschema.validate(bidsmap, schema)
