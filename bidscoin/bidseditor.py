#!/usr/bin/env python3
"""A BIDScoin application with a graphical user interface for editing the bidsmap (See also cli/_bidseditor.py)"""

import sys
import logging
import copy
import webbrowser
import ast
import json
import csv
import nibabel as nib
from bids_validator import BIDSValidator
from typing import Union, List, Dict
from pydicom import dcmread, datadict
from pathlib import Path
from functools import partial
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtGui import QAction, QFileSystemModel
from PyQt6.QtWidgets import (QApplication, QMainWindow, QFileDialog, QDialogButtonBox, QTreeView,
                             QHBoxLayout, QVBoxLayout, QLabel, QDialog, QInputDialog, QMessageBox, QTableWidget,
                             QTableWidgetItem, QHeaderView, QGroupBox, QTextBrowser, QPushButton, QComboBox)
from importlib.util import find_spec
if find_spec('bidscoin') is None:
    sys.path.append(str(Path(__file__).parents[1]))
from bidscoin import bcoin, bids, bidsversion, check_version, trackusage, bidsmap_template, __version__
from bidscoin.bids import extensions, BidsMap, RunItem, DataType

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
    
anon: Set this anonymization flag to 'y' to round off age and to discard acquisition date from the meta data

meta: The file extensions of the associated / equally named (meta)data sourcefiles that are copied over as
    BIDS (sidecar) files, such as ['.json', '.tsv', '.tsv.gz']. You can use this to enrich json sidecar files,
    or add data that is not supported by this plugin

fallback: Appends unhandled dcm2niix suffixes to the `acq` label if 'y' (recommended, else the suffix data is discarded)"""


class MainWindow(QMainWindow):

    def __init__(self, bidsfolder: Path, input_bidsmap: BidsMap, template_bidsmap: BidsMap, datasaved: bool=False, reset: bool=False):

        # Set up the main window
        if not reset:
            super().__init__()
            self.setWindowIcon(QtGui.QIcon(str(BIDSCOIN_ICON)))
            self.set_menu_statusbar()

        if not input_bidsmap.filepath.name:
            filename, _ = QFileDialog.getOpenFileName(self, 'Open a bidsmap file', str(bidsfolder), 'YAML Files (*.yaml *.yml);;All Files (*)')
            if filename:
                input_bidsmap = BidsMap(Path(filename))
                if input_bidsmap.options:
                    template_bidsmap.options = input_bidsmap.options    # Always use the options of the input bidsmap
                    template_bidsmap.plugins = input_bidsmap.plugins    # Always use the plugins of the input bidsmap
            else:
                input_bidsmap = copy.deepcopy(template_bidsmap)
                for dataformat in input_bidsmap.dataformats:
                    for datatype in dataformat.datatypes:
                        dataformat.delete_runs(datatype)

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
        self.dataformats                 = [dataformat.dataformat for dataformat in input_bidsmap.dataformats if input_bidsmap.dir(dataformat)]
        self.bidsignore: List[str]       = input_bidsmap.options['bidsignore']
        self.unknowndatatypes: List[str] = input_bidsmap.options['unknowntypes']
        self.ignoredatatypes: List[str]  = input_bidsmap.options['ignoretypes']

        # Set up the tabs, add the tables and put the bidsmap data in them
        tabwidget = self.tabwidget = QtWidgets.QTabWidget()
        tabwidget.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)
        tabwidget.setTabShape(QtWidgets.QTabWidget.TabShape.Rounded)

        self.subses_table       = {}
        self.samples_table      = {}
        self.options_label      = {}
        self.options_table      = {}
        self.ordered_file_index = {}
        """The mapping between the ordered provenance and an increasing file-index"""
        for dataformat in self.dataformats:
            self.set_tab_bidsmap(dataformat)
        self.set_tab_options()
        self.set_tab_filebrowser()

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
        centralwidget = QtWidgets.QWidget()
        top_layout = QVBoxLayout(centralwidget)
        top_layout.addWidget(tabwidget)
        top_layout.addWidget(buttonbox)
        tabwidget.setCurrentIndex(0)

        self.setCentralWidget(centralwidget)

        # Center the main window to the center point of screen
        if not reset:
            center   = QtGui.QScreen.availableGeometry(QApplication.primaryScreen()).center()
            geometry = self.frameGeometry()
            geometry.moveCenter(center)
            self.move(geometry.topLeft())

        # Restore the samples_table stretching after the main window has been sized / current tabindex has been set (otherwise the main window can become too narrow)
        for dataformat in self.dataformats:
            header = self.samples_table[dataformat].horizontalHeader()
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)

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
            super(MainWindow, self).closeEvent(event)
        else:                               # User pressed alt-X (= menu action) -> normal close()
            self.close()
        QApplication.quit()

    @QtCore.pyqtSlot(QtCore.QPoint)
    def show_contextmenu(self, pos):
        """Pops up a context-menu for deleting or editing the right-clicked sample in the samples_table"""

        # Get the activated row-data
        dataformat = self.tabwidget.widget(self.tabwidget.currentIndex()).objectName()
        table      = self.samples_table[dataformat]
        colindex   = table.currentColumn()
        rowindexes = [index.row() for index in table.selectedIndexes() if index.column() == colindex]
        if rowindexes and colindex in (-1, 0, 4):      # User clicked the index, the edit-button or elsewhere (i.e. not on an activated widget)
            return
        runitems: List[RunItem] = []
        subids: List[str]   = []
        sesids: List[str]   = []
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
                    datasource = bids.DataSource(dataformat=dataformat)
                    for filename in filenames:
                        datasource = bids.DataSource(filename, self.output_bidsmap.plugins, dataformat, self.output_bidsmap.options)
                        if datasource.has_plugin():
                            runitem = self.template_bidsmap.get_run(datatype, 0, datasource)
                            runitem.properties['filepath'] = datasource.properties('filepath')      # Make the added run a strict match (i.e. an exception)
                            runitem.properties['filename'] = datasource.properties('filename')      # Make the added run a strict match (i.e. an exception)
                            LOGGER.verbose(f"Expert usage: User adds run-item {dataformat}[{datatype}]: {filename}")
                            if Path(filename) in self.output_bidsmap.dir(dataformat):
                                LOGGER.warning(f"Added run-item {dataformat}[{datatype}]: {filename} already exists")
                            self.output_bidsmap.insert_run(runitem, 0)                      # Put the run at the front (so it gets matching priority)
                            if dataformat not in self.ordered_file_index:
                                self.ordered_file_index[dataformat] = {datasource.path: 0}
                            else:
                                self.ordered_file_index[dataformat][datasource.path] = max(self.ordered_file_index[dataformat][fname] for fname in self.ordered_file_index[dataformat]) + 1
                    if datasource.has_plugin():
                        self.update_subses_samples(dataformat)

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
                self.update_subses_samples(dataformat)

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

                # Change the datatype for the selected run-items
                for index in rowindexes:
                    datatype   = table.item(index, 2).text()
                    provenance = table.item(index, 5).text()
                    if not Path(provenance).is_file():
                        QMessageBox.warning(self, 'Edit BIDS mapping', f"Cannot reliably change the data type and/or suffix because the source file '{provenance}' can no longer be found.\n\nPlease restore the source data or use the `bidsmapper -s` option to solve this issue")
                        continue

                    # Get the new run from the template
                    oldrun      = self.output_bidsmap.find_run(provenance, dataformat, datatype)
                    templaterun = self.template_bidsmap.get_run(newdatatype, 0, oldrun.datasource)
                    if not templaterun:
                        QMessageBox.warning(self, 'Edit BIDS mapping', f"Cannot find the '{newdatatype}' data type in your template")
                        continue

                    # Insert the new run in our output bidsmap
                    self.output_bidsmap.update(datatype, templaterun)
                    LOGGER.verbose(f"User sets run-item {datatype} -> {templaterun}")

                self.update_subses_samples(dataformat)

    def set_menu_statusbar(self):
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

    def set_tab_bidsmap(self, dataformat: str):
        """Set the SOURCE file sample listing tab"""

        # Set the Participant labels table
        subses_label = QLabel('Participant label')
        subses_label.setToolTip('Subject/session mappings')

        subses_table = MyQTableWidget()
        subses_table.setToolTip(f"Use e.g. '<<filepath:/sub-(.*?)/>>' to parse the subject and (optional) session label from the pathname. NB: the () parentheses indicate the part that is extracted as the subject/session label\n"
                                f"Use a dynamic {dataformat} attribute (e.g. '<<PatientName>>') to extract the subject and (optional) session label from the {dataformat} header")
        subses_table.setMouseTracking(True)
        subses_table.setRowCount(2)
        subses_table.setColumnCount(2)
        horizontal_header = subses_table.horizontalHeader()
        horizontal_header.setVisible(False)
        horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        subses_table.cellChanged.connect(self.subsescell2bidsmap)
        self.subses_table[dataformat] = subses_table

        # Set the bidsmap table
        label = QLabel('Data samples')
        label.setToolTip('List of unique source-data samples')

        self.samples_table[dataformat] = samples_table = MyQTableWidget(minimum=False)
        samples_table.setMouseTracking(True)
        samples_table.setShowGrid(True)
        samples_table.setColumnCount(6)
        samples_table.setHorizontalHeaderLabels(['', f'{dataformat} input', 'BIDS data type', 'BIDS output', 'Action', 'Provenance'])
        samples_table.setSortingEnabled(True)
        samples_table.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)
        samples_table.setColumnHidden(2, True)
        samples_table.setColumnHidden(5, True)
        samples_table.itemDoubleClicked.connect(self.sample_doubleclicked)
        samples_table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        samples_table.customContextMenuRequested.connect(self.show_contextmenu)
        header = samples_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)      # Temporarily set it to Stretch to have Qt set the right window width -> set to Interactive in setupUI -> not reset
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        layout = QVBoxLayout()
        layout.addWidget(subses_label)
        layout.addWidget(subses_table)
        layout.addWidget(label)
        layout.addWidget(samples_table)
        tab = QtWidgets.QWidget()
        tab.setObjectName(dataformat)                                       # NB: Serves to identify the dataformat for the tables in a tab
        tab.setLayout(layout)
        self.tabwidget.addTab(tab, f"{dataformat} mappings")
        self.tabwidget.setCurrentWidget(tab)

        self.update_subses_samples(dataformat)

    def set_tab_options(self):
        """Set the options tab"""

        # Create the bidscoin table
        bidscoin_options = self.output_bidsmap.options
        self.options_label['bidscoin'] = bidscoin_label = QLabel('BIDScoin')
        bidscoin_label.setToolTip(TOOLTIP_BIDSCOIN)
        self.options_table['bidscoin'] = bidscoin_table = MyQTableWidget()
        bidscoin_table.setRowCount(len(bidscoin_options.keys()))
        bidscoin_table.setColumnCount(3)                        # columns: [key] [value] [testbutton]
        bidscoin_table.setToolTip(TOOLTIP_BIDSCOIN)
        horizontal_header = bidscoin_table.horizontalHeader()
        horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        horizontal_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setVisible(False)
        test_button = QPushButton('Test')                       # Add a test-button
        test_button.clicked.connect(self.test_bidscoin)
        test_button.setToolTip(f'Click to test the BIDScoin installation')
        bidscoin_table.setCellWidget(0, 2, test_button)
        for n, (key, value) in enumerate(bidscoin_options.items()):
            bidscoin_table.setItem(n, 0, MyWidgetItem(key, iseditable=False))
            bidscoin_table.setItem(n, 1, MyWidgetItem(value))
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
        layout.addWidget(add_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        # Add a 'Default' button below the tables on the left side
        set_button = QPushButton('Set as default')
        set_button.clicked.connect(self.save_options)
        set_button.setToolTip(f'Click to store these options in your default template bidsmap, i.e. set them as default for all new studies')
        layout.addStretch()
        layout.addWidget(set_button, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

        tab = QtWidgets.QWidget()
        tab.setLayout(layout)

        self.tabwidget.addTab(tab, 'Options')

    def set_tab_filebrowser(self):
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
        tree.sortByColumn(0, QtCore.Qt.SortOrder.AscendingOrder)
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

    def update_subses_samples(self, dataformat: str):
        """(Re)populates the sample list with bidsnames according to the bidsmap"""

        self.datachanged = True
        output_bidsmap   = self.output_bidsmap

        # Update the subject/session table
        subitem = MyWidgetItem('subject', iseditable=False)
        subitem.setToolTip(get_entityhelp('sub'))
        sesitem = MyWidgetItem('session', iseditable=False)
        sesitem.setToolTip(get_entityhelp('ses'))
        subses_table = self.subses_table[dataformat]
        subses_table.setItem(0, 0, subitem)
        subses_table.setItem(1, 0, sesitem)
        subses_table.setItem(0, 1, MyWidgetItem(output_bidsmap.dataformat(dataformat).subject))
        subses_table.setItem(1, 1, MyWidgetItem(output_bidsmap.dataformat(dataformat).session))

        # Update the run samples table
        idx           = 0
        num_files     = self.set_ordered_file_index(dataformat)
        samples_table = self.samples_table[dataformat]
        samples_table.blockSignals(True)
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
                exceptions   = self.output_bidsmap.options['notderivative']
                if runitem.datasource.dynamicvalue(runitem.bids['suffix'], True, True) in bids.get_derivatives(dtype, exceptions):
                    session  = self.bidsfolder/'derivatives'/'[manufacturer]'/subid/sesid
                else:
                    session  = self.bidsfolder/subid/sesid
                row_index    = self.ordered_file_index[dataformat][provenance]

                samples_table.setItem(idx, 0, MyWidgetItem(f"{row_index+1:03d}", iseditable=False))
                samples_table.setItem(idx, 1, MyWidgetItem(provenance.name))
                samples_table.setItem(idx, 2, MyWidgetItem(dtype))                          # Hidden column
                samples_table.setItem(idx, 3, MyWidgetItem(Path(dtype)/(bidsname + '.*')))
                samples_table.setItem(idx, 5, MyWidgetItem(provenance))                     # Hidden column

                samples_table.item(idx, 0).setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
                samples_table.item(idx, 1).setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                samples_table.item(idx, 2).setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
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

    def subsescell2bidsmap(self, rowindex: int, colindex: int):
        """Subject or session value has been changed in subject-session table"""

        # Only if cell was actually clicked, update
        dataformat = self.tabwidget.widget(self.tabwidget.currentIndex()).objectName()
        if colindex == 1 and dataformat in self.dataformats:
            key        = self.subses_table[dataformat].item(rowindex, 0).text().strip()
            value      = self.subses_table[dataformat].item(rowindex, 1).text().strip()
            oldvalue   = getattr(self.output_bidsmap.dataformat(dataformat), key)
            if oldvalue is None:
                oldvalue = ''

            # Only if cell content was changed, update
            if key and value != oldvalue:
                LOGGER.verbose(f"User sets {dataformat}['{key}'] from '{oldvalue}' to '{value}'")
                setattr(self.output_bidsmap.dataformat(dataformat), key, value)
                self.update_subses_samples(dataformat)

    def open_editwindow(self, provenance: Path=Path(), datatype: str=''):
        """Make sure that index map has been updated"""

        dataformat = self.tabwidget.widget(self.tabwidget.currentIndex()).objectName()
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
                    self.editwindow        = EditWindow(runitem, self.output_bidsmap, self.template_bidsmap)
                    self.editwindow_opened = str(provenance)
                    self.editwindow.done_edit.connect(self.update_subses_samples)
                    self.editwindow.finished.connect(self.release_editwindow)
                    self.editwindow.show()
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
        self.options_table[name] = plugin_table = MyQTableWidget()
        plugin_table.setRowCount(max(len(plugin.keys()) + 1, 2))            # Add an extra row for new key-value pairs
        plugin_table.setColumnCount(3)                                      # columns: [key] [value] [testbutton]
        horizontal_header = plugin_table.horizontalHeader()
        horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        horizontal_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setVisible(False)
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
            plugin_table.setItem(n, 0, MyWidgetItem(key))
            plugin_table.setItem(n, 1, MyWidgetItem(value))
            plugin_table.setItem(n, 2, MyWidgetItem('', iseditable=False))
        plugin_table.setItem(plugin_table.rowCount() - 1, 2, MyWidgetItem('', iseditable=False))
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
                        except (ValueError, SyntaxError): pass
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
                    self.update_subses_samples(dataformat)
            else:
                self.output_bidsmap.plugins[plugin] = newoptions

            # Add an extra row if the table is full
            if rowindex + 1 == table.rowCount() and table.currentItem() and table.currentItem().text().strip():
                table.blockSignals(True)
                table.insertRow(table.rowCount())
                table.setItem(table.rowCount() - 1, 2, MyWidgetItem('', iseditable=False))
                table.blockSignals(False)

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
        qdialog = QDialog(modal=True)
        qdialog.setLayout(layout)
        qdialog.setWindowTitle('BIDScoin Options')
        qdialog.setWindowIcon(QtGui.QIcon(str(BIDSCOIN_ICON)))
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
        options = self.input_bidsmap.plugins.get(plugin, self.template_bidsmap.plugins.get(plugin, module.OPTIONS if 'OPTIONS' in dir(module) else {}))

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
            for runitem in self.output_bidsmap.dataformat(dataformat).datatype('fmap').runitems:
                if not (runitem.meta.get('B0FieldSource') or runitem.meta.get('B0FieldIdentifier') or runitem.meta.get('IntendedFor')):
                    LOGGER.warning(f"B0FieldIdentifier/IntendedFor fieldmap value is empty for {dataformat} run-item: {runitem}")

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
                bidsmap = bids.yaml.load(stream)
            bidsmap.options = self.output_bidsmap.options
            bidsmap.plugins = self.output_bidsmap.plugins
            with open(yamlfile, 'w') as stream:
                bids.yaml.dump(bidsmap, stream)

    def sample_doubleclicked(self, item):
        """When source file is double-clicked in the samples_table, show the inspect- or edit-window"""

        dataformat = self.tabwidget.widget(self.tabwidget.currentIndex()).objectName()
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
            ext = ''.join(datafile.suffixes).lower()
            if bids.is_dicomfile(datafile) or bids.is_parfile(datafile) or ext in sum((klass.valid_exts for klass in nib.imageclasses.all_image_classes), ('.nii.gz',)):
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
        messagebox.setIconPixmap(QtGui.QPixmap(str(BIDSCOIN_LOGO)).scaled(150, 150, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))
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

    def __init__(self, runitem: RunItem, bidsmap: BidsMap, template_bidsmap: BidsMap):
        super().__init__()

        # Set the data
        self.datasource        = runitem.datasource
        self.dataformat        = runitem.dataformat
        """The data format of the run-item being edited (bidsmap[dataformat][datatype][run-item])"""
        self.unknowndatatypes: List[str] = [datatype for datatype in bidsmap.options['unknowntypes'] if datatype in template_bidsmap.dataformat(self.dataformat).datatypes]
        self.ignoredatatypes: List[str]  = [datatype for datatype in bidsmap.options['ignoretypes']  if datatype in template_bidsmap.dataformat(self.dataformat).datatypes]
        self.bidsdatatypes     = [str(datatype) for datatype in template_bidsmap.dataformat(self.dataformat).datatypes if datatype not in self.unknowndatatypes + self.ignoredatatypes + ['subject', 'session']]
        self.bidsignore        = bidsmap.options['bidsignore']
        self.output_bidsmap    = bidsmap
        """The bidsmap at the start of the edit = output_bidsmap in the MainWindow"""
        self.template_bidsmap  = template_bidsmap
        """The bidsmap from which new datatype run-items are taken"""
        self.source_run        = runitem
        """The original run-item from the source bidsmap"""
        self.target_run        = copy.deepcopy(runitem)
        """The edited run-item that is inserted in the target_bidsmap"""
        self.allowed_suffixes  = self.get_allowed_suffixes()
        """Set the possible suffixes the user can select for a given datatype"""
        self.subid, self.sesid = runitem.datasource.subid_sesid(bidsmap.dataformat(runitem.dataformat).subject, bidsmap.dataformat(runitem.dataformat).session or '')

        # Set up the window
        self.setWindowIcon(QtGui.QIcon(str(BIDSCOIN_ICON)))
        self.setWindowFlags(self.windowFlags() & QtCore.Qt.WindowType.WindowTitleHint & QtCore.Qt.WindowType.WindowMinMaxButtonsHint & QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle('Edit BIDS mapping')
        self.setWhatsThis(f"BIDScoin mapping of {self.dataformat} properties and attributes to BIDS output data")

        # Get data for the tables
        data_properties, data_attributes, data_bids, data_meta = self.run2data()

        # Set up the properties table
        self.properties_label = QLabel('Properties')
        self.properties_label.setToolTip(f"The filesystem properties that match with (identify) the source file. NB: Expert usage (e.g. using regular expressions, see documentation). Copy: Ctrl+C")
        self.properties_table = self.setup_table(data_properties, 'properties')
        self.properties_table.cellChanged.connect(self.propertiescell2run)
        self.properties_table.setToolTip(f"The filesystem property that matches with the source file")
        self.properties_table.cellDoubleClicked.connect(self.inspect_sourcefile)

        # Set up the attributes table
        self.attributes_label = QLabel(f"Attributes")
        self.attributes_label.setToolTip(f"The {self.dataformat} attributes that match with (identify) the source file. NB: Expert usage (e.g. using regular expressions, see documentation). Copy: Ctrl+C")
        self.attributes_table = self.setup_table(data_attributes, 'attributes', minimum=False)
        self.attributes_table.cellChanged.connect(self.attributescell2run)
        self.attributes_table.setToolTip(f"The {self.dataformat} attribute that matches with the source file")

        # Set up the datatype dropdown menu
        self.datatype_label = QLabel('Data type')
        self.datatype_label.setToolTip(f"The BIDS data type and entities for constructing the BIDS output filename. You are encouraged to change their default values to be more meaningful and readable")
        self.datatype_dropdown = QComboBox()
        self.datatype_dropdown.addItems(self.bidsdatatypes + self.unknowndatatypes + self.ignoredatatypes)
        self.datatype_dropdown.setCurrentIndex(self.datatype_dropdown.findText(self.target_run.datatype))
        self.datatype_dropdown.currentIndexChanged.connect(self.datatype_dropdown_change)
        self.datatype_dropdown.setToolTip('The BIDS data type. First make sure this one is correct, then choose the right suffix')
        for n, datatype in enumerate(self.bidsdatatypes + self.unknowndatatypes):
            self.datatype_dropdown.setItemData(n, get_datatypehelp(datatype), QtCore.Qt.ItemDataRole.ToolTipRole)

        # Set up the BIDS table
        self.bids_label = QLabel('Entities')
        self.bids_label.setToolTip(f"The BIDS entities that are used to construct the BIDS output filename. You are encouraged to change their default values to be more meaningful and readable")
        self.bids_table = self.setup_table(data_bids, 'bids')
        self.bids_table.setToolTip(f"The BIDS entity that is used to construct the BIDS output filename. You are encouraged to change its default value to be more meaningful and readable")
        self.bids_table.cellChanged.connect(self.bidscell2run)

        # Set up the meta table
        self.meta_label = QLabel('Meta data')
        self.meta_label.setToolTip(f"Key-value pairs that will be appended to the (e.g. dcm2niix-produced) json sidecar file")
        self.meta_table = self.setup_table(data_meta, 'meta', minimum=False)
        self.meta_table.setShowGrid(True)
        self.meta_table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.meta_table.customContextMenuRequested.connect(self.show_contextmenu)
        self.meta_table.cellChanged.connect(self.metacell2run)
        self.meta_table.setToolTip(f"The key-value pair that will be appended to the (e.g. dcm2niix-produced) json sidecar file")

        # Set-up non-editable BIDS output name section
        self.bidsname_label = QLabel('Data filename')
        self.bidsname_label.setToolTip(f"Preview of the BIDS output name for this data type")
        self.bidsname_textbox = QTextBrowser()
        self.bidsname_textbox.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.bidsname_textbox.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        self.bidsname_textbox.setMinimumHeight(ROW_HEIGHT + 2)
        self.refresh_bidsname()

        # Group the tables in boxes
        sizepolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        sizepolicy.setHorizontalStretch(1)

        groupbox1 = QGroupBox(self.dataformat + ' input')
        groupbox1.setSizePolicy(sizepolicy)
        layout1 = QVBoxLayout()
        layout1.addWidget(self.properties_label)
        layout1.addWidget(self.properties_table)
        layout1.addWidget(self.attributes_label)
        layout1.addWidget(self.attributes_table)
        groupbox1.setLayout(layout1)

        groupbox2 = QGroupBox('BIDS output')
        groupbox2.setSizePolicy(sizepolicy)
        layout2 = QVBoxLayout()
        layout2.addWidget(self.datatype_label)
        layout2.addWidget(self.datatype_dropdown, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        # layout2.addWidget(self.bids_label)
        layout2.addWidget(self.bids_table)
        layout2.addWidget(self.bidsname_label)
        layout2.addWidget(self.bidsname_textbox)
        layout2.addWidget(self.meta_label)
        layout2.addWidget(self.meta_table)
        groupbox2.setLayout(layout2)

        # Add a box1 -> box2 arrow
        arrow = QLabel()
        arrow.setPixmap(QtGui.QPixmap(str(RIGHTARROW)).scaled(30, 30, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation))

        # Add the boxes to the layout
        layout_tables = QHBoxLayout()
        layout_tables.addWidget(groupbox1)
        layout_tables.addWidget(arrow)
        layout_tables.addWidget(groupbox2)

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
            answer = QMessageBox.question(self, 'Edit BIDS mapping', 'Closing window, do you want to save the changes you made?',
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

        super(EditWindow, self).reject()

    @QtCore.pyqtSlot(QtCore.QPoint)
    def show_contextmenu(self, pos):
        """Pops up a context-menu for importing data in the meta_table"""

        menu        = QtWidgets.QMenu(self)
        import_data = menu.addAction('Import meta data')
        clear_table = menu.addAction('Clear table')
        action      = menu.exec(self.meta_table.viewport().mapToGlobal(pos))

        if action == import_data:

            # Read all the meta-data from the table and store it in the target_run
            metafile, _ = QFileDialog.getOpenFileName(self, 'Import meta data from file', str(self.source_run.provenance),
                                                      'JSON/YAML/CSV/TSV Files (*.json *.yaml *.yml *.txt *.csv *.tsv);;All Files (*)')
            if metafile:

                # Get the existing meta-data from the table
                _, _, _, data_meta = self.run2data()

                # Read the new meta-data from disk
                LOGGER.info(f"Importing meta data from: '{metafile}''")
                try:
                    with open(metafile, 'r') as meta_fid:
                        if Path(metafile).suffix == '.json':
                            metadata = json.load(meta_fid)
                        elif Path(metafile).suffix in ('.yaml', '.yml'):
                            metadata = bids.yaml.load(meta_fid)
                        else:
                            dialect = csv.Sniffer().sniff(meta_fid.read())
                            meta_fid.seek(0)
                            metadata = {}
                            for row in csv.reader(meta_fid, dialect=dialect):
                                metadata[row[0]] = row[1] if len(row)>1 else None
                    if not isinstance(metadata, dict):
                        raise ValueError('Unknown dataformat')
                except Exception as readerror:
                    LOGGER.info(f"Failed to import meta-data from: {metafile}\n{readerror}")
                    return

                # Write all the meta-data to the target_run
                self.target_run.meta.update(metadata)

                # Refresh the meta-table using the target_run
                _, _, _, data_meta = self.run2data()
                self.fill_table(self.meta_table, data_meta)

        elif action == clear_table:
            self.target_run.meta = {}
            self.fill_table(self.meta_table, [])

    def get_allowed_suffixes(self) -> Dict[str, set]:
        """Derive the possible suffixes for each datatype from the template. """

        allowed_suffixes = {}
        for datatype in self.bidsdatatypes + self.unknowndatatypes + self.ignoredatatypes:
            allowed_suffixes[datatype] = set()
            for runitem in self.template_bidsmap.dataformat(self.dataformat).datatype(datatype).runitems:
                suffix = self.datasource.dynamicvalue(runitem.bids['suffix'], True)
                if suffix:
                    allowed_suffixes[str(datatype)].add(suffix)

        return allowed_suffixes

    def run2data(self) -> tuple:
        """Derive the tabular data from the target_run, needed to render the edit window
        :return: (data_properties, data_attributes, data_bids, data_meta)
        """

        runitem  = self.target_run
        filepath = self.datasource.properties('filepath')
        filename = self.datasource.properties('filename')
        filesize = self.datasource.properties('filesize')
        nrfiles  = self.datasource.properties('nrfiles')
        data_properties = [[{'value': 'filepath',                         'iseditable': False},
                            {'value': runitem.properties.get('filepath'), 'iseditable': True},
                            {'value': filepath,                           'iseditable': False}],
                           [{'value': 'filename',                         'iseditable': False},
                            {'value': runitem.properties.get('filename'), 'iseditable': True},
                            {'value': filename,                           'iseditable': False}],
                           [{'value': 'filesize',                         'iseditable': False},
                            {'value': runitem.properties.get('filesize'), 'iseditable': True},
                            {'value': filesize,                           'iseditable': False}],
                           [{'value': 'nrfiles',                          'iseditable': False},
                            {'value': runitem.properties.get('nrfiles'),  'iseditable': True},
                            {'value': nrfiles,                            'iseditable': False}]]

        data_attributes = []
        for key, value in runitem.attributes.items():
            data_attributes.append([{'value': key,   'iseditable': False},
                                    {'value': value, 'iseditable': True}])

        data_bids = []
        bidsname  = runitem.bidsname(self.subid, self.sesid, False) + '.json'
        if bids.check_ignore(runitem.datatype, self.bidsignore) or bids.check_ignore(bidsname, self.bidsignore, 'file') or runitem.datatype in self.ignoredatatypes:
            bidskeys = runitem.bids.keys()
        else:
            bidskeys = [bids.entities[entity]['name'] for entity in bids.entitiesorder if entity not in ('subject','session')] + ['suffix']   # Impose the BIDS-specified order + suffix
        for key in bidskeys:
            if key in runitem.bids:
                value = runitem.bids.get(key)
                if (runitem.datatype in self.bidsdatatypes and key=='suffix') or isinstance(value, list):
                    iseditable = False
                else:
                    iseditable = True
                data_bids.append([{'value': key,   'iseditable': False},
                                  {'value': value, 'iseditable': iseditable}])          # NB: This can be a (menu) list

        data_meta = []
        for key, value in runitem.meta.items():
            data_meta.append([{'value': key,   'iseditable': True},
                              {'value': value, 'iseditable': True}])

        return data_properties, data_attributes, data_bids, data_meta

    def setup_table(self, data: list, name: str, minimum: bool=True) -> QTableWidget:
        """Return a table widget filled with the data"""

        nrcolumns = len(data[0]) if data else 2         # Always at least two columns (i.e. key, value)
        table = MyQTableWidget(minimum=minimum)
        table.setColumnCount(nrcolumns)
        table.setObjectName(name)                       # NB: Serves to identify the tables in fill_table()
        table.setHorizontalHeaderLabels(('key', 'value'))
        horizontal_header = table.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(nrcolumns-1, QHeaderView.ResizeMode.Stretch)
        horizontal_header.setVisible(False)

        self.fill_table(table, data)

        return table

    def fill_table(self, table: QTableWidget, data: list):
        """Fill the table with data"""

        table.blockSignals(True)
        table.clearContents()
        addrow = []
        if table.objectName() == 'meta':
            addrow = [[{'value': '', 'iseditable': True}, {'value': '', 'iseditable': True}]]
        table.setRowCount(len(data + addrow))

        for i, row in enumerate(data + addrow):
            key = row[0]['value']
            if table.objectName() == 'bids' and key == 'suffix' and self.target_run.datatype in self.bidsdatatypes:
                table.setItem(i, 0, MyWidgetItem('suffix', iseditable=False))
                suffix   = self.datasource.dynamicvalue(self.target_run.bids.get('suffix',''))
                suffixes = sorted(self.allowed_suffixes.get(self.target_run.datatype, set()), key=str.casefold)
                suffix_dropdown = self.suffix_dropdown = QComboBox()
                suffix_dropdown.addItems(suffixes)
                suffix_dropdown.setCurrentIndex(suffix_dropdown.findText(suffix))
                suffix_dropdown.currentIndexChanged.connect(self.suffix_dropdown_change)
                suffix_dropdown.setToolTip('The suffix that sets the different run types apart. First make sure the "Data type" dropdown-menu is set correctly before choosing the right suffix here')
                for n, suffix in enumerate(suffixes):
                    suffix_dropdown.setItemData(n, get_suffixhelp(suffix, self.target_run.datatype), QtCore.Qt.ItemDataRole.ToolTipRole)
                table.setCellWidget(i, 1, self.spacedwidget(suffix_dropdown))
                continue
            for j, item in enumerate(row):
                value = item.get('value')
                if table.objectName() == 'bids' and isinstance(value, list):
                    value_dropdown = QComboBox()
                    value_dropdown.addItems(value[0:-1])
                    value_dropdown.setCurrentIndex(value[-1])
                    value_dropdown.currentIndexChanged.connect(partial(self.bidscell2run, i, j))
                    if j == 0:
                        value_dropdown.setToolTip(get_entityhelp(key))
                    table.setCellWidget(i, j, self.spacedwidget(value_dropdown))
                else:
                    value_item = MyWidgetItem(value, iseditable=item['iseditable'])
                    if table.objectName() == 'properties':
                        if j == 1:
                            value_item.setToolTip('The (regex) matching pattern that for this property')
                        if j == 2:
                            value_item.setToolTip(get_propertieshelp(key))
                    elif table.objectName() == 'attributes' and j == 0:
                        value_item.setToolTip(get_attributeshelp(key))
                    elif table.objectName() == 'bids' and j == 0:
                        value_item.setToolTip(get_entityhelp(key))
                    elif table.objectName() == 'meta' and j == 0:
                        value_item.setToolTip(get_metahelp(key))
                    table.setItem(i, j, value_item)

        table.blockSignals(False)

    def propertiescell2run(self, rowindex: int, colindex: int):
        """Source attribute value has been changed"""

        # Only if cell was actually clicked, update (i.e. not when BIDS datatype changes)
        if colindex == 1:
            key      = self.properties_table.item(rowindex, 0).text().strip()
            value    = self.properties_table.item(rowindex, 1).text().strip()
            oldvalue = self.target_run.properties.get(key)
            if oldvalue is None:
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

    def attributescell2run(self, rowindex: int, colindex: int):
        """Source attribute value has been changed"""

        # Only if cell was actually clicked, update (i.e. not when BIDS datatype changes)
        if colindex == 1:
            key      = self.attributes_table.item(rowindex, 0).text().strip()
            value    = self.attributes_table.item(rowindex, 1).text()
            oldvalue = self.target_run.attributes.get(key)
            if oldvalue is None:
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

    def bidscell2run(self, rowindex: int, colindex: int):
        """BIDS attribute value has been changed"""

        # Only if cell was actually clicked, update (i.e. not when BIDS datatype changes) and store the data in the target_run
        if colindex == 1:
            key = self.bids_table.item(rowindex, 0).text()
            if hasattr(self.bids_table.cellWidget(rowindex, 1), 'spacedwidget'):
                dropdown = self.bids_table.cellWidget(rowindex, 1).spacedwidget
                value    = [dropdown.itemText(n) for n in range(len(dropdown))] + [dropdown.currentIndex()]
                oldvalue = self.target_run.bids.get(key)
            else:
                value    = self.bids_table.item(rowindex, 1).text().strip()
                oldvalue = self.target_run.bids.get(key)
            if oldvalue is None:
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
                self.refresh_bidsname()

    def metacell2run(self, rowindex: int, colindex: int):
        """Source meta value has been changed"""

        key      = self.meta_table.item(rowindex, 0).text().strip()
        value    = self.meta_table.item(rowindex, 1).text().strip()
        oldvalue = self.target_run.meta.get(key)
        if oldvalue is None:
            oldvalue = ''
        if value != oldvalue:
            # Replace the (dynamic) value
            if '<<' not in value or '>>' not in value:
                value = self.datasource.dynamicvalue(value, cleanup=False)
                self.meta_table.blockSignals(True)
                self.meta_table.item(rowindex, 1).setText(value)
                self.meta_table.blockSignals(False)
            LOGGER.verbose(f"User sets meta['{key}'] from '{oldvalue}' to '{value}' for {self.target_run}")

        # Read all the meta-data from the table and store it in the target_run
        self.target_run.meta = {}
        for n in range(self.meta_table.rowCount()):
            key_   = self.meta_table.item(n, 0).text().strip()
            value_ = self.meta_table.item(n, 1).text().strip()
            if key_:
                try: value_ = ast.literal_eval(value_)      # E.g. convert stringified list or int back to list or int
                except (ValueError, SyntaxError): pass
                self.target_run.meta[key_] = value_
            elif value_:
                QMessageBox.warning(self, 'Input error', f"Please enter a key-name (left cell) for the '{value_}' value in row {n+1}")

        # Refresh the table, i.e. delete empty rows or add a new row if a key is defined on the last row
        _, _, _, data_meta = self.run2data()
        self.fill_table(self.meta_table, data_meta)

    def change_run(self, suffix_idx):
        """
        Resets the edit dialog window with a new target_run from the template bidsmap after a suffix- or datatype-change

        :param suffix_idx: The suffix or index number that will be used to extract the run from the template bidsmap
        """

        # Add a check to see if we can still read the source data
        provenance = self.target_run.provenance
        if not Path(provenance).is_file():
            LOGGER.warning(f"Can no longer find the source file: {provenance}")
            QMessageBox.warning(self, 'Edit BIDS mapping', f"Cannot reliably change the datatype and/or suffix because the source file '{provenance}' can no longer be found.\n\nPlease restore the source data or use the `bidsmapper -s` option to solve this issue. Resetting the run-item now...")
            self.reset()
            return

        # Get the new target_run from the template
        template_run = self.template_bidsmap.get_run(self.target_run.datatype, suffix_idx, self.datasource)
        if not template_run:
            QMessageBox.warning(self, 'Edit BIDS mapping', f"Cannot find the {self.target_run.datatype}[{suffix_idx}] datatype in your template. Resetting the run-item now...")
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

        # Reset the edit window with the new target_run
        self.reset(refresh=True)

    def datatype_dropdown_change(self):
        """Update the BIDS values and BIDS output name section when the dropdown selection has been taking place"""

        self.target_run.datatype = self.datatype_dropdown.currentText()

        LOGGER.verbose(f"User changes the BIDS data type from '{self.source_run.datatype}' to '{self.target_run.datatype}' for {self.target_run}")

        self.change_run(0)

    def suffix_dropdown_change(self):
        """Update the BIDS values and BIDS output name section when the dropdown selection has been taking place"""

        target_suffix = self.suffix_dropdown.currentText()

        LOGGER.verbose(f"User changes the BIDS suffix from '{self.target_run.bids.get('suffix')}' to '{target_suffix}' for {self.target_run}")

        self.change_run(target_suffix)

    def refresh_bidsname(self):
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

            # Reset the datatype dropdown menu
            self.datatype_dropdown.blockSignals(True)
            self.datatype_dropdown.setCurrentIndex(self.datatype_dropdown.findText(self.target_run.datatype))
            self.datatype_dropdown.blockSignals(False)

        # Refresh the source attributes and BIDS values with data from the target_run
        data_properties, data_attributes, data_bids, data_meta = self.run2data()

        # Refresh the existing tables
        self.fill_table(self.properties_table, data_properties)
        self.fill_table(self.attributes_table, data_attributes)
        self.fill_table(self.bids_table, data_bids)
        self.fill_table(self.meta_table, data_meta)

        # Refresh the BIDS output name
        self.refresh_bidsname()

    def accept_run(self):
        """Save the changes to the target_bidsmap and send it back to the main window: Finished!"""

        # Check if the bidsname is valid
        bidsname  = Path(self.bidsname_textbox.toPlainText())
        validrun  = False not in self.target_run.check(checks=(False, False, False))[1:3]
        bidsvalid = validrun
        datatype  = self.target_run.datatype
        if not (bids.check_ignore(datatype,self.bidsignore) or bids.check_ignore(bidsname.name,self.bidsignore,'file') or datatype in self.ignoredatatypes):
            for ext in extensions:      # NB: `ext` used to be '.json', which is more generic (but see https://github.com/bids-standard/bids-validator/issues/2113)
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
            message = f'The "B0FieldIdentifier/IntendedFor" meta-data is left empty for {bidsname} (not recommended)'
        if message:
            answer = QMessageBox.question(self, 'Edit BIDS mapping', f'WARNING:\n{message}\n\nDo you want to go back and edit the run?',
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
            QMessageBox.information(self, 'Edit BIDS mapping', f"Successfully exported:\n\n{self.target_run} -> {yamlfile}")

    def inspect_sourcefile(self, rowindex: int=None, colindex: int=None):
        """When double-clicked, show popup window"""

        if colindex in (0,2):
            if rowindex == 0:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(Path(self.target_run.provenance).parent)))
            if rowindex == 1:
                self.popup = InspectWindow(Path(self.target_run.provenance))
                self.popup.show()
                self.popup.scrollbar.setValue(0)  # This can only be done after self.popup.show()

    @staticmethod
    def spacedwidget(alignedwidget, align='left'):
        """Place the widget in a QHBoxLayout and add a stretcher next to it. Return the widget as widget.spacedwidget"""

        widget = QtWidgets.QWidget()
        layout = QHBoxLayout()
        if align != 'left':
            layout.addStretch()
            layout.addWidget(alignedwidget)
        else:
            layout.addWidget(alignedwidget)
            layout.addStretch()
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)
        widget.spacedwidget = alignedwidget
        return widget

    def get_help(self):
        """Open web page for help"""
        help_url = HELP_URLS.get(self.target_run.datatype, HELP_URL_DEFAULT)
        webbrowser.open(help_url)


class CompareWindow(QDialog):

    def __init__(self, runitems: List[RunItem], subid: List[str], sesid: List[str]):
        super().__init__()

        # Set up the window
        self.setWindowIcon(QtGui.QIcon(str(BIDSCOIN_ICON)))
        self.setWindowFlags(self.windowFlags() & QtCore.Qt.WindowType.WindowTitleHint & QtCore.Qt.WindowType.WindowMinMaxButtonsHint & QtCore.Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle('Compare BIDS mappings')
        self.setWhatsThis('BIDScoin mapping of properties and attributes to BIDS output data')

        layout_main = QHBoxLayout(self)

        for index, runitem in enumerate(runitems):

            # Get data for the tables
            data_properties, data_attributes, data_bids, data_meta = self.run2data(runitem)

            # Set up the properties table
            properties_label = QLabel('Properties')
            properties_label.setToolTip('The filesystem properties that match with (identify) the source file')
            properties_table = self.fill_table(data_properties, 'properties')
            properties_table.setToolTip('The filesystem property that matches with the source file')
            properties_table.cellDoubleClicked.connect(partial(self.inspect_sourcefile, runitem.provenance))

            # Set up the attributes table
            attributes_label = QLabel('Attributes')
            attributes_label.setToolTip('The attributes that match with (identify) the source file')
            attributes_table = self.fill_table(data_attributes, 'attributes', minimum=False)
            attributes_table.setToolTip('The attribute that matches with the source file')

            # Set up the BIDS table
            bids_label = QLabel('BIDS entities')
            bids_label.setToolTip('The BIDS entities that are used to construct the BIDS output filename')
            bids_table = self.fill_table(data_bids, 'bids')
            bids_table.setToolTip('The BIDS entity that is used to construct the BIDS output filename')

            # Set up the meta table
            meta_label = QLabel('Meta data')
            meta_label.setToolTip('Key-value pairs that will be appended to the (e.g. dcm2niix-produced) json sidecar file')
            meta_table = self.fill_table(data_meta, 'meta', minimum=False)
            meta_table.setToolTip('The key-value pair that will be appended to the (e.g. dcm2niix-produced) json sidecar file')

            bidsname = runitem.bidsname(subid[index], sesid[index], False) + '.*'
            groupbox = QGroupBox(f"{runitem.datatype}/{bidsname}")
            layout   = QVBoxLayout()
            layout.addWidget(properties_label)
            layout.addWidget(properties_table)
            layout.addWidget(attributes_label)
            layout.addWidget(attributes_table)
            layout.addWidget(bids_label)
            layout.addWidget(bids_table)
            layout.addWidget(meta_label)
            layout.addWidget(meta_table)
            groupbox.setLayout(layout)

            # Set up the main layout
            layout_main.addWidget(groupbox)

        self.show()

    @staticmethod
    def run2data(runitem: RunItem) -> tuple:
        """Derive the tabular data from the target_run, needed to render the compare window
        :return: (data_properties, data_attributes, data_bids, data_meta)
        """

        data_properties = [['filepath', runitem.properties.get('filepath'), runitem.datasource.properties('filepath')],
                           ['filename', runitem.properties.get('filename'), runitem.datasource.properties('filename')],
                           ['filesize', runitem.properties.get('filesize'), runitem.datasource.properties('filesize')],
                           ['nrfiles',  runitem.properties.get('nrfiles'),  runitem.datasource.properties('nrfiles')]]

        data_attributes = []
        for key in sorted(runitem.attributes.keys()):
            value = runitem.attributes.get(key)
            data_attributes.append([key, value])

        data_bids = []
        bidskeys = [bids.entities[entity]['name'] for entity in bids.entitiesorder if entity not in ('subject','session')] + ['suffix']   # Impose the BIDS-specified order + suffix
        for key in bidskeys:
            if key in runitem.bids:
                value = runitem.bids.get(key)
                if isinstance(value, list):
                    value = value[value[-1]]
                data_bids.append([key, value])

        data_meta = []
        for key in sorted(runitem.meta.keys()):
            value = runitem.meta.get(key)
            data_meta.append([key, value])

        return data_properties, data_attributes, data_bids, data_meta

    @staticmethod
    def fill_table(data: list, name: str, minimum: bool=True) -> QTableWidget:
        """Return a table widget filled with the data"""

        nrcolumns = len(data[0]) if data else 2         # Always at least two columns (i.e. key, value)
        table = MyQTableWidget(minimum=minimum)
        table.setRowCount(len(data))
        table.setColumnCount(nrcolumns)
        table.setObjectName(name)                       # NB: Serves to identify the tables in fill_table()
        table.setHorizontalHeaderLabels(('key', 'value'))
        horizontal_header = table.horizontalHeader()
        horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        horizontal_header.setSectionResizeMode(nrcolumns-1, QHeaderView.ResizeMode.Stretch)
        horizontal_header.setVisible(False)
        for i, row in enumerate(data):
            for j, value in enumerate(row):
                item = QTableWidgetItem()
                item.setText(str(value or ''))
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
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

        ext = ''.join(filename.suffixes).lower()
        if bids.is_dicomfile(filename):
            if filename.name == 'DICOMDIR':
                LOGGER.bcdebug(f"Getting DICOM fields from {filename} will raise dcmread error below if pydicom => v3.0")
            text = str(dcmread(filename, force=True))
        elif bids.is_parfile(filename) or ext in ('.spar', '.txt', '.text'):
            text = filename.read_text()
        elif ext == '.7':
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
        elif filename.is_file() and ext in sum((klass.valid_exts for klass in nib.imageclasses.all_image_classes), ('.nii.gz',)):
            text = str(nib.load(filename).header)
        else:
            text = f"Could not inspect: {filename}"
            LOGGER.verbose(text)

        self.setWindowIcon(QtGui.QIcon(str(BIDSCOIN_ICON)))
        self.setWindowTitle(str(filename))
        self.setWindowFlags(self.windowFlags() & QtCore.Qt.WindowType.WindowContextHelpButtonHint & QtCore.Qt.WindowType.WindowMinMaxButtonsHint & QtCore.Qt.WindowType.WindowCloseButtonHint)

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


class MyQTableWidget(QTableWidget):

    def __init__(self, minimum: bool=True):
        super().__init__()

        self.setAlternatingRowColors(False)
        self.setShowGrid(False)

        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.setMinimumHeight(2 * (ROW_HEIGHT + 8))
        self.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)

        self.minimizeheight(minimum)

    def minimizeheight(self, minimum: bool=True):
        """Set the vertical QSizePolicy to Minimum"""

        if minimum:
            self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Minimum)
        else:
            self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)


class MyWidgetItem(QTableWidgetItem):

    def __init__(self, value: Union[str,Path]='', iseditable: bool=True):
        """A QTableWidgetItem that is editable or not and that converts integer values to string"""

        super().__init__()
        self.setText(value)

        self.iseditable = iseditable
        if iseditable:
            self.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEditable)
        else:
            self.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.setForeground(QtGui.QColor('gray'))

    def setText(self, p_str):
        """Catch int and None"""

        if p_str is None:
            p_str = ''

        super(MyWidgetItem, self).setText(str(p_str))


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
    if datatype in bids.bidsdatatypesdef:
        return f"{bids.bidsdatatypesdef[datatype]['display_name']}\n{bids.bidsdatatypesdef[datatype]['description']}"

    return f"{datatype}\nAn unknown/private datatype"


def get_suffixhelp(suffix: str, datatype: Union[str, DataType]) -> str:
    """
    Reads the description of the suffix in the schema/objects/suffixes.yaml file

    :param suffix:      The suffix for which the help text is obtained
    :param datatype:    The datatype of the suffix
    :return:            The obtained help text
    """

    if not suffix:
        return "Please provide a suffix"

    isderivative = ''
    if suffix in bids.get_derivatives(datatype):
        isderivative = '\nNB: This is a BIDS derivatives datatype'

    # Return the description for the suffix or a default text
    if suffix in bids.suffixes:
        return f"{bids.suffixes[suffix]['display_name']}\n{bids.suffixes[suffix]['description']}{isderivative}"

    return f"{suffix}\nAn unknown/private suffix"


def get_entityhelp(entitykey: str) -> str:
    """
    Reads the description of a matching entity=entitykey in the schema/entities.yaml file

    :param entitykey:   The bids key for which the help text is obtained
    :return:            The obtained help text
    """

    if not entitykey:
        return "Please provide a key-name"

    # Return the description from the entities or a default text
    for entity in bids.entities:
        if bids.entities[entity]['name'] == entitykey:
            return f"{bids.entities[entity]['display_name']}\n{bids.entities[entity]['description']}"

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
    for field in bids.metafields:
        if metakey == bids.metafields[field].get('name'):
            description = bids.metafields[field]['description']
            if metakey == 'IntendedFor':                            # IntendedFor is a special search-pattern field in BIDScoin
                description += ('\nNB: These associated files can be dynamically searched for'
                                '\nduring bidscoiner runtime with glob-style matching patterns,'
                                '\n"such as <<Reward*_bold><Stop*_epi>>" or <<dwi/*acq-highres*>>'
                                '\n(see documentation)')
            if metakey in ('B0FieldIdentifier', 'B0FieldSource'):   # <<session>> is a special dynamic value in BIDScoin
                description += ('\nNB: The `<<session>>` (sub)string will be replaced by the'
                                '\nsession label during bidscoiner runtime. In this way you can'
                                '\ncreate session-specific B0FieldIdentifier/Source tags (recommended)')

            return f"{bids.metafields[field]['display_name']}\n{description}"

    return f"{metakey}\nAn unknown/private meta key"


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
    if input_bidsmap.options:
        template_bidsmap.options = input_bidsmap.options    # Always use the options of the input bidsmap
        template_bidsmap.plugins = input_bidsmap.plugins    # Always use the plugins of the input bidsmap

    # Start the Qt-application
    app = QApplication(sys.argv)
    app.setApplicationName(f"{bidsmapfile} - BIDS editor {__version__}")
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
        trackusage('bidseditor_exception')
        raise error


if __name__ == '__main__':
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
