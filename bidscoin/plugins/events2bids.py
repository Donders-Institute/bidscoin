"""The events2bids plugin converts neurobs Presentation logfiles to event.tsv files"""

import logging
import json
import pandas as pd
from typing import Union
from bids_validator import BIDSValidator
from pathlib import Path
from bidscoin import bids
from bidscoin.bids import BidsMap, DataFormat, EventsParser, is_hidden, Plugin
# from convert_eprime.utils import remove_unicode

LOGGER = logging.getLogger(__name__)

# The default/fallback options that are set when installing/using the plugin
OPTIONS = Plugin({'table': 'event', 'meta': ['.json', '.tsv']})  # The file extensions of the equally named metadata sourcefiles that are copied over as BIDS sidecar files


def test(options: Plugin=OPTIONS) -> int:
    """
    Performs a Presentation test

    :param options: A dictionary with the plugin options, e.g. taken from the bidsmap.plugins['events2bids']
    :return:        The errorcode: 0 for successful execution, 1 for general tool errors, 2 for `ext` option errors, 3 for `meta` option errors
    """

    LOGGER.info('Testing the events2bids installation:')

    # Test the Presentation installation
    try:
        pass

    except Exception as eventserror:

        LOGGER.error(f"Events2bids error:\n{eventserror}")
        return 1

    return 0


def has_support(file: Path, dataformat: Union[DataFormat, str]='') -> str:
    """
    This plugin function assesses whether a sourcefile is of a supported dataformat

    :param file:        The sourcefile that is assessed
    :param dataformat:  The requested dataformat (optional requirement)
    :return:            The valid/supported dataformat of the sourcefile
    """

    if dataformat and dataformat != 'Presentation':
        return ''

    ext = ''.join(file.suffixes)
    if ext.lower() in ('.log',):
        return 'Presentation'

    return ''


def get_attribute(dataformat: Union[DataFormat, str], sourcefile: Path, attribute: str, options: Plugin) -> Union[str, int, float, list]:
    """
    This plugin supports reading attributes from DICOM and PAR dataformats

    :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. DICOM of PAR
    :param sourcefile:  The sourcefile from which the attribute value should be read
    :param attribute:   The attribute key for which the value should be read
    :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap.plugins['events2bids']
    :return:            The retrieved attribute value
    """

    if dataformat == 'Presentation':

        try:
            with sourcefile.open() as fid:
                while '-' in (line := fid.readline()):
                    key, value = line.split('-', 1)
                    if attribute == key.strip():
                        return value.strip()

        except (IOError, OSError) as ioerror:
            LOGGER.exception(f"Could not get the Presentation '{attribute}' attribute from {sourcefile}\n{ioerror}")

    return ''


def bidsmapper_plugin(session: Path, bidsmap_new: BidsMap, bidsmap_old: BidsMap, template: BidsMap) -> None:
    """
    The goal of this plugin function is to identify all the different runs in the session and update the
    bidsmap if a new run is discovered

    :param session:     The full-path name of the subject/session raw data source folder
    :param bidsmap_new: The new study bidsmap that we are building
    :param bidsmap_old: The previous study bidsmap that has precedence over the template bidsmap
    :param template:    The template bidsmap with the default heuristics
    """

    # See for every source file in the session if we already discovered it or not
    for sourcefile in session.rglob('*'):

        # Check if the sourcefile is of a supported dataformat
        if is_hidden(sourcefile.relative_to(session)) or not (dataformat := has_support(sourcefile)):
            if not is_hidden(sourcefile.relative_to(session)):
                LOGGER.bcdebug(f"Skipping {sourcefile} (not supported by {dataformat})")
            continue

        # See if we can find a matching run in the old bidsmap
        run, oldmatch = bidsmap_old.get_matching_run(sourcefile, dataformat)

        # If not, see if we can find a matching run in the template
        if not oldmatch:
            run, _ = template.get_matching_run(sourcefile, dataformat)

        # See if we have already put the run somewhere in our new bidsmap
        if not bidsmap_new.exist_run(run):

            # Communicate with the user if the run was not present in bidsmap_old or in template, i.e. that we found a new sample
            if not oldmatch:
                LOGGER.info(f"Discovered sample: {run.datasource}")
            else:
                LOGGER.bcdebug(f"Known sample: {run.datasource}")

            # Copy the filled-in run over to the new bidsmap
            bidsmap_new.insert_run(run)

        else:
            LOGGER.bcdebug(f"Existing/duplicate sample: {run.datasource}")


def bidscoiner_plugin(session: Path, bidsmap: BidsMap, bidsses: Path) -> None:
    """
    The bidscoiner plugin to convert the session Presentation source-files into BIDS-valid NIfTI-files in the
    corresponding bids session-folder

    :param session:     The full-path name of the subject/session source folder
    :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
    :param bidsses:     The full-path name of the BIDS output `sub-/ses-` folder
    :return:            Nothing (i.e. personal data is not available)
    """

    # Get the subject identifiers from the bidsses folder
    subid   = bidsses.name if bidsses.name.startswith('sub-') else bidsses.parent.name
    sesid   = bidsses.name if bidsses.name.startswith('ses-') else ''
    options = bidsmap.plugins['events2bids']
    runid   = ''

    # Read or create a scans_table and tsv-file
    scans_tsv = bidsses/f"{subid}{'_'+sesid if sesid else ''}_scans.tsv"
    if scans_tsv.is_file():
        scans_table = pd.read_csv(scans_tsv, sep='\t', index_col='filename')
    else:
        scans_table = pd.DataFrame(columns=['acq_time'], dtype='str')
        scans_table.index.name = 'filename'

    # Collect the different Presentation source files for all files in the session
    for sourcefile in session.rglob('*'):

        # Check if the sourcefile is of a supported dataformat
        if is_hidden(sourcefile.relative_to(session)) or not (dataformat := has_support(sourcefile)):
            continue

        # Get a matching run from the bidsmap
        run, runid = bidsmap.get_matching_run(sourcefile, dataformat, runtime=True)

        # Check if we should ignore this run
        if run.datatype in bidsmap.options['ignoretypes']:
            LOGGER.info(f"--> Leaving out: {run.datasource}")
            bids.bidsprov(bidsses, sourcefile, run)                     # Write out empty provenance logging data
            continue

        # Check if we already know this run
        if not runid:
            LOGGER.error(f"Skipping unknown run: {run.datasource}\n-> Re-run the bidsmapper and delete {bidsses} to solve this warning")
            bids.bidsprov(bidsses, sourcefile)                          # Write out empty provenance logging data
            continue

        LOGGER.info(f"--> Coining: {run.datasource}")

        # Create the BIDS session/datatype output folder
        outfolder = bidsses/run.datatype
        outfolder.mkdir(parents=True, exist_ok=True)

        # Compose the BIDS filename using the matched run
        bidsignore = bids.check_ignore(run.datatype, bidsmap.options['bidsignore'])
        bidsname   = run.bidsname(subid, sesid, not bidsignore, runtime=True)
        bidsignore = bidsignore or bids.check_ignore(bidsname+'.json', bidsmap.options['bidsignore'], 'file')
        bidsname   = run.increment_runindex(outfolder, bidsname, scans_table)
        eventsfile = (outfolder/bidsname).with_suffix('.tsv')

        # Check if the bidsname is valid
        bidstest = (Path('/')/subid/sesid/run.datatype/bidsname).with_suffix('.nii').as_posix()
        isbids   = BIDSValidator().is_bids(bidstest)
        if not isbids and not bidsignore:
            LOGGER.warning(f"The '{bidstest}' output name did not pass the bids-validator test")

        # Check if file already exists (-> e.g. when a static runindex is used)
        if eventsfile.is_file():
            LOGGER.warning(f"{eventsfile} already exists and will be deleted -- check your results carefully!")
            eventsfile.unlink()

        # Save the sourcefile as a BIDS NIfTI file and write out provenance logging data
        run.eventsparser().write(eventsfile)
        bids.bidsprov(bidsses, sourcefile, run, [eventsfile] if eventsfile.is_file() else [])

        # Check the output
        if not eventsfile.is_file():
            LOGGER.error(f"Output file not found: {eventsfile}")
            continue

        # Load/copy over the source meta-data
        sidecar  = eventsfile.with_suffix('.json')
        metadata = bids.poolmetadata(run.datasource, sidecar, run.meta, options.get('meta', []))
        if metadata:
            with sidecar.open('w') as json_fid:
                json.dump(metadata, json_fid, indent=4)

        # Add an entry to the scans_table (we typically don't have useful data to put there)
        scans_table.loc[eventsfile.relative_to(bidsses).as_posix(), 'acq_time'] = 'n/a'

    if not runid:
        LOGGER.info(f"--> No {__name__} sourcedata found in: {session}")
        return

    # Write the scans_table to disk
    LOGGER.verbose(f"Writing data to: {scans_tsv}")
    scans_table.replace('','n/a').to_csv(scans_tsv, sep='\t', encoding='utf-8', na_rep='n/a')


class PresentationEvents(EventsParser):
    """Parser for Presentation (Neurobs) logfiles"""

    def __init__(self, sourcefile: Path, _data: dict, options: dict):
        """
        Reads the event table from the Presentation logfile

        :param sourcefile:  The full filepath of the logfile
        :param data:        The run['events'] data (from a bidsmap)
        :param options:     The plugin options
        """

        super().__init__(sourcefile, _data, options)

        # Read the log-tables from the Presentation logfile
        self._sourcetable = pd.read_csv(self.sourcefile, sep='\t', skiprows=3, skip_blank_lines=True)
        """The Presentation log-tables (https://www.neurobs.com/pres_docs/html/03_presentation/07_data_reporting/01_logfiles/index.html)"""

    @property
    def logtable(self) -> pd.DataFrame:
        """Returns a Presentation log-table"""

        nrows          = len(self._sourcetable)
        stimulus_start = (self._sourcetable.iloc[:, 0] == 'Event Type').idxmax() or nrows
        video_start    = (self._sourcetable.iloc[:, 0] == 'filename').idxmax() or nrows
        survey_start   = (self._sourcetable.iloc[:, 0] == 'Time').idxmax() or nrows

        # Drop the stimulus, video and survey tables
        if self.options['table'] == 'event':
            begin = 0
            end   = min(stimulus_start, video_start, survey_start)
        elif self.options['table'] == 'stimulus':
            self._sourcetable.columns = self._sourcetable.iloc[stimulus_start]
            begin = stimulus_start + 1
            end   = min(video_start, survey_start)
        elif self.options['table'] == 'video':
            self._sourcetable.columns = self._sourcetable.iloc[video_start]
            begin = video_start + 1
            end   = survey_start
        else:
            begin = 0
            end   = nrows
            LOGGER.error(f"NOT IMPLEMENTED TABLE: {self.options['table']}")

        LOGGER.bcdebug(f"Slicing '{self.options['table']}' sourcetable[{begin}:{end}]")

        return self._sourcetable.iloc[begin:end]
