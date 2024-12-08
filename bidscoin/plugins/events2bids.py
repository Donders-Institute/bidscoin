"""The events2bids plugin converts neurobs Presentation logfiles to event.tsv files"""

import logging
import json
import pandas as pd
from typing import Union
from bids_validator import BIDSValidator
from pathlib import Path
from bidscoin import bids
from bidscoin.plugins import PluginInterface, EventsParser
from bidscoin.bids import BidsMap, DataFormat, is_hidden, Plugin
# TODO: from convert_eprime.utils import ..

LOGGER = logging.getLogger(__name__)

# The default/fallback options that are set when installing/using the plugin
OPTIONS = Plugin({'table': 'event', 'skiprows': 3, 'meta': ['.json', '.tsv']})  # The file extensions of the equally named metadata sourcefiles that are copied over as BIDS sidecar files


class Interface(PluginInterface):

    def has_support(self, file: Path, dataformat: Union[DataFormat, str]='') -> str:
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

    def get_attribute(self, dataformat: Union[DataFormat, str], sourcefile: Path, attribute: str, options) -> Union[str, int, float, list]:
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

    def bidscoiner(self, session: Path, bidsmap: BidsMap, bidsses: Path) -> None:
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
        self._sourcetable = pd.read_csv(self.sourcefile, sep='\t', skiprows=options.get('skiprows',3), skip_blank_lines=True)
        """The Presentation log-tables (https://www.neurobs.com/pres_docs/html/03_presentation/07_data_reporting/01_logfiles/index.html)"""
        self._sourcecols  = self._sourcetable.columns
        """Store the original column names"""

    @property
    def logtable(self) -> pd.DataFrame:
        """Returns a Presentation log-table"""

        df              = self._sourcetable
        nrows           = len(df)
        stimulus_header = (df.iloc[:, 0] == 'Event Type').idxmax() or nrows
        video_header    = (df.iloc[:, 0] == 'filename').idxmax() or nrows
        survey_header   = (df.iloc[:, 0] == 'Time').idxmax() or nrows

        # Get the row indices to slice the event, stimulus, video or survey table
        df.columns = self._sourcecols
        if self.options['table'] == 'event':
            begin = 0
            end   = min(stimulus_header, video_header, survey_header)
        elif self.options['table'] == 'stimulus':
            df.columns = df.iloc[stimulus_header]
            begin = stimulus_header + 1
            end   = min(video_header, survey_header)
        elif self.options['table'] == 'video':
            df.columns = df.iloc[video_header]
            begin = video_header + 1
            end   = survey_header
        elif self.options['table'] == 'survey':
            df.columns = df.iloc[survey_header]
            begin = survey_header + 1
            end   = nrows
        else:
            begin = 0
            end   = nrows
            LOGGER.error(f"NOT IMPLEMENTED TABLE: {self.options['table']}")

        # Ensure unique column names by renaming columns with NaN or empty names, and by appending suffixes to duplicate names
        cols = []                               # The new column names
        dupl = {}                               # The duplicate index number
        for i, col in enumerate(df.columns):
            if pd.isna(col) or col == '':       # Check if the column name is NaN or an empty string
                cols.append(new_col := f"unknown_{i}")
                LOGGER.info(f"Renaming empty column name at index {i}: {col} -> {new_col}")
            elif col in dupl:                   # If duplicate, append the index number
                dupl[col] += 1
                cols.append(new_col := f"{col}_{dupl[col]}")
                LOGGER.info(f"Renaming duplicate column name: {col} -> {new_col}")
            else:                               # First occurrence of the column name, add it to dupl
                dupl[col] = 0
                cols.append(col)
        df.columns = cols

        # Return the sliced the table
        LOGGER.bcdebug(f"Slicing '{self.options['table']}{df.shape}' sourcetable[{begin}:{end}]")
        return df.iloc[begin:end]
