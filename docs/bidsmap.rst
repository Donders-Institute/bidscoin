The bidsmap explained
=====================

Structure and content
---------------------

Generally speaking, a bidsmap contains a collection of key-value dictionaries that define how different source data runs (e.g. a T1w- or a T2w-scan) should map onto BIDS filenames. As illustrated in the figure below (but see also the screenshot of the `edit window <screenshots.html>`__), a run-item consists of ``provenance``, ``attributes`` and ``bids`` key-value dictionaries:

 - The provenance item contains the pathname of a source data sample that is representative for this run.
 - The attributes dictionary contains keys and values that are properties of the source data and that are (pre-) selected to uniquely identify a run item. A source data sample is positively identified only if all specified (non-empty) values match.
 - The bids dictionary contains key-value pairs that are used to construct the associated BIDS output filename.

.. figure:: ./_static/bidsmap_sample.png

   A snippet of a study ``bidsmap.yaml`` file, showing a ``DICOM`` section with a few run items in the ``anat`` subsection

A bidsmap has a BIDScoin ``Options`` and a ``PlugIns`` section, followed by source modality sections (e.g. ``DICOM``, ``PAR``, ``P7``, ``Nifti``, ``FileSystem``). Within a source modality section there sub-sections for the ``participant_label`` and ``session_label``, and for the BIDS datatypes (``anat``, ``func``, ``dwi``, ``fmap``, ``pet``, ``beh``) plus the additional ``extra_data`` datatype. BIDScoin tools will go through the list of run items of a datatype from top to bottom until they come across an item that matches with the data sample at hand. At that point a bidsmapping is established.

From template to study
----------------------

A bidsmap can either be a template bidsmap or a study bidsmap. The difference between them is that a template bidsmap is a comprehensive set of pre-defined run items and serves as an input for the bidsmapper to automatically make a first version of a study bidsmap. The study bidsmap is thus derived from the template bidsmap and contains only those run items that are present in the data. The study bidsmap can be interactively edited with knowledge that is specific to a study and that cannot be extracted from the data (e.g. set a ``task`` value to "rest"). A user normally doesn't have to interact with the template bidsmap, but it is sure possible to `create your own <advanced.html#site-specific-customized-template>`__.

.. figure:: ./_static/bidsmap_flow.png

   Creation and application of a study bidsmap

Special bidsmap features
------------------------

* **Source attribute wildcards**. Source attribute values can contain `Unix shell-style <https://docs.python.org/3/library/fnmatch.html>`__ ``*`` wildcards to facilitate more liberal run matching. For instance you can use ``SeriesDescription: '*MPRAGE*'`` to match all MPRAGE DICOM series as they come from your MRI scanner.

* **Source attribute list**. Instead of a normal string, a source attribute value can also be a list of strings, in which case a match is positive if any of the list items matches with the source attribute of the run. For instance ``SequenceName: ['\*epfid\*', 'fm2d2r']`` will liberally match all DICOM sequences with that have ``epfid`` in their ``SequenceName`` and it will strictly match on ``fm2d2r``.

* **Dynamic bids value**. Bids values can be static, in which case the value is just a normal string, or dynamic, when the string is enclosed with pointy brackets. In case of single pointy brackets the bids value will be replaced during bidsmapper, bidseditor and bidscoiner runtime by the value of the source attribute. For instance ``acq: <MRAcquisitionType><SeriesDescription>`` will be replaced by ``acq: 3DMPRAGE``. In case of double enclosed pointy brackets, the value will be updated only during bidscoiner runtime -- this is useful for bids values that are subject/session dependent. For instance ``run: <<1>>`` will be replaced with ``run: 1`` or e.g. increased to ``run: 2`` if a file with that bidsname already exists.

* **Bids value list**. Instead of a normal string, a bids value can also be a list of strings, with the last list item being the (zero-based) list index that selects the final bids value. For instance the list ``['mag', 'phase', 'real', 'imag', 1]`` would select ``phase`` as a value. A bids value list is made visible in the bidseditor as a drop-down menu.

The special bidsmap features are most useful when added to template bidsmaps.
