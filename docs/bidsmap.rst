The bidsmap explained
=====================

Structure and content
---------------------

A central concept in BIDScoin is the so-called bidsmap. Generally speaking, a bidsmap is a collection of run-items that define how source data types (e.g. a T1w- or a T2w-scan) should be converted to `BIDS data types <https://bids-specification.readthedocs.io/en/stable/02-common-principles.html#definitions>`__. As illustrated in the figure below (but see also the screenshot of the `edit window <screenshots.html>`__), run-items consist of a ``provenance`` field and a ``properties``, ``attributes``, ``bids`` and a ``meta`` `dictionary <https://en.wikipedia.org/wiki/Associative_array>`__ (a set of key-value pairs):

1. The provenance field contains the pathname of a source data sample that is representative for the run-item. The provenance data is not strictly necessary but very useful for deeper inspection of the source data and for tracing back the conversion process, e.g. in case of encountering unexpected results
2. The properties dictionary contains file system properties of the data sample, i.e. the file path, the file name, the file size on disk and the number of files in the containing folder. Depending on your data management, this information allows or can help to identify different datatypes in your source data repository
3. The attributes dictionary contains attributes from the source data itself, such as the 'ProtocolName' from the DICOM header. The source attributes are a very rich source of information of which a minimal subset is normally sufficient to identify the different datatypes in your source data repository
4. The bids dictionary contains the BIDS datatype and entities that determine the filename of the BIDS output data. The values in this dictionary are encouraged to be edited by the user
5. The meta dictionary contains custom key-value pairs that are added to the json sidecar file by the BIDScoin plugins. Meta data may well vary from session to session, hence this dictionary often contains dynamic attribute values that are evaluated during bidscoiner runtime (see the `special features <#special-bidsmap-features>`__ below)

In sum, a run-item contains a single bids-mapping, which links the input dictionaries (2) and (3) to the output dictionaries (4) and (5).

.. figure:: ./_static/bidsmap_sample.png

   A snippet of study bidsmap in YAML format. The bidsmap contains separate sections for each source data format (here ``DICOM``) and sub-sections for the BIDS datatypes (here ``anat``). The arrow illustrates how the ``properties`` and ``attributes`` input dictionaries are mapped onto the ``bids`` and ``meta`` output dictionaries. Note that the `part` value in the bids dictionary is a list, which is presented in the bidseditor GUI as a drop-down menu (with the first empty item being selected). Also note the special double bracket dynamic values (<<1>> and <<PatientComments>>), which are explained later below.

At the root level, a bidsmap is hierarchically organised in ``DICOM`` and ``PAR`` data format sections, which in turn contain subsections for the``participant_label`` and ``session_label``, subsections for the BIDS datatypes (``fmap``, ``anat``, ``func``, ``perf``, ``dwi``, ``pet``, ``meg``, ``eeg``, ``ieeg``, ``beh``) and for the ``extra_data`` and ``exclude`` datatypes. The particpicant- and session-label subsections are common to all run-items and contain key-value pairs that identify the subject and session labels. The datatype subsections contain the actual run-items. Next to the data format sections there is a general ``Options`` section, that accommodates BIDScoin and plugin settings.

When BIDScoin routines process source data, they will scan the entire repository and take samples of the data and compare them with the run-items in the bidsmap until they come across a run-item of which all (non-empty) properties and attribute values match (explained further `below <#special-bidsmap-features>`__) with the values extracted from the data sample at hand. At that point a bidsmapping is established. Within a datatype, run-items are matched from top to bottom, and scan order between datatypes is 'exclude', 'fmap', 'anat', 'func', 'perf', 'dwi', 'pet', 'meg', 'eeg', 'ieeg', 'beh' and 'extra_data'. The 'exclude' datatype contains run-items for source data that need to be omitted when converting the source data to BIDS and the 'extra_data' datatype contains run-items for including miscellaneous data that is not (yet) defined in the BIDS specifications. Bidsmaps can contain an unlimited number of run-items, including multiple run-items mapping onto the same BIDS target (e.g. when you renamed your DICOM scan protocol halfway your study and you don't want that irrelevant change to be reflected in the BIDS output).

From template to study
----------------------

In BIDScoin a bidsmap can either be a template bidsmap or a study bidsmap. The difference between the two is that a template bidsmap is a comprehensive set of pre-defined run-items and serves as an input for the bidsmapper (see below) to automatically generate a first instantiation of a study bidsmap, containing just the matched run-items. Empty attribute values of the matched run-item will be expanded with values from the data sample, making the run-item much more specific and sensitive to small changes in the scan protocol. Users normally don't have to know about or interact with the template bidsmap, but they can create their own `customized template <advanced.html#customized-template-bidsmap>`__. The study bidsmap can be interactively edited by the bidseditor before feeding it to the bidscoiner, but it is also possible (but not recommended) to skip the editing step and convert the data without any user interaction.

.. figure:: ./_static/bidsmap_flow.png

   Creation and application of a study bidsmap

Special bidsmap features
------------------------

The dictionary values in a bidsmap are not simple strings but have some special features that make BIDScoin powerful, flexible and helpful:

* **Source matching**. Source property and attribute values are `regular expression patterns <https://docs.python.org/3/library/re.html>`__ to  run matching. For instance you can use ``SeriesDescription: '.*MPRAGE.*'`` to match all MPRAGE DICOM series as they come from your MRI scanner. This feature is useful for template bidsmaps.

* **Dynamic values**. Dictionary values can be static, in which case the value is just a normal string, or dynamic, when the string is enclosed with pointy brackets. In case of single pointy brackets the bids value will be replaced / expanded during bidsmapper, bidseditor and bidscoiner runtime by the value of the source attribute. For instance ``acq: <MRAcquisitionType><SeriesDescription>`` will be replaced by ``acq: 3DMPRAGE``. In case of double enclosed pointy brackets, the value will be replaced only during bidscoiner runtime -- this is useful for bids values that are subject/session dependent. For instance ``run: <<1>>`` will be replaced with ``run: 1`` or e.g. increased to ``run: 2`` if a file for that subject with that bidsname already exists. Dynamic values are also useful for meta data that is subject or session specific, such <<ImageComments>> or <<RadionuclideTotalDose>>, but not saved by default in the json sidecar files.

* **Bids value lists**. Instead of a normal string, a bids dictionary value can also be a list of strings, with the last list item being the (zero-based) list index that selects the actual value from the list. For instance the list ``part: ['', 'mag', 'phase', 'real', 'imag', 2]`` would select 'phase' as the value belonging to 'part'. A bids value list is made visible in the bidseditor as a drop-down menu in which the user can select the value (i.e. set the list index).
