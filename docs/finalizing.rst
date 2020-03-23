Finishing up
============

After a successful run of ``bidscoiner``, the work to convert your data
in a fully compliant BIDS dataset is unfortunately not yet fully over
and, depending on the complexity of your data-set, additional tools may
need to be run and meta-data may need to be entered manually (not
everything can be automated). 

Adding meta-data
----------------
For instance, you should update the
content of the ``dataset_description.json`` and ``README`` files in your
bids folder and you may need to provide e.g. additional
``*_scans.tsv``,\ ``*_sessions.tsv`` or ``participants.json`` files (see
the `BIDS specification <http://bids.neuroimaging.io/bids_spec.pdf>`__
for more information). Moreover, if you have behavioural log-files you
will find that BIDScoin does not (yet)
`support <#bidscoin-functionality--todo>`__ converting these into BIDS
compliant ``*_events.tsv/json`` files (advanced users are encouraged to
use the ``bidscoiner`` `plug-in <#options-and-plug-in-functions>`__
possibility and write their own log-file parser).

BIDS validation
---------------

If all of the above work is done, you can (and should) run the web-based
`bidsvalidator <https://bids-standard.github.io/bids-validator/>`__ to
check for inconsistencies or missing files in your bids data-set (NB:
the bidsvalidator also exists as a `command-line
tool <https://github.com/bids-standard/bids-validator>`__).

Multi-echo combination
----------------------

Defacing
--------
