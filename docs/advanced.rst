Advanced usage
==============

Customized template bidsmap
---------------------------

 The run-items in the default 'bidsmap_dccn' template bidsmap have source dictionary values that are tailored to MRI acquisitions in the Donders Institute. Hence, if you are using different protocol parameters that do not match with these template values, then your runs will initially be data (mis)typed by the bidsmapper as miscellaneous 'extra_data' -- which you then need to correct afterwards yourself. To improve that initial data typing and further automate your workflow, you may consider creating your own customized template bidsmap.

.. tip::
   Make a copy of the DCCN template (``[path_to_bidscoin]/heuristics/bidsmap_dccn.yaml``) as a starting point for your own template bidsmap, and adapt it to your environment. You can test your bidsmap with ``bidscoin -t`` and install it with ``bidscoin -i``

.. note::
   If you want to use different source attributes than the default set to identify source data types, then beware that the attribute values should not vary between different repeats of the data acquision. Otherwise the number of run-items in the bidsmap will not be a unique shortlist of the acquisition protocols in your study, but will instead become a lengthy list that is proportional to the number of subjects and sessions.

Editing the template
^^^^^^^^^^^^^^^^^^^^

1. **Using the bidseditor**. While this is certainly not recommended for most use cases, the easiest (quick and dirty) way to create a bidsmap template is to use the bidseditor GUI. If you have a run item in your study that you would like to be automatically mapped in other / future studies you can simply append that run to the standard or to a custom template bidsmap by editing it to your needs and click the [Export] button (see below). Note that you should first clear the attribute values (e.g. 'EchoTime') that vary across repeats of the same or similar acquisitions. You can still add advanced features, such as `regular expression patterns <https://docs.python.org/3/library/re.html>`__ for the attribute values. You can also open the template bidsmap itself with the bidseditor and edit it directly. The main limitation of using the GUI is that the run items are simply appended to a bidsmap template, meaning that they are last in line (for that datatype) when the bidsmapper tries to find a matching run-item. Another limitation is that with the GUI you cannot make usage of YAML anchors and references, yielding a less clearly formatted bidsmap that is harder to maintain. Both limitations are overcome when directly editing the template bidsmap yourself using a text editor (see next point).

.. figure:: ./_static/bidseditor_edit_tooltip.png

   The edit window with the option to export the customized mapping of run a item, and featuring properties matching and dynamic meta-data values

2. **Using a text editor**. This is the adviced and most powerful way to create or modify a bidsmap template but requires more knowledge of `YAML <http://yaml.org/>`__ and more `understanding of bidsmaps <bidsmap.html>`__. To organise and empower your template you can take the DCCN template bidsmap (``[path_to_bidscoin]/heuristics/bidsmap_dccn.yaml``) as an example and work from there. If you open that template with a text editor, there are a few handy things to take notice of (as shown in the template snippet below). First, you can see that the DCCN template makes use of YAML `anchors and aliases <https://blog.daemonl.com/2016/02/yaml.html>`__ (to make maintanance more sustainable). The second thing to notice is that, of the first run, all values of the attribute dictionary are empty, meaning that it won't match any run-item. In that way, however, the subsequent runs that dereference (e.g. with ``<<: *anatattributes_dicom``) this anchor (e.g. ``&anatattributes_dicom``) will inherit only the keys and can inject their own values, as shown in the second run. The first run of each modality sub-section (like ``anat``) also serves as the default bidsmapping when users manually overrule / change the bids modality using the `bidseditor <workflow.html#step-1b-running-the-bidseditor>`__ GUI.

.. tip::
   - Run-items are matched from top to bottom. You can use this to your advantage by placing certain run-items above others
   - The power of regular expressions is nearly unlimited, you can e.g. use `negative look aheads <https://docs.python.org/3/howto/regex.html#lookahead-assertions>`__ to *not* match (exclude) certain strings
   - Use more attributes for more selective run-item matching. For instance, to distinguish an equally named SBRef DWI scan from the normal DWI scans, you can add ``DiffusionDirectionality: NONE`` to your attribute dictionary
   - When creating new run-items, make sure to adhere to the format defined in the BIDS schema files (``[path_to_bidscoin]/bidscoin/schema/datatypes``).

.. code-block:: yaml

   anat:       # ----------------------- All anatomical runs --------------------
   - provenance: ~                 # The fullpath name of the DICOM file from which the attributes are read. Serves also as a look-up key to find a run in the bidsmap
     properties: &fileattr         # This is an optional (stub) entry of filesystem matching (could be added to any run-item)
       filepath: ~                 # File folder, e.g. ".*Parkinson.*" or ".*(phantom|bottle).*"
       filename: ~                 # File name, e.g. ".*fmap.*" or ".*(fmap|field.?map|B0.?map).*"
       filesize: ~                 # File size, e.g. "2[4-6]\d MB" for matching files between 240-269 MB
       nrfiles: ~                  # Number of files in the folder that match the above criteria, e.g. "5/d/d" for matching a number between 500-599
     attributes: &anat_dicomattr   # An empty / non-matching reference dictionary that can be derefenced in other run-items of this data type
       Modality: ~
       ProtocolName: ~
       SeriesDescription: ~
       ImageType: ~
       SequenceName: ~
       SequenceVariant: ~
       ScanningSequence: ~
       MRAcquisitionType: ~
       SliceThickness: ~
       FlipAngle: ~
       EchoNumbers: ~
       EchoTime: ~
       RepetitionTime: ~
       PhaseEncodingDirection: ~
     bids: &anat_dicoment_nonparametric  # See: schema/datatypes/anat.yaml
       acq: <SeriesDescription>    # This will be expanded by the bidsmapper (so the user can edit it)
       ce: ~
       rec: ~
       run: <<1>>                  # This will be updated during bidscoiner runtime (as it depends on the already existing files)
       part: ['', 'mag', 'phase', 'real', 'imag', 0]
       suffix: T1w
     meta:                         # This is an optional entry for meta-data that will be appended to the json sidecar files produced by dcm2niix
   - provenance: ~
     properties:
       <<: *fileattr
       nrfiles: [1-3]/d/d          # Number of files in the folder that match the above criteria, e.g. "5/d/d" for matching a number between 500-599
     attributes:
       <<: *anat_dicomattr
       ProtocolName: '(?i).*(MPRAGE|T1w).*'
       MRAcquisitionType: '3D'
     bids: *anat_dicoment_nonparametric
     meta:
       Comments: <<ImageComments>>    # This will be expanded during bidscoiner runtime (as it may vary from session to session)
   - provenance: ~
     attributes:
       <<: *anat_dicomattr
       ProtocolName: '(?i).*T2w.*'
       SequenceVariant: '[''SK'', ''SP'']'       # NB: Uses a yaml single-quote escape
     bids:
       <<: *anat_dicoment_nonparametric
       suffix: T2w

*Snippet derived from the bidsmap_dccn template, showing a `DICOM` section with a void `anat` run-item and two normal run-items that dereference from the void item*
