"""Base classes for the pre-installed plugins + IO helper functions"""

import logging
import re
import pandas as pd
import dateutil.parser
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Union, Iterable, List
from bidscoin import is_hidden
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from bidscoin.bids import BidsMap, DataSource       # = Circular import

LOGGER = logging.getLogger(__name__)


class PluginInterface(ABC):
    """Base interface class for plugins"""

    def test(self, options) -> int:
        """
        Performs a plugin test

        :param options: A dictionary with the plugin options, e.g. taken from the bidsmap.plugins[__name__]
        :return:        The errorcode: 0 for successful execution, 1 for general plugin errors, etc
        """

        LOGGER.info(f"The {__name__} plugin test function is not implemented")

        return 0

    @abstractmethod
    def has_support(self, sourcefile: Path, dataformat: str) -> str:
        """
        This plugin function assesses whether a sourcefile is of a supported dataformat

        :param sourcefile:  The sourcefile that is assessed
        :param dataformat:  The requested dataformat (optional requirement)
        :return:            The name of the supported dataformat of the sourcefile. This name should
                            correspond to the name of a dataformat section in the bidsmap
        """

    @abstractmethod
    def get_attribute(self, dataformat, sourcefile: Path, attribute: str, options: dict) -> Union[str, int, float, list]:
        """
        This plugin supports reading attributes from DICOM and PAR dataformats

        :param dataformat:  The bidsmap-dataformat of the sourcefile, e.g. DICOM of PAR
        :param sourcefile:  The sourcefile from which the attribute value should be read
        :param attribute:   The attribute key for which the value needs to be retrieved
        :param options:     A dictionary with the plugin options, e.g. taken from the bidsmap.plugins['nibabel2bids']
        :return:            The retrieved attribute value
        """

    def personals(self, bidsmap: 'BidsMap', datasource: 'DataSource') -> dict:
        """
        Collects personal data from a datasource to populate the participants.tsv file. See code for ad hoc age/sex
        encoding corrections

        :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
        :param datasource:  The data source from which (personal) dynamic values are read
        :return:            A dictionary with the personal data (e.g. age or sex)
        """

        personals = {}
        for key, item in bidsmap.dataformat(datasource.dataformat).participant.items():
            if key in ('participant_id', 'session_id'):
                continue
            else:
                personals[key] = datasource.dynamicvalue(item.get('value'), cleanup=False, runtime=True)

            # Perform ad hoc age encoding corrections (-> DICOM/Twix PatientAge: nnnD, nnnW, nnnM or nnnY)
            if key == 'age' and personals['age'] and isinstance(personals['age'], str):
                age = personals['age']
                try:
                    if '-' in age:      # -> Pfile: rhr_rh_scan_date - rhe_dateofbirth
                        scandate, dateofbirth = age.split('-', 1)
                        age = dateutil.parser.parse(scandate) - dateutil.parser.parse(dateofbirth)
                        age = str(age.days) + 'D'
                    if   age.endswith('D'): age = float(age.rstrip('D')) / 365.2524
                    elif age.endswith('W'): age = float(age.rstrip('W')) / 52.1775
                    elif age.endswith('M'): age = float(age.rstrip('M')) / 12
                    elif age.endswith('Y'): age = float(age.rstrip('Y'))
                    if bidsmap.options.get('anon','y') in ('y','yes'):
                        age = int(float(age))
                    personals['age'] = str(age)             # Or better keep it as int/float?
                except Exception as exc:
                    LOGGER.warning(f"Could not parse '{personals['age']}' as 'age' from: {datasource}\n{exc}")

            # Perform add hoc sex encoding corrections (-> Pfile rhe_patsex: 0=O, 1=M, 2=F)
            elif key == 'sex':
                if   personals['sex'] == '0': personals['sex'] = 'O'
                elif personals['sex'] == '1': personals['sex'] = 'M'
                elif personals['sex'] == '2': personals['sex'] = 'F'

        return personals

    def bidsmapper(self, session: Path, bidsmap_new: 'BidsMap', bidsmap_old: 'BidsMap', template: 'BidsMap') -> None:
        """
        The goal of this plugin function is to identify all the different runs in the session and update the
        bidsmap if a new run is discovered

        :param session:     The full-path name of the subject/session raw data source folder
        :param bidsmap_new: The new study bidsmap that we are building
        :param bidsmap_old: The previous study bidsmap that has precedence over the template bidsmap
        :param template:    The template bidsmap with the default heuristics
        """

        # See for every source file in the session if we already discovered it or not
        sourcefiles = session.rglob('*')
        if not sourcefiles:
            LOGGER.info(f"No {__name__} sourcedata found in: {session}")
        for sourcefile in sourcefiles:

            # Check if the sourcefile is of a supported dataformat
            if is_hidden(sourcefile.relative_to(session)) or not (dataformat := self.has_support(sourcefile, dataformat='')):
                continue

            # See if we can find a matching run in the old bidsmap
            run, oldmatch = bidsmap_old.get_matching_run(sourcefile, dataformat)

            # If not, see if we can find a matching run in the template
            if not oldmatch:
                run, _ = template.get_matching_run(sourcefile, dataformat)

            # See if we have a proper matching run and if we already put it in the new bidsmap
            if run.dataformat and not bidsmap_new.exist_run(run):

                # Communicate with the user if the run was not present in bidsmap_old or in template, i.e. that we found a new sample
                if not oldmatch:
                    LOGGER.info(f"Discovered sample: {run.datasource}")
                else:
                    LOGGER.bcdebug(f"Known sample: {run.datasource}")

                # Copy the filled-in run over to the new bidsmap
                bidsmap_new.insert_run(run)

            else:
                LOGGER.bcdebug(f"Existing/duplicate sample: {run.datasource}")

    @abstractmethod
    def bidscoiner(self, session: Path, bidsmap: 'BidsMap', bidsses: Path) -> None:
        """
        The bidscoiner plugin to convert the session Nibabel source-files into BIDS-valid NIfTI-files in the
        corresponding bids session-folder

        :param session:     The full-path name of the subject/session source folder
        :param bidsmap:     The full mapping heuristics from the bidsmap YAML-file
        :param bidsses:     The full-path name of the BIDS output `sub-/ses-` folder
        :return:            Nothing (i.e. personal data is not available)
        """


class EventsTime:
    """An events['time'] dictionary with 'start', 'cols' and 'unit' values"""
    def __init__(self, data: dict):

        # Create a data dictionary with all required event.time keys
        for key, val in {'cols': [], 'unit': 1, 'start': {}}.items():
            if key not in data: data[key] = val
        self._data = data

    def __repr__(self):

        return (f"{self.__class__}\n"
                f"Time.cols:\t{self.cols}\n"
                f"Time.unit:\t{self.unit}\n"
                f"Time.start:\t{self.start}")

    @property
    def cols(self) -> list:
        return self._data['cols']

    @cols.setter
    def cols(self, value: list):
        self._data['cols'] = value

    @property
    def unit(self) -> float:
        return self._data['unit']

    @unit.setter
    def unit(self, value: float):
        self._data['unit'] = value

    @property
    def start(self) -> dict:
        return self._data['start']

    @start.setter
    def start(self, value: dict):
        self._data['start'] = value


class EventsParser(ABC):
    """Base parser for stimulus presentation logfiles"""

    def __init__(self, sourcefile: Path, data: dict, options: dict):
        """
        Sets all required attributes

        :param sourcefile:  The full filepath of the raw log file
        :param data:        The run['events'] data (from a bidsmap)
        :param options:     The plugin options
        """

        # Create a data dictionary with all required events keys
        data = data or {}
        for key, val in {'parsing': {}, 'columns': [{'onset':''}, {'duration':''}], 'rows': [{}], 'time': {}}.items():
            if key not in data: data[key] = val
        self._data = data
        self.time                       # Initialize all required data['time'] keys

        self.sourcefile = Path(sourcefile)
        self.options    = options

    def __repr__(self):

        return (f"{self.__class__}\n"
                f"Path:\t\t{self.sourcefile}\n"
                f"Columns:\t{self.columns}\n"
                f"Rows:\t{self.rows}\n"
                f"{repr(self.time)}")

    def __str__(self):

        return f"{self.sourcefile}"

    @abstractmethod
    def logtable(self) -> pd.DataFrame:
        """Returns the source logging data"""

    def eventstable(self) -> pd.DataFrame:
        """Returns the target events.tsv data"""

        # Check the parser's data structure
        logtable = self.logtable()
        if not len(logtable):
            return pd.DataFrame(columns=['onset', 'duration'])
        if not self.isvalid:
            pass

        df = logtable.copy()                # Ensure we do not change the source data

        # Convert the timing values to seconds (with maximally 4 digits after the decimal point)
        timecols     = list(set(col for col in df for pattern in self.time.cols if re.fullmatch(pattern, col)))
        df[timecols] = (df[timecols].apply(pd.to_numeric, errors='coerce') / self.time.unit).round(4)

        # Take the logtable columns of interest and from now on use the BIDS column names
        df         = df.loc[:, [sourcecol for item in self.columns for sourcecol in item.values() if sourcecol in df]]
        df.columns = [eventscol for item in self.columns for eventscol, sourcecol in item.items() if sourcecol in df]
        if 'onset'    not in df: df.insert(0, 'onset',    None)
        if 'duration' not in df: df.insert(1, 'duration', None)

        # Set the clock at zero at the start of the experiment
        if self.time.start:
            start = pd.Series(True, index=df.index)
            for column, value in self.time.start.items():
                if column in logtable:
                    start &= (logtable[column].astype(str) == str(value))
            if start.any():
                LOGGER.bcdebug(f"Resetting clock offset: {df['onset'][start].iloc[0]}")
                df['onset'] -= df['onset'][start].iloc[0]                   # Take the time of the first occurrence as zero

        # Loop over the row groups to filter/edit the rows
        rows = pd.Series(len(self.rows) == 0, index=df.index)               # All rows are True if no row expressions were specified
        for group in self.rows:                                             # With a group the expressions are AND between groups they are OR

            rowgroup = pd.Series(True, index=df.index)
            for column, pattern in (group.get('condition') or {}).items():

                if column not in logtable:
                    LOGGER.bcdebug(f"Unknown condition column: {column}")
                    continue

                # Get the rows that match the expression, i.e. make them True
                rowgroup &= logtable[column].astype(str).str.fullmatch(str(pattern))

            # Write the value(s) of the matching rows
            for colname, values in (group.get('cast') or {}).items():
                df.loc[rowgroup, colname] = values

            # Add the matching rows to the grand rows group
            rows |= rowgroup

        return df.loc[rows].sort_values(by='onset', key=lambda x: pd.to_numeric(x, errors='coerce'))

    @property
    def parsing(self) -> dict:
        """A dictionary with settings, e.g. to parse the source table from the log file"""
        return self._data['parsing']

    @parsing.setter
    def parsing(self, value: dict):
        self._data['parsing'] = value

    @property
    def columns(self) -> list[dict]:
        """List with mappings for the column names of the eventstable"""
        return self._data['columns']

    @columns.setter
    def columns(self, value: list[dict]):
        self._data['columns'] = value

    @property
    def rows(self) -> list[dict]:
        """List with fullmatch regular expression dictionaries that yield row sets (conditions) in the eventstable"""
        return self._data['rows']

    @rows.setter
    def rows(self, value: list[dict]):
        self._data['rows'] = value

    @property
    def time(self) -> EventsTime:
        return EventsTime(self._data['time'])

    @property
    def isvalid(self) -> bool:
        """Check the EventsParser data structure"""

        def is_float(s):
            try:
                float(s)
                return True
            except (ValueError, TypeError):
                return False

        if not (valid := len(self.columns) >= 2):
            LOGGER.warning(f"Events table must have at least two columns, got {len(self.columns)} instead\n{self}")
            return False

        if (key := [*self.columns[0].keys()][0] if self.columns[0] else '') != 'onset':
            LOGGER.warning(f"First events column must be named 'onset', got '{key}' instead\n{self}")
            valid = False

        if (key := [*self.columns[1].keys()][0] if self.columns[1] else '') != 'duration':
            LOGGER.warning(f"Second events column must be named 'duration', got '{key}' instead\n{self}")
            valid = False

        elif not is_float(self.time.unit):
            LOGGER.warning(f"Time conversion factor must be a float, got '{self.time.unit}' instead\n{self}")
            valid = False

        # Check if the logtable has existing and unique column names
        columns = self.logtable().columns
        for name in set([name for item in self.columns for name in item.values()] +
                        [name for item in self.rows for name in (item.get('condition') or {}).keys()] + [*self.time.start.keys()]):
            if name and name not in columns:
                LOGGER.info(f"Column '{name}' not found in the input table parsed from {self}")
                valid = False
        if columns.duplicated().any():
            LOGGER.warning(f"Duplicate columns found: {columns}\n{self}")
            valid = False

        return valid

    def write(self, targetfile: Path):
        """Write the eventstable to a BIDS events.tsv file"""

        LOGGER.verbose(f"Saving events to: {targetfile}")
        self.eventstable().to_csv(targetfile, sep='\t', index=False)

    def rename_duplicates(self, columns: Iterable[str]) -> List[str]:
        """
        Ensure unique column names by renaming columns with NaN or empty names, and by appending suffixes to duplicate names

        :param columns: The columns with potential duplicates to rename
        :return:        The renamed columns
        """

        newcols = []                                # The new column names
        dup_idx = {}                                # The duplicate index number
        for i, column in enumerate(columns):
            if pd.isna(column) or column == '':     # Check if the column name is NaN or an empty string
                newcols.append(new_col := f"Unnamed: {i}")
                LOGGER.bcdebug(f"Renaming empty column name at index {i}: {column} -> {new_col}")
            elif column in dup_idx:                 # If duplicate, append the index number
                dup_idx[column] += 1
                newcols.append(new_col := f"{column}.{dup_idx[column]}")
                LOGGER.bcdebug(f"Renaming duplicate column name: {column} -> {new_col}")
            else:                                   # First occurrence of the column name, add it to dup_idx
                dup_idx[column] = 0
                newcols.append(column)

        # Just make sure we don't have duplicates anymore
        if len(newcols) != len(set(newcols)):
            LOGGER.bcdebug(f"--> Renaming de-duplicated columns: {newcols}")
            newcols = self.rename_duplicates(newcols)

        return newcols
