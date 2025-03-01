"""The events2bids plugin converts neurobs Presentation logfiles to event.tsv files"""

import logging
import json
import dateutil.parser
import pandas as pd
from typing import Union
from importlib.util import find_spec
from bids_validator import BIDSValidator
from pathlib import Path
from bidscoin import bids, is_hidden
from bidscoin.plugins import PluginInterface, EventsParser
from bidscoin.bids import BidsMap, DataFormat, Plugin
# TODO: from convert_eprime.utils import ..
if find_spec('psychopy'):
    import psychopy
    from psychopy.misc import fromFile

LOGGER = logging.getLogger(__name__)

# The default/fallback options that are set when installing/using the plugin
OPTIONS = Plugin({'meta': ['.json']})  # The file extensions of the equally named metadata source files that are copied over as BIDS sidecar files


class Interface(PluginInterface):

    def has_support(self, sourcefile: Path, dataformat: Union[DataFormat, str]= '') -> str:
        """
        This plugin function assesses whether a sourcefile is of a supported dataformat

        :param sourcefile:  The sourcefile that is assessed
        :param dataformat:  The requested dataformat (optional requirement)
        :return:            The valid/supported dataformat of the sourcefile
        """

        if dataformat and dataformat not in ('Presentation', 'Psychopy'):
            return ''

        if sourcefile.suffix.lower() in ('.log',):
            try:
                with sourcefile.open('r') as fid:
                    for n in (1,2,3):
                        if fid.readline().startswith('Scenario -'):
                            return 'Presentation'
            except Exception:
                pass

        if sourcefile.suffix.lower() in ('.tsv', '.csv'):           # '.psydat' = WIP
            with sourcefile.open('r', encoding='utf-8-sig') as fid:
                header = fid.readline()
            return 'Psychopy' if 'psychopyVersion' in header else ''

        return ''

    def get_attribute(self, dataformat: Union[DataFormat, str], sourcefile: Path, attribute: str, options) -> Union[str, int, float, list]:
        """
        This plugin supports reading header attributes from Presentation files and `extraInfo` attributes from PsychoPy files

        :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. "Presentation" of "Psychopy"
        :param sourcefile:  The sourcefile from which the attribute value should be read
        :param attribute:   The attribute key for which the value should be read
        :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap.plugins['events2bids']
        :return:            The retrieved attribute value
        """

        if dataformat == 'Presentation':

            try:
                with sourcefile.open('r') as fid:
                    while '-' in (line := fid.readline()):
                        key, value = line.split('-', 1)
                        if attribute == key.strip():
                            return value.strip()

            except (IOError, OSError) as ioerror:
                LOGGER.exception(f"Could not get the Presentation '{attribute}' attribute from {sourcefile}\n{ioerror}")

        elif dataformat == 'Psychopy':
            if sourcefile.suffix.lower() in ('.psydat',):
                if find_spec('psychopy'):
                    psydat = fromFile(sourcefile)
                    return psydat.extraInfo.get(attribute) or ''
                else:
                    LOGGER.warning(f"Could not read the PsychoPy '{sourcefile}', please install `psychopy`")

            if sourcefile.suffix.lower() in ('.tsv', '.csv'):
                df = pd.read_csv(sourcefile, nrows=1, sep=None, engine='python', skip_blank_lines=True, encoding='utf-8-sig')
                if attribute in df.columns[-(options.get('extraInfo',7) + 1):]:     # The `extraInfo` columns (7?) are always last + a separator
                    return df.loc[0, attribute]

        return ''

    def bidscoiner(self, session: Path, bidsmap: BidsMap, bidsses: Path) -> None:
        """
        The bidscoiner plugin to convert the session Presentation source-files into BIDS-valid NIfTI-files in the
        corresponding bids session-folder

        :param session: The full-path name of the subject/session source folder
        :param bidsmap: The full mapping heuristics from the bidsmap YAML-file
        :param bidsses: The full-path name of the BIDS output `sub-/ses-` folder
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
            scans_table = pd.DataFrame(columns=['acq_time'], dtype='str').rename_axis('filename')

        # Collect the different Presentation source files for all files in the session
        for sourcefile in session.rglob('*'):

            # Check if the sourcefile is of a supported dataformat
            if is_hidden(sourcefile.relative_to(session)) or not (dataformat := self.has_support(sourcefile)):
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
            target     = (outfolder/bidsname).with_suffix('.tsv')

            # Check if the bidsname is valid
            bidstest = (Path('/')/subid/sesid/run.datatype/bidsname).with_suffix('.tsv').as_posix()
            isbids   = BIDSValidator().is_bids(bidstest)
            if not isbids and not bidsignore:
                LOGGER.warning(f"The '{bidstest}' output name did not pass the bids-validator test")

            # Check if file already exists (-> e.g. when a static runindex is used)
            if target.is_file():
                LOGGER.warning(f"{target} already exists and will be deleted -- check your results carefully!")
                target.unlink()

            # Save the sourcefile as a BIDS NIfTI file and write out provenance logging data
            run.eventsparser().write(target)
            bids.bidsprov(bidsses, sourcefile, run, [target] if target.is_file() else [])

            # Check the output
            if not target.is_file():
                LOGGER.error(f"Output file not found: {target}")
                continue

            # Load/copy over the source metadata
            sidecar  = target.with_suffix('.json')
            metadata = bids.poolmetadata(run.datasource, sidecar, run.meta, options.get('meta', []))
            if metadata:
                with sidecar.open('w') as json_fid:
                    json.dump(metadata, json_fid, indent=4)

            # Add an entry to the scans_table
            try:
                acq_time = dateutil.parser.parse(run.datasource.attribute('Logfile written') or run.datasource.attribute('date'))
                if bidsmap.options.get('anon', 'y') in ('y', 'yes'):
                    acq_time = acq_time.replace(year=1925, month=1, day=1)  # Privacy protection (see BIDS specification)
                acq_time = acq_time.isoformat()
            except Exception as date_error:
                LOGGER.warning(f"Could not parse the acquisition time from: {sourcefile}\n{date_error}")
                acq_time = pd.NA
            scans_table.loc[target.relative_to(bidsses).as_posix(), 'acq_time'] = acq_time

        if not runid:
            LOGGER.info(f"--> No {__name__} sourcedata found in: {session}")
            return

        # Write the scans_table to disk
        LOGGER.verbose(f"Writing data to: {scans_tsv}")
        scans_table.replace('','n/a').to_csv(scans_tsv, sep='\t', encoding='utf-8', na_rep='n/a')


class PresentationEvents(EventsParser):
    """Parser for NeuroBS Presentation logfiles"""

    def __init__(self, sourcefile: Path, _data: dict, options: dict):
        """
        Reads the event table from the Presentation log file

        :param sourcefile:  The full filepath of the log file
        :param _data:       The run['events'] data (from a bidsmap)
        :param options:     The plugin options
        """

        super().__init__(sourcefile, _data, options)

        # Count the number of header lines, i.e. until the line starts with "Subject"
        header = 0
        with sourcefile.open('r') as fid:
            for header, line in enumerate(fid):
                if line.startswith('Subject'): break
        if not header:
            LOGGER.warning(f"No 'event' table found in: {sourcefile}")

        # Read the log-tables from the Presentation log file
        self._sourcetable = pd.read_csv(self.sourcefile, sep='\t', skiprows=header, skip_blank_lines=True) if self.sourcefile.is_file() else pd.DataFrame()
        """The Presentation log-tables (https://www.neurobs.com/pres_docs/html/03_presentation/07_data_reporting/01_logfiles/index.html)"""
        self._sourcecols  = self._sourcetable.columns
        """Store the original column names"""

    @property
    def logtable(self) -> pd.DataFrame:
        """Returns a Presentation log-table"""

        df = self._sourcetable
        if not (nrows := len(df)):
            return df

        # Get the row indices to slice the event, stimulus, video or survey table
        stimulus_header = (df.iloc[:, 0] == 'Event Type').idxmax() or nrows
        video_header    = (df.iloc[:, 0] == 'filename').idxmax() or nrows
        survey_header   = (df.iloc[:, 0] == 'Time').idxmax() or nrows

        # Get the first and last row index of the table of interest
        name = self.parsing.get('name', ['event', 'stimulus', 'video', 'survey', 0])
        try:
            df.columns = self._sourcecols
            if name[name[-1]] == 'event':
                begin = 0
                end   = min(stimulus_header, video_header, survey_header)
            elif name[name[-1]] == 'stimulus':
                df.columns = df.iloc[stimulus_header]
                begin = stimulus_header + 1
                end   = min(video_header, survey_header)
            elif name[name[-1]] == 'video':
                df.columns = df.iloc[video_header]
                begin = video_header + 1
                end   = survey_header
            elif name[name[-1]] == 'survey':
                df.columns = df.iloc[survey_header]
                begin = survey_header + 1
                end   = nrows
            else:
                begin = 0
                end   = nrows
                LOGGER.error(f"NOT IMPLEMENTED TABLE: {name[name[-1]]}")
        except IndexError as parseerror:
            LOGGER.warning(f"Could not parse the {name[name[-1]]} table from: {self.sourcefile}\n{parseerror}")
            return pd.DataFrame()

        # Ensure unique column names by appending suffixes to duplicate names
        df.columns = self.rename_duplicates(df.columns)

        # Return the sliced the table
        LOGGER.bcdebug(f"Slicing '{name[name[-1]]}' table {df.shape} -> sourcetable[{begin}:{end}]")
        return df.iloc[begin:end]


class PsychopyEvents(EventsParser):
    """Parser for Psychopy logfiles"""

    def __init__(self, sourcefile: Path, _data: dict, options: dict):
        """
        Reads the event table from the Psychopy log file

        :param sourcefile:  The full filepath of the log file
        :param _data:       The run['events'] data (from a bidsmap)
        :param options:     The plugin options
        """

        super().__init__(sourcefile, _data, options)
        sourcefile = self.sourcefile

        # Read log-tables from Psychopy psydat files. = WIP
        if sourcefile.suffix in ('.psydat',) and find_spec('psychopy'):
            try:
                psydat = fromFile(sourcefile)
                if psydat.extraInfo.get('psychopyVersion') != psychopy.getVersion():
                    LOGGER.warning(f"Incompatible PsychoPy versions may cause errors. You have installed version {psychopy.getVersion()}, but the data has version {psydat.extraInfo.get('psychopyVersion')}")
                psydat.saveAsWideText(widetext := Path(f"{sourcefile.name}_tmp.tsv"))
                self._sourcetable = pd.read_csv(widetext, sep=None, engine='python', skip_blank_lines=True, encoding='utf-8-sig') if self.sourcefile.is_file() else pd.DataFrame()
                widetext.unlink()
            except Exception as error:
                LOGGER.error(f"Could not parse the input table from: {sourcefile}\n{error}")
                self._sourcetable = pd.DataFrame()

        elif sourcefile.suffix in ('.csv', '.tsv'):
            self._sourcetable = pd.read_csv(self.sourcefile, sep=None, engine='python', skip_blank_lines=True, encoding='utf-8-sig') if self.sourcefile.is_file() else pd.DataFrame()

        else:
            LOGGER.debug(f"Cannot read/parse {sourcefile}")
            self._sourcetable = pd.DataFrame()

    @property
    def logtable(self) -> pd.DataFrame:
        """Returns the Psychopy log-table"""

        # TODO: make some sort of pivot table
        df = self._sourcetable  #.pivot_table(values='event', columns='filename', index='time', aggfunc='count')

        # Ensure unique column names by appending suffixes to duplicate names
        df.columns = self.rename_duplicates(df.columns)

        return df
