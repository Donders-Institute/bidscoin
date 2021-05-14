Advanced usage
==============

Site specific / customized template
-----------------------------------

 The run-items in the default 'bidsmap_dccn' template bidsmap have source dictionary values that are tailored to MRI acquisitions in the Donders Institute. Hence, if you are using different protocol parameters that do not match with the template values, then your runs will initially be data (mis)typed by the bidsmapper as miscellaneous ``extra_data`` -- which you then need to correct afterwards yourself. To improve that initial data typing and further automate your workflow, you may consider creating and using your own customized template bidsmap.

.. tip::
   Make a copy of the DCCN template (``[path_to_bidscoin]/heuristics/bidsmap_dccn.yaml``) as a starting point for your own template bidsmap, and adapt it to your environment

.. note::
   If you want to use different source attributes than the default set, then beware that the attribute values should not vary between different repeats of the data acquision. Otherwise the number of run-items in the bidsmap will not be a unique shortlist of the acquisition protocols in your study, but will instead become a lengthy list that is proportional to the number of subjects and sessions.

Editing the template
^^^^^^^^^^^^^^^^^^^^

1. **Using the bidseditor**. While this is certainly not recommended for most cases, the easiest (quick and dirty) way to create a bidsmap template is to use the bidseditor GUI. If you have a run item in your study that you would like to be automatically mapped in other / future studies you can simply append that run to the standard or to a custom template bidsmap by editing it to your needs and click the ``Export`` button (see below). Note that you should first clear the attribute values (e.g. ``EchoTime``) that vary across repeats of the same or similar acquisitions. With the GUI you can still use advanced features, such as `regular expression patterns <https://docs.python.org/3/library/re.html>`__ for the attribute values. You can also open the template bidsmap itself with the bidseditor and edit it directly. The main limitation of using the GUI is that the run items are simply appended to a bidsmap template, meaning that they are last in line (for that datatype) when the bidsmapper tries to find a matching run-item. Another (smaller) limitation is that with the GUI you cannot make usage of YAML anchors and references, yielding a less clearly formatted bidsmap that is harder to maintain. Both limitations are overcome when directly editing the template bidsmap yourself using a text editor (see next point).

.. figure:: ./_static/bidseditor_edit.png

   The edit window with the option to export the customized mapping of run a item

2. **Using a text editor**. This is the most powerful way to create or modify a bidsmap template but requires more knowledge of `YAML <http://yaml.org/>`__ and of `understanding of bidsmaps <bidsmap.html>`__. To organise and empower your template you can take the DCCN template bidsmap (``[path_to_bidscoin]/heuristics/bidsmap_dccn.yaml``) as an example and work from there. If you open that template with a text editor, there are a few handy things to take notice of (as shown in the template snippet below). First, you can see that the DCCN template makes use of YAML `anchors and aliases <https://blog.daemonl.com/2016/02/yaml.html>`__ (to make maintanance more sustainable). The second thing to notice is that, of the first run, all values of the attribute dictionary are empty, meaning that it won't match any run-item. In that way, however, the subsequent runs that dereference (e.g. with ``<<: *anatattributes_dicom``) this anchor (e.g. ``&anatattributes_dicom``) will inherit only the keys and can inject their own values, as shown in the second run. The first run of each modality sub-section (like ``anat``) also serves as the default bidsmapping when users manually overrule / change the bids modality using the `bidseditor <workflow.html#step-1b-running-the-bidseditor>`__ GUI.

.. tip::
   - Run-items are matched from top to bottom. You can use this to your advantage by placing certain run-items above others
   - The power of regular expressions is nearly unlimited, you can e.g. use `negative look aheads <https://docs.python.org/3/howto/regex.html#lookahead-assertions>`__ to *not* match (exclude) certain strings
   - Use more attributes for more selective run-item matching. For instance, to distinguish an equally named SBRef DWI scan from the normal DWI scans, you can add ``DiffusionDirectionality: NONE`` to your attribute dictionary

.. code-block:: yaml

   anat:       # ----------------------- All anatomical runs --------------------
   - provenance: ~                 # The fullpath name of the DICOM file from which the attributes are read. Serves also as a look-up key to find a run in the bidsmap
     filesystem: &fileattr         # This is an optional (stub) entry of filesystem matching (could be added to any run-item)
       path: ~                     # File folder, e.g. ".*Parkinson.*" or ".*(phantom|bottle).*"
       name: ~                     # File name, e.g. ".*fmap.*" or ".*(fmap|field.?map|B0.?map).*"
       size: ~                     # File size, e.g. "2[4-6]\d MB" for matching files between 240-269 MB
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
       acq: <SeriesDescription>
       ce: ~
       rec: ~
       run: <<1>>
       part: ['', 'mag', 'phase', 'real', 'imag', 0]
       suffix: T1w
     meta:                         # This is an optional entry for meta-data that will be appended to the json sidecar files produced by dcm2niix
   - provenance: ~
     filesystem:
       <<: *fileattr
       nrfiles: [1-3]/d/d          # Number of files in the folder that match the above criteria, e.g. "5/d/d" for matching a number between 500-599
     attributes:
       <<: *anat_dicomattr
       ProtocolName: '(?i).*(MPRAGE|T1w).*'
       MRAcquisitionType: '3D'
     bids: *anat_dicoment_nonparametric
     meta:
       Comments: <<ImageComments>>
   - provenance: ~
     attributes:
       <<: *anat_dicomattr
       ProtocolName: '(?i).*T2w.*'
       SequenceVariant: '[''SK'', ''SP'']'       # NB: Uses a yaml single-quote escape
     bids:
       <<: *anat_dicoment_nonparametric
       suffix: T2w

*Snippet from the bidsmap_dccn template, showing a `DICOM` section with a void `anat` run-item and two normal run-items that dereference from the void item*

Plugins
-------

BIDScoin uses a flexible plugin architecture to map and convert your source data to BIDS. The bidsmapper and bidscoiner tools loop over the subjects/sessions in your source directory and then call the plugins listed in the bidsmap to do the actual work. As can be seen in the API code snippet below, the plugins can contain optional ``test``, ``bidsmapper_plugin`` and ``bidscoiner_plugin`` functions that have input arguments with information about the plugin options and about the data input and BIDS output. The 'test()' function is executed when users click on the test-button in the bidseditor GUI, the 'bidsmapper_plugin()' function is called by the bidsmapper and the 'bidscoiner_plugin()' function by the bidscoiner. See also the default ``dcm2bidsmap`` and ``dcm2niix2bids`` plugins for reference implementation.

Plugins can be listed, installed and uninstalled using the central ``bidscoin`` command-line tool.

.. code-block:: python3

   import logging
   from pathlib import Path

   LOGGER = logging.getLogger(__name__)


   def test(options: dict) -> bool:
       """
       An internal routine to test the working of the plugin + its bidsmap options

       :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
       :return:        True if the test was successful
       """

       LOGGER.debug(f'This is a demo-plugin test routine, validating its working with options: {options}')

       return True


   def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
       """
       All the logic to map the Philips PAR/XML fields onto bids labels go into this plugin function. The function is
       expecte to update / append new runs to the bidsmap_new data structure. The bidsmap options for this plugin can
       be found in:

       bidsmap_new/old['Options']['plugins']['README']

       See e.g. dcm2bidsmap.py for an example implementation

       :param session:     The full-path name of the subject/session raw data source folder
       :param bidsmap_new: The study bidsmap that we are building
       :param bidsmap_old: Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
       :param template:    The template bidsmap with the default heuristics
       :param store:       The paths of the source- and target-folder
       :return:
       """

       LOGGER.debug(f'This is a bidsmapper demo-plugin working on: {session}')


   def bidscoiner_plugin(session: Path, bidsmap: dict, bidsfolder: Path, personals: dict, subprefix: str, sesprefix: str) -> None:
       """
       The plugin to convert the runs in the source folder and save them in the bids folder. Each saved datafile should be
       accompanied with a json sidecar file. The bidsmap options for this plugin can be found in:

       bidsmap_new/old['Options']['plugins']['README']

       See e.g. dcm2niix2bids.py for an example implementation

       :param session:     The full-path name of the subject/session raw data source folder
       :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
       :param bidsfolder:  The full-path name of the BIDS root-folder
       :param personals:   The dictionary with the personal information
       :param subprefix:   The prefix common for all source subject-folders
       :param sesprefix:   The prefix common for all source session-folders
       :return:            Nothing
       """

       LOGGER.debug(f'This is a bidscoiner demo-plugin working on: {session} -> {bidsfolder}')

*The README plugin placeholder code*
