import jsonschema
import json
from bidscoin import bcoin, bidscoinroot
from ruamel.yaml import YAML
yaml = YAML()
yaml.representer.ignore_aliases = lambda *data: True                         # Expand aliases (https://stackoverflow.com/questions/58091449/disabling-alias-for-yaml-file-in-python)

bcoin.setup_logging()


def test_validate_bidsmaps():

    # Use the schema to validate the bidsmap
    with (bidscoinroot/'heuristics'/'schema.json').open('r') as stream:
        schema = json.load(stream)
    for template in (bidscoinroot/'heuristics').glob('*.yaml'):
        with template.open('r') as stream:
            bidsmap = yaml.load(stream)
        jsonschema.validate(bidsmap, schema)
