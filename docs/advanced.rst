Advanced usage
==============

Site specific / customized template
-----------------------------------

If you want to convert many studies with similar acquisition protocols then you **may** consider (NB: this is in no way necessary) creating your own customized bidsmap template. This template can then be passed to the `bidsmapper <workflow.html#step-1b-running-the-bidsmapper>`__ tool (instead of the default ``[path_to_bidscoin]/heuristics/bidsmap_template.yaml`` template) to automatically identify the different scans in your (future) studies and map these to the correct BIDS modalities.

Generally speaking, a bidsmap file contains a collection of key-value dictionaries that define unique mappings between different types (runs) of source data onto BIDS outcome data. As illustrated in the figure below, each run item in the bidsmap has a ``provenance`` key-value pair to store the pathname of a representative data sample of that run. Each run item also contains a source data ``attributes`` object, i.e. a key-value dictionary with keys and values that are extracted from the provenance data sample, as well as a ``bids`` object, i.e. a key-value dictionary that determines the filename of the BIDS output file. The different key-value pairs in the ``attributes`` dictionary represent properties of the source data and should uniquely identify the different runs in a session. But these attrribute-values should not vary between sessions, making the length of the bidsmap only dependent on the acquisition protocol and not on the number of subjects and sessions in the data collection. The difference between a bidsmap template and the study bidsmap that comes out of the ``bidsmapper`` is that the template contains / defines the key-values that will be used by the bidsmapper and that the template contains all possible runs. The study bidsmap contains only runs that were encountered in the study, with key-values that are specific for that study. A bidsmap has different sections for different source data modalities, i.e.  ``DICOM``, ``PAR``, ``P7``, ``Nifti``, ``FileSystem``, as well as a section for the BIDScoin ``Options``. Within each source data section there sub-sections for the different BIDS modalities, i.e. for ``anat``, ``func``, ``dwi``, ``fmap``, ``pet``, ``beh`` and ``extra_data``, and for the ``participant_label`` and ``session_label``. It is important to note that BIDScoin tools, given a data sample, will go through the bidsmap (from top to bottom) until they come across a run with attribute values that match the attribute values of the data sample (NB: empty values are ignored). At that point a bidsmapping is made, i.e. the bids values will be taken to contruct a BIDS output filename.

.. figure:: ./_static/bidsmap_sample.png

   A snippet of a study bidsmap, showing a ``DICOM`` section with a few run items in the ``anat`` subsection

To create your own template bidsmap you can best first make a copy of the default template (``[path_to_bidscoin]/heuristics/bidsmap_template.yaml``) or of the DCCN example template (``[path_to_bidscoin]/heuristics/bidsmap_dccn.yaml``) and customize that bidsmap to your needs:

1. **Using the bidseditor**. This is the easiest way to create a bidsmap template since it uses only a GUI and doesn't require in-depth knowledge of bidsmaps and YAML files. If you have a run item in your study that you would like to be automatically mapped in other / future studies you can simply append that run to the standard or to a custom template bidsmap by editting it to your needs and click the ``Export`` button (see below). With the GUI you can still use advanced features, such as `Unix shell-style wildcards <https://docs.python.org/3/library/fnmatch.html>`__ in the values of the source attributes (see left panel), or such as using lists of attribute values (of which either one can match), or simply empty field to ignore the item. The main limitation of using the GUI is that the run items are always appended to a bidsmap template, meaning that they are last in line and will be used only if no other item in the template matches. It also means that like this you cannot edit the already existing run items in the bidsmap. Another smaller limitation is that with the GUI you cannot make usage of YAML anchors and references. Both these limitations are overcome when directly editting the template bidsmap yourself using a text editor (see next point).

.. figure:: ./_static/bidseditor_edit.png

   The edit window with the option to export the customized mapping of run a item

2. **Using a text editor**. This is the most powerful way to create or modify a bidsmap template but requires more indepth knowledge of `YAML <http://yaml.org/>`__ and of how BIDScoin identifies different acquisitions in a protocol given a bidsmap. How you can customize your template is well illustrated by the DCCN template bidsmap (``[path_to_bidscoin]/heuristics/bidsmap_dccn.yaml``). If you open that template, there are a few things to take notice of (as shown in the template snippet below). First, you can see that the DCCN template makes use of YAML `anchors and aliases <https://blog.daemonl.com/2016/02/yaml.html>`__ (to make maintanance more sustainable). The second thing to notice is that, of the first run, all values of the attribute dictionary are empty, meaning that it won't match any run / will be ignored. In that way, however, the subsequent runs that alias (``<<: *anatattributes_dicom``) this anchor (``&anatattributes_dicom``) will inherit only the keys and can inject their own values, as shown in the second run. The first run of each modality sub-section (like ``anat``) also serves as the default bidsmapping when users manually overrule / change the bids modality using the `bidsmapper <workflow.html#step-1a-running-the-bidsmapper>`__ GUI. Finally, it is important to take notice of the usage of the lists of values (any of which can match) and `Unix shell-style wildcards <https://docs.python.org/3/library/fnmatch.html>`__ (see ``DICOM Attributes``).

.. code-block:: yaml

   anat:       # ----------------------- All anatomical runs --------------------
   - provenance: ~                 # The first run item with empty attributes will not match anything but will be used when changing modality in the bidseditor GUI -> suffix = T1w
     attributes: &anatattributes_dicom
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
     bids: &anatbids_dicom
       acq: <SeriesDescription>    # A dynamic label which will be replaced during bidscoiner runtime with the DICOM attribute value
       ce: ~
       rec: ~
       run: <<1>>                  # A dynamic label that will be increased during bidscoiner runtime. NB: changing this value may lead to collisions / overwriting of BIDS data
       mod: ~
       suffix: T1w
   - provenance: ~                 # The second run item with non-empty attributes ('SeriesDescription' and 'MRAcquisitionType') will match any run with these attribute values
     attributes:
       <<: *anatattributes_dicom
       SeriesDescription: ['*mprage*', '*MPRAGE*', '*MPRage*', '*t1w*', '*T1w*', '*T1W*']
       MRAcquisitionType: 3D
     bids:
       <<: *anatbids_dicom
       suffix: T1w

*Snippet from the ``bidsmap_dccn.yaml`` template*, showing a ``DICOM`` section with the first two run items in the ``anat`` subsection

Plugins
-------

BIDScoin has the option to import plugins to further automate / complete the conversion from source data to BIDS. The plugin takes is called each time the BIDScoin tool has finished processing a run or session, with arguments containing information about the run or session, as shown in the plugin example code below. The functions in the plugin module should be named ``bidsmapper_plugin`` to be called by ``bidsmapper`` and ``bidscoiner_plugin`` to be called by ``bidscoiner``.

.. code-block:: python3

   import logging
   from pathlib import Path

   LOGGER = logging.getLogger(f'bidscoin.{Path(__file__).stem}')


   def bidsmapper_plugin(seriesfolder: Path, bidsmap: dict, bidsmap_template: dict) -> dict:
       """
       The plugin to map info onto bids labels

       :param seriesfolder:        The full-path name of the raw-data series folder
       :param bidsmap:             The study bidsmap
       :param bidsmap_template:    Full BIDS heuristics data structure, with all options, BIDS labels and attributes, etc
       :return:                    The study bidsmap with new entries in it
       """

       LOGGER.debug(f'This is a bidsmapper demo-plugin working on: {seriesfolder}')
       return bidsmap


   def bidscoiner_plugin(session: Path, bidsmap: dict, bidsfolder: Path, personals: dict) -> None:
       """
       The plugin to cast the series into the bids folder

       :param session:     The full-path name of the subject/session raw data source folder
       :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
       :param bidsfolder:  The full-path name of the BIDS root-folder
       :param personals:   The dictionary with the personal information
       :return:            Nothing
       """

       LOGGER.debug(f'This is a bidscoiner demo-plugin working on: {session} -> {bidsfolder}')

*Plugin example code*
