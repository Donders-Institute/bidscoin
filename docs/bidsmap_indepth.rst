The bidsmap in depth
====================

A central concept in BIDScoin is the so-called bidsmap. Generally speaking, a bidsmap contains all the information needed to convert a source dataset to BIDS. It includes all processing options, as well as a hierarchically organized collection of its key units, the so-called run-items. The two kinds of bidsmaps -- the template bidsmap and the dataset bidsmap -- share the same structure and differ mainly in the run-items they contain.

Processing options
------------------

At the root level, a bidsmap always contains an 'Options' section for storing all settings used by BIDScoin and its plugins. The ``bidscoin`` settings include command-line arguments passed to bidsmapper, along with settings that the user can edit with the bidseditor. The ``plugins`` section lists the plugins that will be employed, each with its own set of settings. The list of plugins can be passed as a bidsmapper command-line argument, and their settings can be edited with the bidseditor.

Data formats
------------

Next to the options section, at the root level, bidsmaps contain optional data format sections, e.g. named 'DICOM' or 'PAR'. The run-items in these sections differ from each other in that they contain data format specific attributes and dynamic values. The section name is important and should be equal to the data format(s) supported by the plugins, i.e. to the value returned by ``PluginInterface().has_support()``. The options and data format sections will all show up as individual tabs in the bidseditor GUI.

The structure of a data format section always consists of a 'participant' subsection, various BIDS data type subsections (such as 'fmap', 'anat', and 'func'), and subsections for 'extra_data' and 'exclude'. These subsections serve different purposes:

* **The 'participant' subsection** contains optional key-item pairs to populate the participants.tsv/json files. However, two keys, ``particpant_id`` and ``session_id``, must always be included, as they are needed to generate the subject and session labels in the BIDS output file-paths. Items always have a ``value`` field to populate the content of the participants.tsv file, as well as a ``meta`` field to populate the sidecar participants.json file (see figure below). Since sessions are optional in BIDS, the value of session_id item can be lefty empty to produce session-less output datasets.
* **A BIDS subsection** holds a list of run-items for source data that should be converted normally.
* **The 'extra_data' subsection** holds a list of run-items for data that should be converted to (unofficial) BIDS-like data.
* **The 'exclude' subsection** holds a list of run-items for source data that BIDScoin should skip during conversion.

.. code-block:: yaml

    DICOM:
    # --------------------------------------------------------------------------------
    # DICOM key-value heuristics (DICOM fields that are mapped to the BIDS labels)
    # --------------------------------------------------------------------------------
      participant:                                  # Attributes or properties to populate the participants tsv/json files
        participant_id: &participant_id
          value: <<filepath:/sub-(.*?)/>>           # This filesystem property extracts the subject label from the source directory. NB: Any property or attribute can be used as subject-label, e.g. <PatientID>
          meta:                                     # All data in "meta" is stored in the participants json sidecar-file
            Description: The unique participant identifier of the form sub-<label>, matching a participant entity found in the dataset
        session_id: &session_id
          value: <<filepath:/sub-.*?/ses-(.*?)/>>   # This filesystem property extracts the session label from the source directory. NB: Any property or attribute can be used as session-label, e.g. <StudyID>
          meta:
            Description: The session identifier of the form ses-<label>, matching a session found in the dataset
        age: &age
          value: <<PatientAge>>
          meta:
            Description: Age of the participant
            Units: year
        sex: &sex
          value: <<PatientSex>>
          meta:
            Description: Sex of the participant
            Levels:
              M: male
              F: female
              O: other
        height: &height
          value: <<PatientSize>>
          meta:
            Description: Height of the participant
            Units: meter
        weight: &weight
          value: <<PatientWeight>>
          meta:
            Description: Weight of the participant
            Units: kilogram

*Snippet from the "DICOM" data format section of the bidsmap_dccn template, showing the 'participant' subsection*

Run-items
---------

As mentioned, in a bidsmap, the run-items are the key units that define how source data types map (are to be converted) to specific `BIDS data types <https://bids-specification.readthedocs.io/en/stable/02-common-principles.html#definitions>`__. Each run-item consist of a 'provenance' field, along with 'properties', 'attributes', 'bids', 'meta' and 'events' `dictionaries <https://en.wikipedia.org/wiki/Associative_array>`__:

1. **The provenance field** contains the pathname of a source data sample that is representative for the run-item. The provenance data serves as a look-up key, and can be very useful for deeper inspection of the source data and for tracing back the conversion process, e.g. in case of encountering unexpected results.
2. **The properties dictionary** contains file system properties of the data sample, i.e. the file path, the file name, the file size on disk and the number of files in the containing folder. Depending on your data management, these properties can extract e.g. subject labels or data types from your source data.
3. **The attributes dictionary** contains attributes from the source data itself, such as the 'ProtocolName' from the DICOM header. The source attributes are typically a rich source of information of which a minimal subset is normally sufficient to identify the different data types in your source data repository. The attributes are read from (the header of) the source file itself or, if present, from an accompanying sidecar file. This sidecar file transparently extends (or supplants) the available source attributes, as if that data would have been written to (the header of) the source data file itself. The name of the sidecar file should be the same as the name of the first associated source file and have a ``.json`` file extension. For instance, the ``001.dcm``, ``002.dcm``, ``003.dcm``, [..], DICOM source images can have a sidecar file in the same directory named ``001.json`` (e.g. containing metadata that is not available in the DICOM header or that must be overruled). It should be noted that BIDScoin `plugins <./plugins.html>`__ will copy the extended attribute data over to the json sidecar files in your BIDS output folder, giving you additional control to generate your BIDS sidecar files (in addition to the meta dictionary described in point 5 below).
4. **The bids dictionary** contains the BIDS data type and entities that determine the filename of the BIDS output data. Instead of a normal string, a bids dictionary value can also be a list of strings, with the last list item being the (zero-based) list index that selects the actual value from the list. For instance the list ``{part: ['', 'mag', 'phase', 'real', 'imag', 2]}`` would select 'phase' as the value belonging to 'part'. A bids value list is represented in the bidseditor as a drop-down menu in which the user can choose between the values (i.e. set the list index).
5. **The meta dictionary** contains custom key-value pairs that are added to the json sidecar file by the BIDScoin plugins. Metadata may well vary from session to session, hence this dictionary often contains dynamic attribute values that are evaluated during bidscoiner runtime (see the `special features <#special-bidsmap-features>`__ below).
6. **The events dictionary** contains mapping data on how to convert stimulus log files to BIDS `task events <https://bids-specification.readthedocs.io/en/stable/modality-specific-files/task-events.html>`__ files. Currently, this dictionary is only used by the `events2bids <./plugins.html#events2bids-a-plugin-for-neurobs-presentation-log-data>`__ plugin.

   .. dropdown:: More details...

      The events dictionary includes fields for selecting the ``columns`` and ``rows`` from the source data, and a field for ``time`` calibration:

      * The **'columns' field** contains a list of key-value pairs, in which the key is the name of the BIDS target column, and the value the name of a source column.
      * The **'rows' field** contains a list of items that have an ``condition`` dictionary and a ``cast`` key-value pair. The keys in the "condition" dictionary are source column names, the value are regular expressions for selecting its rows (cells).
      * The **'time' field** contains:

        * **cols** -- A list of source columns that hold time values
        * **unit** -- The number of source data time units per second
        * **start** -- The event-codes that define the start of the run (time zero)

      |nbsp|

      .. code-block:: yaml

         events:
           columns:               # Columns that are included in the output table, i.e. {output column: input column}
           - onset: Time          # The mapping for the first required column 'onset'
           - duration: Duration   # The mapping for the second required column 'duration'
           - code: Code
           - event_type: Event Type
           - trial_nr: Trial
           rows:                  # Rows that are included in the output table
           - condition:           # Dict(s): key = column name of the log input table, value = fullmatch regular expression to select the rows of interest
               Event Type: .*
             cast:                # Dict(s): column name + value(s) of the condition in the output table
           time:
             cols: ['Time', 'TTime', 'Uncertainty', 'Duration', 'ReqTime', 'ReqDur']
             unit: 10000          # The precision of Presentation clock times is 0.1 milliseconds
             start:
               Code: 10           # The column name and event-code used to log the first (or any) scanner pulse

      *A bidsmap snippet from a run-item, featuring its events dictionary*

In sum, a run-item maps the input dictionaries (2) and (3) to the output dictionaries (4), (5) and (6), as illustrated in the figure below (and reflected in the `edit window <./screenshots.html>`__).

.. figure:: ./_static/bidsmap_sample.png

   A snippet of a dataset bidsmap, featuring an example run-item from the 'anat' data type subsection within the 'DICOM' data format section. The arrow illustrates how the 'properties' and 'attributes' input dictionaries are mapped onto the 'bids' and 'meta' output dictionaries. Note that the 'part' value in the bids dictionary is a list, which appears in the bidseditor GUI as a drop-down menu (with the first empty item being selected). Also note the special double bracket `dynamic values <./bidsmap_features.html#dynamic-values>`__ (<<..>>).

.. note::
   Out of the box, BIDScoin plugins typically produce sidecar files that contain metadata from the source headers. However, when such metadata is missing (e.g. as for nibabel2bids), or when it needs to be appended or overruled, then users can add sidecar files to the source data (as explained `here <./bidsmap_indepth.html#run-items>`__) or add that metadata using the bidseditor (the latter takes precedence). Metadata keys with empty/missing values will be removed from the sidecar files.

Run-item matching
-----------------

The source properties and attribute values of run-items in a bidsmap are interpreted as `regular expression patterns <https://docs.python.org/3/library/re.html>`__ when matched with your source data samples. For instance, a key-value pair of an attribute dictionary in your template bidsmap could be ``{ProtocolName: .*(mprage|T1w).*}``. This pattern would test if the extracted DICOM attribute 'ProtocolName' of a given data sample contains either a 'mprage' or a 'T1w' substring. Specifically, the Python expression that is evaluated is: ``match = re.fullmatch('.*(mprage|T1w).*', 't1_mprage_sag_p2_iso_1.0')``) if the ProtocolName of the data sample is 't1_mprage_sag_p2_iso_1.0'.

The bidsmapper and bidscoiner routines process source data, they will scan the entire repository and take samples of the data and compare them with the run-items in the bidsmap until they come across a run-item of which all (non-empty) properties and attribute values match (using `fullmatch <https://docs.python.org/3/library/re.html>`__) with the values extracted from the data sample at hand. At that point a run-item match is established, i.e. BIDScoin then knows precisely how to convert the data sample to BIDS. Bidsmaps can contain an unlimited number of run-items, including multiple run-items mapping onto the same BIDS target (e.g. when you renamed your DICOM scan protocol halfway your study and you don't want that irrelevant change to be reflected in the BIDS output).

From template to dataset bidsmap
--------------------------------

In BIDScoin a bidsmap can either be a template bidsmap or a dataset bidsmap. A template bidsmap contains a comprehensive set of run-items that contain prior knowledge about the source data properties and attributes that typically belong to a BIDS target. A dataset bidsmap, on the other hand, contains only run-items that matched positively with the source data of a dataset, i.e. it represents all the source data types present in the dataset (but nothing more). Moreover, this shortlist of run-items can be edited by the user (adding the posterior knowledge) to get the optimal mapping to BIDS for the data at hand. In the workflow (see figure below), the bidsmapper takes the template bidsmap and source data as input to automatically produce a first version of a dataset bidsmap. The runs in this dataset bidsmap are taken from the template bidsmap, with the difference that all attribute values of the matching run-item (including empty values and values with regular expressions) are supplanted with the attribute values of the data samples. In this way, the run-items will uniquely match to the data samples, providing a complete mapping of all source data types to BIDS data types. These mappings can be edited by the user with the bidseditor and then given to the bidscoiner to do the actual conversion of the source data to BIDS.

Users normally don't have to know about or interact with the template bidsmap, and only see dataset bidsmaps (in the bidseditor). To have a fully automated workflow, users with a customized template bidsmap and standardized data acquisition protocol can rely on the automated mappings and skip the bidseditor step (and hence don't see the dataset bidsmap). In fact, it is then even possible (but not recommended) to skip the bidsmapping step and pass the template bidsmap directly to the bidscoiner (for this to work you need to be sure beforehand that all source data types have matching run-items in the template bidsmap).

.. figure:: ./_static/bidsmap_flow.png

   Creation and application of a dataset bidsmap

Building your own template bidsmap
----------------------------------

The run-items in the default 'bidsmap_dccn' template bidsmap have values that are tailored to MRI acquisitions in the Donders Institute. Hence, if you are using different protocol parameters that do not match with these template values or you are using e.g. filenames instead of header information to typify your data, then your runs will initially be data (mis)typed by the bidsmapper as miscellaneous 'extra_data' -- which you then need to correct afterwards yourself. To improve that initial data typing and further automate your workflow, you may consider creating your own customized template bidsmap. Here are some things to keep in mind when building your own template bidsmap:

- To get the correct match for every source data type, run-items of template (but not dataset) bidsmaps typically contain regular expressions in their property and/or in attribute values. These regular expressions should best be designed to broadly but uniquely match the values in the source data, i.e. they should match with all variations of the same source data type, but never match with any other source data type. The expressions can be considered as prior knowledge about the data, and can be dependent on your data acquisition protocol.

- When matching a data sample to run-items in a bidsmap, the search order is such that data samples will first be matched to the 'exclude' run-items, then, if they don't match, to the BIDS run-items (the items in 'fmap', 'anat', 'func', etc) and finally, if none of those match either, to the 'extra_data' run-items. The search order for the list of run-items within each BIDS data type is from top to bottom. The search order can play a role (and can be exploited) if you have run-items that are very similar, i.e. have (partly) overlapping properties or attributes. You can use this to your advantage by placing certain run-items before others. For instance, if you are adding run-items for multi-band EPI pulse sequences, you may want to put your 'SBREF' run-item before your 'MB' run-item and put a minor extra property and/or attribute that is unique to the additionally acquired single-band reference image. So if the SeriesDescription is "task_fMRI" for the MB sequence and "task_fMRISBREF" for the SBREF sequence, then you can have ``{SeriesDescription: .*fMRI.*}`` for the MB run-item while narrowing down the matching pattern of the SBREF to ``{SeriesDescription: .*fMRISBREF.*}``. MB data samples will not match the latter pattern but will match with the MB run-item. SBREF samples will match with both run-items, but only the SBREF run-item will be copied over to the dataset bidsmap because it is encountered before the MB run-item (BIDScoin stops searching the bidsmap if it finds a match).

- In your template bidsmap you can populate your run-items with any set of ``properties`` and/or ``attributes``. For instance if in your center you are using the "PerformedProcedureStepDescription" DICOM attribute instead of "SeriesDescription" to store your metadata then you can (probably should) include that attribute to get more successful matches for your run-items. What you should **not** include there are properties or attributes that vary between repeats of the same acquisition, e.g. the DICOM 'AcquisitionTime' attribute (that makes every data sample unique and will hence give you a very long list of mostly redundant run-items in your dataset bidsmap). It is however perfectly fine to use such varying properties or attributes in dynamic values of the ``bids`` and ``meta`` run-item dictionaries (see below).

- Single dynamic brackets containing source properties or attributes can be used in the bids and meta dictionary, to have them show up in the bidseditor as pre-filled proposals for BIDS labels and/or sidecar metadata values. For instance, if you put ``{ContrastName: <ContrastAgent>}`` in a meta-dictionary in your template bidsmap, it will show up in the bidseditor GUI as ``{ContrastName: PureGadolinium}``. Double dynamic brackets can also be used, but these remain unevaluated until bidscoiner runtime. Double brackets are therefore only needed when the property or attribute value varies from subject to subject (such as "<<Age>>") or from acquisition to acquisition (such as "<<InjectedMass>>").

- Finally, it is a good practice for the first run-item in each BIDS data type section of your template bidsmap to have all empty `properties` and `attributes` values. The benefit of this is that you can dereference ('copy') it in other run-items (see the editing section below), and in this way improve your consistency and reduce the maintenance burden of keeping your template bidsmap up-to-date. The first run-item is also the item that is selected when a user manually sets the run-item to this BIDS data type in the bidseditor GUI.

.. tip::
   - Make a copy of the DCCN template (``[home]/.bidscoin/[version]/templates/bidsmap_dccn.yaml``) as a starting point for your own template bidsmap, and adapt it to your needs. You can set your copy as the new default template by editing the ``[home]/.bidscoin/config.toml`` file. Default templates and config file are automatically recreated from source when deleted
   - The power of regular expressions is nearly unlimited, you can e.g. use `negative look aheads <https://docs.python.org/3/howto/regex.html#lookahead-assertions>`__ to **not** match (exclude) certain strings
   - When creating new run-items, make sure to adhere to the YAML format and to the definitions in the BIDS schema files (``[path_to_bidscoin]/bidscoin/schema/datatypes``). You can test your YAML syntax using an online `YAML-validator <https://www.yamllint.com>`__ and your compliance with the BIDS standard with ``bidscoin -t your_template_bidsmap``. If all seems well you can install it using ``bidscoin -i your_template_bidsmap``.
   - In addition to DICOM attribute names, the more advanced/unambiguous pydicom-style `tag numbers <https://pydicom.github.io/pydicom/stable/old/base_element.html#tag>`__ can also be used for indexing a DICOM header. For instance, the ``PatientName``, ``0x00100010``, ``0x10,0x10``, ``(0x10,0x10)``, and ``(0010,0010)`` index keys are all equivalent. Moreover, you can use bracketed tags to retrieve nested attributes, e.g. ``[(0x0040,0x0275)][0][0x00321060]`` to retrieve the ``Requested Procedure Description`` of the first sequence item of the ``(0040,0275)`` attribute.

Anchors and aliases
^^^^^^^^^^^^^^^^^^^

The template bidsmap data is stored in `YAML <http://yaml.org/>`__ format, so you can use a text editor and edit the raw bidsmap data directly, provided that have some basic understanding of this data-serialization language. Most notably, it is useful to know how to use `anchors and aliases <https://blog.daemonl.com/2016/02/yaml.html>`__. The DCCN template bidsmap uses anchors in the first run-item of a BIDS data type, and aliases in the others (to dereference the content of the anchors). And because all values of the ``properties`` and ``attributes`` dictionary are empty, in the other run-items all you have to declare are the (non-empty) key-value pairs that you want to use for matching your source data types.

.. code-block:: yaml

   anat:       # ----------------------- All anatomical run-items --------------------
   - properties:                   # This is an optional (stub) entry of properties matching (could be added to any run-item)
       filepath:                   # File folder, e.g. ".*/Parkinson/.*" or ".*(phantom|bottle).*"
       filename:                   # File name, e.g. ".*fmap.*" or ".*(fmap|field.?map|B0.?map).*"
       filesize:                   # File size, e.g. "2[4-6]\d MB" for matching files between 240-269 MB
       nrfiles:                    # Number of files in the folder
     attributes: &anat_dicomattr   # An empty / non-matching reference dictionary that can be dereferenced in other run-items of this data type
       Modality:
       ProtocolName:
       SeriesDescription:
       ImageType:
       SequenceName:
       PulseSequenceName:
       SequenceVariant:
       ScanningSequence:
       EchoPulseSequence:          # Enhanced DICOM
       MRAcquisitionType:
       SliceThickness:
       FlipAngle:
       EchoNumbers:
       EchoTime:
       EffectiveEchoTime:
       RepetitionTime:
       InPlanePhaseEncodingDirection:
     bids: &anat_dicoment_nonparametric  # See: schema/rules/files/raw/anat.yaml
       task:
       acq: <SeriesDescription>    # This will be expanded by the bidsmapper (so the user can edit it in the bidseditor)
       ce:
       rec:
       run: <<>>                   # This will be updated dynamically during bidscoiner runtime (as it depends on the already existing files)
       echo:
       part: ['', mag, phase, real, imag, 0]   # This BIDS value list will be shown as a dropdown menu in the bidseditor with the first (empty) item selected (as indicated by the last item, i.e. 0)
       chunk:
       suffix:
     meta: {}                      # This is an optional entry for metadata that will be appended to the json sidecar files produced by the plugin
   - attributes:
       <<: *anat_dicomattr
       ProtocolName: (?i).*(MPRAGE|T1w).*
       MRAcquisitionType: 3D
     bids:
       <<: *anat_dicoment_nonparametric
       suffix: T1w
   - attributes:
       <<: *anat_dicomattr
       ProtocolName: (?i).*T2w.*
       SequenceVariant: "['SK', 'SP']"
     bids:
       <<: *anat_dicoment_nonparametric
       suffix: T2w

*Snippet from the "DICOM" data format section of the bidsmap_dccn template. Here a "void" anat run-item is featured, followed by a T1w and a T2w run-item that dereference and add data to the void run-item (e.g. the* ``&anatattributes_dicom`` *anchor is dereferenced with the* ``<<: *anatattributes_dicom`` *alias).*

.. |nbsp| unicode:: 0xA0
   :trim:
