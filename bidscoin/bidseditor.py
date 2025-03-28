#!/usr/bin/env python3
"""A BIDScoin application with a graphical user interface for editing the bidsmap (See also cli/_bidseditor.py)"""

import sys
import logging
import copy
import webbrowser
import ast
import re
import json
import csv
import nibabel as nib
import pandas as pd
import random
from bids_validator import BIDSValidator
from typing import Union
from pydicom import dcmread, datadict, config
from pathlib import Path
from functools import partial
from PyQt6.QtCore import Qt, QAbstractTableModel
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtGui import QAction, QFileSystemModel
from PyQt6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QDialogButtonBox, QTreeView, QHBoxLayout, QVBoxLayout, QLabel, QDialog, QInputDialog,
                             QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QTextBrowser, QPushButton, QComboBox, QTableView)
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    sys.path.append(str(Path(__file__).parents[1]))
from bidscoin import bcoin, bids, bidsversion, check_version, trackusage, bidsmap_template, DEBUG, __version__
from bidscoin.bids import BidsMap, RunItem, DataType
from bidscoin.utilities import is_dicomfile, is_parfile

config.INVALID_KEY_BEHAVIOR = 'IGNORE'              # Ignores warnings such as "UserWarning: Invalid value 'filepath' used with the 'in' operator: must be an element tag as a 2-tuple or int, or an element"
config.IGNORE               = 0 if DEBUG else 1     # Ignores warnings such as "The value length (68) exceeds the maximum length of 64 allowed for VR LO" and "Invalid value for VR UI: [..]"

ROW_HEIGHT       = 22
BIDSCOIN_LOGO    = Path(__file__).parent/'bidscoin_logo.png'
BIDSCOIN_ICON    = Path(__file__).parent/'bidscoin.ico'
RIGHTARROW       = Path(__file__).parent/'rightarrow.png'
MAIN_HELP_URL    = f"https://bidscoin.readthedocs.io/en/{__version__.split('+')[0]}"
HELP_URL_DEFAULT = f"https://bids-specification.readthedocs.io/en/v{bidsversion()}"
HELP_URLS        = {
    'anat': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#anatomy-imaging-data",
    'dwi' : f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#diffusion-imaging-data",
    'fmap': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data",
    'func': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#task-including-resting-state-imaging-data",
    'perf': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#arterial-spin-labeling-perfusion-data",
    'eeg' : f"{HELP_URL_DEFAULT}/04-modality-specific-files/03-electroencephalography.html",
    'ieeg': f"{HELP_URL_DEFAULT}/04-modality-specific-files/04-intracranial-electroencephalography.html",
    'beh' : f"{HELP_URL_DEFAULT}/04-modality-specific-files/07-behavioral-experiments.html",
    'pet' : f"{HELP_URL_DEFAULT}/04-modality-specific-files/09-positron-emission-tomography.html",
    # self.unknowndatatypes: HELP_URL_DEFAULT,
    # self.ignoredatatypes : HELP_URL_DEFAULT
}

TOOLTIP_BIDSCOIN = f"""BIDScoin
version:    Used to check for version conflicts 
bidsignore: List of data types that are added to the .bidsignore file,
            e.g. extra_data/;myfile.txt;yourfile.csv
subprefix:  The subject prefix used in the source data folders (e.g. "Pt" is the subprefix if subject folders are named "Pt018", "Pt019", ...)
sesprefix:  The session prefix used in the source data folders (e.g. "M_" is the subprefix if session folders are named "M_pre", "M_post", ...)
anon:       Set this anonymization flag to 'y' to round off age and to discard acquisition date from the metadata
For more information see: {MAIN_HELP_URL}/options.html"""

TOOLTIP_DCM2NIIX = """dcm2niix2bids
command: Command to run dcm2niix from the terminal, such as:
    dcm2niix (if the executable is already present on your path)
    module add dcm2niix/v1.0.20210317; dcm2niix (if you use a module system)
    PATH=/opt/dcm2niix/bin:$PATH; dcm2niix (prepend the path to your executable)
    /opt/dcm2niix/bin/dcm2niix (specify the fullpath to the executable)
    C:\\"Program Files"\\dcm2niix\\dcm2niix.exe (use quotes to deal with whitespaces in your fullpath)
    
args: Argument string that is passed to dcm2niix. Click [Test] and see the terminal output for usage
    Tip: SPM users may want to use '-z n', which produces unzipped NIfTI's
    
meta: The file extensions of the associated / equally named (meta)data source files that are copied over as
    BIDS (sidecar) files, such as ['.json', '.tsv', '.tsv.gz']. You can use this to enrich json sidecar files,
    or add data that is not supported by this plugin

fallback: Appends unhandled dcm2niix suffixes to the `acq` label if 'y' (recommended, else the suffix data is discarded)"""


class MyQTableModel(QAbstractTableModel):
    """Custom model to connect a Pandas DataFrame with QTableView"""

    def __init__(self, parent, df: pd.DataFrame):
        super().__init__(parent)
        self._df = df

    def rowCount(self, parent=None):
        return len(self._df)

    def columnCount(self, parent=None):
        return len(self._df.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:             # Display Data
            return str(self._df.iloc[index.row(), index.column()])
        if role == Qt.ItemDataRole.ForegroundRole:
            return QtGui.QColor('gray')                     # Set all cells' foreground to gray
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:    # Column Headers
                return str(self._df.columns[section])
        return None

    def update_df(self, new_df):
        """Update DataFrame and notify view"""
        self.beginResetModel()
        self._df = new_df
        self.endResetModel()                                # Notify Qt that data has changed


class MyQTableView(QTableView):

    def __init__(self, parent, df: pd.DataFrame):
        super().__init__(parent)

        self.setModel(MyQTableModel(self, df))
        self.setSelectionMode(QTableView.SelectionMode.NoSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.update_table()

    def update_table(self, df: pd.DataFrame=None):
        """Updates the table data and resize the columns based on first 20 rows & header labels"""

        model: MyQTableModel = self.model()
        if df is not None:
            model.update_df(df)

        num_rows = min(20, model.rowCount())

        for col in range(model.columnCount()):

            max_width = 0  # Track the max width required

            # Measure the width of the header label
            header_text = model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            max_width   = max(max_width, self.fontMetrics().horizontalAdvance(header_text))

            # Measure the width of the first 20 row values
            for row in range(num_rows):
                cell_text = str(model.data(model.index(row, col), Qt.ItemDataRole.DisplayRole))
                max_width = max(max_width, self.fontMetrics().horizontalAdvance(cell_text))

            self.horizontalHeader().resizeSection(col, max_width + 10)  # +10 for padding


class MyQTable(QTableWidget):

    def __init__(self, parent, min_vsize: bool=True, ncols: int=0, nrows: int=0):
        """A clean QTableWidget without headers, with some custom default (re)size policies"""

        super().__init__(parent)

        self.setAlternatingRowColors(False)
        self.setShowGrid(False)

        self.horizontalHeader().setVisible(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        if min_vsize:
            self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        else:
            self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        if ncols:
            self.setColumnCount(ncols)
        if nrows:
            self.setRowCount(nrows)


class MyQTableItem(QTableWidgetItem):

    def __init__(self, value: Union[str,Path,int]='', editable: bool=True):
        """A QTableWidgetItem that is editable or not, + a safe setText() method"""

        super().__init__()

        self.setText(value)
        self.editable = editable
        if editable:
            self.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
        else:
            self.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.setForeground(QtGui.QColor('gray'))

    def setText(self, value: Union[str,Path,int]):
        """Sets value as normal text (i.e. converts int/Path->str and None->'')"""

        if value is None:
            value = ''
        elif isinstance(value, dict):
            value = dict(value)         # Convert OrderedDict to dict

        super().setText(str(value))


class MainWindow(QMainWindow):

    def __init__(self, bidsfolder: Path, input_bidsmap: BidsMap, template_bidsmap: BidsMap, datasaved: bool=False, reset: bool=False):

        # Set up the main window
        if not reset:
            super().__init__()
            self.setWindowIcon(QtGui.QIcon(str(BIDSCOIN_ICON)))
            self.__init_menu_statusbar__()

        if not input_bidsmap.dataformats and not input_bidsmap.filepath.is_file():
            filename, _ = QFileDialog.getOpenFileName(self, 'Open a bidsmap file', str(bidsfolder), 'YAML Files (*.yaml *.yml);;All Files (*)')
            if filename:
                input_bidsmap = BidsMap(Path(filename))
                if input_bidsmap.options:
                    template_bidsmap.options = input_bidsmap.options    # Always use the options of the input bidsmap
                    template_bidsmap.plugins = input_bidsmap.plugins    # Always use the plugins of the input bidsmap
            else:
                input_bidsmap = copy.deepcopy(template_bidsmap)
                input_bidsmap.delete_runs()

        # Make sure we do not try to add data samples to the provenance store (i.e. when using bidsmapper -s)
        input_bidsmap.store = {}

        # Keep track of the EditWindow status
        self.editwindow_opened: Union[str,None] = None
        """The provenance of the run-item that is opened in the EditWindow"""

        # Set the input data
        self.bidsfolder                  = Path(bidsfolder)
        """The folder where the bids data is / will be stored"""
        self.input_bidsmap               = input_bidsmap
        """The original/unedited bidsmap"""
        self.output_bidsmap              = copy.deepcopy(input_bidsmap)
        """The edited bidsmap"""
        self.template_bidsmap            = template_bidsmap
        """The bidsmap from which new data type run-items are taken"""
        self.datasaved                   = datasaved
        """True if data has been saved on disk"""
        self.dataformats                 = [dataformat.dataformat for dataformat in input_bidsmap.dataformats if input_bidsmap.dir(dataformat) and dataformat.dataformat]
        self.bidsignore: list[str]       = input_bidsmap.options['bidsignore']
        self.unknowndatatypes: list[str] = input_bidsmap.options['unknowntypes']
        self.ignoredatatypes: list[str]  = input_bidsmap.options['ignoretypes']

        # Set up the tabs, add the tables and put the bidsmap data in them
        self.participant_table  = {}
        self.samples_table      = {}
        """table columns: 0=index, 1=provenance.name, 2=datatype, 3=bidsname, 4=editbutton, 5=provenance"""
        self.options_label      = {}
        self.options_table      = {}
        self.ordered_file_index = {}
        """The mapping between the ordered provenance and an increasing file-index"""
        tabwidget = self.tabwidget = QtWidgets.QTabWidget()
        for dataformat in self.dataformats:
            self.__init_tab_dataformat__(dataformat)
        self.__init_tab_options__()
        self.__init_tab_filebrowser__()

        # Set datachanged = False only after all the tables are updated (which assigns datachanged = True)
        self.datachanged: bool = False
        """Keeps track of the bidsmap data status -> True if data has been edited"""

        # Set up the buttons
        buttonbox = QDialogButtonBox()
        buttonbox.setStandardButtons(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Reset | QDialogButtonBox.StandardButton.Help)
        buttonbox.helpRequested.connect(self.get_help)
        buttonbox.button(QDialogButtonBox.StandardButton.Help).setToolTip('Go to the online BIDScoin documentation')
        buttonbox.button(QDialogButtonBox.StandardButton.Save).setToolTip('Save the bidsmap to disk if you are satisfied with all the BIDS output names')
        buttonbox.button(QDialogButtonBox.StandardButton.Reset).setToolTip('Reset all the Options and BIDS mappings')
        buttonbox.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self.reset)
        buttonbox.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self.save_bidsmap)
        validatebutton = buttonbox.addButton('Validate', QDialogButtonBox.ButtonRole.ActionRole)
        validatebutton.setIcon(QtGui.QIcon.fromTheme('tools-check-spelling'))
        validatebutton.setToolTip('Test the run-items and bidsname of all normal runs in the study bidsmap (see terminal output)')
        validatebutton.clicked.connect(self.validate_runs)

        # Set up the main layout
        top_layout = QVBoxLayout()
        top_layout.addWidget(tabwidget)
        top_layout.addWidget(buttonbox)
        tabwidget.setCurrentIndex(0)
        centralwidget = QtWidgets.QWidget()
        centralwidget.setLayout(top_layout)
        self.setCentralWidget(centralwidget)

    def __init_menu_statusbar__(self):
        """Set up the menu and statusbar"""

        # Set the menus
        menubar  = QtWidgets.QMenuBar(self)
        menufile = QtWidgets.QMenu(menubar)
        menufile.setTitle('File')
        menubar.addAction(menufile.menuAction())
        menuhelp = QtWidgets.QMenu(menubar)
        menuhelp.setTitle('Help')
        menubar.addAction(menuhelp.menuAction())
        self.setMenuBar(menubar)

        # Set the file menu actions
        actionreset = QAction(self)
        actionreset.setText('Reset')
        actionreset.setStatusTip('Reset the bidsmap')
        actionreset.setShortcut('Ctrl+R')
        actionreset.triggered.connect(self.reset)
        menufile.addAction(actionreset)

        actionopen = QAction(self)
        actionopen.setText('Open')
        actionopen.setStatusTip('Open a new bidsmap from disk')
        actionopen.setShortcut('Ctrl+O')
        actionopen.triggered.connect(self.open_bidsmap)
        menufile.addAction(actionopen)

        actionsave = QAction(self)
        actionsave.setText('Save')
        actionsave.setStatusTip('Save the bidsmap to disk')
        actionsave.setShortcut('Ctrl+S')
        actionsave.triggered.connect(self.save_bidsmap)
        menufile.addAction(actionsave)

        actionexit = QAction(self)
        actionexit.setText('Exit')
        actionexit.setStatusTip('Exit the application')
        actionexit.setShortcut('Ctrl+X')
        actionexit.triggered.connect(self.closeEvent)
        menufile.addAction(actionexit)

        # Set help menu actions
        actionhelp = QAction(self)
        actionhelp.setText('Documentation')
        actionhelp.setStatusTip('Go to the online BIDScoin documentation')
        actionhelp.setShortcut('F1')
        actionhelp.triggered.connect(self.get_help)
        menuhelp.addAction(actionhelp)

        actionbidshelp = QAction(self)
        actionbidshelp.setText('BIDS specification')
        actionbidshelp.setStatusTip('Go to the online BIDS specification documentation')
        actionbidshelp.setShortcut('F2')
        actionbidshelp.triggered.connect(self.get_bids_help)
        menuhelp.addAction(actionbidshelp)

        actionabout = QAction(self)
        actionabout.setText('About BIDScoin')
        actionabout.setStatusTip('Show information about the application')
        actionabout.triggered.connect(self.show_about)
        menuhelp.addAction(actionabout)

        # Set the statusbar
        statusbar = QtWidgets.QStatusBar(self)
        statusbar.setStatusTip('Statusbar')
        self.setStatusBar(statusbar)

    def __init_tab_dataformat__(self, dataformat: str):
        """Set the SOURCE file sample listing tab"""

        # Set the Participant table
        participant_label = QLabel('Participant data')
        participant_label.setToolTip('Data to parse the subject/session labels, and to populate the participants tsv- and json-files')

        self.participant_table[dataformat] = participant_table = MyQTable(self, ncols=3)
        participant_table.setToolTip(f"Use e.g. '<<filepath:/sub-(.*?)/>>' to parse the subject and (optional) session label from the pathname. NB: the () parentheses indicate the part that is extracted as the subject/session label\n"
                                     f"Use a dynamic {dataformat} attribute (e.g. '<<PatientName>>') to extract the subject and (optional) session label from the {dataformat} header")
        participant_table.cellChanged.connect(self.participant_table2bidsmap)
        header = participant_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.fill_participant_table(dataformat)

        # Set the bidsmap table
        label = QLabel('Representative samples')
        label.setToolTip('List of unique source-data samples (datatypes)')

        self.samples_table[dataformat] = samples_table = MyQTable(self, min_vsize=False, ncols=6)
        """table columns: 0=index, 1=provenance.name, 2=datatype, 3=bidsname, 4=editbutton, 5=provenance"""
        samples_table.setMouseTracking(True)                                # Needed for showing filepath in the statusbar
        samples_table.setShowGrid(True)
        samples_table.setHorizontalHeaderLabels(['', f'{dataformat} input', 'BIDS data type', 'BIDS output', 'Action', 'Provenance'])
        samples_table.setSortingEnabled(True)
        samples_table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        samples_table.setColumnHidden(2, True)
        samples_table.setColumnHidden(5, True)
        samples_table.itemDoubleClicked.connect(self.sample_doubleclicked)
        samples_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        samples_table.customContextMenuRequested.connect(self.samples_menu)
        header = samples_table.horizontalHeader()
        header.setVisible(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.fill_samples_table(dataformat)
        samples_table.resizeColumnsToContents()
        for col in range(samples_table.columnCount()):
            samples_table.setColumnWidth(col, samples_table.columnWidth(col) + 20)  # Add 20 pixels of padding
        layout = QVBoxLayout()
        layout.addWidget(participant_label)
        layout.addWidget(participant_table)
        layout.addWidget(label)
        layout.addWidget(samples_table)
        tab = QtWidgets.QWidget()
        tab.setObjectName(dataformat)                                       # NB: Serves to identify the dataformat for the tables in a tab
        tab.setLayout(layout)
        self.tabwidget.addTab(tab, f"{dataformat} mappings")

    def __init_tab_options__(self):
        """Set the options tab"""

        # Create the bidscoin table
        bidscoin_options = self.output_bidsmap.options
        self.options_label['bidscoin'] = bidscoin_label = QLabel('BIDScoin')
        bidscoin_label.setToolTip(TOOLTIP_BIDSCOIN)
        self.options_table['bidscoin'] = bidscoin_table = MyQTable(self, ncols=3)    # columns: [key] [value] [testbutton]
        bidscoin_table.setRowCount(len(bidscoin_options.keys()))
        bidscoin_table.setToolTip(TOOLTIP_BIDSCOIN)
        header = bidscoin_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        test_button = QPushButton('Test')                       # Add a test-button
        test_button.clicked.connect(self.test_bidscoin)
        test_button.setToolTip(f'Click to test the BIDScoin installation')
        bidscoin_table.setCellWidget(0, 2, test_button)
        for n, (key, value) in enumerate(bidscoin_options.items()):
            bidscoin_table.setItem(n, 0, MyQTableItem(key, editable=False))
            bidscoin_table.setItem(n, 1, MyQTableItem(value))
        bidscoin_table.cellChanged.connect(self.options2bidsmap)

        # Set up the tab layout and add the bidscoin table
        layout = self.options_layout = QVBoxLayout()
        layout.addWidget(bidscoin_label)
        layout.addWidget(bidscoin_table)

        # Add the plugin tables
        for plugin, options in self.output_bidsmap.plugins.items():
            plugin_label, plugin_table = self.plugin_table(plugin, options)
            layout.addWidget(plugin_label)
            layout.addWidget(plugin_table)

        # Add an 'Add' button below the tables on the right side
        add_button = QPushButton('Add')
        add_button.clicked.connect(self.add_plugin)
        add_button.setToolTip(f'Click to add an installed plugin')
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignRight)

        # Add a 'Default' button below the tables on the left side
        set_button = QPushButton('Set as default')
        set_button.clicked.connect(self.save_options)
        set_button.setToolTip(f'Click to store these options in your default template bidsmap, i.e. set them as default for all new studies')
        layout.addStretch()
        layout.addWidget(set_button, alignment=Qt.AlignmentFlag.AlignLeft)

        tab = QtWidgets.QWidget()
        tab.setLayout(layout)

        self.tabwidget.addTab(tab, 'Options')

    def __init_tab_filebrowser__(self):
        """Set the raw data folder inspector tab"""

        rootfolder = str(self.bidsfolder.parent)
        label = QLabel(rootfolder)
        label.setWordWrap(True)

        filesystem = self.filesystem = QFileSystemModel()
        filesystem.setRootPath(rootfolder)
        filesystem.setFilter(QtCore.QDir.Filter.NoDotAndDotDot | QtCore.QDir.Filter.AllDirs | QtCore.QDir.Filter.Files)
        tree = QTreeView()
        tree.setModel(filesystem)
        tree.setRootIndex(filesystem.index(rootfolder))
        tree.setAnimated(False)
        tree.setSortingEnabled(True)
        tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        tree.setExpanded(filesystem.index(str(self.bidsfolder)), True)
        tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree.header().setStretchLastSection(False)
        tree.doubleClicked.connect(self.open_inspectwindow)

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(tree)
        tab = QtWidgets.QWidget()
        tab.setLayout(layout)

        self.tabwidget.addTab(tab, 'Data browser')

    def closeEvent(self, event):
        """Handle exit of the main window -> check if data has been saved"""

        if not self.datasaved or self.datachanged:
            answer = QMessageBox.question(self, 'Closing the BIDS editor', 'Do you want to save the bidsmap to disk?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Yes)
            if answer == QMessageBox.StandardButton.Yes:
                self.save_bidsmap()
            elif answer == QMessageBox.StandardButton.Cancel:
                if event: event.ignore()    # User clicked the 'X'-button or pressed alt-F4 -> drop signal
                return
            self.datasaved   = True         # Prevent re-entering this if-statement after close() -> closeEvent()
            self.datachanged = False        # Prevent re-entering this if-statement after close() -> closeEvent()

        if event:                           # User clicked the 'X'-button or pressed alt-F4 -> normal closeEvent
            super().closeEvent(event)
        else:                               # User pressed alt-X (= menu action) -> normal close()
            self.close()
        QApplication.quit()

    def fill_participant_table(self, dataformat: str):
        """(Re)populate the participant table with the new bidsmap data"""

        # Populate the participant table
        participant_table = self.participant_table[dataformat]
        participant_table.blockSignals(True)
        participant_table.hide()
        participant_table.setRowCount(len(self.output_bidsmap.dataformat(dataformat).participant) + 1)
        participant_table.clearContents()
        n = 0
        for n, (key, item) in enumerate(self.output_bidsmap.dataformat(dataformat).participant.items()):
            tableitem = MyQTableItem(key, editable=key not in ('participant_id','session_id'))
            tableitem.setToolTip(get_columnhelp(key))
            participant_table = self.participant_table[dataformat]
            participant_table.setItem(n, 0, tableitem)
            participant_table.setItem(n, 1, MyQTableItem(item['value']))
            edit_button = QPushButton('Metadata')
            edit_button.setToolTip('Data for participants json sidecar-file')
            edit_button.clicked.connect(self.edit_metadata)
            participant_table.setCellWidget(n, 2, edit_button)
        participant_table.setItem(n+1, 0, MyQTableItem())
        participant_table.setItem(n+1, 1, MyQTableItem())
        participant_table.resizeColumnsToContents()
        participant_table.show()
        participant_table.blockSignals(False)

    def participant_table2bidsmap(self, rowindex: int, colindex: int):
        """
        A value has been changed in the participant table. If it is valid, save it to the bidsmap and update the
        participant and samples table

        :param rowindex:
        :param colindex:
        :return:
        """

        # Only if cell was actually clicked, update
        if self.tabwidget.currentIndex() < 0:
            return
        dataformat        = self.tabwidget.currentWidget().objectName()
        participant_data  = self.output_bidsmap.dataformat(dataformat).participant
        participant_table = self.participant_table[dataformat]
        key               = participant_table.item(rowindex, 0).text().strip()
        value             = participant_table.item(rowindex, 1).text().strip()

        # Check if the participant keys are still present in the participant_table
        datachanged = False
        if colindex == 0:
            for key_ in participant_data.copy():
                if key_ not in [participant_table.item(row, 0).text().strip() for row in range(participant_table.rowCount()-1)]:
                    participant_data.pop(key_, None)
                    datachanged = True

        # Add the key-value data to the participant data
        if key:
            if key not in participant_data:
                LOGGER.verbose(f"User adds {dataformat}['{key}']")
                participant_data[key] = {'value': value, 'meta': {'Description': ''}}
                datachanged           = True
            else:
                if value != (oldvalue := participant_data[key]['value']):
                    LOGGER.verbose(f"User sets {dataformat}['{key}'] from '{oldvalue}' to '{value}'")
                    participant_data[key]['value'] = value
                    datachanged                    = True

        # Only if cell content was changed, update
        if datachanged:
            self.fill_participant_table(dataformat)
            self.fill_samples_table(dataformat)
            self.datachanged = True

    def edit_metadata(self):
        """Pop-up a text window to edit the sidecar metadata of participant item"""

        dataformat        = self.tabwidget.currentWidget().objectName()
        participant_table = self.participant_table[dataformat]
        clicked           = self.focusWidget()
        rowindex          = participant_table.indexAt(clicked.pos()).row()
        key               = participant_table.item(rowindex, 0).text().strip()
        meta              = self.output_bidsmap.dataformat(dataformat).participant[key].get('meta', {})

        text, ok = QtWidgets.QInputDialog.getMultiLineText(self, 'Edit sidecar metadata', f"json metadata for '{key}':", text=json.dumps(meta, indent=2))
        if ok:
            try:
                meta_ = json.loads(text)
                if meta_ != meta:
                    self.output_bidsmap.dataformat(dataformat).participant[key]['meta'] = meta_
                    self.datachanged = True
            except json.decoder.JSONDecodeError as jsonerror:
                QMessageBox.warning(self, f"Sidecar metadata parsing error", f"{text}\n\nPlease provide valid json metadata:\n{jsonerror}")
                self.edit_metadata()

    def fill_samples_table(self, dataformat: str):
        """(Re)populate the sample table with bidsnames according to the new bidsmap data"""

        self.datachanged = True
        output_bidsmap   = self.output_bidsmap

        # Add runs to the samples table
        idx           = 0
        num_files     = self.set_ordered_file_index(dataformat)
        samples_table = self.samples_table[dataformat]
        """table columns: 0=index, 1=provenance.name, 2=datatype, 3=bidsname, 4=editbutton, 5=provenance"""
        samples_table.blockSignals(True)
        samples_table.hide()
        samples_table.setRowCount(num_files)
        samples_table.setSortingEnabled(False)
        samples_table.clearContents()
        for datatype in output_bidsmap.dataformat(dataformat).datatypes:
            for runitem in datatype.runitems:

                # Check the runitem and get some data
                dtype        = datatype.datatype
                validrun     = all(runitem.check(checks=(False, False, False))[1:3])
                provenance   = Path(runitem.provenance)
                subid        = output_bidsmap.dataformat(dataformat).subject
                sesid        = output_bidsmap.dataformat(dataformat).session
                subid, sesid = runitem.datasource.subid_sesid(subid, sesid or '')
                bidsname     = runitem.bidsname(subid, sesid, not bids.check_ignore(datatype,self.bidsignore) and dtype not in self.ignoredatatypes)
                ignore       = bids.check_ignore(datatype, self.bidsignore) or bids.check_ignore(bidsname+'.json', self.bidsignore, 'file')
                session      = self.bidsfolder/subid/sesid
                row_index    = self.ordered_file_index[dataformat][provenance]

                samples_table.setItem(idx, 0, MyQTableItem(f"{row_index + 1:03d}", editable=False))
                samples_table.setItem(idx, 1, MyQTableItem(provenance.name))
                samples_table.setItem(idx, 2, MyQTableItem(dtype))                          # Hidden column
                samples_table.setItem(idx, 3, MyQTableItem(Path(dtype)/(bidsname + '.*')))
                samples_table.setItem(idx, 5, MyQTableItem(provenance))                     # Hidden column

                samples_table.item(idx, 0).setFlags(Qt.ItemFlag.NoItemFlags)
                samples_table.item(idx, 1).setFlags(Qt.ItemFlag.ItemIsEnabled)
                samples_table.item(idx, 2).setFlags(Qt.ItemFlag.ItemIsEnabled)
                samples_table.item(idx, 1).setToolTip('Double-click to inspect the header information')
                samples_table.item(idx, 1).setStatusTip(str(provenance.parent) + str(Path('/')))
                if dtype not in self.ignoredatatypes:
                    samples_table.item(idx, 3).setStatusTip(str(session) + str(Path('/')))

                if samples_table.item(idx, 3):
                    if ignore:
                        samples_table.item(idx, 3).setForeground(QtGui.QColor('darkorange'))
                        samples_table.item(idx, 3).setToolTip(f"Orange: This {datatype} item is ignored by BIDS-apps and BIDS-validators")
                    elif dtype in self.ignoredatatypes:
                        samples_table.item(idx, 1).setForeground(QtGui.QColor('gray'))
                        samples_table.item(idx, 3).setForeground(QtGui.QColor('gray'))
                        font = samples_table.item(idx, 3).font()
                        font.setStrikeOut(True)
                        samples_table.item(idx, 3).setFont(font)
                        samples_table.item(idx, 3).setToolTip('Gray/Strike-out: This imaging data type will be ignored and not converted BIDS')
                    elif not validrun or dtype in self.unknowndatatypes:
                        samples_table.item(idx, 3).setForeground(QtGui.QColor('red'))
                        samples_table.item(idx, 3).setToolTip(f"Red: This {datatype} item is not BIDS-valid but will still be converted. You should edit this item or make sure it is in your bidsignore list ([Options] tab)")
                    else:
                        samples_table.item(idx, 3).setForeground(QtGui.QColor('green'))
                        samples_table.item(idx, 3).setToolTip(f"Green: This '{datatype}' data type is part of BIDS")

                if validrun or ignore or dtype in self.ignoredatatypes:
                    edit_button = QPushButton('Edit')
                    edit_button.setToolTip('Click to see more details and edit the BIDS output name')
                else:
                    edit_button = QPushButton('Edit*')
                    edit_button.setToolTip('*: Contains invalid/missing values! Click to see more details and edit the BIDS output name')
                edit_button.clicked.connect(self.open_editwindow)
                edit_button.setCheckable(not sys.platform.startswith('darwin'))
                edit_button.setAutoExclusive(True)
                if provenance.name and str(provenance) == self.editwindow_opened:   # Highlight the previously opened item
                    edit_button.setChecked(True)
                else:
                    edit_button.setChecked(False)
                samples_table.setCellWidget(idx, 4, edit_button)

                idx += 1

        samples_table.setSortingEnabled(True)
        samples_table.show()
        samples_table.blockSignals(False)

    def set_ordered_file_index(self, dataformat: str) -> int:
        """Sets the mapping between the ordered provenance and an increasing file-index"""

        provenances = self.output_bidsmap.dir(dataformat)
        if len(provenances) > len(self.ordered_file_index.get(dataformat,[])):
            ordered_index = {}
            for file_index, file_name in enumerate(provenances):
                ordered_index[file_name]        = file_index
            self.ordered_file_index[dataformat] = ordered_index

        return len(provenances)

    def open_editwindow(self, provenance: Path=Path(), datatype: str=''):
        """Make sure that index map has been updated"""

        dataformat = self.tabwidget.currentWidget().objectName()
        if not datatype:
            samples_table = self.samples_table[dataformat]
            clicked       = self.focusWidget()
            rowindex      = samples_table.indexAt(clicked.pos()).row()
            if rowindex < 0:                                        # This presumably happened on PyQt5@macOS (rowindex = -1)? (github issue #131)
                LOGGER.bcdebug(f"User clicked on the [Edit] button (presumably) but PyQt returns pos={clicked.pos()} -> rowindex={rowindex}")
                return                                              # TODO: Simply changing this to 0? (the value of rowindex when data type is DICOM)
            datatype      = samples_table.item(rowindex, 2).text()
            provenance    = samples_table.item(rowindex, 5).text()

        # Check for open edit window, find the right data type index and open the edit window
        if not self.editwindow_opened:
            # Find the source index of the runitem in the list of runitemss (using the provenance) and open the edit window
            for runitem in self.output_bidsmap.dataformat(dataformat).datatype(datatype).runitems:
                if Path(runitem.provenance) == Path(provenance):
                    LOGGER.verbose(f'User is editing {provenance}')
                    self.editwindow = editwindow = EditWindow(self, runitem, self.output_bidsmap, self.template_bidsmap)
                    self.editwindow_opened = str(provenance)
                    editwindow.done_edit.connect(self.fill_samples_table)
                    editwindow.finished.connect(self.release_editwindow)
                    editwindow.setWindowFlags(editwindow.windowFlags() | Qt.WindowType.Window)
                    editwindow.show()
                    return
            LOGGER.error(f"Could not find [{datatype}] {provenance} run-item")

        else:
            # Ask the user if he wants to save his results first before opening a new edit window
            self.editwindow.reject()
            if self.editwindow_opened:
                return
            self.open_editwindow(provenance, datatype)

    def release_editwindow(self):
        """Allow a new edit window to be opened"""
        self.editwindow_opened = None

    def plugin_table(self, name: str, plugin: dict) -> tuple:
        """:return: a plugin-label and a filled plugin-table"""

        self.options_label[name] = plugin_label = QLabel(f"{name} - plugin")
        self.options_table[name] = plugin_table = MyQTable(self, ncols=3)   # columns: [key] [value] [testbutton]
        plugin_table.setRowCount(max(len(plugin.keys()) + 1, 2))            # Add an extra row for new key-value pairs
        header = plugin_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        test_button = QPushButton('Test')                                   # Add a test-button
        test_button.clicked.connect(partial(self.test_plugin, name))
        test_button.setToolTip(f'Click to test the "{name}" installation')
        plugin_table.setCellWidget(0, 2, test_button)
        delete_button = QPushButton('Remove')                               # Add a delete-button
        delete_button.clicked.connect(partial(self.del_plugin, name))
        delete_button.setToolTip(f'Click to discard / stop using the "{name}" plugin')
        plugin_table.setCellWidget(1, 2, delete_button)
        plugin_label.setToolTip(bcoin.import_plugin(name).__doc__)
        plugin_table.setToolTip(TOOLTIP_DCM2NIIX if name == 'dcm2niix2bids' else f"Here you can enter key-value data for the '{name}' plugin")
        for n, (key, value) in enumerate(plugin.items()):
            plugin_table.setItem(n, 0, MyQTableItem(key))
            plugin_table.setItem(n, 1, MyQTableItem(value))
            plugin_table.setItem(n, 2, MyQTableItem('', editable=False))
        plugin_table.setItem(plugin_table.rowCount() - 1, 2, MyQTableItem('', editable=False))
        plugin_table.cellChanged.connect(self.options2bidsmap)

        return plugin_label, plugin_table

    def options2bidsmap(self, rowindex: int, colindex: int):
        """Saves all Options tables to the bidsmap and add an extra row to the plugin_table if it is full"""

        for plugin, table in self.options_table.items():
            if plugin == 'bidscoin':
                oldoptions = self.output_bidsmap.options
            else:
                oldoptions = self.output_bidsmap.plugins.get(plugin,{})
            newoptions = {}
            for rownr in range(table.rowCount()):
                keyitem = table.item(rownr, 0)
                valitem = table.item(rownr, 1)
                key = val = ''
                if keyitem: key = keyitem.text().strip()
                if valitem: val = valitem.text().strip()
                if key:
                    if not val.startswith('"') and not val.endswith('"'):           # E.g. convert string or int to list or int but avoid encoding strings such as "C:\tmp" (\t -> tab)
                        try: val = ast.literal_eval(val)
                        except (ValueError, TypeError, SyntaxError): pass
                    newoptions[key] = val
                    if val != oldoptions.get(key):
                        LOGGER.verbose(f"User sets the '{plugin}' option from '{key}: {oldoptions.get(key)}' to '{key}: {val}'")
                        self.datachanged = True
            if plugin == 'bidscoin':
                self.output_bidsmap.options = newoptions
                self.unknowndatatypes  = newoptions.get('unknowntypes', [])
                self.ignoredatatypes   = newoptions.get('ignoretypes', [])
                self.bidsignore        = newoptions.get('bidsignore', [])
                for dataformat in self.dataformats:
                    self.fill_samples_table(dataformat)
            else:
                self.output_bidsmap.plugins[plugin] = newoptions

            # Add an extra row if the table is full
            if rowindex + 1 == table.rowCount() and table.currentItem() and table.currentItem().text().strip():
                table.blockSignals(True)
                table.insertRow(table.rowCount())
                table.setItem(table.rowCount() - 1, 2, MyQTableItem('', editable=False))
                table.blockSignals(False)

    @QtCore.pyqtSlot(QtCore.QPoint)
    def samples_menu(self, pos):
        """Pops up a context-menu for deleting or editing the right-clicked sample in the samples_table"""

        # Get the activated row-data
        dataformat = self.tabwidget.currentWidget().objectName()
        table      = self.samples_table[dataformat]
        colindex   = table.currentColumn()
        rowindexes = [index.row() for index in table.selectedIndexes() if index.column() == colindex]
        if rowindexes and colindex in (-1, 0, 4):      # User clicked the index, the edit-button or elsewhere (i.e. not on an activated widget)
            return
        runitems: list[RunItem] = []
        subids:   list[str]     = []
        sesids:   list[str]     = []
        for index in rowindexes:
            datatype   = table.item(index, 2).text()
            provenance = table.item(index, 5).text()
            runitems.append(self.output_bidsmap.find_run(provenance, dataformat, datatype))
            subids.append(bids.get_bidsvalue(table.item(index, 3).text(), 'sub'))
            sesids.append(bids.get_bidsvalue(table.item(index, 3).text(), 'ses'))

        # Pop-up the context-menu
        menu    = QtWidgets.QMenu(self)
        compare = menu.addAction('Compare')
        compare.setEnabled(len(rowindexes) > 1)
        compare.setToolTip('Compare the BIDS mappings of multiple run-items')
        edit    = menu.addAction('Edit')
        edit.setEnabled(len(rowindexes) > 0)
        edit.setToolTip('Edit a single run-item in detail or edit the data type of multiple run-items')
        add     = menu.addAction('Add')
        add.setToolTip('Add a run-item (expert usage)')
        delete  = menu.addAction('Remove')
        delete.setEnabled(len(rowindexes) > 0)
        delete.setToolTip('Delete run-items (expert usage)')
        action  = menu.exec(table.viewport().mapToGlobal(pos))

        datatypes = [dtype.datatype for dtype in self.template_bidsmap.dataformat(dataformat).datatypes]    # Get the datatypes for the dataformat(s)
        if action == add:
            filenames, _ = QFileDialog.getOpenFileNames(self, 'Select the data source(s) for which you want to add a run-item(s)', str(self.bidsfolder))
            if filenames:
                datatype, ok = QInputDialog.getItem(self, 'Select the data type of the run-item(s)', 'datatype', datatypes, editable=False)
                if datatype and ok:
                    runitem = None
                    for filename in filenames:
                        datasource = bids.DataSource(filename, self.output_bidsmap.plugins, dataformat, self.output_bidsmap.options)
                        if datasource.has_support():
                            runitem = self.template_bidsmap.get_run(datatype, 0, datasource)
                            runitem.properties['filepath'] = datasource.property('filepath')    # Make the added run a strict match (i.e. an exception)
                            runitem.properties['filename'] = datasource.property('filename')    # Make the added run a strict match (i.e. an exception)
                            LOGGER.verbose(f"Expert usage: User adds run-item {dataformat}[{datatype}]: {filename}")
                            if Path(filename) in self.output_bidsmap.dir(dataformat):
                                LOGGER.warning(f"Added run-item {dataformat}[{datatype}]: {filename} already exists")
                            self.output_bidsmap.insert_run(runitem, 0)                  # Put the run at the front (so it gets matching priority)
                            if dataformat not in self.ordered_file_index:
                                self.ordered_file_index[dataformat] = {datasource.path: 0}
                            else:
                                self.ordered_file_index[dataformat][datasource.path] = max(self.ordered_file_index[dataformat][fname] for fname in self.ordered_file_index[dataformat]) + 1
                    if runitem:
                        self.fill_samples_table(dataformat)

        elif action == delete:
            deleted = False
            for index in rowindexes:
                datatype   = table.item(index, 2).text()
                provenance = table.item(index, 5).text()
                if Path(provenance).is_file():
                    answer = QMessageBox.question(self, f"Remove {dataformat} mapping for {provenance}",
                                                  'Only delete run-items that are obsolete or irregular (unless you are an expert user). Do you want to continue?',
                                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
                    if answer != QMessageBox.StandardButton.Yes: continue
                LOGGER.verbose(f"Expert usage: User removes run-item {dataformat}[{datatype}]: {provenance}")
                self.output_bidsmap.delete_run(provenance, datatype, dataformat)
                deleted = True
            if deleted:
                self.fill_samples_table(dataformat)

        elif action == compare:
            CompareWindow(runitems, subids, sesids)

        elif action == edit:
            if len(rowindexes) == 1:
                datatype   = table.item(table.currentRow(), 2).text()
                provenance = table.item(table.currentRow(), 5).text()
                self.open_editwindow(provenance, datatype)
            else:
                newdatatype, ok = QInputDialog.getItem(self, 'Edit data types', 'Select the new data type for your run-items', datatypes, editable=False)
                if not (newdatatype and ok):
                    return

                # Change the data type for the selected run-items
                for index in rowindexes:
                    datatype   = table.item(index, 2).text()
                    provenance = table.item(index, 5).text()
                    if not Path(provenance).is_file():
                        QMessageBox.warning(self, 'Edit BIDS mappings', f"Cannot reliably change the data type and/or suffix because the source file '{provenance}' can no longer be found.\n\nPlease restore the source data or use the `bidsmapper -s -f` options to solve this issue")
                        continue

                    # Get the new run from the template
                    oldrun      = self.output_bidsmap.find_run(provenance, dataformat, datatype)
                    templaterun = self.template_bidsmap.get_run(newdatatype, 0, oldrun.datasource)
                    if not templaterun:
                        QMessageBox.warning(self, 'Edit BIDS mappings', f"Cannot find the '{newdatatype}' data type in your template")
                        continue

                    # Insert the new run in our output bidsmap
                    self.output_bidsmap.update(datatype, templaterun)
                    LOGGER.verbose(f"User sets run-item {datatype} -> {templaterun}")

                self.fill_samples_table(dataformat)

    def add_plugin(self):
        """Interactively add an installed plugin to the Options-tab and save the data in the bidsmap"""

        # Set-up a plugin dropdown menu
        label     = QLabel('Select a plugin that you would like to add')
        plugins,_ = bcoin.list_plugins()
        dropdown  = QComboBox()
        dropdown.addItems([plugin.stem for plugin in plugins])

        # Set-up OK/Cancel buttons
        buttonbox = QDialogButtonBox()
        buttonbox.setStandardButtons(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttonbox.button(QDialogButtonBox.StandardButton.Ok).setToolTip('Adds the selected plugin to the bidsmap options')

        # Set up the dialog window and wait till the user has selected a plugin
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(dropdown)
        layout.addWidget(buttonbox)
        qdialog = QDialog(self, modal=True)
        qdialog.setLayout(layout)
        qdialog.setWindowTitle('BIDScoin Options')
        buttonbox.accepted.connect(qdialog.accept)
        buttonbox.rejected.connect(qdialog.reject)
        answer = qdialog.exec()
        if not answer:
            return

        # Check the selected plugin and get its options
        plugin = dropdown.currentText()
        if plugin in self.output_bidsmap.plugins:
            LOGGER.error(f"Cannot add the '{plugin}' plugin as it already exists in the bidsmap")
            return
        module  = bcoin.import_plugin(plugin)
        options = self.input_bidsmap.plugins.get(plugin, self.template_bidsmap.plugins.get(plugin, getattr(module, 'OPTIONS', {})))

        # Insert the selected plugin in the options_layout
        LOGGER.info(f"Adding the '{plugin}' plugin to bidsmap")
        plugin_label, plugin_table = self.plugin_table(plugin, options)
        self.options_layout.insertWidget(self.options_layout.count()-3, plugin_label)
        self.options_layout.insertWidget(self.options_layout.count()-3, plugin_table)
        self.output_bidsmap.plugins[plugin] = options
        self.datachanged = True

        # Notify the user that the bidsmapper need to be re-run
        QMessageBox.information(self, 'Add plugin', f"The '{plugin}' plugin was added. Most likely you need to save and close the bidseditor now and re-run the bidsmapper to discover new source datatypes with the new plugin")

    def del_plugin(self, plugin: str):
        """Removes the plugin table from the Options-tab and the data from the bidsmap"""

        LOGGER.info(f"Removing the '{plugin}' from bidsmap.plugins")
        plugin_label = self.options_label[plugin]
        plugin_table = self.options_table[plugin]
        self.options_layout.removeWidget(plugin_label)
        self.options_layout.removeWidget(plugin_table)
        plugin_label.deleteLater()
        plugin_table.deleteLater()
        self.options_label.pop(plugin, None)
        self.options_table.pop(plugin, None)
        self.output_bidsmap.plugins.pop(plugin, None)
        self.datachanged = True

    def test_plugin(self, plugin: str):
        """Test the plugin and show the result in a pop-up window"""

        status = bcoin.test_plugin(Path(plugin), self.output_bidsmap.plugins.get(plugin,{}))
        if not status or (status==3 and plugin=='dcm2niix2bids'):
            QMessageBox.information(self, 'Plugin test', f"Import of {plugin}: Passed\nSee terminal output for more info")
        else:
            QMessageBox.warning(self, 'Plugin test', f"Import of {plugin}: Failed\nSee terminal output for more info")

    def test_bidscoin(self):
        """Test the bidsmap tool and show the result in a pop-up window"""

        if not bcoin.test_bidscoin(self.input_bidsmap, options=self.output_bidsmap.options, testplugins=False, testgui=False, testtemplate=False):
            QMessageBox.information(self, 'Tool test', f"BIDScoin test: Passed\nSee terminal output for more info")
        else:
            QMessageBox.warning(self, 'Tool test', f"BIDScoin test: Failed\nSee terminal output for more info")

    def validate_runs(self):
        """Test the runs in the study bidsmap"""

        LOGGER.info(' ')
        self.output_bidsmap.check()
        LOGGER.info(' ')
        self.output_bidsmap.validate(2)

    def reset(self):
        """Reset button: reset the window with the original input BIDS map"""

        if self.editwindow_opened:
            self.editwindow.reject(confirm=False)

        LOGGER.info('User resets the bidsmap')
        self.__init__(self.bidsfolder, self.input_bidsmap, self.template_bidsmap, self.datasaved, reset=True)

        # Start with a fresh errorlog
        for filehandler in LOGGER.handlers:
            if filehandler.name=='errorhandler' and Path(filehandler.baseFilename).stat().st_size:
                errorfile = filehandler.baseFilename
                LOGGER.verbose(f"Resetting {errorfile}")
                with open(errorfile, 'w'): pass     # This works, but it is a hack that somehow prefixes a lot of whitespace to the first LOGGER call

    def open_bidsmap(self):
        """Load a bidsmap from disk and open it the main window"""

        if not self.datasaved or self.datachanged:
            answer = QMessageBox.question(self, 'Opening a new bidsmap', 'Do you want to save the current bidsmap to disk?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Yes)
            if answer == QMessageBox.StandardButton.Yes:
                self.save_bidsmap()
            elif answer == QMessageBox.StandardButton.Cancel:
                return

        filename, _ = QFileDialog.getOpenFileName(self, 'Open File', str(self.bidsfolder/'code'/'bidscoin'/'bidsmap.yaml'), 'YAML Files (*.yaml *.yml);;All Files (*)')
        if filename:
            QtCore.QCoreApplication.setApplicationName(f"{filename} - BIDS editor {__version__}")
            self.input_bidsmap = BidsMap(Path(filename))
            self.reset()

    def save_bidsmap(self):
        """Check and save the bidsmap to file"""

        for dataformat in self.dataformats:
            if 'fmap' in self.output_bidsmap.dataformat(dataformat).datatypes:
                for runitem in self.output_bidsmap.dataformat(dataformat).datatype('fmap').runitems:
                    if not (runitem.meta.get('B0FieldSource') or runitem.meta.get('B0FieldIdentifier') or runitem.meta.get('IntendedFor')):
                        LOGGER.warning(f"B0FieldIdentifier/IntendedFor field map value is empty for {dataformat} run-item: {runitem}")

        filename,_ = QFileDialog.getSaveFileName(self, 'Save File',  str(self.bidsfolder/'code'/'bidscoin'/'bidsmap.yaml'), 'YAML Files (*.yaml *.yml);;All Files (*)')
        if filename:
            self.output_bidsmap.save(Path(filename))
            QtCore.QCoreApplication.setApplicationName(f"{filename} - BIDS editor {__version__}")
            self.datasaved   = True
            self.datachanged = False

    def save_options(self):
        """Export the options to a template bidsmap on disk"""

        yamlfile, _ = QFileDialog.getOpenFileName(self, 'Select the (default) template bidsmap to save the options in',
                        str(bidsmap_template), 'YAML Files (*.yaml *.yml);;All Files (*)')
        if yamlfile:
            LOGGER.info(f"Saving bidsmap options in: {yamlfile}")
            with open(yamlfile, 'r') as stream:
                bidsmap = bids.yaml.safe_load(stream)
            bidsmap.options = self.output_bidsmap.options
            bidsmap.plugins = self.output_bidsmap.plugins
            with open(yamlfile, 'w') as stream:
                bids.yaml.safe_dump(bidsmap, stream, sort_keys=False, allow_unicode=True)

    def sample_doubleclicked(self, item):
        """When source file is double-clicked in the samples_table, show the inspect- or edit-window"""

        dataformat = self.tabwidget.currentWidget().objectName()
        datatype   = self.samples_table[dataformat].item(item.row(), 2).text()
        sourcefile = self.samples_table[dataformat].item(item.row(), 5).text()
        if item.column() == 1:
            self.popup = InspectWindow(Path(sourcefile))
            self.popup.show()
            self.popup.scrollbar.setValue(0)  # This can only be done after self.popup.show()
        if item.column() == 3:
            self.open_editwindow(sourcefile, datatype)

    def open_inspectwindow(self, index: int):
        """Opens the inspect- or native application-window when a data file in the file-tree tab is double-clicked"""

        datafile = Path(self.filesystem.fileInfo(index).absoluteFilePath())
        if datafile.is_file():
            ext = datafile.suffix.lower()
            if is_dicomfile(datafile) or is_parfile(datafile) or ext in sum((klass.valid_exts for klass in nib.imageclasses.all_image_classes), ('.7','.spar')) or datafile.name.endswith('.nii.gz'):
                self.popup = InspectWindow(datafile)
                self.popup.show()
                self.popup.scrollbar.setValue(0)  # This can only be done after self.popup.show()
            else:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(datafile)))

    def show_about(self):
        """Shows a pop-up window with the BIDScoin version"""

        _, _, message = check_version()
        # QMessageBox.about(self, 'About', f"BIDS editor {__version__}\n\n{message}")    # Has an ugly/small icon image
        messagebox = QMessageBox(self)
        messagebox.setText(f"\n\nBIDS editor {__version__}\n\n{message}")
        messagebox.setWindowTitle('About')
        messagebox.setIconPixmap(QtGui.QPixmap(str(BIDSCOIN_LOGO)).scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        messagebox.show()

    @staticmethod
    def get_help():
        """Get online help. """
        webbrowser.open(MAIN_HELP_URL)

    @staticmethod
    def get_bids_help():
        """Get online help. """
        webbrowser.open(HELP_URL_DEFAULT)


class EditWindow(QDialog):
    """
    EditWindow().result() == 1: done with result, i.e. done_edit -> edited dataformat
    EditWindow().result() == 2: done without result
    """

    # Emit the new bidsmap when done (see docstring)
    done_edit = QtCore.pyqtSignal(str)

    def __init__(self, parent, runitem: RunItem, bidsmap: BidsMap, template_bidsmap: BidsMap):
        super().__init__(parent)

        # Add missing default events and events.time keys
        runitem.events()

        # Set the data
        self.datasource        = runitem.datasource
        self.dataformat        = runitem.dataformat
        """The data format of the run-item being edited (bidsmap[dataformat][datatype][run-item])"""
        self.unknowndatatypes: list[str] = [datatype for datatype in bidsmap.options['unknowntypes'] if datatype in template_bidsmap.dataformat(self.dataformat).datatypes]
        self.ignoredatatypes:  list[str] = [datatype for datatype in bidsmap.options['ignoretypes']  if datatype in template_bidsmap.dataformat(self.dataformat).datatypes]
        self.bidsdatatypes     = [str(datatype) for datatype in template_bidsmap.dataformat(self.dataformat).datatypes if datatype not in self.unknowndatatypes + self.ignoredatatypes]
        self.bidsignore        = bidsmap.options['bidsignore']
        self.output_bidsmap    = bidsmap
        """The bidsmap at the start of the edit = output_bidsmap in the MainWindow"""
        self.template_bidsmap  = template_bidsmap
        """The bidsmap from which new datatype run-items are taken"""
        self.source_run        = runitem
        """The original run-item from the source bidsmap"""
        self.target_run        = copy.deepcopy(runitem)
        """The edited run-item that is inserted in the target_bidsmap"""
        self.events            = self.target_run.events()
        """The EventsParser instance of the target run-item"""
        self.allowed_suffixes  = self.get_allowed_suffixes()
        """Set the possible suffixes the user can select for a given datatype"""
        self.subid, self.sesid = runitem.datasource.subid_sesid(bidsmap.dataformat(runitem.dataformat).subject, bidsmap.dataformat(runitem.dataformat).session or '')

        # Set up the window
        self.setWindowFlags(self.windowFlags() & Qt.WindowType.WindowTitleHint & Qt.WindowType.WindowMinMaxButtonsHint & Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle(f"Edit run-item [{self.dataformat}/{self.source_run.datatype}]")
        self.setWhatsThis(f"BIDScoin mapping of {self.dataformat} properties and attributes to BIDS output data")

        # Get data for the tables
        properties_data, attributes_data, bids_data, meta_data, events_data = self.run2data()

        # Set up the properties table
        properties_label = QLabel('Properties')
        properties_label.setToolTip(f"The filesystem properties that match with (identify) the source file. NB: Expert usage (e.g. using regular expressions, see documentation). Copy: Ctrl+C")
        self.properties_table = properties_table = self.setup_table(properties_data, 'properties')
        properties_table.cellChanged.connect(self.properties2run)
        properties_table.setToolTip(f"The filesystem property that matches with the source file")
        properties_table.cellDoubleClicked.connect(self.inspect_sourcefile)
        properties_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        properties_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        properties_table.setMinimumHeight(properties_table.height() + 10)                   # Add 10 pixels of padding (to avoid scrollbar flickering on some older systems)

        # Set up the attributes table
        attributes_label = QLabel(f"Attributes")
        attributes_label.setToolTip(f"The {self.dataformat} attributes that match with (identify) the source file. NB: Expert usage (e.g. using regular expressions, see documentation). Copy: Ctrl+C")
        self.attributes_table = attributes_table = self.setup_table(attributes_data, 'attributes', min_vsize=False)
        attributes_table.resizeColumnsToContents()          # TODO: Fix (this should work to make the edit window wider, except that it doesn't)
        attributes_table.cellChanged.connect(self.attributes2run)
        attributes_table.setToolTip(f"The {self.dataformat} attribute that matches with the source file")
        attributes_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        attributes_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        # Set up the datatype dropdown menu
        datatype_label = QLabel('Data type')
        datatype_label.setToolTip(f"The BIDS data type and entities for constructing the BIDS output filename. You are encouraged to change their default values to be more meaningful and readable")
        self.datatype_dropdown = datatype_dropdown = QComboBox()
        datatype_dropdown.addItems(self.bidsdatatypes + self.unknowndatatypes + self.ignoredatatypes)
        datatype_dropdown.setCurrentIndex(datatype_dropdown.findText(self.target_run.datatype))
        datatype_dropdown.setToolTip('The BIDS data type. First make sure this one is correct, then choose the right suffix')
        for n, datatype in enumerate(self.bidsdatatypes + self.unknowndatatypes + self.ignoredatatypes):
            datatype_dropdown.setItemData(n, get_datatypehelp(datatype), Qt.ItemDataRole.ToolTipRole)
        datatype_dropdown.currentIndexChanged.connect(self.change_datatype)

        # Set up the BIDS table
        self.bids_table = bids_table = self.setup_table(bids_data, 'bids')
        bids_table.setToolTip(f"The BIDS entity that is used to construct the BIDS output filename. You are encouraged to change its default value to be more meaningful and readable")
        bids_table.cellChanged.connect(self.bids2run)

        # Set-up non-editable BIDS output name section
        bidsname_label = QLabel('Filename')
        bidsname_label.setToolTip(f"Preview of the BIDS output name for this data type")
        self.bidsname_textbox = bidsname_textbox = QTextBrowser()
        bidsname_textbox.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        bidsname_textbox.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        self.update_bidsname()

        # Set up the meta table
        meta_label = QLabel('Metadata')
        meta_label.setToolTip(f"Key-value pairs that will be appended to the (e.g. dcm2niix-produced) json sidecar file")
        self.meta_table = meta_table = self.setup_table(meta_data, 'meta', min_vsize=False)
        meta_table.setShowGrid(True)
        meta_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        meta_table.customContextMenuRequested.connect(self.import_menu)
        meta_table.cellChanged.connect(self.meta2run)
        meta_table.setToolTip(f"The key-value pair that will be appended to the (e.g. dcm2niix-produced) json sidecar file")

        # Set up the event-input table
        inspect_button = QPushButton('Source')
        inspect_button.setToolTip('Show the raw source data')
        inspect_button.clicked.connect(self.inspect_sourcefile)
        events_parsing_label = QLabel('Parsing')
        self.events_parsing = events_parsing = self.setup_table(events_data.get('parsing',[]), 'events_parsing')
        events_parsing.cellChanged.connect(self.events_parsing2run)
        events_parsing.setToolTip(f"Settings for parsing the input table from the source file")
        events_parsing.setStyleSheet('QTableView::item {border-right: 1px solid #d6d9dc;}')
        events_parsing.setMinimumSize(events_parsing.sizeHint())
        log_table_label = QLabel('Log data')
        self.log_table  = log_table = MyQTableView(self, self.events.logtable() if self.events else pd.DataFrame())
        log_table.setToolTip(f"The raw stimulus presentation data that is parsed from the log file")

        # Set up the event-mapping table
        events_time_label = QLabel('Timing')
        self.events_time = events_time = self.setup_table(events_data.get('time',[]), 'events_time')
        events_time.cellChanged.connect(self.events_time2run)
        events_time.setToolTip(f"Columns: The number of time units per second + the column names that contain timing information (e.g. [10000, 'Time', 'Duration'])\n"
                               f"Start: The event that marks the beginning of the experiment, i.e. where the clock should be (re)set to 0 (e.g. 'Code=10' if '10' is used to log the pulses)")
        events_rows_label = QLabel('Rows')
        self.events_rows = events_rows = self.setup_table(events_data.get('rows',[]), 'events_rows')
        events_rows.cellChanged.connect(self.events_rows2run)
        events_rows.setToolTip(f"The groups of rows that are included in the output table")
        events_rows.horizontalHeader().setVisible(True)
        events_rows.setStyleSheet('QTableView::item {border-right: 1px solid #d6d9dc;}')
        events_columns_label = QLabel('Columns')
        self.events_columns = events_columns = self.setup_table(events_data.get('columns',[]), 'events_columns')
        events_columns.cellChanged.connect(self.events_columns2run)
        events_columns.setToolTip(f"The mappings of the included output columns. To add a new column, enter its mapping in the empty bottom row")
        events_columns.horizontalHeader().setVisible(True)
        events_columns.setStyleSheet('QTableView::item {border-right: 1px solid #d6d9dc;}')

        # Set up the event-output table
        self.edit_button = edit_button = QPushButton('Edit')
        edit_button.setToolTip('Edit the events table')
        edit_button.clicked.connect(self.edit_events)
        self.done_button = done_button = QPushButton('Done')
        done_button.setToolTip('Approve the events table')
        done_button.clicked.connect(self.done_events)
        done_button.hide()
        events_table_label = QLabel('Events data')
        self.events_table  = events_table = MyQTableView(self, self.events.eventstable() if self.events else pd.DataFrame())

        # Group the tables in boxes
        layout1 = QVBoxLayout()
        layout1.addWidget(properties_label)
        layout1.addWidget(properties_table)
        layout1.addWidget(attributes_label)
        layout1.addWidget(attributes_table)
        sizepolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.MinimumExpanding)
        sizepolicy.setHorizontalStretch(1)
        self.sourcebox = sourcebox = QGroupBox(f"{self.dataformat} input")
        sourcebox.setSizePolicy(sizepolicy)
        sourcebox.setLayout(layout1)

        layout1_ = QVBoxLayout()
        layout1_.addWidget(inspect_button, alignment=Qt.AlignmentFlag.AlignRight)
        if events_data.get('parsing'):
            layout1_.addWidget(events_parsing_label)
            layout1_.addWidget(events_parsing)
        layout1_.addWidget(log_table_label)
        layout1_.addWidget(log_table)
        self.events_inputbox = events_inputbox = QGroupBox(f"{self.dataformat} input data")
        events_inputbox.setSizePolicy(sizepolicy)
        events_inputbox.setLayout(layout1_)

        self.arrow = arrow = QLabel()
        arrow.setPixmap(QtGui.QPixmap(str(RIGHTARROW)).scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        arrow_ = QLabel()
        arrow_.setPixmap(QtGui.QPixmap(str(RIGHTARROW)).scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

        layout2 = QVBoxLayout()
        layout2.addWidget(datatype_label)
        layout2.addWidget(datatype_dropdown, alignment=Qt.AlignmentFlag.AlignLeft)
        layout2.addWidget(bids_table)
        layout2.addWidget(bidsname_label)
        layout2.addWidget(bidsname_textbox)
        layout2.addWidget(meta_label)
        layout2.addWidget(meta_table)
        self.bidsbox = bidsbox = QGroupBox('BIDS output')
        bidsbox.setSizePolicy(sizepolicy)
        bidsbox.setLayout(layout2)

        layout2_ = QVBoxLayout()
        layout2_.addWidget(arrow_)
        layout2_.setAlignment(arrow_, Qt.AlignmentFlag.AlignHCenter)
        layout2_.addWidget(events_columns_label)
        layout2_.addWidget(events_columns)
        layout2_.addWidget(events_rows_label)
        layout2_.addWidget(events_rows)
        layout2_.addWidget(events_time_label)
        layout2_.addWidget(events_time)
        layout2_.addStretch()
        self.events_editbox = events_editbox = QGroupBox('Mapping')
        events_editbox.setSizePolicy(sizepolicy)
        events_editbox.setLayout(layout2_)

        layout3 = QVBoxLayout()
        layout3.addWidget(edit_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout3.addWidget(done_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout3.addWidget(events_table_label)
        layout3.addWidget(events_table)
        events_outputbox = QGroupBox('BIDS output data')
        events_outputbox.setSizePolicy(sizepolicy)
        events_outputbox.setLayout(layout3)

        # Add the boxes + a source->bids arrow to the tables layout
        layout_tables = QHBoxLayout()
        layout_tables.addWidget(sourcebox)
        layout_tables.addWidget(arrow)
        layout_tables.addWidget(bidsbox)
        if self.events:
            layout_tables.addWidget(events_inputbox)
            layout_tables.addWidget(events_editbox)
            layout_tables.addWidget(events_outputbox)
            events_inputbox.hide()
            events_editbox.hide()

        # Set-up buttons
        buttonbox    = QDialogButtonBox()
        exportbutton = buttonbox.addButton('Export', QDialogButtonBox.ButtonRole.ActionRole)
        exportbutton.setIcon(QtGui.QIcon.fromTheme('document-save'))
        exportbutton.setToolTip('Export this run item to an existing (template) bidsmap')
        exportbutton.clicked.connect(self.export_run)
        buttonbox.setStandardButtons(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Reset | QDialogButtonBox.StandardButton.Help)
        buttonbox.button(QDialogButtonBox.StandardButton.Reset).setToolTip('Reset the edits you made')
        buttonbox.button(QDialogButtonBox.StandardButton.Ok).setToolTip('Apply the edits you made and close this window')
        buttonbox.button(QDialogButtonBox.StandardButton.Cancel).setToolTip('Discard the edits you made and close this window')
        buttonbox.button(QDialogButtonBox.StandardButton.Help).setToolTip('Go to the online BIDS specification for more info')
        buttonbox.accepted.connect(self.accept_run)
        buttonbox.rejected.connect(partial(self.reject, False))
        buttonbox.helpRequested.connect(self.get_help)
        buttonbox.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self.reset)

        # Set up the main layout
        layout_main = QVBoxLayout(self)
        layout_main.addLayout(layout_tables)
        layout_main.addWidget(buttonbox)

    def reject(self, confirm=True):
        """Ask if the user really wants to close the window"""

        if confirm and self.target_run != self.source_run:
            self.raise_()
            answer = QMessageBox.question(self, 'Edit run-item', 'Closing window, do you want to save the changes you made?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Yes)
            if answer == QMessageBox.StandardButton.Yes:
                self.accept_run()
                return
            if answer == QMessageBox.StandardButton.No:
                self.done(2)
                LOGGER.verbose(f'User has discarded the edit')
                return
            if answer == QMessageBox.StandardButton.Cancel:
                return

        LOGGER.verbose(f'User has canceled the edit')

        super().reject()

    def setup_table(self, data: list, name: str, min_vsize: bool=True) -> MyQTable:
        """Return a table widget with resize policies, filled with the data"""

        table = MyQTable(self, min_vsize)
        table.setObjectName(name)                       # NB: Serves to identify the tables in fill_table()

        self.fill_table(table, data)

        return table

    def fill_table(self, table: MyQTable, data: list):
        """Fill the table with data"""

        # Some ugly hacks to adjust individual tables
        tablename = table.objectName()
        header    = tablename in ('events_rows', 'events_columns')
        extrarow  = [[{'value': '', 'editable': True}, {'value': '', 'editable': True}]] if tablename in ('events_rows','events_columns','meta') else []
        ncols     = len(data[0]) if data else 2         # Always at least two columns (i.e. key, value)

        # Populate the blocked/hidden table
        table.blockSignals(True)
        table.hide()
        table.clearContents()
        table.setRowCount(len(data + extrarow) - header)
        table.setColumnCount(ncols)

        for i, row in enumerate(data + extrarow):

            if not row: continue

            key = row[0]['value']

            if tablename == 'bids' and key == 'suffix' and self.target_run.datatype in self.bidsdatatypes:
                table.setItem(i, 0, MyQTableItem('suffix', editable=False))
                suffix   = self.datasource.dynamicvalue(self.target_run.bids.get('suffix',''))
                suffixes = sorted(self.allowed_suffixes.get(self.target_run.datatype, set()), key=str.casefold)
                dropdown = self.suffix_dropdown = QComboBox()
                dropdown.addItems(suffixes)
                dropdown.setCurrentIndex(dropdown.findText(suffix))
                dropdown.currentIndexChanged.connect(self.change_suffix)
                dropdown.setToolTip('The suffix that sets the different run types apart. First make sure the "Data type" dropdown-menu is set correctly before choosing the right suffix here')
                for n, suffix in enumerate(suffixes):
                    dropdown.setItemData(n, get_suffixhelp(suffix), Qt.ItemDataRole.ToolTipRole)
                table.setCellWidget(i, 1, self.spacedwidget(dropdown))
                continue

            elif header:
                if i == 0:              # The first/header row of the data has the column names
                    table.setHorizontalHeaderLabels(str(item.get('value')) for item in row)
                    continue
                i -= 1                  # Account for the header row

            for j, item in enumerate(row):
                itemvalue = item['value']

                if tablename in ('bids', 'events_parsing') and isinstance(itemvalue, list):
                    dropdown = QComboBox()
                    dropdown.addItems(itemvalue[0:-1])
                    dropdown.setCurrentIndex(itemvalue[-1])
                    dropdown.currentIndexChanged.connect(partial(self.bids2run if tablename=='bids' else self.events_parsing2run, i, j))
                    if tablename=='bids' and j == 0:
                        dropdown.setToolTip(get_entityhelp(key))
                    table.setCellWidget(i, j, self.spacedwidget(dropdown))

                else:
                    myitem = MyQTableItem(itemvalue, item['editable'])
                    if tablename == 'properties':
                        if j == 1:
                            myitem.setToolTip('The (regex) matching pattern that for this property')
                        if j == 2:
                            myitem.setToolTip(get_propertieshelp(key))
                    elif tablename == 'attributes' and j == 0:
                        myitem.setToolTip(get_attributeshelp(key))
                    elif tablename == 'bids' and j == 0:
                        myitem.setToolTip(get_entityhelp(key))
                    elif tablename == 'meta' and j == 0:
                        myitem.setToolTip(get_metahelp(key))
                    elif tablename == 'events_columns' and j == 1:
                        myitem.setToolTip(get_eventshelp(itemvalue))
                    table.setItem(i, j, myitem)

        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(ncols - 1, QHeaderView.ResizeMode.Stretch)
        table.show()
        table.blockSignals(False)

    @QtCore.pyqtSlot(QtCore.QPoint)
    def import_menu(self, pos):
        """Pops up a context-menu for importing data in the meta_table"""

        menu        = QtWidgets.QMenu(self)
        import_data = menu.addAction('Import metadata')
        clear_table = menu.addAction('Clear table')
        action      = menu.exec(self.meta_table.viewport().mapToGlobal(pos))

        if action == import_data:

            # Read all the metadata from disk and store it in the target_run
            metafile, _ = QFileDialog.getOpenFileName(self, 'Import metadata from file', str(self.source_run.provenance),
                                                      'JSON/YAML/CSV/TSV Files (*.json *.yaml *.yml *.txt *.csv *.tsv);;All Files (*)')
            if metafile:

                # Get the existing metadata from the table
                _,_,_,meta_data,_ = self.run2data()

                # Read the new metadata from disk
                LOGGER.info(f"Importing metadata from: '{metafile}''")
                try:
                    with open(metafile, 'r') as meta_fid:
                        if Path(metafile).suffix == '.json':
                            metadata = json.load(meta_fid)
                        elif Path(metafile).suffix in ('.yaml', '.yml'):
                            metadata = bids.yaml.safe_load(meta_fid)
                        else:
                            dialect = csv.Sniffer().sniff(meta_fid.read())
                            meta_fid.seek(0)
                            metadata = {}
                            for row in csv.reader(meta_fid, dialect=dialect):
                                metadata[row[0]] = row[1] if len(row)>1 else None
                    if not isinstance(metadata, dict):
                        raise ValueError('Unknown dataformat')
                except Exception as readerror:
                    LOGGER.info(f"Failed to import metadata from: {metafile}\n{readerror}")
                    return

                # Write all the metadata to the target_run
                self.target_run.meta.update(metadata)

                # Refresh the meta-table using the target_run
                _,_,_,meta_data,_ = self.run2data()
                self.fill_table(self.meta_table, meta_data)

        elif action == clear_table:
            self.target_run.meta = {}
            self.fill_table(self.meta_table, [])

    def run2data(self) -> tuple:
        """Derive the tabular data from the target_run, needed to render the tables in the edit window
        :return: (properties_data, attributes_data, bids_data, meta_data, events_data)
        """

        runitem = self.target_run

        # Set up the data for the properties table
        property = self.datasource.property
        properties_data = [[{'value': 'filepath', 'editable': False}, {'value': runitem.properties['filepath'], 'editable': True}, {'value': property('filepath'), 'editable': False}],
                           [{'value': 'filename', 'editable': False}, {'value': runitem.properties['filename'], 'editable': True}, {'value': property('filename'), 'editable': False}],
                           [{'value': 'filesize', 'editable': False}, {'value': runitem.properties['filesize'], 'editable': True}, {'value': property('filesize'), 'editable': False}],
                           [{'value': 'nrfiles',  'editable': False}, {'value': runitem.properties['nrfiles'],  'editable': True}, {'value': property('nrfiles'),  'editable': False}]]

        # Set up the data for the attributes table
        attributes_data = []
        for atrkey, atrvalue in runitem.attributes.items():
            attributes_data.append([{'value': atrkey, 'editable': False}, {'value': atrvalue, 'editable': True}])

        # Set up the data for the bids table
        bids_data = []
        bidsname  = runitem.bidsname(self.subid, self.sesid, False) + '.json'
        if bids.check_ignore(runitem.datatype, self.bidsignore) or bids.check_ignore(bidsname, self.bidsignore, 'file') or runitem.datatype in self.ignoredatatypes:
            bidskeys = runitem.bids.keys()
        else:
            bidskeys = [bids.entities[entity].name for entity in bids.entityrules if entity not in ('subject', 'session')] + ['suffix']   # Impose the BIDS-specified order + suffix
        for bidsent in bidskeys:
            if bidsent in runitem.bids:
                bidsvalues = runitem.bids.get(bidsent)
                if (runitem.datatype in self.bidsdatatypes and bidsent=='suffix') or isinstance(bidsvalues, list):
                    editable = False
                else:
                    editable = True
                bids_data.append([{'value': bidsent, 'editable': False}, {'value': bidsvalues, 'editable': editable}])          # NB: This can be a (menu) list

        # Set up the data for the meta table
        meta_data = []
        for metakey, metavalue in runitem.meta.items():
            meta_data.append([{'value': metakey, 'editable': True}, {'value': metavalue, 'editable': True}])

        # Set up the data for the events timing
        events_data = {}
        if self.events:
            events_data['time'] = [[{'value': 'columns',   'editable': False}, {'value': self.events.time.cols,  'editable': True}],
                                   [{'value': 'units/sec', 'editable': False}, {'value': self.events.time.unit,  'editable': True}],
                                   [{'value': 'start',     'editable': False}, {'value': self.events.time.start, 'editable': True}]]

            # Set up the data for the events parsing
            events_data['parsing'] = []
            for key, value in self.events.parsing.items():
                events_data['parsing'].append([{'value': key, 'editable': False}, {'value': value, 'editable': True}])

            # Set up the data for the events conditions / row groups
            events_data['rows'] = [[{'value': 'condition', 'editable': False}, {'value': 'output column', 'editable': False}]]
            for condition in self.events.rows:
                events_data['rows'].append([{'value': f"{dict(condition.get('condition') or {})}", 'editable': True}, {'value': f"{dict(condition.get('cast') or {})}", 'editable': True}])

            # Set up the data for the events columns
            events_data['columns'] = [[{'value': 'input', 'editable': False}, {'value': 'output', 'editable': False}]]
            for mapping in self.events.columns:
                for key, value in mapping.items():
                    events_data['columns'].append([{'value': value, 'editable': True}, {'value': key, 'editable': key not in ('onset','duration')}])

        return properties_data, attributes_data, bids_data, meta_data, events_data

    def properties2run(self, rowindex: int, colindex: int):
        """Source attribute value has been changed. If OK, update the target run"""

        # Only if cell was actually clicked, update (i.e. not when BIDS datatype changes)
        if colindex == 1:
            key      = self.properties_table.item(rowindex, 0).text().strip()
            value    = self.properties_table.item(rowindex, 1).text().strip()
            if (oldvalue := self.target_run.properties.get(key)) is None:
                oldvalue = ''

            # Only if cell was changed, update
            if key and value != oldvalue:
                answer = QMessageBox.question(self, f"Edit {self.dataformat} properties",
                                              f'It is discouraged to change {self.dataformat} property values unless you are an expert user. Do you really want to change "{oldvalue}" to "{value}"?',
                                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if answer == QMessageBox.StandardButton.Yes:
                    LOGGER.verbose(f"Expert usage: User sets ['{key}'] from '{oldvalue}' to '{value}' for {self.target_run}")
                    self.target_run.properties[key] = value
                else:
                    self.properties_table.blockSignals(True)
                    self.properties_table.item(rowindex, 1).setText(oldvalue)
                    self.properties_table.blockSignals(False)

    def attributes2run(self, rowindex: int, colindex: int):
        """Source attribute value has been changed. If OK, update the target run"""

        # Only if cell was actually clicked, update (i.e. not when BIDS datatype changes)
        if colindex == 1:
            key      = self.attributes_table.item(rowindex, 0).text().strip()
            value    = self.attributes_table.item(rowindex, 1).text()
            if (oldvalue := self.target_run.attributes.get(key)) is None:
                oldvalue = ''

            # Only if cell was changed, update
            if key and value != oldvalue:
                answer = QMessageBox.question(self, f"Edit {self.dataformat} attributes",
                                              f'It is discouraged to change {self.dataformat} attribute values unless you are an expert user. Do you really want to change "{oldvalue}" to "{value}"?',
                                              QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                if answer == QMessageBox.StandardButton.Yes:
                    LOGGER.verbose(f"Expert usage: User sets ['{key}'] from '{oldvalue}' to '{value}' for {self.target_run}")
                    self.target_run.attributes[key] = value
                else:
                    self.attributes_table.blockSignals(True)
                    self.attributes_table.item(rowindex, 1).setText(oldvalue)
                    self.attributes_table.blockSignals(False)

    def bids2run(self, rowindex: int, colindex: int):
        """BIDS attribute value has been changed. If OK, update the target run"""

        # Only if cell was actually clicked, update (i.e. not when BIDS datatype changes) and store the data in the target_run
        if colindex == 1:
            key = self.bids_table.item(rowindex, 0).text()
            if hasattr(self.bids_table.cellWidget(rowindex, 1), 'spacedwidget'):
                dropdown = self.bids_table.cellWidget(rowindex, 1).spacedwidget
                value    = [dropdown.itemText(n) for n in range(len(dropdown))] + [dropdown.currentIndex()]
            else:
                value    = self.bids_table.item(rowindex, 1).text().strip()
            if (oldvalue := self.target_run.bids.get(key)) is None:
                oldvalue = ''

            # Only if cell was changed, update
            if key and value != oldvalue:
                # Validate user input against BIDS or replace the (dynamic) bids-value if it is a run attribute
                self.bids_table.blockSignals(True)
                if isinstance(value, str) and ('<<' not in value or '>>' not in value):
                    value = bids.sanitize(self.datasource.dynamicvalue(value))
                    self.bids_table.item(rowindex, 1).setText(value)
                if key == 'run' and value and '<<' in oldvalue and '>>' in oldvalue and not ('<<' in value and '>>' in value):
                    answer = QMessageBox.question(self, f"Edit bids entities",
                                                  f'It is discouraged to remove the <<dynamic>> run-index. Do you really want to change "{oldvalue}" to "{value}"?',
                                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
                    if answer == QMessageBox.StandardButton.Yes:
                        LOGGER.verbose(f"Expert usage: User sets bids['{key}'] from '{oldvalue}' to '{value}' for {self.target_run}")
                    else:
                        value = oldvalue
                        self.bids_table.item(rowindex, 1).setText(oldvalue)
                        LOGGER.verbose(f"User sets bids['{key}'] from '{oldvalue}' to '{value}' for {self.target_run}")
                else:
                    LOGGER.verbose(f"User sets bids['{key}'] from '{oldvalue}' to '{value}' for {self.target_run}")
                self.bids_table.blockSignals(False)
                self.target_run.bids[key] = value
                self.update_bidsname()

    def meta2run(self, rowindex: int, colindex: int):
        """Meta value has been changed. If OK, update the target run"""

        key      = self.meta_table.item(rowindex, 0).text().strip()
        value    = self.meta_table.item(rowindex, 1).text().strip()
        if value != (oldvalue := self.target_run.meta.get(key)):
            # Replace the (dynamic) value
            if '<<' not in value or '>>' not in value:
                value = self.datasource.dynamicvalue(value, cleanup=False)
                self.meta_table.blockSignals(True)
                self.meta_table.item(rowindex, 1).setText(value)
                self.meta_table.blockSignals(False)
            LOGGER.verbose(f"User sets meta['{key}'] from '{oldvalue}' to '{value}' for {self.target_run}")

        # Read all the metadata from the table and store it in the target_run
        self.target_run.meta = {}
        for n in range(self.meta_table.rowCount()):
            key_   = self.meta_table.item(n, 0).text().strip()
            value_ = self.meta_table.item(n, 1).text().strip()
            if key_:
                try: value_ = ast.literal_eval(value_)      # E.g. convert stringified list or int back to list or int
                except (ValueError, TypeError, SyntaxError): pass
                self.target_run.meta[key_] = value_
            elif value_:
                QMessageBox.warning(self, 'Input error', f"Please enter a key-name (left cell) for the '{value_}' value in row {n+1}")

        # Refresh the table, i.e. delete empty rows or add a new row if a key is defined on the last row
        _,_,_,meta_data,_ = self.run2data()
        self.fill_table(self.meta_table, meta_data)

    def events_time2run(self, rowindex: int, colindex: int):
        """Events value has been changed. Read the data from the event 'time' table and, if OK, update the target run"""

        # events_data['time'] = [['columns',   events.timecols],
        #                        ['units/sec', events.timeunit],
        #                        ['start',     events.start]]
        key      = self.events_time.item(rowindex, 0).text().strip()
        value    = self.events_time.item(rowindex, 1).text().strip()
        timecols = self.events.time.cols
        timeunit = self.events.time.unit
        start    = self.events.time.start

        try:
            if key == 'columns':
                value = ast.literal_eval(value)             # Convert stringified list back to list
                for pattern in value:
                    re.compile(pattern)
                LOGGER.verbose(f"User sets events['timecols'] from '{timecols}' to '{value}' for {self.target_run}")
                self.events.time.cols = value
            elif key == 'units/sec':
                value = int(value)
                LOGGER.verbose(f"User sets events['units/sec'] from '{timeunit}' to '{value}' for {self.target_run}")
                self.events.time.unit = value
            elif key == 'start':
                value = ast.literal_eval(value)             # Convert stringified dict back to dict
                for column in value.copy():
                    if column not in self.events.logtable():
                        newcol = self.get_input_column(column)
                        if newcol == column:
                            raise KeyError
                        value[newcol] = value.pop(column)   # Rename the input column
                LOGGER.verbose(f"User sets events['{key}'] from '{start}' to '{value}' for {self.target_run}")
                self.events.time.start = value
        except (ValueError, TypeError, SyntaxError):
            QMessageBox.warning(self, 'Input error', f"Please enter a valid '{value}' value")
        except re.error as pattern_error:
            QMessageBox.warning(self, 'Input error', f"Please enter a valid '{value}' pattern:\n\n{pattern_error}")
        except KeyError as key_error:
            pass

        # Refresh the events tables, i.e. delete empty rows or add a new row if a key is defined on the last row
        _,_,_,_,events_data = self.run2data()
        self.fill_table(self.events_time,  events_data['time'])
        self.events_table.update_table(self.events.eventstable())

    def events_parsing2run(self, rowindex: int, colindex: int):
        """Events parsing table has been changed. Read the data from the event 'parsing' table and, if OK, update the target run"""

        key = self.events_parsing.item(rowindex, 0).text().strip()
        if hasattr(self.events_parsing.cellWidget(rowindex, 1), 'spacedwidget'):
            dropdown = self.events_parsing.cellWidget(rowindex, 1).spacedwidget
            value    = [dropdown.itemText(n) for n in range(len(dropdown))] + [dropdown.currentIndex()]
        else:
            value    = self.events_parsing.item(rowindex, 1).text().strip()
        if (oldvalue := self.events.parsing.get(key)) is None:
            oldvalue = ''

        # Only if cell was changed, update
        if key and value != oldvalue:
            LOGGER.verbose(f"User sets events['parsing']['{key}'] from '{oldvalue}' to '{value}' for {self.target_run}")
            self.events.parsing[key] = value

        # Refresh the log and events tables
        self.log_table.update_table(self.events.logtable())
        self.events_table.update_table(self.events.eventstable())

    def events_rows2run(self, rowindex: int, colindex: int):
        """Events value has been changed. Read the data from the event 'rows' table and, if OK, update the target run"""

        # row: [[condition, {column_in: pattern, column_in: pattern}], [cast, {column_out: value, column_out: value}]]
        mapping = self.events_rows.item(rowindex, colindex).text().strip() if self.events_rows.item(rowindex, colindex) else ''
        nrows   = self.events_rows.rowCount()

        if mapping:
            try:
                mapping = ast.literal_eval(mapping)                 # Convert stringified dict back to dict
                for column, pattern in mapping.copy().items():
                    re.compile(str(pattern) if colindex==0 else '')
                    if colindex == 0 and column not in self.events.logtable():
                        newcol = self.get_input_column(column)
                        if newcol == column:                        # The user cancelled the dialogue
                            raise KeyError
                        mapping[newcol] = mapping.pop(column)       # Rename the input column
                LOGGER.verbose(f"User sets events['rows'][{rowindex}] to {mapping}' for {self.target_run}")
                if rowindex == nrows - 1:
                    self.events.rows.append({'condition' if colindex==0 else 'cast': mapping})
                else:
                    self.events.rows[rowindex]['condition' if colindex==0 else 'cast'] = mapping
            except (ValueError, TypeError, SyntaxError) as dict_error:
                QMessageBox.warning(self, 'Input error', f"Please enter a valid '{mapping}' dictionary\n\n{dict_error}")
            except re.error as pattern_error:
                QMessageBox.warning(self, 'Input error', f"Please enter a valid '{mapping}' pattern:\n\n{pattern_error}")
            except KeyError as key_error:
                pass
        elif colindex == 0 and rowindex < nrows - 1:                # Remove the row
            del self.events.rows[rowindex]
        else:
            LOGGER.bcdebug(f"Cannot remove events['rows'][{rowindex}] for {self.target_run}")

        # Refresh the events tables, i.e. delete empty rows or add a new row if a key is defined on the last row
        _,_,_,_,events_data = self.run2data()
        self.fill_table(self.events_rows, events_data['rows'])
        self.events_table.update_table(self.events.eventstable())

    def events_columns2run(self, rowindex: int, colindex: int, _input: str=''):
        """Events value has been changed. Read the data from the event 'columns' table and, if OK, update the target run"""

        # events_data['columns'] = [[{'source1': target1}],
        #                           [{'source2': target2}],
        #                           [..]]
        input  = self.events_columns.item(rowindex, 0).text().strip() if self.events_columns.item(rowindex, 0) and not _input else _input
        output = self.events_columns.item(rowindex, 1).text().strip() if self.events_columns.item(rowindex, 1) else ''
        nrows  = self.events_columns.rowCount()

        if colindex == 0 and input and not output:
            output = input

        if not input or input in self.events.logtable():
            LOGGER.verbose(f"User sets the events column to: '{input}: {output}' for {self.target_run}")
            if output:                              # Evaluate and store the data
                if rowindex == nrows - 1:
                    self.events.columns.append({output: input})
                    self.events_columns.insertRow(nrows)
                else:
                    self.events.columns[rowindex] = {output: input}
            elif rowindex < nrows - 1:              # Remove the row
                del self.events.columns[rowindex]
        elif not _input:
            self.events_columns2run(rowindex, -1, self.get_input_column(input))
            return

        # Refresh the events tables, i.e. delete empty rows or add a new row if a key is defined on the last row
        _,_,_,_,events_data = self.run2data()
        self.fill_table(self.events_columns, events_data['columns'])
        self.events_table.update_table(self.events.eventstable())

    def get_input_column(self, input: str) -> str:
        """Ask the user to pick an input column from the log table"""

        # Get column names
        columns    = self.events.logtable().columns.tolist()
        column, ok = QInputDialog.getItem(self, 'Input error', f"Your '{input}' input column does not exist, please choose one of the existing columns:", columns, 0, False)

        return column if ok else input

    def edit_events(self):
        """Edit button clicked"""

        self.sourcebox.hide()
        self.arrow.hide()
        self.bidsbox.hide()
        self.events_inputbox.show()
        self.events_editbox.show()
        self.edit_button.hide()
        self.done_button.show()

    def done_events(self):
        """Done button clicked"""

        self.sourcebox.show()
        self.arrow.show()
        self.bidsbox.show()
        self.events_inputbox.hide()
        self.events_editbox.hide()
        self.edit_button.show()
        self.done_button.hide()

    def change_run(self, suffix_idx):
        """
        Resets the edit dialog window with a new target_run from the template bidsmap after a suffix- or datatype-change

        :param suffix_idx: The suffix or index number that will be used to extract the run from the template bidsmap
        """

        # Add a check to see if we can still read the source data
        provenance = self.target_run.provenance
        if not Path(provenance).is_file():
            LOGGER.warning(f"Can no longer find the source file: {provenance}")
            QMessageBox.warning(self, 'Edit run-item', f"Cannot reliably change the datatype and/or suffix because the source file '{provenance}' can no longer be found.\n\nPlease restore the source data or use the `bidsmapper -s` option to solve this issue. Resetting the run-item now...")
            self.reset()
            return

        # Get the new target_run from the template
        template_run = self.template_bidsmap.get_run(self.target_run.datatype, suffix_idx, self.datasource)
        if not template_run:
            QMessageBox.warning(self, 'Edit run-item', f"Cannot find the {self.target_run.datatype}[{suffix_idx}] datatype in your template. Resetting the run-item now...")
            self.reset()
            return

        # Transfer the old provenance and entity data to the new run-item if it is missing
        old_entities               = self.target_run.bids.copy()
        self.target_run.properties = template_run.properties.copy()
        self.target_run.attributes = template_run.attributes.copy()
        self.target_run.bids       = template_run.bids.copy()
        for key, val in old_entities.items():
            if val and key in self.target_run.bids and not self.target_run.bids[key]:
                self.target_run.bids[key] = val
        self.target_run.meta       = template_run.meta.copy()
        self.target_run._events    = copy.deepcopy(template_run._events)

        # Reset the edit window with the new target_run
        self.reset(refresh=True)

    def change_datatype(self):
        """Update the BIDS values and BIDS output name section when the dropdown selection has been taking place"""

        self.target_run.datatype = self.datatype_dropdown.currentText()

        LOGGER.verbose(f"User changes the BIDS data type from '{self.source_run.datatype}' to '{self.target_run.datatype}' for {self.target_run}")

        self.change_run(0)

    def change_suffix(self):
        """Update the BIDS values and BIDS output name section when the dropdown selection has been taking place"""

        target_suffix = self.suffix_dropdown.currentText()

        LOGGER.verbose(f"User changes the BIDS suffix from '{self.target_run.bids.get('suffix')}' to '{target_suffix}' for {self.target_run}")

        self.change_run(target_suffix)

    def update_bidsname(self):
        """Updates the bidsname with the current (edited) bids values"""

        datatype = self.target_run.datatype
        ignore   = bids.check_ignore(datatype,self.bidsignore) or datatype in self.ignoredatatypes
        bidsname = (Path(datatype)/self.target_run.bidsname(self.subid, self.sesid, not ignore)).with_suffix('.*')

        font = self.bidsname_textbox.font()
        if bids.check_ignore(datatype, self.bidsignore) or bids.check_ignore(bidsname.name, self.bidsignore, 'file'):
            self.bidsname_textbox.setToolTip(f"Orange: This '{datatype}' data type is ignored by BIDS-apps and BIDS-validators")
            self.bidsname_textbox.setTextColor(QtGui.QColor('darkorange'))
            font.setStrikeOut(False)
        elif datatype in self.unknowndatatypes:
            self.bidsname_textbox.setToolTip(f"Red: This '{datatype}' data type is not part of BIDS but will be converted to a BIDS-like entry in the {self.unknowndatatypes} folder. Click 'OK' if you want your BIDS output data to look like this")
            self.bidsname_textbox.setTextColor(QtGui.QColor('red'))
            font.setStrikeOut(False)
        elif datatype in self.ignoredatatypes:
            self.bidsname_textbox.setToolTip(f"Gray/Strike-out: This '{datatype}' data type will be ignored and not converted BIDS. Click 'OK' if you want your BIDS output data to look like this")
            self.bidsname_textbox.setTextColor(QtGui.QColor('gray'))
            font.setStrikeOut(True)
        elif not all(self.target_run.check(checks=(False, True, True))[1:3]):
            self.bidsname_textbox.setToolTip(f"Red: This name is not valid according to the BIDS standard -- see terminal output for more info")
            self.bidsname_textbox.setTextColor(QtGui.QColor('red'))
            font.setStrikeOut(False)
        else:
            self.bidsname_textbox.setToolTip(f"Green: This '{datatype}' data type is part of BIDS. Click 'OK' if you want your BIDS output data to look like this")
            self.bidsname_textbox.setTextColor(QtGui.QColor('green'))
            font.setStrikeOut(False)
        self.bidsname_textbox.setFont(font)
        self.bidsname_textbox.clear()
        self.bidsname_textbox.textCursor().insertText(str(bidsname))

    def reset(self, refresh: bool=False):
        """Resets the edit with the target_run if refresh=True or otherwise with the original source_run (=default)"""

        # Reset the target_run to the source_run
        if not refresh:
            LOGGER.verbose('User resets the BIDS mapping')
            self.target_run = copy.deepcopy(self.source_run)
            self.events     = self.target_run.events()

            # Reset the datatype dropdown menu
            self.datatype_dropdown.blockSignals(True)
            self.datatype_dropdown.setCurrentIndex(self.datatype_dropdown.findText(self.target_run.datatype))
            self.datatype_dropdown.blockSignals(False)

        # Refresh the source attributes and BIDS values with data from the target_run
        properties_data, attributes_data, bids_data, meta_data, events_data = self.run2data()

        # Refresh the existing tables
        self.fill_table(self.properties_table, properties_data)
        self.fill_table(self.attributes_table, attributes_data)
        self.fill_table(self.bids_table, bids_data)
        self.fill_table(self.meta_table, meta_data)
        if self.events:
            self.log_table.update_table(self.events.logtable())
            self.events_table.update_table(self.events.eventstable())
            self.fill_table(self.events_parsing, events_data['parsing'])
            self.fill_table(self.events_time, events_data['time'])
            self.fill_table(self.events_rows, events_data['rows'])
            self.fill_table(self.events_columns, events_data['columns'])
        self.properties_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.properties_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.attributes_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.attributes_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        # Refresh the BIDS output name
        self.update_bidsname()

    def accept_run(self):
        """Save the changes to the target_bidsmap and send it back to the main window: Finished!"""

        # Check if the bidsname is valid
        bidsname  = Path(self.bidsname_textbox.toPlainText())
        validrun  = False not in self.target_run.check(checks=(False, False, False))[1:3]
        bidsvalid = validrun
        datatype  = self.target_run.datatype
        if not (bids.check_ignore(datatype,self.bidsignore) or bids.check_ignore(bidsname.name,self.bidsignore,'file') or datatype in self.ignoredatatypes):
            for ext in bids.extensions + ['.tsv' if self.target_run.bids['suffix']=='events' else '.dum']:     # NB: `ext` used to be '.json', which is more generic (but see https://github.com/bids-standard/bids-validator/issues/2113)
                if bidsvalid := BIDSValidator().is_bids((Path('/')/self.subid/self.sesid/bidsname).with_suffix(ext).as_posix()): break

        # If the bidsname is not valid, ask the user if that's OK
        message = ''
        if validrun and not bidsvalid:
            message = f'The run-item seems valid but the "{bidsname}" name did not pass the bids-validator test'
        elif not validrun and bidsvalid:
            message = f'The run-item does not seem to be valid but the "{bidsname}" name does pass the bids-validator test'
        elif not validrun:
            message = f'The "{bidsname}" name is not valid according to the BIDS standard'
        elif datatype=='fmap' and not (self.target_run.meta.get('B0FieldSource') or
                                       self.target_run.meta.get('B0FieldIdentifier') or
                                       self.target_run.meta.get('IntendedFor')):
            message = f'The "B0FieldIdentifier/IntendedFor" metadata is left empty for {bidsname} (not recommended)'
        if message:
            answer = QMessageBox.question(self, 'Edit run-item', f'WARNING:\n{message}\n\nDo you want to go back and edit the run?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if answer == QMessageBox.StandardButton.Yes: return
            LOGGER.warning(message)

        LOGGER.verbose(f'User approves the edit')
        if self.target_run != self.source_run:
            self.output_bidsmap.update(self.source_run.datatype, self.target_run)
            self.done_edit.emit(self.dataformat)
            self.done(1)
        else:
            self.done(2)

    def export_run(self):
        """Export the edited run to a (e.g. template) bidsmap on disk"""

        yamlfile, _ = QFileDialog.getOpenFileName(self, 'Export run item to (template) bidsmap',
                                                  str(bidsmap_template), 'YAML Files (*.yaml *.yml);;All Files (*)')
        if yamlfile:
            LOGGER.info(f'Exporting run item {self.target_run} -> {yamlfile}')
            bidsmap = BidsMap(Path(yamlfile), checks=(False, False, False))
            bidsmap.insert_run(self.target_run)
            bidsmap.save()
            QMessageBox.information(self, 'Edit run-item', f"Successfully exported:\n\n{self.target_run} -> {yamlfile}")

    def get_allowed_suffixes(self) -> dict[str, set]:
        """Derive the possible suffixes for each datatype from the template. """

        allowed_suffixes = {}
        for datatype in self.bidsdatatypes + self.unknowndatatypes + self.ignoredatatypes:
            allowed_suffixes[datatype] = set()
            for runitem in self.template_bidsmap.dataformat(self.dataformat).datatype(datatype).runitems:
                suffix = self.datasource.dynamicvalue(runitem.bids['suffix'], True)
                if suffix:
                    allowed_suffixes[str(datatype)].add(suffix)

        return allowed_suffixes

    def inspect_sourcefile(self, rowindex: int=None, colindex: int=None):
        """When double-clicked, show popup window"""

        # The properties table has two columns: 0: filename, 2: provenance
        if colindex in (0,2,None):
            if rowindex == 1 or colindex is None:
                self.popup = InspectWindow(Path(self.target_run.provenance))
                self.popup.show()
                self.popup.scrollbar.setValue(0)  # This can only be done after self.popup.show()
            elif rowindex == 0:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(Path(self.target_run.provenance).parent)))

    @staticmethod
    def spacedwidget(childwidget, align='left'):
        """Place the widget in a QHBoxLayout and add a stretcher next to it. Return the widget as widget.spacedwidget"""

        widget = QtWidgets.QWidget()
        layout = QHBoxLayout()
        if align != 'left':
            layout.addStretch()
            layout.addWidget(childwidget)
        else:
            layout.addWidget(childwidget)
            layout.addStretch()
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)
        widget.spacedwidget = childwidget
        return widget

    def get_help(self):
        """Open web page for help"""
        help_url = HELP_URLS.get(self.target_run.datatype, HELP_URL_DEFAULT)
        webbrowser.open(help_url)

        messagebox = QMessageBox(self)
        messagebox.setText(f"\n{get_douglas_adams_quote()}")
        messagebox.setWindowTitle("Don't panic")
        messagebox.setIconPixmap(QtGui.QPixmap(str(Path(__file__).parent/'egg.png')).scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        messagebox.setToolTip("Thanks for all the fish!")
        messagebox.setFont(QtGui.QFont('Courier New', pointSize=13))
        messagebox.show()


class CompareWindow(QDialog):

    def __init__(self, runitems: list[RunItem], subid: list[str], sesid: list[str]):
        super().__init__()

        # Set up the window
        self.setWindowIcon(QtGui.QIcon(str(BIDSCOIN_ICON)))
        self.setWindowFlags(self.windowFlags() & Qt.WindowType.WindowTitleHint & Qt.WindowType.WindowMinMaxButtonsHint & Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle('Compare BIDS mappings')
        self.setWhatsThis('BIDScoin mapping of properties and attributes to BIDS output data')

        layout_main = QHBoxLayout(self)

        for index, runitem in enumerate(runitems):

            # Get data for the tables
            properties_data, attributes_data, bids_data, meta_data = self.run2data(runitem)

            # Set up the properties table
            properties_label = QLabel('Properties')
            properties_label.setToolTip('The filesystem properties that match with (identify) the source file')
            properties_table = self.fill_table(properties_data, 'properties')
            properties_table.setToolTip('The filesystem property that matches with the source file')
            properties_table.cellDoubleClicked.connect(partial(self.inspect_sourcefile, runitem.provenance))
            properties_table.setMinimumHeight(properties_table.height() + 10)  # Add 10 pixels of padding (to avoid scrollbar flickering on some older systems)

            # Set up the attributes table
            attributes_label = QLabel('Attributes')
            attributes_label.setToolTip('The attributes that match with (identify) the source file')
            attributes_table = self.fill_table(attributes_data, 'attributes', min_vsize=False)
            attributes_table.setToolTip('The attribute that matches with the source file')

            # Set up the BIDS table
            bids_label = QLabel('BIDS entities')
            bids_label.setToolTip('The BIDS entities that are used to construct the BIDS output filename')
            bids_table = self.fill_table(bids_data, 'bids')
            bids_table.setToolTip('The BIDS entity that is used to construct the BIDS output filename')

            # Set up the meta table
            if meta_data:
                meta_label = QLabel('Metadata')
                meta_label.setToolTip('Key-value pairs that will be appended to the (e.g. dcm2niix-produced) json sidecar file')
                meta_table = self.fill_table(meta_data, 'meta')
                meta_table.setToolTip('The key-value pair that will be appended to the (e.g. dcm2niix-produced) json sidecar file')

            # Set up the events table
            events = runitem.events()
            if events:
                events_label = QLabel('Events data')
                events_label.setToolTip('The stimulus events data that are save as tsv-file')
                events_table = MyQTableView(self, events.eventstable())
                events_table.setToolTip('The stimulus events data that are save as tsv-file')

            bidsname = runitem.bidsname(subid[index], sesid[index], False) + '.*'
            groupbox = QGroupBox(f"{runitem.datatype}/{bidsname}")
            layout   = QVBoxLayout()
            layout.addWidget(properties_label)
            layout.addWidget(properties_table)
            layout.addWidget(attributes_label)
            layout.addWidget(attributes_table)
            layout.addWidget(bids_label)
            layout.addWidget(bids_table)
            if meta_data:
                layout.addWidget(meta_label)
                layout.addWidget(meta_table)
            if events:
                layout.addWidget(events_label)
                layout.addWidget(events_table)
            groupbox.setLayout(layout)

            # Set up the main layout
            layout_main.addWidget(groupbox)

        self.show()

    @staticmethod
    def run2data(runitem: RunItem) -> tuple:
        """Derive the tabular data from the target_run, needed to render the compare window
        :return: (properties_data, attributes_data, bids_data, meta_data)
        """

        properties_data = [['filepath', runitem.properties.get('filepath'), runitem.datasource.property('filepath')],
                           ['filename', runitem.properties.get('filename'), runitem.datasource.property('filename')],
                           ['filesize', runitem.properties.get('filesize'), runitem.datasource.property('filesize')],
                           ['nrfiles',  runitem.properties.get('nrfiles'),  runitem.datasource.property('nrfiles')]]

        attributes_data = []
        for key in sorted(runitem.attributes.keys()):
            value = runitem.attributes.get(key)
            attributes_data.append([key, value])

        bids_data = []
        bidskeys = [bids.entities[entity].name for entity in bids.entityrules if entity not in ('subject', 'session')] + ['suffix']   # Impose the BIDS-specified order + suffix
        for key in bidskeys:
            if key in runitem.bids:
                value = runitem.bids.get(key)
                if isinstance(value, list):
                    value = value[value[-1]]
                bids_data.append([key, value])

        meta_data = []
        for key in sorted(runitem.meta.keys()):
            value = runitem.meta.get(key)
            meta_data.append([key, value])

        return properties_data, attributes_data, bids_data, meta_data

    def fill_table(self, data: list, name: str, min_vsize: bool=True) -> MyQTable:
        """Return a table widget filled with the data"""

        ncols = len(data[0]) if data else 2             # Always at least two columns (i.e. key, value)
        table = MyQTable(self, min_vsize, ncols, len(data))
        table.setObjectName(name)                       # NB: Serves to identify the tables in fill_table()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        for i, row in enumerate(data):
            for j, value in enumerate(row):
                item = QTableWidgetItem()
                item.setText(str(value or ''))
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                table.setItem(i, j, item)

        return table

    def inspect_sourcefile(self, provenance: str, rowindex: int=None, colindex: int=None):
        """When double-clicked, show popup window"""

        if colindex in (0,2):
            if rowindex == 0:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(Path(provenance).parent)))
            if rowindex == 1:
                self.popup = InspectWindow(Path(provenance))
                self.popup.show()
                self.popup.scrollbar.setValue(0)  # This can only be done after self.popup.show()


class InspectWindow(QDialog):

    def __init__(self, filename: Path):
        super().__init__()

        if is_dicomfile(filename):
            if filename.name == 'DICOMDIR':
                LOGGER.bcdebug(f"Getting DICOM fields from {filename} will raise dcmread error below if pydicom => v3.0")
            text = str(dcmread(filename, force=True))
        elif is_parfile(filename) or filename.suffix.lower() in ('.spar', '.txt', '.text', '.log', '.csv', '.tsv'):
            text = filename.read_text()
        elif filename.suffix.lower() == '.7':
            try:
                from spec2nii.GE.ge_read_pfile import Pfile
                text = ''
                hdr = Pfile(filename).hdr
                for field in hdr._fields_:
                    data = getattr(hdr, field[0])
                    if type(data) is bytes:
                        try: data = data.decode('UTF-8')
                        except UnicodeDecodeError: pass
                    text += f"{field[0]}:\t {data}\n"
            except ImportError as perror:
                text = f"Could not inspect: {filename}"
                LOGGER.verbose(f"Could not import spec2nii to read {filename}\n{perror}")
        elif filename.is_file() and filename.suffix.lower() in sum((klass.valid_exts for klass in nib.imageclasses.all_image_classes), ('.nii',)) or filename.name.endswith('.nii.gz'):
            text = str(nib.load(filename).header)
        else:
            text = f"Could not inspect: {filename}"
            LOGGER.verbose(text)

        self.setWindowIcon(QtGui.QIcon(str(BIDSCOIN_ICON)))
        self.setWindowTitle(str(filename))
        self.setWindowFlags(self.windowFlags() & Qt.WindowType.WindowContextHelpButtonHint & Qt.WindowType.WindowMinMaxButtonsHint & Qt.WindowType.WindowCloseButtonHint)

        layout = QVBoxLayout(self)

        textbrowser = QTextBrowser(self)
        textbrowser.setFont(QtGui.QFont("Courier New"))
        textbrowser.insertPlainText(text)
        textbrowser.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.NoWrap)
        textbrowser.setWhatsThis(f"This window displays all available source attributes")
        self.scrollbar = textbrowser.verticalScrollBar()        # For setting the slider to the top (can only be done after self.show()
        layout.addWidget(textbrowser)

        # Set the layout-width to the width of the text
        fontmetrics = QtGui.QFontMetrics(textbrowser.font())
        textwidth   = fontmetrics.size(0, text).width()
        self.resize(min(textwidth + 70, 1200), self.height())


def get_propertieshelp(propertieskey: str) -> str:
    """
    Reads the description of a matching attributes key in the source dictionary

    :param propertieskey:   The properties key for which the help text is obtained
    :return:                The obtained help text
    """

    # Return the description from the DICOM dictionary or a default text
    if propertieskey == 'filepath':
        return 'The path of the source file that is matched against the (regex) pattern'
    if propertieskey == 'filename':
        return 'The name of the source file that is matched against the (regex) pattern'
    if propertieskey == 'filesize':
        return 'The size of the source file that is matched against the (regex) pattern'
    if propertieskey == 'nrfiles':
        return 'The nr of similar files in the folder that matched against the properties (regex) patterns'

    return f"{propertieskey} is not a valid property-key"


def get_attributeshelp(attributeskey: str) -> str:
    """
    Reads the description of a matching attributes key in the source dictionary

    TODO: implement PAR/REC support

    :param attributeskey:   The attribute key for which the help text is obtained
    :return:                The obtained help text
    """

    if not attributeskey:
        return 'Please provide a key-name'

    # Return the description from the DICOM dictionary or a default text
    try:
        return f"{attributeskey}\nThe DICOM '{datadict.dictionary_description(attributeskey)}' attribute"

    except ValueError:
        return f"{attributeskey}\nAn unknown/private attribute"


def get_datatypehelp(datatype: Union[str, DataType]) -> str:
    """
    Reads the description of the datatype in the schema/objects/datatypes.yaml file

    :param datatype:    The datatype for which the help text is obtained
    :return:            The obtained help text
    """

    datatype = str(datatype)

    if not datatype:
        return "Please provide a datatype"

    # Return the description for the datatype or a default text
    bidsdatatypes = bids.bidsschema.objects.datatypes
    if datatype in bidsdatatypes:
        return f"{bidsdatatypes[datatype].display_name}\n{bidsdatatypes[datatype].description}"
    elif datatype == 'exclude':
        return 'Source data that is to be excluded / not converted to BIDS'
    elif datatype == 'extra_data':
        return 'Source data that is converted to BIDS-like output data'

    return f"{datatype}\nAn unknown/private datatype"


def get_suffixhelp(suffix: str) -> str:
    """
    Reads the description of the suffix in the schema/objects/suffixes.yaml file

    :param suffix:      The suffix for which the help text is obtained
    :return:            The obtained help text
    """

    if not suffix:
        return "Please provide a suffix"

    # Return the description for the suffix or a default text
    suffixes = bids.bidsschema.objects.suffixes
    if suffix in suffixes:
        return f"{suffixes[suffix].display_name}\n{suffixes[suffix].description}"

    return f"{suffix}\nAn unknown/private suffix"


def get_columnhelp(column: str) -> str:
    """
    Reads the description of a matching entity=entitykey in the bidsschema.objects.columns

    :param column:   The column name for which the help text is obtained
    :return:         The obtained help text
    """

    if not column:
        return "Please provide a column-name"

    # Return the description from the entities or a default text
    for _, entity in bids.bidsschema.objects.columns.items():
        if entity.name == column:
            return f"{entity.display_name}\n{entity.description}"

    return f"{column}\nAn unknown/private column name"


def get_entityhelp(entitykey: str) -> str:
    """
    Reads the description of a matching entity=entitykey in the schema/entities.yaml file

    :param entitykey:   The bids key for which the help text is obtained
    :return:            The obtained help text
    """

    if not entitykey:
        return "Please provide a key-name"

    # Return the description from the entities or a default text
    for _, entity in bids.entities.items():
        if entity.name == entitykey:
            return f"{entity.display_name}\n{entity.description}"

    return f"{entitykey}\nAn unknown/private entity"


def get_metahelp(metakey: str) -> str:
    """
    Reads the description of a matching schema/metadata/metakey.yaml file

    :param metakey: The meta key for which the help text is obtained
    :return:        The obtained help text
    """

    if not metakey:
        return "Please provide a key-name"

    # Return the description from the metadata file or a default text
    for _, item in bids.bidsschema.objects.metadata.items():
        if metakey == item.name:
            description = item.description
            if metakey == 'IntendedFor':                            # IntendedFor is a special search-pattern field in BIDScoin
                description += ('\nNB: These associated files can be dynamically searched for'
                                '\nduring bidscoiner runtime with glob-style matching patterns,'
                                '\n"such as <<Reward*_bold><Stop*_epi>>" or <<dwi/*acq-highres*>>'
                                '\n(see documentation)')
            if metakey in ('B0FieldIdentifier', 'B0FieldSource'):   # <<session>> is a special dynamic value in BIDScoin
                description += ('\nNB: The `<<session>>` (sub)string will be replaced by the'
                                '\nsession label during bidscoiner runtime. In this way you can'
                                '\ncreate session-specific B0FieldIdentifier/Source tags (recommended)')

            return f"{item.display_name}\n{description}"

    return f"{metakey}\nAn unknown/custom meta key"


def get_eventshelp(eventkey: str) -> str:
    """
    Reads the description of a matching entity=eventkey in the schema/objects/columns.yaml file

    :param eventkey:    The bids key for which the help text is obtained
    :return:            The obtained help text
    """

    if not eventkey:
        return "Please provide a key-name"

    # Return the description from the entities or a default text
    for _, item in bids.bidsschema.objects.columns.items():
        if item.name == eventkey:
            return f"{item.display_name}\n{item.description}"

    return f"{eventkey}\nA custom column name"


def get_douglas_adams_quote():
    quotes = ['The answer to the ultimate question of life, the universe, and everything is 42.',
              "Don't Panic and always carry a towel!",
              'I love deadlines. I love the whooshing noise they make as they go by.',
              'A common mistake that people make when trying to design something completely foolproof is to underestimate the ingenuity of complete fools.',
              'Time is an illusion. Lunchtime doubly so.',
              'Human beings, who are almost unique in having the ability to learn from the experience of others, are also remarkable for their apparent disinclination to do so.',
              'Flying is learning how to throw yourself at the ground and miss.',
              'It is a mistake to think you can solve any major problems just with potatoes.',
              'The major difference between a thing that might go wrong and a thing that cannot possibly go wrong is that when a thing that cannot possibly go wrong goes wrong it usually turns out to be impossible to get at or repair.',
              "The chances of finding out what's really going on in the universe are so remote, the only thing to do is hang the sense of it and keep yourself occupied.",
              'This must be Thursday. I never could get the hang of Thursdays.',
              'For a moment, nothing happened. Then, after a second or so, nothing continued to happen.',
              "The ships hung in the sky in much the same way that bricks don't.",
              'In the beginning the Universe was created. This has made a lot of people very angry and been widely regarded as a bad move.',
              'I may not have gone where I intended to go, but I think I have ended up where I needed to be.',
              'He was a dreamer, a thinker, a speculative philosopher... or, as his wife would have it, an idiot.',
              "Coding is simple. You just have to gaze at an empty IDE until your forehead develops a persistent twitch and your keyboard starts typing 'Hello World' by itself out of sheer pity.",
              "Debugging follows the same principles as flying: The trick is to throw yourself at the keyboard, miss completely, and by some miraculous oversight of the universe's quality assurance process, end up with working code.",
              "Space is big. Really big. You just won't believe how vastly, hugely, mind-bogglingly big it is. I mean, you may think it's long way down the road to the chemist's, but that's just peanuts to space.",
              "There is a theory which states that if ever anyone discovers exactly what the Universe is for and why it is here, it will instantly disappear and be replaced by something even more bizarre and inexplicable.\n\nThere is another theory which states that this has already happened.",
              "You live and learn. At any rate, you live.",
              "Anyone who is capable of getting themselves made President should on no account be allowed to do the job.",
              "If it looks like a duck, and quacks like a duck, we have at least to consider the possibility that we have a small aquatic bird of the family anatidae on our hands."]

    return random.choice(quotes)


def bidseditor(bidsfolder: str, bidsmap: str='', template: str=bidsmap_template) -> None:
    """
    Collects input and launches the bidseditor GUI

    :param bidsfolder: The name of the BIDS root folder
    :param bidsmap:    The name of the bidsmap YAML-file
    :param template:   The name of the bidsmap template YAML-file
    """

    bidsfolder   = Path(bidsfolder).resolve()
    bidsmapfile  = Path(bidsmap)
    templatefile = Path(template)

    # Start logging
    bcoin.setup_logging(bidsfolder/'code'/'bidscoin'/'bidseditor.log')
    LOGGER.info('')
    LOGGER.info('-------------- START BIDSeditor ------------')
    LOGGER.info(f">>> bidseditor bidsfolder={bidsfolder} bidsmap={bidsmapfile} template={templatefile}")

    # Obtain the initial bidsmap info
    template_bidsmap = BidsMap(templatefile, checks=(True, True, False))
    input_bidsmap    = BidsMap(bidsmapfile,  bidsfolder/'code'/'bidscoin')
    template_bidsmap.check_template()
    if input_bidsmap.filepath.is_file() and input_bidsmap.options:
        template_bidsmap.options = input_bidsmap.options    # Always use the options of the input bidsmap
        template_bidsmap.plugins = input_bidsmap.plugins    # Always use the plugins of the input bidsmap

    # Start the Qt-application
    app = QApplication(sys.argv)
    app.setApplicationName(f"{input_bidsmap.filepath} - BIDS editor {__version__}")
    mainwin = MainWindow(bidsfolder, input_bidsmap, template_bidsmap, datasaved=True)
    mainwin.show()
    app.exec()

    LOGGER.info('-------------- FINISHED! -------------------')
    LOGGER.info('')

    bcoin.reporterrors()


def main():
    """Console script entry point"""

    from bidscoin.cli._bidseditor import get_parser

    # Parse the input arguments and run bidseditor
    args = get_parser().parse_args()

    trackusage('bidseditor')
    try:
        bidseditor(**vars(args))

    except Exception as error:
        trackusage('bidseditor_exception', error)
        raise error


if __name__ == '__main__':
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
