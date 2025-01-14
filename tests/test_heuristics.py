import jsonschema
import json
import yaml
from bidscoin import bcoin, bidscoinroot

bcoin.setup_logging()


def test_jsonschema_validate_bidsmaps():

    # Use the schema to validate the bidsmap
    with (bidscoinroot/'heuristics'/'schema.json').open('r') as stream:
        schema = json.load(stream)
    for template in (bidscoinroot/'heuristics').glob('*.yaml'):
        with template.open('r') as stream:
            bidsmap = yaml.safe_load(stream)
        jsonschema.validate(bidsmap, schema)
