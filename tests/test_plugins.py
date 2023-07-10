"""
Run the plugin test routines

@author: Marcel Zwiers
"""

import pytest
import inspect
from bidscoin import bcoin, bids, bidsmap_template

bcoin.setup_logging()
template, _ = bids.load_bidsmap(bidsmap_template, checks=(False, False, False))


# Test all plugins using the template & default options
@pytest.mark.parametrize('plugin', bcoin.list_plugins()[0])
@pytest.mark.parametrize('options', [template['Options']['plugins'], {}])
def test_plugin(plugin, options):

    # First test to see if we can import the plugin
    module = bcoin.import_plugin(plugin, ('bidsmapper_plugin', 'bidscoiner_plugin'))
    if not inspect.ismodule(module):
        raise ImportError(f"Invalid plugin: '{plugin}'")

    # Then run the plugin's own 'test' routine (if implemented)
    assert module.test(options.get(plugin.stem, {})) == 0
