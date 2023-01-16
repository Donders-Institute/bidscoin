The bidsmap explained
=====================

Structure and content
---------------------

A central concept in BIDScoin is the so-called bidsmap. Generally speaking, a bidsmap is a collection of run-items that define how source data types (e.g. a T1w- or a T2w-scan) should be converted to `BIDS data types <https://bids-specification.readthedocs.io/en/stable/02-common-principles.html#definitions>`__. As illustrated in the figure below (but see also the screenshot of the `edit window <screenshots.html>`__), run-items consist of a 'provenance' field and a 'properties', 'attributes', 'bids' and a 'meta' `dictionary <https://en.wikipedia.org/wiki/Associative_array>`__ (a set of key-value pairs):

1. **The provenance field** contains the pathname of a source data sample that is representative for the run-item. The provenance data is not strictly necessary but very useful for deeper inspection of the source data and for tracing back the conversion process, e.g. in case of encountering unexpected results
2. **The properties dictionary** contains file system properties of the data sample, i.e. the file path, the file name, the file size on disk and the number of files in the containing folder. Depending on your data management, this information allows or can help to identify different datatypes in your source data repository
3. **The attributes dictionary** contains attributes from the source data itself, such as the 'ProtocolName' from the DICOM header. The source attributes are a very rich source of information of which a minimal subset is normally sufficient to identify the different datatypes in your source data repository. The attributes are read from (the header of) the source file itself or, if present, from an accompanying sidecar file. This sidecar file transparently extends the available source attributes and should have the same filename as the first associated source file. For instance, the ``001.dcm``, ``002.dcm``, ``003.dcm``, [..], DICOM source images can have a sidecar file in the same directory named ``001.json`` (e.g. containing metadata that is not available in the DICOM header or that must be overruled). It should be noteed that BIDScoin `plugins <plugins.html>`__ will copy the extended attribute data over to the json sidecar files in your BIDS output folder, giving you additional control to generate your BIDS sidecar files (in addition to the meta dictionary described in point 5 below).
4. **The bids dictionary** contains the BIDS datatype and entities that determine the filename of the BIDS output data. The values in this dictionary are encouraged to be edited by the user
5. **The meta dictionary** contains custom key-value pairs that are added to the json sidecar file by the BIDScoin plugins. Meta data may well vary from session to session, hence this dictionary often contains dynamic attribute values that are evaluated during bidscoiner runtime (see the `special features <#special-bidsmap-features>`__ below)

In sum, a run-item contains a single bids-mapping, which links the input dictionaries (2) and (3) to the output dictionaries (4) and (5).

.. figure:: ./_static/bidsmap_sample.png

   A snippet of study bidsmap in YAML format. The bidsmap contains separate sections for each source data format (here 'DICOM') and sub-sections for the BIDS datatypes (here 'anat'). The arrow illustrates how the 'properties' and 'attributes' input dictionaries are mapped onto the 'bids' and 'meta' output dictionaries. Note that the 'part' value in the bids dictionary is a list, which is presented in the bidseditor GUI as a drop-down menu (with the first empty item being selected). Also note the special double bracket dynamic values (<<..>>), which are explained `below <#special-bidsmap-features>`__.

At the root level, a bidsmap is hierarchically organized in data format sections, such as 'DICOM' and 'PAR', which in turn contain subsections for the 'participant_label' and 'session_label', and subsections for the BIDS datatypes (such as 'fmap', 'anat', 'func') and for the 'exclude' and 'extra_data' datatypes. The 'exclude' datatype contains run-items for source data that need to be omitted when converting the source data to BIDS and the 'extra_data' datatype contains run-items for including miscellaneous data that is not (yet) defined in the BIDS specifications.
The particpicant- and session-label subsections contain key-value pairs for setting the BIDS subject and session labels. Next to the data format sections there is a general 'Options' section, that accommodates BIDScoin and plugin settings.

When BIDScoin workflow routines process source data, they will scan the entire repository and take samples of the data and compare them with the run-items in the bidsmap until they come across a run-item of which all (non-empty) properties and attribute values match (using `fullmatch <https://docs.python.org/3/library/re.html>`__) with the values extracted from the data sample at hand. At that point a run-item match is established, i.e. BIDScoin then knows precisely how to convert the data sample to BIDS. Bidsmaps can contain an unlimited number of run-items, including multiple run-items mapping onto the same BIDS target (e.g. when you renamed your DICOM scan protocol halfway your study and you don't want that irrelevant change to be reflected in the BIDS output).

From template to study bidsmap
------------------------------

In BIDScoin a bidsmap can either be a template bidsmap or a study bidsmap. A template bidsmap contains a comprehensive set of run-items (one run-item for each BIDS target), each of which containing the prior knowledge about the source data properties and attributes that typically belong to a BIDS target. A study bidsmap, on the other hand, contains only run-items that matched positively with the source data of a study, i.e. it represents all the source data types present in the study (but nothing more). Moreover, this shortlist of run-items can be edited by the user (adding the posterior knowledge) to get the optimal mapping to BIDS for the data at hand. In the workflow (see figure below), the bidsmapper takes the template bidsmap and source data as input to automatically produce a first version of a study bidsmap. The runs in this study bidsmap are taken from the template bidsmap, with the difference that all attribute values of the matching run-item (including empty values and values with regular expressions) are replaced with the attribute values of the data samples. In this way, the run-items will uniquely match to the data samples, providing a complete mapping of all source data types to BIDS data types. These mappings can be edited by the user with the bidsedsitor and then given to the bidscoiner to do the actual conversion of the source data to BIDS.

Users normally don't have to know about or interact with the template bidsmap, and only see study bidsmaps (in the bidseditor). To have a fully automated workflow, users with a very good template bidsmap and standardized data acquisition protocol can rely on the automated mappings and skip the bidseditor step (and hence don't see the study bidsmap). In fact, it is then even possible (but certainly not recommended) to skip the bidsmapping step and pass the template bidsmap directly to the bidscoiner (for this to work you need to be sure beforehand that all source datatypes have matching run-items in the template bidsmap).

.. figure:: ./_static/bidsmap_flow.png

   Creation and application of a study bidsmap

Special bidsmap features
------------------------

The dictionary values in a bidsmap are not simple strings but have some special features that make BIDScoin powerful, flexible and helpful:

* **Run-item matching**. Source property and attribute values of run-items in a bidsmap are interpreted as `regular expression patterns <https://docs.python.org/3/library/re.html>`__ when they are matched with your source data samples. For instance, a key-value pair of an attribute dictionary in your template bidsmap could be ``{ProtocolName: .*(mprage|T1w).*}``, which would test if the extracted attribute string for 'ProtocolName' from the `DICOM header <https://www.dicomstandard.org>`__ of a data sample contains either a 'mprage' or a 'T1w' substring. More precisely, the Python expression that is evaluated is: ``match = re.fullmatch('.*(mprage|T1w).*', 't1_mprage_sag_p2_iso_1.0')``) if the ProtocolName of the data sample is 't1_mprage_sag_p2_iso_1.0'.

* **Dynamic values**. Dictionary values can be static, in which case the value is just a normal string, or dynamic, when the string is enclosed with single or double pointy brackets. In case of single pointy brackets the bids value will be replaced during bidsmapper, bidseditor and bidscoiner runtime by the value of the source attribute or property of the data sample at hand. It is also possible to then extract a substring from the source string by adding a colon-separated regular expression to the bids value. For instance the two dynamic values in ``{acq: <MRAcquisitionType>Demo<SeriesDescription:t1_(.*?)_sag>}`` will be replaced by ``{acq: 3DDemoMPRAGE}`` if the 'MRAcquisitionType' of the data sample is '3D' and 'SeriesDescription' is 't1_MPRAGE_sag_p2_iso_1.0'. More precisely, the Python expression that is evaluated for the second  dynamic 'SeriesDescription' value is: ``substring = re.findall('t1_(.*?)_sag', 't1_mprage_sag_p2_iso_1.0')``. If dynamic values are enclosed with double pointy brackets, the only difference is that they will be replaced only during bidscoiner runtime -- this is useful for bids values that are subject/session dependent. Double bracket dynamic values can for instance be used to add DICOM meta data that is not saved by default in the json sidecar files, such as <<ImageComments>> or <<RadionuclideTotalDose>>. Another example is the extraction of the subject and session label. For instance, you can use ``<<filepath:/sub-(.*?)/>>`` to extract '003' (i.e. the shortest string between ``/sub-`` and ``/``) if the data for that subject is in ``/data/raw/sub-003/ses-01``. Alternatively, if the subject label is encoded in the DICOM ``PatientName`` as e.g. ``ID_003_anon``, then ``<<PatientName:ID_(.*?)_>>`` would likewise extract '003'. To test out dynamic values (either with or without appended regular expressions), you can handily enter them in the bidseditor within single brackets to instantly obtain their resulting value.

* **Run-index**. Dynamic values can handle many use cases and can be used throughout BIDScoin. Yet there are two exceptions that cannot always be handled directly with dynamic values. The first exception is the 'run'-index in the bids output dictionary, since this index number cannot usually be determined from the data file alone. In that case, if the run-index is a dynamic number (e.g. ``{run: <<1>>}``) and another output file with that run-index already exists, then during bidscoiner runtime this number will be incremented in compliance with the BIDS standard (e.g. to ``{run: 2}``). If the run index is encoded in the header or filename, then the index can unambiguously be extracted using dynamic values. For instance, using ``{run: <<ProtocolName:run-(.*?)_>>}`` will give ``{run: 3}`` if the DICOM ProtocolName is ``t1_mprage_sag_run-3_iso_1.0``.

* **IntendedFor**. The other exception not covered by dynamic values is the 'IntendedFor' value in the meta dictionary of fieldmaps. The IntendedFor value is a list of associated output files that you can specify within a dynamic value using Unix shell-style wildcards. In that way, the bidscoiner will lookup the path of these images on disk using the Python `glob(*dynamic_value*) <https://docs.python.org/3.8/library/pathlib.html#pathlib.Path.glob>`__ expression. For instance, using a simple ``{IntendedFor: <<task>>}`` value will lookup all functional runs in the BIDS subject[/session] folder (since in BIDS these runs always have 'task' in their filename), whereas a more specific ``{IntendedFor: <<func/*Stop*Go_bold><func/*Reward*_bold>>}`` value will select all 'Stop1Go'-, 'Stop2Go'- and 'Reward' bold-runs in the func sub-folder. In case duplicated fieldmaps are acquired (e.g. when a scan failed or a session was interrupted) you can limit the search scope by appending a colon-separated "bounding" term to the search pattern. E.g. ``{IntendedFor: <<task:[]>>}`` will bound the wildcard search to files that are 'uninterruptedly connected' to the current fieldmap, i.e. without there being another run of the fieldmap in between. The bounded search can be further constrained by limiting the maximum number of matches, indicated with lower and upper limits. For instance ``{IntendedFor: <<task:[-3:0]>>}`` will limit the bounded search to maximally three runs preceding the fieldmap. Similarly, ``{IntendedFor: <<task:[-2:2]>>}`` will limit the bounded search to maximally two preceding and two subsequent runs, and ``{IntendedFor: <<task:[0:]>>}`` will limit the bounded search to all matches acquired after the fieldmap. In this latter case, for the first fieldmap, only ``task-Stop_run-1`` and ``task-Stop_run-2`` will match the bounded search if the 5 collected runs were named: 1) ``fieldmap_run-1``, 2) ``task-Stop_run-1``, 3) ``task-Stop_run-2``, 4) ``fieldmap_run-2``, 5) ``task-Stop_run-3``. The second run of the fieldmap will match with ``task-Stop_run-3`` only (note that the second fieldmap would have matched all task runs if the bounding term would have been ``[]``, ``[:]`` or ``[-2:2]``).

.. note::

   The ``IntendedFor`` field is a legacy way to deal with fieldmaps. Instead, it is recommended to use the ``B0FieldIdentifier`` and ``B0FieldSource`` fields that were `introduced with BIDS 1.7 <https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#using-b0fieldidentifier-metadata>`__

* **BIDS value lists**. Instead of a normal string, a bids dictionary value can also be a list of strings, with the last list item being the (zero-based) list index that selects the actual value from the list. For instance the list ``{part: ['', 'mag', 'phase', 'real', 'imag', 2]}`` would select 'phase' as the value belonging to 'part'. A bids value list is made visible in the bidseditor as a drop-down menu in which the user can select the value (i.e. set the list index).

.. tip::

   In addition to DICOM attribute names, the more advanced / unambiguous pydicom-style `tag numbers <https://pydicom.github.io/pydicom/stable/old/base_element.html#tag>`__ can also be used for indexing a DICOM header. For instance, the ``PatientName``, ``0x00100010``, ``0x10,0x10``, ``(0x10, 0x10)``, and ``(0010, 0010)`` index keys are all equivalent.

Building your own template bidsmap
----------------------------------

The run-items in the default 'bidsmap_dccn' template bidsmap have source dictionary values that are tailored to MRI acquisitions in the Donders Institute. Hence, if you are using different protocol parameters that do not match with these template values, then your runs will initially be data (mis)typed by the bidsmapper as miscellaneous 'extra_data' -- which you then need to correct afterwards yourself. To improve that initial data typing and further automate your workflow, you may consider creating your own customized template bidsmap.

When creating a template bidsmap, keep in mind that a data sample will first be matched to the 'exclude' run-items, then, if they don't match, to the BIDS run-items (the items in 'fmap', 'anat', 'func', etc) and finally, if none of those match either, to the 'extra_data' run-items.

.. tip::
   Make a copy of the DCCN template (``[path_to_bidscoin]/heuristics/bidsmap_dccn.yaml``) as a starting point for your own template bidsmap, and adapt it to your environment. You can test your bidsmap with ``bidscoin -t`` and install it with ``bidscoin -i``

.. note::
   If you want to use different source attributes than the default set to identify source data types, then beware that the attribute values should not vary between different repeats of the data acquision. Otherwise the number of run-items in the bidsmap will not be a unique shortlist of the acquisition protocols in your study, but will instead become a lengthy list that is proportional to the number of subjects and sessions.

Editing the template bidsmap
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. **Using the bidseditor**. While this is certainly not recommended for most use cases, the easiest (quick and dirty) way to create a bidsmap template is to use the bidseditor GUI. If you have a run item in your study that you would like to be automatically mapped in other / future studies you can simply append that run to the standard or to a custom template bidsmap by editing it to your needs and click the [Export] button (see below). Note that you should first clear the attribute values (e.g. 'EchoTime') that vary across repeats of the same or similar acquisitions. You can still add advanced features, such as `regular expression patterns <https://docs.python.org/3/library/re.html>`__ for the attribute values. You can also open the template bidsmap itself with the bidseditor and edit it directly. The main limitation of using the GUI is that the run items are simply appended to a bidsmap template, meaning that they are last in line (for that datatype) when the bidsmapper tries to find a matching run-item. Another limitation is that with the GUI you cannot make usage of YAML anchors and references, yielding a less clearly formatted bidsmap that is harder to maintain. Both limitations are overcome when directly editing the template bidsmap yourself using a text editor (see next point).

.. figure:: ./_static/bidseditor_edit_tooltip.png

   The edit window with the option to export the customized mapping of run a item, and featuring properties matching and dynamic meta-data values

2. **Using a text editor**. This is the adviced and most powerful way to create or modify a bidsmap template but requires more knowledge of `YAML <http://yaml.org/>`__ and more `understanding of bidsmaps <bidsmap.html>`__. To organise and empower your template you can take the DCCN template bidsmap (``[path_to_bidscoin]/heuristics/bidsmap_dccn.yaml``) as an example and work from there. If you open that template with a text editor, there are a few handy things to take notice of (as shown in the template snippet below). First, you can see that the DCCN template makes use of YAML `anchors and aliases <https://blog.daemonl.com/2016/02/yaml.html>`__ (to make maintanance more sustainable). The second thing to notice is that, of the first run, all values of the attribute dictionary are empty, meaning that it won't match any run-item. In that way, however, the subsequent runs that dereference (e.g. with ``<<: *anatattributes_dicom``) this anchor (e.g. ``&anatattributes_dicom``) will inherit only the keys and can inject their own values, as shown in the second run. The first run of each modality sub-section (like ``anat``) also serves as the default bidsmapping when users manually overrule / change the bids modality using the `bidseditor <workflow.html#step-1b-running-the-bidseditor>`__ GUI.

.. tip::
   - For each datatype, the list of run-items are matched from top to bottom. You can use this to your advantage by placing certain run-items above others
   - The power of regular expressions is nearly unlimited, you can e.g. use `negative look aheads <https://docs.python.org/3/howto/regex.html#lookahead-assertions>`__ to **not** match (exclude) certain strings
   - Use more attributes for more selective run-item matching. For instance, to distinguish an equally named SBRef DWI scan from the normal DWI scans, you can add ``DiffusionDirectionality: NONE`` to your attribute dictionary
   - When creating new run-items, make sure to adhere to the format defined in the BIDS schema files (``[path_to_bidscoin]/bidscoin/schema/datatypes``).

.. code-block:: yaml

   anat:       # ----------------------- All anatomical runs --------------------
   - provenance:                    # The fullpath name of the DICOM file from which the attributes are read. Serves also as a look-up key to find a run in the bidsmap
     properties: &fileattr          # This is an optional (stub) entry of filesystem matching (could be added to any run-item)
       filepath:                    # File folder, e.g. ".*Parkinson.*" or ".*(phantom|bottle).*"
       filename:                    # File name, e.g. ".*fmap.*" or ".*(fmap|field.?map|B0.?map).*"
       filesize:                    # File size, e.g. "2[4-6]\d MB" for matching files between 240-269 MB
       nrfiles:                     # Number of files in the folder that match the above criteria, e.g. "5/d/d" for matching a number between 500-599
     attributes: &anat_dicomattr    # An empty / non-matching reference dictionary that can be derefenced in other run-items of this data type
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
       run: <<1>>                   # This will be updated dynamically during bidscoiner runtime (as it depends on the already existing files)
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

*Snippet derived from the bidsmap_dccn template, showing a `DICOM` section with a void `anat` run-item and two normal run-items that dereference from the void item*
