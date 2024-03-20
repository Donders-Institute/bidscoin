The bidsmap explained
=====================

Structure and content
---------------------

A central concept in BIDScoin is the so-called bidsmap. Generally speaking, a bidsmap is a collection of run-items that define how source data types (e.g. a T1w- or a T2w-scan) should be converted to `BIDS data types <https://bids-specification.readthedocs.io/en/stable/02-common-principles.html#definitions>`__. As illustrated in the figure below (but see also the screenshot of the `edit window <./screenshots.html>`__), run-items consist of a 'provenance' field and a 'properties', 'attributes', 'bids' and a 'meta' `dictionary <https://en.wikipedia.org/wiki/Associative_array>`__ (a set of key-value pairs):

1. **The provenance field** contains the pathname of a source data sample that is representative for the run-item. The provenance data is not strictly necessary but very useful for deeper inspection of the source data and for tracing back the conversion process, e.g. in case of encountering unexpected results
2. **The properties dictionary** contains file system properties of the data sample, i.e. the file path, the file name, the file size on disk and the number of files in the containing folder. Depending on your data management, this information allows or can help to identify different datatypes in your source data repository
3. **The attributes dictionary** contains attributes from the source data itself, such as the 'ProtocolName' from the DICOM header. The source attributes are a very rich source of information of which a minimal subset is normally sufficient to identify the different datatypes in your source data repository. The attributes are read from (the header of) the source file itself or, if present, from an accompanying sidecar file. This sidecar file transparently extends (or overrule) the available source attributes, as if that data would have been written to (the header of) the source data file itself. The name of the sidecar file should be the same as the name of the first associated source file and have a ``.json`` file extension. For instance, the ``001.dcm``, ``002.dcm``, ``003.dcm``, [..], DICOM source images can have a sidecar file in the same directory named ``001.json`` (e.g. containing metadata that is not available in the DICOM header or that must be overruled). It should be noted that BIDScoin `plugins <./plugins.html>`__ will copy the extended attribute data over to the json sidecar files in your BIDS output folder, giving you additional control to generate your BIDS sidecar files (in addition to the meta dictionary described in point 5 below).
4. **The bids dictionary** contains the BIDS datatype and entities that determine the filename of the BIDS output data. The values in this dictionary are encouraged to be edited by the user
5. **The meta dictionary** contains custom key-value pairs that are added to the json sidecar file by the BIDScoin plugins. Meta data may well vary from session to session, hence this dictionary often contains dynamic attribute values that are evaluated during bidscoiner runtime (see the `special features <#special-bidsmap-features>`__ below)

In sum, a run-item contains a single bids-mapping, which links the input dictionaries (2) and (3) to the output dictionaries (4) and (5).

.. figure:: ./_static/bidsmap_sample.png

   A snippet of study bidsmap in YAML format. The bidsmap contains separate sections for each source data format (here 'DICOM') and sub-sections for the BIDS datatypes (here 'anat'). The arrow illustrates how the 'properties' and 'attributes' input dictionaries are mapped onto the 'bids' and 'meta' output dictionaries. Note that the 'part' value in the bids dictionary is a list, which is presented in the bidseditor GUI as a drop-down menu (with the first empty item being selected). Also note the special double bracket dynamic values (<<..>>), which are explained `below <#special-bidsmap-features>`__.

At the root level, a bidsmap is hierarchically organized in data format sections, such as 'DICOM' and 'PAR', which in turn contain subsections for the 'participant_label' and 'session_label', and subsections for the BIDS datatypes (such as 'fmap', 'anat', 'func') and for the 'exclude' and 'extra_data' datatypes. The 'exclude' datatype contains a list of run-items for source data that need to be omitted when converting the source data to BIDS and the 'extra_data' datatype contains a list of run-items for including miscellaneous data that is not (yet) defined in the BIDS specifications. In general you can think of the BIDS subsections as run-item lists of source datatypes that should be converted to it.
The participant- and session-label subsections contain key-value pairs for setting the BIDS subject and session labels. Next to the data format sections there is a general 'Options' section, that accommodates BIDScoin and plugin settings.

When BIDScoin workflow routines process source data, they will scan the entire repository and take samples of the data and compare them with the run-items in the bidsmap until they come across a run-item of which all (non-empty) properties and attribute values match (using `fullmatch <https://docs.python.org/3/library/re.html>`__) with the values extracted from the data sample at hand. At that point a run-item match is established, i.e. BIDScoin then knows precisely how to convert the data sample to BIDS. Bidsmaps can contain an unlimited number of run-items, including multiple run-items mapping onto the same BIDS target (e.g. when you renamed your DICOM scan protocol halfway your study and you don't want that irrelevant change to be reflected in the BIDS output).

From template to study bidsmap
------------------------------

In BIDScoin a bidsmap can either be a template bidsmap or a study bidsmap. A template bidsmap contains a comprehensive set of run-items (one run-item for each BIDS target), each of which containing the prior knowledge about the source data properties and attributes that typically belong to a BIDS target. A study bidsmap, on the other hand, contains only run-items that matched positively with the source data of a study, i.e. it represents all the source data types present in the study (but nothing more). Moreover, this shortlist of run-items can be edited by the user (adding the posterior knowledge) to get the optimal mapping to BIDS for the data at hand. In the workflow (see figure below), the bidsmapper takes the template bidsmap and source data as input to automatically produce a first version of a study bidsmap. The runs in this study bidsmap are taken from the template bidsmap, with the difference that all attribute values of the matching run-item (including empty values and values with regular expressions) are replaced with the attribute values of the data samples. In this way, the run-items will uniquely match to the data samples, providing a complete mapping of all source data types to BIDS data types. These mappings can be edited by the user with the bidseditor and then given to the bidscoiner to do the actual conversion of the source data to BIDS.

Users normally don't have to know about or interact with the template bidsmap, and only see study bidsmaps (in the bidseditor). To have a fully automated workflow, users with a very good template bidsmap and standardized data acquisition protocol can rely on the automated mappings and skip the bidseditor step (and hence don't see the study bidsmap). In fact, it is then even possible (but certainly not recommended) to skip the bidsmapping step and pass the template bidsmap directly to the bidscoiner (for this to work you need to be sure beforehand that all source datatypes have matching run-items in the template bidsmap).

.. figure:: ./_static/bidsmap_flow.png

   Creation and application of a study bidsmap

Special bidsmap features
------------------------

The dictionary values in a bidsmap are not simple strings but have some special features that make BIDScoin powerful, flexible and helpful:

Run-item matching
^^^^^^^^^^^^^^^^^
Source property and attribute values of run-items in a bidsmap are interpreted as `regular expression patterns <https://docs.python.org/3/library/re.html>`__ when they are matched with your source data samples. For instance, a key-value pair of an attribute dictionary in your template bidsmap could be ``{ProtocolName: .*(mprage|T1w).*}``, which would test if the extracted attribute string for 'ProtocolName' from the `DICOM header <https://www.dicomstandard.org>`__ of a data sample contains either a 'mprage' or a 'T1w' substring. More precisely, the Python expression that is evaluated is: ``match = re.fullmatch('.*(mprage|T1w).*', 't1_mprage_sag_p2_iso_1.0')``) if the ProtocolName of the data sample is 't1_mprage_sag_p2_iso_1.0'.

Dynamic values
^^^^^^^^^^^^^^
Dictionary values in the bidsmap can be **static**, in which case the value is just a normal string, or **dynamic**, when the string is enclosed with single ``<>`` or double ``<<>>`` pointy brackets. The enclosed string is an attribute or property that will be extracted from the data source to replace the dynamic value. In case of single pointy brackets the bids value will be replaced during bidsmapper, bidseditor and bidscoiner runtime by the value of the source attribute or property of the data sample at hand. Single brackets are typically used in template bidsmaps, meaning that you will not see them at all in the bidseditor (or anywhere after that), but instead you will see the actual values from the data. If the values are enclosed with double pointy brackets, then they won't be replaced until bidscoiner runtime. This means that they will be moved over to the study bidsmap unmodified, and that you can see, edit or add them yourself anywhere in the bidseditor. In the final BIDS output data, they will be replaced, just like the single bracket values. The rationale for using double bracket values is that certain properties or attributes vary from subject to subject, or even from acquisition to acquisition, and therefore they cannot directly be represented in the study bidsmap, i.e. their extraction needs to be postponed until bidscoiner runtime. For instance, suppose you want to include the scan operator's comments or the PET dose in the BIDS sidecar files, then you could add ``<<ImageComments>>`` and ``<<RadionuclideTotalDose>>`` as meta data values in your bidsmap.

It is useful that dynamic values can extract source properties and attributes, but sometimes you may want to extract just a part of the value. That is where **regular expressions** come in. You can simply append a semi-colon to the property or attribute, followed by a `findall <https://docs.python.org/3/library/re.html#re.findall>`__ regex pattern, which is then applied to the extracted value. For instance, say you want to extract the subject and session label from the filepath of your source data in ``/data/raw/sub-003/ses-01``. In your bidsmap you could then use ``{subject: <<filepath:/sub-(.*?)/>>}`` to evaluate ``re.findall('/sub-(.*?)/', '/data/raw/sub-003/ses-01')`` under the hood, and get ``{subject: 003}`` (i.e. the shortest string between ``/sub-`` and ``/``) during bidscoiner runtime. Alternatively, if the subject label is encoded in the DICOM ``PatientName`` attribute as e.g. ``ID_003_anon``, then ``{subject: <<PatientName:ID_(.*?)_>>}`` in your bidsmap would likewise evaluate ``re.findall('ID_(.*?)_', 'ID_003_anon')`` and give you ``{subject: 003}`` at bidscoiner runtime.

As may have become clear from the above, dynamic values are BIDScoin's hidden powerhouse. But you can take it even one step further and make combinations of static and dynamic values. For instance the static and dynamic values in ``<MRAcquisitionType>Demo<SeriesDescription:t1_(.*?)_sag>`` will result in ``3DDemoMPRAGE`` if the 'MRAcquisitionType' of the data sample is '3D' and 'SeriesDescription' is 't1_MPRAGE_sag_p2_iso_1.0' (hint: the second dynamic value will evaluates ``re.findall('t1_(.*?)_sag', 't1_mprage_sag_p2_iso_1.0')`` to give ``MPRAGE``).

.. tip::
   Dynamic values with (or without) regular expressions can be hard to grasp and predict their outcome. To easily test out their working, you can just enter dynamic values in the bidseditor (in any value field) using single brackets and instantly obtain their resulting value

Run-index
^^^^^^^^^
If the run index is encoded in the header or filename, then the index number can be normally extracted using dynamic values. For instance, using ``{run: <<ProtocolName:run_nr-(.*?)_>>}`` in the bids output dictionary will give ``{run: 3}`` if the DICOM ProtocolName is ``t1_mprage_sag_run_nr-3_iso_1.0``. Yet, if the index information is not available in the header or filename, then it needs to be determined from the presence of other files in the output directory. To handle that, the run-index value can be a **dynamic number** (similar to a dynamic value). This dynamic number (e.g. ``{run: <<1>>}``) will be incremented during bidscoiner runtime if an output file with the same name already exists (so ``.._run-1_..`` will become ``.._run-2_..``). If the dynamic number if left empty (``{run: <<>>}``), then the run-index is omitted from the output filename if there are no other files with the same name (i.e. if only a single run was acquired). If that's not the case and multiple runs were acquired, then ``{run: <<>>}`` will behave the same as ``{run: <<1>>}``, i.e. then ``.._run-1_..``, ``.._run-2_..``, etc will be included in the output filenames.

Fieldmaps: IntendedFor
^^^^^^^^^^^^^^^^^^^^^^
According to the BIDS specification, the IntendedFor value of fieldmaps must be a list of relative pathnames of associated target files. However, these target files may vary from session to session, i.e. the 'IntendedFor' value is dependent on the presence of other files in the output folder. To handle that, the dynamic ``IntendedFor`` value of the meta dictionary can be specified using Unix shell-style wildcard search strings. In that way, during bidscoiner runtime, the exact paths of these images on disk will be looked up using the Python ``glob(*value*)`` expression (see `here <https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob>`__ for the exact syntax). For instance, using a simple ``{IntendedFor: <<task>>}`` value will use ``glob(*task*)`` to lookup all functional runs in the BIDS subject[/session] folder (since in BIDS these runs always have 'task' in their filename), whereas a more advanced ``{IntendedFor: <<func/*Stop*Go_bold><func/*Reward*_bold>>}`` value will select all 'Stop1Go'-, 'Stop2Go'- and 'Reward' bold-runs in the func sub-folder.

In case duplicated field maps are acquired (e.g. when a scan failed or a session was interrupted) you can limit the search scope by appending a colon-separated "bounding" term to the search pattern. E.g. ``{IntendedFor: <<task:[]>>}`` will bound the wildcard search to files that are 'uninterruptedly connected' to the current field map, i.e. without there being another run of the field map in between. The bounded search can be further constrained by limiting the maximum number of matches, indicated with lower and upper limits. For instance ``{IntendedFor: <<task:[-3:0]>>}`` will limit the bounded search to maximally three runs preceding the field map. Similarly, ``{IntendedFor: <<task:[-2:2]>>}`` will limit the bounded search to maximally two preceding and two subsequent runs, and ``{IntendedFor: <<task:[0:]>>}`` will limit the bounded search to all matches acquired after the field map. In this latter case, for the first field map, only ``task-Stop_run-1`` and ``task-Stop_run-2`` will match the bounded search if the 5 collected runs were named: 1) ``fieldmap_run-1``, 2) ``task-Stop_run-1``, 3) ``task-Stop_run-2``, 4) ``fieldmap_run-2``, 5) ``task-Stop_run-3``. The second run of the field map will match with ``task-Stop_run-3`` only (note that the second field map would have matched all task runs if the bounding term would have been ``[]``, ``[:]`` or ``[-2:2]``).

Fieldmaps: B0FieldIdentifier/B0FieldSource
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
According to the BIDS specification, within a subject folder, fieldmaps and their target scans can also be associated by way of `B0FieldIdentifier and B0FieldSource <https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#using-b0fieldidentifier-metadata>`__ tags. However, in practice if you acquire multiple scan session, fieldmaps are only associated with targets that were acquired within the same scan session. To achieve that you can add a special ``<<session>>`` dynamic value to your tags, which will be replaced with the session label during bidscoiner runtime. And similar to the IntendedFor value, you can append a colon-separated "bounding" term to the session tag, e.g. ``<<session:[0:3]>>`` to uniquely tag the fieldmap and three subsequent associated runs. So for instance, if you have ``{B0FieldIdentifier: pepolar_<<session>>}`` in your bidsmap metadata, then your actual output metadata in your ``ses-01`` subfolder will be ``{B0FieldIdentifier: pepolar_01}`` and in your ``ses-02`` subfolder it will be ``{B0FieldIdentifier: pepolar_02}``. Here is an example with a single fieldmap and three subsequent functional runs that was interrupted after two runs and re-scanned, with ``mytag<<session:[0:3]>>`` as B0FieldIdentifier/Source value::

    |-- fmap
    |   |-- sub-001_ses-01_run-1_magnitude1.json      <- {B0FieldIdentifier: mytag<<ses01_1>>}  (SeriesNumber = 01)
    |   |-- sub-001_ses-01_run-1_magnitude2.json      <- {B0FieldIdentifier: mytag<<ses01_1>>}  (SeriesNumber = 01)
    |   |-- sub-001_ses-01_run-1_phasediff.json       <- {B0FieldIdentifier: mytag<<ses01_1>>}  (SeriesNumber = 01)
    |   |-- sub-001_ses-01_run-2_magnitude1.json      <- {B0FieldIdentifier: mytag<<ses01_2>>}  (SeriesNumber = 08)
    |   |-- sub-001_ses-01_run-2_magnitude2.json      <- {B0FieldIdentifier: mytag<<ses01_2>>}  (SeriesNumber = 08)
    |   `-- sub-001_ses-01_run-2_phasediff.json       <- {B0FieldIdentifier: mytag<<ses01_2>>}  (SeriesNumber = 08)
    |
    `-- func
        |-- sub-001_ses-01_task-rest_run-1_bold.json  <- {B0FieldSource: mytag<<ses01_1>>}      (SeriesNumber = 02)
        |-- sub-001_ses-01_task-rest_run-2_bold.json  <- {B0FieldSource: mytag<<ses01_1>>}      (SeriesNumber = 03)
        |-- sub-001_ses-01_task-rest_run-3_bold.json  <- {B0FieldSource: mytag<<ses01_2>>}      (SeriesNumber = 09)
        |-- sub-001_ses-01_task-rest_run-4_bold.json  <- {B0FieldSource: mytag<<ses01_2>>}      (SeriesNumber = 10)
        `-- sub-001_ses-01_task-rest_run-5_bold.json  <- {B0FieldSource: mytag<<ses01_2>>}      (SeriesNumber = 11)

.. note::
   The ``IntendedFor`` field is a legacy way to deal with field maps. Instead, it is recommended to use the ``B0FieldIdentifier`` and ``B0FieldSource`` fields that were introduced with BIDS 1.7, or use both. If you neither specify IntendedFor nor B0FieldIdentifier/Source values then your fieldmaps are most likely not going to be used by any BIDS application

BIDS value lists
^^^^^^^^^^^^^^^^
Instead of a normal string, a bids dictionary value can also be a list of strings, with the last list item being the (zero-based) list index that selects the actual value from the list. For instance the list ``{part: ['', 'mag', 'phase', 'real', 'imag', 2]}`` would select 'phase' as the value belonging to 'part'. A bids value list is represented in the bidseditor as a drop-down menu in which the user can choose between the values (i.e. set the list index).

Building your own template bidsmap
----------------------------------

The run-items in the default 'bidsmap_dccn' template bidsmap have values that are tailored to MRI acquisitions in the Donders Institute. Hence, if you are using different protocol parameters that do not match with these template values or you are using e.g. filenames instead of header information to typify your data, then your runs will initially be data (mis)typed by the bidsmapper as miscellaneous 'extra_data' -- which you then need to correct afterwards yourself. To improve that initial data typing and further automate your workflow, you may consider creating your own customized template bidsmap. Here are some things to keep in mind when building your own template bidsmap:

- To get the correct match for every source data type, run-items of template (but not study) bidsmaps typically contain regular expressions in their property and/or in attribute values. These regular expressions should best be designed to broadly but uniquely match the values in the source data, i.e. they should match with all variations of the same source data type, but never match with any other source data type. The expressions can be considered as prior knowledge about the data, and can be dependent on your data acquisition protocol.

- When matching a data sample to run-items in a bidsmap, the search order is such that data samples will first be matched to the 'exclude' run-items, then, if they don't match, to the BIDS run-items (the items in 'fmap', 'anat', 'func', etc) and finally, if none of those match either, to the 'extra_data' run-items. The search order for the list of run-items within each BIDS datatype is from top to bottom. The search order can play a role (and can be exploited) if you have run-items that are very similar, i.e. have (partly) overlapping properties or attributes. You can use this to your advantage by placing certain run-items before others. For instance, if you are adding run-items for multi-band EPI pulse sequences, you may want to put your 'SBREF' run-item before your 'MB' run-item and put a minor extra property and/or attribute that is unique to the additionally acquired single-band reference image. So if the SeriesDescription is "task_fMRI" for the MB sequence and "task_fMRISBREF" for the SBREF sequence, then you can have ``{SeriesDescription: .*fMRI.*}`` for the MB run-item while narrowing down the matching pattern of the SBREF to ``{SeriesDescription: .*fMRISBREF.*}``. MB data samples will not match the latter pattern but will match with the MB run-item. SBREF samples will match with both run-items, but only the SBREF run-item will be copied over to the study bidsmap because it is encountered before the MB run-item (BIDScoin stops searching the bidsmap if it finds a match).

- In your template bidsmap you can populate your run-items with any set of ``properties`` and/or ``attributes``. For instance if in your center you are using the "PerformedProcedureStepDescription" DICOM attribute instead of "SeriesDescription" to store your metadata then you can (probably should) include that attribute to get more successful matches for your run-items. What you should **not** include there are properties or attributes that vary between repeats of the same acquisition, e.g. the DICOM 'AcquisitionTime' attribute (that makes every data sample unique and will hence give you a very long list of mostly redundant run-items in your study bidsmap). It is however perfectly fine to use such varying properties or attributes in dynamic values of the ``bids`` and ``meta`` run-item dictionaries (see below).

- Single dynamic brackets containing source properties or attributes can be used in the bids and meta dictionary, to have them show up in the bidseditor as pre-filled proposals for BIDS labels and/or sidecar meta data values. For instance, if you put ``{ContrastName: <ContrastAgent>}`` in a meta-dictionary in your template bidsmap, it will show up in the bidseditor GUI as ``{ContrastName: PureGadolinium}``. Double dynamic brackets can also be used, but these remain unevaluated until bidscoiner runtime. Double brackets are therefore only needed when the property or attribute value varies from subject to subject (such as "<<Age>>") or from acquisition to acquisition (such as "<<InjectedMass>>").

- Finally, it is a good practice for the first run-item in each BIDS datatype section of your template bidsmap to have all empty `properties` and `attributes` values. The benefit of this is that you can dereference ('copy') it in other run-items (see the editing section below), and in this way improve your consistency and reduce the maintenance burden of keeping your template bidsmap up-to-date. The first run-item is also the item that is selected when a user manually sets the run-item to this BIDS datatype in the bidseditor GUI.

.. tip::
   - Make a copy of the DCCN template (``[home]/.bidscoin/[version]/templates/bidsmap_dccn.yaml``) as a starting point for your own template bidsmap, and adapt it to your needs. You can set your copy as the new default template by editing the ``[home]/.bidscoin/config.toml`` file. Default templates and config file are automatically recreated from source when deleted
   - The power of regular expressions is nearly unlimited, you can e.g. use `negative look aheads <https://docs.python.org/3/howto/regex.html#lookahead-assertions>`__ to **not** match (exclude) certain strings
   - When creating new run-items, make sure to adhere to the YAML format and to the definitions in the BIDS schema files (``[path_to_bidscoin]/bidscoin/schema/datatypes``). You can test your YAML syntax using an online `YAML-validator <https://www.yamllint.com>`__ and your compliance with the BIDS standard with ``bidscoin -t your_template_bidsmap``. If all seems well you can install it using ``bidscoin -i your_template_bidsmap``.
   - In addition to DICOM attribute names, the more advanced / unambiguous pydicom-style `tag numbers <https://pydicom.github.io/pydicom/stable/old/base_element.html#tag>`__ can also be used for indexing a DICOM header. For instance, the ``PatientName``, ``0x00100010``, ``0x10,0x10``, ``(0x10, 0x10)``, and ``(0010, 0010)`` index keys are all equivalent.

Editing the template bidsmap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. **Using the bidseditor**. While this is certainly not recommended for most use cases (as it may break), the easiest (quick and dirty) way to create a bidsmap template is to use the bidseditor GUI. If you have a run item in your study bidsmap that you would like to be automatically mapped in other / future studies you can simply append that run to any template bidsmap by using the [Export] button in the GUI (see screenshot below). However, as explained above, before you do that you should always clear the attribute values (e.g. 'EchoTime') that vary across repeats of the same or similar acquisitions. If you want to make the run-item more generic, note that you can still use regular expressions as ``properties`` and ``attributes`` matching patterns. Instead of exporting to a template bidsmap, you can also open (and edit) the template bidsmap itself with the bidseditor. An important limitation of exporting run items is that they are appended to a bidsmap template, meaning that they are last in line (for that datatype) when the bidsmapper searches for a matching run-item. Another limitation is that with the GUI you cannot make use of YAML anchors and references, giving you a less clearly formatted bidsmap that is harder to maintain. Both limitations are overcome when directly editing the template bidsmap yourself using a text editor.

2. **Using a text editor**. The advised way to create or modify template bidsmaps is to use a text editor and edit the raw bidsmap data directly. The bidsmap data is stored in `YAML <http://yaml.org/>`__ format, so you do have to have some basic understanding of this data-serialization language. As can be seen from the template snippet below, YAML format is quite human-friendly and human-readable, but there are a few things you should be aware of, most notably the use of `anchors and aliases <https://blog.daemonl.com/2016/02/yaml.html>`__. The DCCN template bidsmap uses anchors in the first run-item of a BIDS datatype, and aliases in the others (to dereference the content of the anchors). And because all values of the ``properties`` and ``attributes`` dictionary are empty, in the other run-items all you have to declare are the (non-empty) key-value pairs that you want to use for matching your source data types.

.. code-block:: yaml

   anat:       # ----------------------- All anatomical runs --------------------

   - provenance:                    # The fullpath name of the DICOM file from which the attributes are read. Serves also as a look-up key to find a run in the bidsmap
     properties: &fileattr          # This is an optional (stub) entry of filesystem matching (could be added to any run-item)
       filepath:                    # File folder, e.g. ".*Parkinson.*" or ".*(phantom|bottle).*"
       filename:                    # File name, e.g. ".*fmap.*" or ".*(fmap|field.?map|B0.?map).*"
       filesize:                    # File size, e.g. "2[4-6]\d MB" for matching files between 240-269 MB
       nrfiles:                     # Number of files in the folder that match the above criteria, e.g. "5/d/d" for matching a number between 500-599
     attributes: &anat_dicomattr    # An empty / non-matching "reference" dictionary that can be dereferenced in other run-items of this data type
       Modality:
       ProtocolName:
       SeriesDescription:
       ImageType:
       SequenceName:
       SequenceVariant:
       ScanningSequence:
       MRAcquisitionType:
       SliceThickness:
       FlipAngle:
       EchoNumbers:
       EchoTime:
       RepetitionTime:
       InPlanePhaseEncodingDirection:
     bids: &anat_dicoment_nonparametric  # See: schema/datatypes/anat.yaml
       acq: <SeriesDescription>     # This will be expanded by the bidsmapper (so the user can edit it in the bidseditor)
       ce:
       rec:
       run: <<>>                   # This will be updated dynamically during bidscoiner runtime (as it depends on the already existing files)
       part: ['', 'mag', 'phase', 'real', 'imag', 0]    # This BIDS value list will be shown as a dropdown menu in the bidseditor with the first (empty) item selected (as indicated by the last item, i.e. 0)
       suffix: T1w
     meta:                          # This is an optional entry for meta-data that will be appended to the json sidecar files produced by dcm2niix

   - provenance:
     properties:
       <<: *fileattr
       nrfiles: [1-3]/d/d           # Number of files in the folder that match the above criteria, e.g. "5/d/d" for matching a number between 500-599
     attributes:
       <<: *anat_dicomattr
       ProtocolName: '(?i).*(MPRAGE|T1w).*'
       MRAcquisitionType: '3D'
     bids: *anat_dicoment_nonparametric
     meta:
       Comments: <<ImageComments>>  # This will be expanded dynamically during bidscoiner runtime (as it may vary from session to session)

   - provenance:
     attributes:
       <<: *anat_dicomattr
       ProtocolName: '(?i).*T2w.*'
       SequenceVariant: '[''SK'', ''SP'']'       # NB: Uses a yaml single-quote escape
     bids:
       <<: *anat_dicoment_nonparametric
       suffix: T2w

*Snippet derived from the bidsmap_dccn template, showing a "DICOM" section with a void "anat" run-item and two normal run-items that dereference the first run-item* (e.g. the ``&anatattributes_dicom`` anchor is dereferenced with the ``<<: *anatattributes_dicom`` alias)
