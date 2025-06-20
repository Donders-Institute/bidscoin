Plugins
=======

As shown in the figure below, all interactions of BIDScoin routines with source data are done via an Interface class that abstracts away differences between source data formats. The bidsmapper and bidscoiner tools loop over the subjects/sessions in your source data repository and then use the plugins that are listed in the bidsmap to do the actual work.

.. figure:: ./_static/bidscoin_architecture.png

   The BIDScoin architecture and dataflow, showing different layers of abstraction. The BIDScoin layer interacts with the plugins using a single programming interface (API), which in turn interact with the source data in a dataformat dependent way. The BIDScoin layer also interacts with the metadata layer, where all prior knowledge and mapping information is stored.

You can use the ``bidscoin`` utility to list, install or uninstall BIDScoin plugins, but the following plugins come pre-installed:

Dcm2niix2bids: a plugin for DICOM and PAR/REC data
--------------------------------------------------

The 'dcm2niix2bids' plugin is a wrapper around the well-known pydicom, nibabel and (in particular) `dcm2niix <https://github.com/rordenlab/dcm2niix>`__ tools to interact with and convert DICOM and Philips SPAR/REC source data. Pydicom is used to read DICOM attributes, nibabel is used to read PAR attribute values and dcm2niix is used to convert the DICOM and PAR/REC source data to NIfTI and create BIDS sidecar files. Personal data from the source header (e.g. Age, Sex) is added to the BIDS participants.tsv file. The plugin supports a custom tag ``PatientAgeDerived``, which computes age with high precision by taking the difference between ``AcquisitionDate`` and ``BirthDate``. Please cite: `DOI: 10.1016/j.jneumeth.2016.03.001 <https://doi.org/10.1016/j.jneumeth.2016.03.001>`__

Spec2nii2bids: a plugin for MR spectroscopy data
------------------------------------------------

The 'spec2nii2bids' plugin is a wrapper around the recent `spec2nii <https://github.com/wtclarke/spec2nii>`__ Python library to interact with and convert MR spectroscopy source data. Presently, the spec2nii2bids plugin is a first implementation that supports the conversion of Philips SPAR/SDAT files, Siemens Twix files and GE P-files to NIfTI, in conjunction with BIDS sidecar files. Personal data from the source header (e.g. Age, Sex) is added to the BIDS participants.tsv file. Please cite: `DOI: 10.1002/mrm.29418 <https://doi.org/10.1002/mrm.29418>`__

Nibabel2bids: a generic plugin for imaging data
-----------------------------------------------

The nibabel2bids plugin wraps around the versatile `nibabel <https://nipy.org/nibabel>`__ tool to convert a wide variety of data formats into NIfTI-files. Currently, the default template bidsmap is tailored to NIfTI source data only (but this can readily be extended), and BIDS sidecar files are not automatically produced by nibabel (but see the note further below). Please cite: `DOI: 10.5281/zenodo.591597 <https://doi.org/10.5281/zenodo.591597>`__

Events2bids: a plugin for stimulus presentation log data
--------------------------------------------------------

The events2bids plugin parses `NeuroBS <https://www.neurobs.com/>`__ Presentation, `PsychoPy <https://psychopy.org/>`__, as well as generic behavioural log files to BIDS task events files. See the `workflow page <./workflow.html#stimulus-events>`__ for usage.

The plugin programming interface
--------------------------------

This paragraph describes the requirements and structure of plugins in order to allow users and developers to write their own plugin and extent or customize BIDScoin to their needs.

The main task of a plugin is to perform the actual conversion of the source data into a format that is part of the BIDS standard. BIDScoin offers the Python library module named ``bids`` to interact with bidsmaps and to provide the intended output names and metadata. Notably, the bids library contains a class named ``BidsMap()`` that provides various methods and other useful classes for building and interacting with bidsmap data. Bidsmap objects provide access (hierarchically) to ``DataFormat()``, ``Datatype()``, ``RunItem()``, ``DataSource()`` and ``EventsParser`` objects, each of which comes with methods to interact with the corresponding sections of the bidsmap data. The RunItem objects can be used to obtain the mapping to the BIDS output names, and the DataSource object can read the source data attributes and properties. The DataSource object transparently handles dynamic values (including regular expressions) as well as the extended source data attributes. In addition, a plugin can implement a class named ``[DataFormat]Events()`` to read and convert stimulus presentation log data to task events files. This class inherits from the ``bidscoin.plugins.EventsParser`` abstract base class, and is required to make an initial parsing of the source data to a Pandas DataFrame (table).

In short, the purpose of the plugin is to interact with the data, by providing methods from the abstract base classes ``bidscoin.plugins.PluginInterface`` and, optionally, ``bidscoin.plugins.EventsParser``. Most notably, plugins can implement the following methods:

- **test()**: Optional. A test function for the plugin + its bidsmap options. Can be called by the user from the bidseditor and the bidscoin utility
- **has_support()**: If given a source data file that the plugin supports, then report back the name of its data format, i.e. the name of the section in the bidsmap
- **get_attribute()**: If given a source data file that the plugin supports, then report back its attribute value (e.g. from the header)
- **bidsmapper()**: Optional. From a given session folder, identify the different runs (source datatypes) and, if they haven't been discovered yet, add them to the study bidsmap
- **bidscoiner()**: From a given session folder, identify the different runs (source datatypes) and convert them to BIDS output files using the mapping data specified in the runitem

The plugin programming interface is further illustrated in the placeholder Python code below. For real-world examples, it's best to start by exploring the ``nibabel2bids`` or ``events2bids`` plugins, which provide clean and minimal implementations of the required functionality. A more advanced implementation, supporting multiple data formats, can be found in the ``spec2nii2bids`` plugin. Finally, the ``dcm2niix2bids`` plugin serves as the most complex example due to the additional logic required to handle special output files and various irregularities.

.. code-block:: python3

    from bidscoin.bids import BidsMap, EventsParser, is_hidden
    from bidscoin.plugins import PluginInterface

    class Interface(PluginInterface):

        def has_support(self, file: Path) -> str:
            """
            This plugin function assesses whether a sourcefile is of a supported dataformat

            :param file:        The sourcefile that is assessed
            :param dataformat:  The requested dataformat (optional requirement)
            :return:            The name of the supported dataformat of the sourcefile. This name should
                                correspond to the name of a dataformat section in the bidsmap
            """

            return 'dataformat_name' if file.suffix == 'a_supported_suffix' else ''

        def get_attribute(self, dataformat: str, sourcefile: Path, attribute: str, options: dict) -> str:
            """
            This plugin function reads attributes from the supported sourcefile

            :param dataformat:  The dataformat of the sourcefile, e.g. DICOM of PAR
            :param sourcefile:  The sourcefile from which key-value data needs to be read
            :param attribute:   The attribute key for which the value needs to be retrieved
            :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap.plugins[__name__]
            :return:            The retrieved attribute value
            """

            return read_header(sourcefile, attribute) if dataformat in ('dataformat_name', 'another_dataformat_name') else ''

        @due.dcite(Doi('put.your/doi.here'), description='This is an optional duecredit decorator for citing your paper(s)', tags=['implementation'])
        def bidscoiner(self, session: Path, bidsmap: BidsMap, bidsses: Path) -> Union[None, dict]:
            """
            The plugin to convert the runs in the source folder and save them in the bids folder. Each saved datafile should be
            accompanied by a json sidecar file. The bidsmap options for this plugin can be found in:

            bidsmap.plugins[__name__]

            See also the dcm2niix2bids plugin for reference implementation

            :param session:     The full-path name of the subject/session raw data source folder
            :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
            :param bidsses:     The full-path name of the BIDS output `sub-/ses-` folder
            :return:            A dictionary with personal data for the participants.tsv file (such as sex or age)
            """

            # Go over the different source files in the session
            for sourcefile in session.rglob('*'):

                # Check if the sourcefile is of a supported dataformat
                if is_hidden(sourcefile.relative_to(session)) or not (dataformat := has_support(sourcefile)):
                    continue

                # Get a matching run from the bidsmap
                run, runid = bidsmap.get_matching_run(sourcefile, dataformat, runtime=True)

                # Compose the BIDS filename using the matched run
                bidsname = run.bidsname(subid, sesid, validkeys=True, runtime=True)

                # Save the sourcefile as a BIDS NIfTI file
                targetfile = (outfolder/bidsname).with_suffix('.nii')
                convert(sourcefile, targetfile)

                # Write out provenance logging data (= useful but not strictly necessary)
                bids.bidsprov(bidsses, sourcefile, run, targetfile)

                # Pool all sources of metadata and save it as a json sidecar file
                sidecar = targetfile.with_suffix('.json')
                ext_meta = bidsmap.plugins[__name__]['meta']
                metadata = bids.poolmetadata(run.datasource, sidecar, run.meta, ext_meta)
                save(sidecar, metadata)


    class PresentationEvents(EventsParser):
        """Parser for stimulus presentation logfiles"""

        def __init__(self, sourcefile: Path, _data):
            """
            Reads the event table from a log file

            :param sourcefile:  The full filepath of the log file
            :param data:        The run['events'] data (from a bidsmap)
            """

            super().__init__(sourcefile, _data)

            # Parse an initial table from the Presentation log file
            self.sourcetable = pd.read_csv(self.sourcefile, sep='\t', skiprows=3, skip_blank_lines=True)

        def logtable(self) -> pd.DataFrame:
            """Returns the source logging data"""

            return self.sourcetable

*Plugin placeholder code, illustrating the structure of a plugin with minimal functionality*
