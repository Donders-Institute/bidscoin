The bidsmap explained
=====================

Structure and content
---------------------

Generally speaking, a bidsmap contains a collection of key-value dictionaries that define how different source data runs (e.g. a T1w- or a T2w-scan) should map onto BIDS filenames. As illustrated in the figure below (but see also the screenshot of the `edit window <screenshots.html>`__), a run-item consists of ``provenance``, ``attributes`` and ``bids`` key-value dictionaries:

 - The ``provenance`` item contains the pathname of a source data sample that is representative for this run.
 - The ``attributes`` dictionary contains keys and values that are properties of the source data and that are (pre-) selected to uniquely identify a run item. A source data sample is positively identified only if all specified (non-empty) values match.
 - The ``bids`` dictionary contains key-value pairs that are used to construct the associated BIDS output filename.

.. figure:: ./_static/bidsmap_sample.png

   A snippet of a study ``bidsmap.yaml`` file, showing a ``DICOM`` section with a few run items in the ``anat`` subsection

A bidsmap has a BIDScoin ``Options`` and a ``PlugIns`` section, followed by source modality sections (e.g. ``DICOM``, ``PAR``, ``P7``, ``Nifti``, ``FileSystem``). Within a source modality section there sub-sections for the ``participant_label`` and ``session_label``, and for the BIDS datatypes (``anat``, ``func``, ``dwi``, ``fmap``, ``pet``, ``beh``) plus the additional ``extra_data`` datatype. BIDScoin tools will go through the list of run items of a datatype from top to bottom until they come across an item that matches with the data sample at hand. At that point a bidsmapping is established.

From template to study
----------------------

A bidsmap can either be a template bidsmap or a study bidsmap. The difference between them is that a template bidsmap is a comprehensive set of pre-defined run items and serves as an input for the bidsmapper to automatically make a first version of a study bidsmap. The study bidsmap is thus derived from the template bidsmap and contains only those run items that are present in the data. The study bidsmap can be interactively corrected or enriched with knowledge that is specific to a study and that cannot be extracted from the data (e.g. set the func ``task`` label). A user normally doesn't have to interact with the template bidsmap, but it is sure possible to `create your own <advanced.html#site-specific-customized-template>`__.

.. figure:: ./_static/bidsmap_flow.png

   Creation and application of a study bidsmap

Special features & editing tips
-------------------------------

Source attributes
^^^^^^^^^^^^^^^^^
An (DICOM) attribute label can also be a list, in which case the BIDS labels / mapping are applied if a (DICOM) attribute value is in this list. If the attribute value is empty it is not used to identify the run. Wildcards can also be given, either as a single '*', or enclosed by '*'. Examples:

:SequenceName: '*'
:SequenceName: '\*epfid\*'
:SequenceName: ['epfid2d1rs', 'fm2d2r']
:SequenceName: ['\*epfid\*', 'fm2d2r']

NB: Editing the source attributes of a study bidsmap is usually not necessary and adviced against

Dynamic BIDS labels
^^^^^^^^^^^^^^^^^^^
BIDS labels can be static, in which case the label is just a normal string, or dynamic, when the string is enclosed with pointy brackets like `<attribute>`, `<attribute1><attribute2>` or `<<attribute1><attribute2>>`. In case of single enclosed pointy brackets the label will be replaced during bidsmapper, bidseditor and bidscoiner runtime by the value of the (DICOM) attribute with that name. In case of double enclosed pointy brackets, the label will be updated for each subject/session during bidscoiner runtime. For instance, the `run` label `<<1>>` in the bids name will be replaced with `1` or increased to `2` if a file with runindex `1` already exists in that directory.

BIDS label menus
^^^^^^^^^^^^^^^^
A BIDS label can be a list of label options, with the last list item being the (zero-based) list index that selects the current label. For instance the list ``['mag', 'phase', 'real', 'imag', 1]`` would select ``phase`` as a label. The list index can be set in the bidseditor via a drop-down menu.

Fieldmaps
---------

Select 'magnitude1' if you have 'magnitude1' and 'magnitude2' data in one series-folder (this is what Siemens does) -- the bidscoiner will automatically pick up the 'magnitude2' data during runtime. The same holds for 'phase1' and 'phase2' data. See the BIDS specification for more details on fieldmap suffixes

You can use the `IntendedFor` field to indicate for which runs (DICOM series) a fieldmap was intended. The dynamic label of the `IntendedFor` field can be a list of string patterns that is used to include all runs in a session that have that string pattern in their BIDS file name. Example: use `<<task>>` to include all functional runs or `<<Stop*Go><Reward>>` to include "Stop1Go"-, "Stop2Go"- and "Reward"-runs. NB: The fieldmap might not be used at all if this field is left empty!
