"""Pre-installed plugins"""

import logging
import copy
import pandas as pd
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List

LOGGER = logging.getLogger(__name__)


class EventsParser(ABC):
    """Parser for stimulus presentation logfiles"""

    def __init__(self, sourcefile: Path, eventsdata: dict, options: dict):
        """
        Reads the events table from the events logfile

        :param sourcefile:  The full filepath of the raw logfile
        :param eventsdata:  The run['events'] data (from a bidsmap)
        :param options:     The plugin options
        """

        self.sourcefile = sourcefile
        self._data      = eventsdata
        self.options    = options

    def __repr__(self):

        return (f"{self.__class__}\n"
                f"Path:\t\t{self.sourcefile}\n"
                f"Time.cols:\t{self.time.get('cols')}\n"
                f"Time.unit:\t{self.time.get('unit')}\n"
                f"Time.start:\t{self.time.get('start')}\n"
                f"Columns:\t{self.columns}\n"
                f"Rows:\t{self.rows}")

    def __str__(self):

        return f"{self.sourcefile}"

    @property
    @abstractmethod
    def logtable(self) -> pd.DataFrame:
        """Returns the source logging data"""

    @property
    def eventstable(self) -> pd.DataFrame:
        """Returns the target events.tsv data"""

        # Check the parser's data structure
        if not self.isvalid:
            return pd.DataFrame()

        df = copy.deepcopy(self.logtable)

        # Convert the timing values to seconds (with maximally 4 digits after the decimal point)
        df[self.time['cols']] = (df[self.time['cols']].apply(pd.to_numeric, errors='coerce') / self.time['unit']).round(4)

        # Take the logtable columns of interest and from now on use the BIDS column names
        df         = df.loc[:, [sourcecol for item in self.columns for sourcecol in item.values() if sourcecol]]
        df.columns = [eventscol for item in self.columns for eventscol, sourcecol in item.items() if sourcecol]

        # Set the clock at zero at the start of the experiment
        if self.time.get('start'):
            start = pd.Series([True] * len(df))
            for column, value in self.time['start'].items():
                start &= (self.logtable[column].astype(str) == str(value)).values
            if start.any():
                LOGGER.bcdebug(f"Resetting clock offset: {df['onset'][start.values].iloc[0]}")
                df['onset'] -= df['onset'][start.values].iloc[0]  # Take the time of the first occurrence as zero

        # Loop over the row groups to filter/edit the rows
        rows = pd.Series([len(self.rows) == 0] * len(df)).astype(bool)  # Boolean series with True values if no row expressions were specified
        for group in self.rows:

            for column, regex in group['include'].items():

                # Get the rows that match the expression, i.e. make them True
                rowgroup = self.logtable[column].astype(str).str.fullmatch(str(regex))

                # Add the matching rows to the grand rows group
                rows |= rowgroup.values

                # Write the value(s) of the matching rows
                for colname, values in (group.get('cast') or {}).items():
                    df.loc[rowgroup, colname] = values

        return df.loc[rows.values].sort_values(by='onset')

    @property
    def columns(self) -> List[dict]:
        """List with mappings for the column names of the eventstable"""
        return self._data.get('columns') or []

    @columns.setter
    def columns(self, value: List[dict]):
        self._data['columns'] = value

    @property
    def rows(self) -> List[dict]:
        """List with fullmatch regular expression dictionaries that yield row sets in the eventstable"""
        return self._data.get('rows') or []

    @rows.setter
    def rows(self, value: List[dict]):
        self._data['rows'] = value

    @property
    def time(self) -> dict:
        """A dictionary with 'start', 'cols' and 'unit' values"""
        return self._data.get('time') or {}

    @time.setter
    def time(self, value: dict):
        self._data['time'] = value

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

        if (key := [*self.columns[0].keys()][0]) != 'onset':
            LOGGER.warning(f"First events column must be named 'onset', got '{key}' instead\n{self}")
            valid = False

        if (key := [*self.columns[1].keys()][0]) != 'duration':
            LOGGER.warning(f"Second events column must be named 'duration', got '{key}' instead\n{self}")
            valid = False

        if len(self.time.get('cols',[])) < 2:
            LOGGER.warning(f"Events table must have at least two timecol items, got {len(self.time.get('cols',[]))} instead\n{self}")
            return False

        elif not is_float(self.time.get('unit')):
            LOGGER.warning(f"Time conversion factor must be a float, got '{self.time.get('unit')}' instead\n{self}")
            valid = False

        # Check if the logtable has existing and unique column names
        columns = self.logtable.columns
        for name in set([name for item in self.columns for name in item.values()] + [name for item in self.rows for name in item['include'].keys()] +
                        [*self.time.get('start',{}).keys()] + self.time.get('cols',[])):
            if name and name not in columns:
                LOGGER.warning(f"Column '{name}' not found in the event table of {self}")
                valid = False
        if columns.duplicated().any():
            LOGGER.warning(f"Duplicate columns found: {columns}\n{self}")
            valid = False

        return valid

    def write(self, targetfile: Path):
        """Write the eventstable to a BIDS events.tsv file"""

        self.eventstable.to_csv(targetfile, sep='\t', index=False)

