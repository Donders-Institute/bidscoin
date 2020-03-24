Options
=======

BIDScoin options
----------------
The nifti- and json-files are generated with
`dcm2niix <https://github.com/rordenlab/dcm2niix>`__. 

dcm2niix
--------

The mapping information is stored as key-value pairs in the human
readable and widely supported `YAML <http://yaml.org/>`__ files.

Plugins
-------

BIDScoin provides the possibility for researchers to write custom python
functions that will be executed at bidsmapper and bidscoiner runtime. To
use this functionality, enter the name of the module (default location
is the plugins-folder; otherwise the full path must be provided) in the
bidsmap dictionary file to import the plugin functions. The functions in
the module should be named ``bidsmapper_plugin`` for bidsmapper and
``bidscoiner_plugin`` for bidscoiner. See
`README.py <./bidscoin/plugins/README.py>`__ for more details and
placeholder code.

