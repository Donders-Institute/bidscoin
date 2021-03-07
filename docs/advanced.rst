Advanced usage
==============

Site specific / customized template
-----------------------------------

 The run-items in the default template bidsmap (named ``bidsmap_template.yaml``) have empty / non-matching source attributes, and therefore the ``bidsmapper`` will not make any guesses about BIDS datatypes and run-items. As a result, it will classify all runs as ``extra_data``, leaving all the subsequent ``bidseditor`` decision making to the user. One alternative is to use the much more intelligent ``bidsmap_dccn.yaml`` template bidsmap. This bidsmap may work much better but it may also make wrong suggestions, since it is tailored to the MR acquisitions at the Donders Institute. To improve that and to have BIDScoin convert your studies in a better way, you **may** consider creating and using your own customized template bidsmap.

.. tip::
   To create your own template bidsmap you can probably best make a copy of the DCCN template (``[path_to_bidscoin]/heuristics/bidsmap_dccn.yaml``) as a starting point and adapt it to your needs. If you want to use different source attributes to improve run identifications, then beware that the attribute values should not vary between different repeats of the data acquision. Otherwise the number of run-items in the bidsmap will not be a shortlist of the different acquisition protocols in your study, but will become a lengthy list that is proportional to the number of subjects and sessions.

Editing the template
^^^^^^^^^^^^^^^^^^^^

1. **Using the bidseditor**. This is the easiest way to create a bidsmap template since it uses only a GUI and doesn't require in-depth knowledge of bidsmaps and YAML files. If you have a run item in your study that you would like to be automatically mapped in other / future studies you can simply append that run to the standard or to a custom template bidsmap by editing it to your needs and click the ``Export`` button (see below). Note that you should first empty the source attribute values (e.g. ``EchoTime``) that vary across repeats of the same run. With the GUI you can still use advanced features, such as `Unix shell-style wildcards <https://docs.python.org/3/library/fnmatch.html>`__ in the values of the source attributes (see left panel), or such as using lists of attribute values (of which either one can match), or simply empty fields to ignore the item. The main limitation of using the GUI is that the run items are always appended to a bidsmap template, meaning that they are last in line and will be used only if no other item in the template matches. It also means that like this you cannot edit the already existing run items in the bidsmap. Another (smaller) limitation is that with the GUI you cannot make usage of YAML anchors and references, yielding a less clearly formatted bidsmap that is harder to maintain. Both limitations are overcome when directly editing the template bidsmap yourself using a text editor (see next point).

.. figure:: ./_static/bidseditor_edit.png

   The edit window with the option to export the customized mapping of run a item

2. **Using a text editor**. This is the most powerful way to create or modify a bidsmap template but requires more indepth knowledge of `YAML <http://yaml.org/>`__ and of how BIDScoin identifies different acquisitions in a protocol given a bidsmap. How you can customize your template is well illustrated by the DCCN template bidsmap (``[path_to_bidscoin]/heuristics/bidsmap_dccn.yaml``). If you open that template, there are a few things to take notice of (as shown in the template snippet below). First, you can see that the DCCN template makes use of YAML `anchors and aliases <https://blog.daemonl.com/2016/02/yaml.html>`__ (to make maintanance more sustainable). The second thing to notice is that, of the first run, all values of the attribute dictionary are empty, meaning that it won't match any run / will be ignored. In that way, however, the subsequent runs that alias (``<<: *anatattributes_dicom``) this anchor (``&anatattributes_dicom``) will inherit only the keys and can inject their own values, as shown in the second run. The first run of each modality sub-section (like ``anat``) also serves as the default bidsmapping when users manually overrule / change the bids modality using the `bidseditor <workflow.html#step-1b-running-the-bidseditor>`__ GUI.

.. code-block:: yaml

   anat:       # ----------------------- All anatomical runs --------------------
   - provenance: ~                       # The fullpath name of the DICOM file from which the attributes are read. Serves also as a look-up key to find a run in the bidsmap
     attributes: &anat_dicomattr
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
   - provenance: ~
     attributes:
       <<: *anat_dicomattr
       SeriesDescription: ['*mprage*', '*MPRAGE*', '*MPRage*', '*t1w*', '*T1W*', '*T1w*', '*T1*']
       MRAcquisitionType: 3D
     bids: *anat_dicoment_nonparametric
   - provenance: ~
     attributes:
       <<: *anat_dicomattr
       SeriesDescription: ['*t2w*', '*T2w*', '*T2W*', '*T2*']
       SequenceVariant: "['SK', 'SP']"
     bids:
       <<: *anat_dicoment_nonparametric
       suffix: T2w

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
