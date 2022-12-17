"""
Run the plugin test routines

@author: Marcel Zwiers
"""

import pytest
import inspect
from pathlib import Path
try:
    from bidscoin import bidscoin, bids
except ImportError:
    import sys
    sys.path.append(str(Path(__file__).parents[1]/'bidscoin'))         # This should work if bidscoin was not pip-installed
    import bidscoin, bids


bidscoin.setup_logging()
template, _ = bids.load_bidsmap(bidscoin.bidsmap_template, check=(False,False,False))


# Test all plugins using the template & default options
@pytest.mark.parametrize('plugin', bidscoin.list_plugins()[0])
@pytest.mark.parametrize('options', [template['Options']['plugins'], {}])
def test_plugin(plugin, options):

    # First test to see if we can import the plugin
    module = bidscoin.import_plugin(plugin, ('bidsmapper_plugin', 'bidscoiner_plugin'))
    if not inspect.ismodule(module):
        raise ImportError(f"Invalid plugin: '{plugin}'")

    # Then run the plugin's own 'test' routine (if implemented)
    assert module.test(options.get(plugin.stem, {})) in ((0,) if plugin.stem != 'dcm2niix2bids' else (0,3))
