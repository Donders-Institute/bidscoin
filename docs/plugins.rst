Plugins
=======

As shown in the figure below, all interactions of BIDScoin routines with source data are done via a plugin layer that abstracts away differences between source data formats. The bidsmapper and bidscoiner tools loop over the subjects/sessions in your source data repository and then use the plugins listed in the bidsmap to do the actual work.

.. figure:: ./_static/bidscoin_architecture.png

   The BIDScoin architecture and dataflow, showing different layers of abstraction. The BIDScoin layer interacts with the plugins using a single programming interface (API), which in turn interact with the source data in a dataformat dependent way. The BIDScoin layer also interacts with the metadata layer, where all prior knowledge and mapping information is stored.

These plugins come pre-installed:

Dcm2niix2bids: a plugin for DICOM and PAR/XML data
--------------------------------------------------

The 'dcm2niix2bids' plugin is a wrapper around the well-known pydicom, nibabel and (in particular) `dcm2niix <https://github.com/rordenlab/dcm2niix>`__ tools to interact with and convert DICOM and Philips PAR(/REC)/XML source data. Pydicom is used to read DICOM attributes, nibabel is used to read PAR/XML attribute values and dcm2niix is used to convert the DICOM and PAR/XML source data to NIfTI  and create BIDS sidecar files. These sidecar files contain standard metadata but, to give more control to the user, this metadata is appended or overwritten by the data in the BIDS-mapping meta dictionary.

Spec2nii2bids: a plugin for MR spectroscopy data
------------------------------------------------

The 'spec2nii2bids' plugin is a wrapper around the recent `spec2nii <https://github.com/wexeee/spec2nii>`__ Python library to interact with and convert MR spectroscopy source data. Presently, the spec2nii2bids plugin is a first implementation that supports the conversion to BIDS for Philips SPAR/SDAT files, Siemens Twix files and GE P-files. As with the dcm2niix2bids plugin, the produced sidecar files already contain standard metadata that is complemented or overruled by the meta data that users specified in the bidseditor.

Nibabel2bids: a generic plugin for imaging data
-----------------------------------------------

The nibabel2bids plugin wraps around the flexible `nibabel <https://nipy.org/nibabel>`__ tool to convert a wide variety of data formats into BIDS-valid nifti-files. Currently, the default template bidsmap is tailored to nifti source data only (but this can readily be extended), and the user has to provide the metadata (e.g. in the bidseditor GUI) for producing valid json sidecar files.

Phys2bidscoin: a plugin for physiological data
----------------------------------------------

The 'phys2bidscoin' plugin is a wrapper around the `phys2bids <https://phys2bids.readthedocs.io>`__ Python library to interact with and convert physiological source data. Phys2bids currently supports the conversion of labchart (ADInstruments) and AcqKnowledge (BIOPAC) source files to compressed tab-separated value (``.tsv.gz``) files and create their json sidecar files, as per BIDS specifications. As in the other plugins, the sidecar files contain standard metadata that is overwritten by the user data entered in the bidseditor. This plugin has been developed during the `OHBM hackathon 2021 <https://github.com/ohbm/hackathon2021/issues/12>`__ and is still considered experimental.

Plugin programming interface
----------------------------

This paragraph describes the requirements and structure of plugins in order to allow advanced users and developers to write their own plugin and extent or customize BIDScoin to their needs. As can be seen in the API code snippet below (but aso see the default plugins for reference implementation), a BIDScoin plugin is a Python module with the following programming interface (functions):

.. note:: Run the ``bidscoin`` utility to list, install or uninstall BIDScoin plugins

.. code-block:: python3

   """
   This module contains placeholder code demonstrating the bidscoin plugin API, both for the bidsmapper and for
   the bidscoiner. The functions in this module are called if the basename of this module (when located in the
   plugins-folder; otherwise the full path must be provided) is listed in the bidsmap. The presence of the
   plugin functions is optional but should be named:

   - test:                 A test function for the plugin + its bidsmap options. Can be called in the bidseditor
   - is_sourcefile:        A function to assess whether a source file is supported by the plugin. The return value should correspond to a data format section in the bidsmap
   - get_attribute:        A function to read an attribute value from a source file
   - bidsmapper_plugin:    A function to discover BIDS-mappings in a source data session. To avoid code duplications and minimize plugin development time, various support functions are available to the plugin programmer in BIDScoin's library module named 'bids'
   - bidscoiner_plugin:    A function to convert a single source data session to bids according to the specified BIDS-mappings. Various support functions are available in the 'bids' library module
   """

   import logging
   from pathlib import Path

   LOGGER = logging.getLogger(__name__)

   # The default options that are set when installing the plugin
   OPTIONS = {'command': 'demo',   # Plugin option
              'args': 'foo bar'}   # Another plugin option

   # The default bids-mappings that are added when installing the plugin
   BIDSMAP = {'DemoFormat':{
       'subject': '<<filepath:/sub-(.*?)/>>',     # This filesystem property extracts the subject label from the source directory. NB: Any property or attribute can be used as subject-label, e.g. <PatientID>
       'session': '<<filepath:/ses-(.*?)/>>',     # This filesystem property extracts the session label from the source directory. NB: Any property or attribute can be used as session-label, e.g. <StudyID>

       'func': [                   # ----------------------- All functional runs --------------------
           {'provenance': '',      # The fullpath name of the source file from which the attributes and properties are read. Serves also as a look-up key to find a run in the bidsmap
            'properties':          # The matching (regexp) criteria go in here
               {'filepath': '',    # File folder, e.g. ".*Parkinson.*" or ".*(phantom|bottle).*"
                'filename': '',    # File name, e.g. ".*fmap.*" or ".*(fmap|field.?map|B0.?map).*"
                'filesize': '',    # File size, e.g. "2[4-6]\d MB" for matching files between 240-269 MB
                'nrfiles': ''},    # Number of files in the folder that match the above criteria, e.g. "5/d/d" for matching a number between 500-599
            'attributes':          # The matching (regexp) criteria go in here
               {'ch_num': '.*',
                'filetype': '.*',
                'freq': '.*',
                'ch_name': '.*',
                'units': '.*',
                'trigger_idx': '.*'},
            'bids':
               {'task': '',
                'acq': '',
                'ce': '',
                'dir': '',
                'rec': '',
                'run': '<<1>>',    # This will be updated during bidscoiner runtime (as it depends on the already existing files)
                'recording': '',
                'suffix': 'physio'},
            'meta':                # This is an optional entry for meta-data dictionary that are appended to the json sidecar files
               {'TriggerChannel': '<<trigger_idx>>',
                'ExpectedTimepoints': '<<num_timepoints_found>>',
                'ChannelNames': '<<ch_name>>',
                'Threshold': '<<thr>>',
                'TimeOffset': '<<time_offset>>'}}],

       [...]

       'exclude': [  # ----------------------- Data that will be left out -------------
           {'provenance': '',
            'properties':
               {'filepath': '',
                'filename': '',
                'filesize': '',
                'nrfiles': ''},
            'attributes':
               {'ch_num': '.*',
                'filetype': '.*',
                'freq': '.*',
                'ch_name': '.*',
                'units': '.*',
                'trigger_idx': '.*'},
            'bids':
               {'task': '',
                'acq': '',
                'ce': '',
                'dir': '',
                'rec': '',
                'run': '<<1>>',
                'recording': '',
                'suffix': 'physio'},
            'meta':
               {'TriggerChannel': '<<trigger_idx>>',
                'ExpectedTimepoints': '<<num_timepoints_found>>',
                'ChannelNames': '<<ch_name>>',
                'Threshold': '<<thr>>',
                'TimeOffset': '<<time_offset>>'}}]}}


   def test(options: dict) -> bool:
       """
       This plugin function tests the working of the plugin + its bidsmap options

       :param options: A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
       :return:        True if the test was successful
       """

       LOGGER.debug(f'This is a demo-plugin test routine, validating its working with options: {options}')

       return True


   def is_sourcefile(file: Path) -> str:
       """
       This plugin function assesses whether a sourcefile is of a supported dataformat

       :param file:    The sourcefile that is assessed
       :return:        The valid / supported dataformat of the sourcefile
       """

       if file.is_file():

           LOGGER.debug(f'This is a demo-plugin is_sourcefile routine, assessing whether "{file}" has a valid dataformat')
           return 'dataformat'

       return ''


   def get_attribute(dataformat: str, sourcefile: Path, attribute: str, options: dict) -> Union[str, int]:
       """
       This plugin function reads attributes from the supported sourcefile

       :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. DICOM of PAR
       :param sourcefile:  The sourcefile from which the attribute value should be read
       :param attribute:   The attribute key for which the value should be read
       :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap['Options']
       :return:            The attribute value
       """

       if dataformat in ('DICOM','PAR'):
           LOGGER.debug(f'This is a demo-plugin get_attribute routine, reading the {dataformat} "{attribute}" attribute value from "{sourcefile}"')

       return ''


   def bidsmapper_plugin(session: Path, bidsmap_new: dict, bidsmap_old: dict, template: dict, store: dict) -> None:
       """
       All the logic to map the Philips PAR/XML fields onto bids labels go into this plugin function. The function is
       expecte to update / append new runs to the bidsmap_new data structure. The bidsmap options for this plugin can
       be found in:

       bidsmap_new/old['Options']['plugins']['README']

       See also the dcm2niix2bids plugin for reference implementation

       :param session:     The full-path name of the subject/session raw data source folder
       :param bidsmap_new: The new study bidsmap that we are building
       :param bidsmap_old: The previous study bidsmap that has precedence over the template bidsmap
       :param template:    The template bidsmap with the default heuristics
       :param store:       The paths of the source- and target-folder
       :return:
       """

       LOGGER.debug(f'This is a bidsmapper demo-plugin working on: {session}')


   def bidscoiner_plugin(session: Path, bidsmap: dict, bidsses: Path) -> None:
       """
       The plugin to convert the runs in the source folder and save them in the bids folder. Each saved datafile should be
       accompanied with a json sidecar file. The bidsmap options for this plugin can be found in:

       bidsmap_new/old['Options']['plugins']['README']

       See also the dcm2niix2bids plugin for reference implementation

       :param session:     The full-path name of the subject/session source folder
       :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
       :param bidsses:     The full-path name of the BIDS output `ses-` folder
       :return:            Nothing
       """

       LOGGER.debug(f'This is a bidscoiner demo-plugin working on: {session} -> {bidsfolder}')

*The README plugin placeholder code*