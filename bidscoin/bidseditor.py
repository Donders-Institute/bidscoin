#!/usr/bin/env python
"""
This tool launches a graphical user interface for editing the bidsmap.yaml file
that is e.g. produced by the bidsmapper or by this bidseditor itself. The user can
fill in or change the BIDS labels for entries that are unidentified or sub-optimal,
such that meaningful BIDS output names will be generated from these labels. The saved
bidsmap.yaml output file can be used for converting the source data to BIDS using
the bidscoiner.
"""

import os
import sys
import argparse
import textwrap
import logging
import copy
import webbrowser
import pydicom
from functools import partial

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileSystemModel, QFileDialog, QDialogButtonBox,
                             QTreeView, QHBoxLayout, QVBoxLayout, QLabel, QDialog, QMessageBox,
                             QTableWidget, QTableWidgetItem, QGroupBox, QTextBrowser,
                             QAbstractItemView, QPushButton, QComboBox, QDesktopWidget)

try:
    from bidscoin import bids
except ImportError:
    import bids             # This should work if bidscoin was not pip-installed

SOURCE = 'DICOM'            # TODO: allow for non-DICOM (e.g. PAR/REC) edits

LOGGER = logging.getLogger('bidscoin')

MAIN_WINDOW_WIDTH   = 1250
MAIN_WINDOW_HEIGHT  = 700

EDIT_WINDOW_WIDTH   = 1100
EDIT_WINDOW_HEIGHT  = 600

INSPECT_WINDOW_WIDTH = 850
INSPECT_WINDOW_HEIGHT = 750

OPTIONS_TAB_INDEX = 1
BIDSMAP_TAB_INDEX = 2

ROW_HEIGHT = 22

ICON_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "icons", "bidscoin.ico")

MAIN_HELP_URL = "https://github.com/Donders-Institute/bidscoin/blob/master/README.md"

HELP_URL_DEFAULT = "https://bids-specification.readthedocs.io/en/latest/"

HELP_URLS = {
    "anat": "https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#anatomy-imaging-data",
    "beh" : "https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/07-behavioral-experiments.html",
    "dwi" : "https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#diffusion-imaging-data",
    "fmap": "https://bids-specification.readthedocs.io/en/latest/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data",
    "func": "https://bids-specification.readthedocs.io/en/latest/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#task-including-resting-state-imaging-data",
    "pet" : "https://docs.google.com/document/d/1mqMLnxVdLwZjDd4ZiWFqjEAmOmfcModA_R535v3eQs0/edit",
    bids.unknownmodality: HELP_URL_DEFAULT,
    bids.ignoremodality : HELP_URL_DEFAULT
}

OPTIONS_TOOLTIP_BIDSCOIN = """bidscoin
version:    should correspond with the version in ../bidscoin/version.txt
bidsignore: Semicolon-separated list of entries that are added to the .bidsignore file
            (for more info, see BIDS specifications), e.g. extra_data/;pet/;myfile.txt;yourfile.csv"""

OPTIONS_TOOLTIP_DCM2NIIX = """dcm2niix
path: Command to set the path to dcm2niix, e.g.:
      module add dcm2niix/1.0.20180622; (note the semi-colon at the end)
      PATH=/opt/dcm2niix/bin:$PATH; (note the semi-colon at the end)
      /opt/dcm2niix/bin/  (note the slash at the end)
      '\"C:\\Program Files\\dcm2niix\"' (note the quotes to deal with the whitespace)
args: Argument string that is passed to dcm2niix. Click [Test] and see the terminal output for usage
      Tip: SPM users may want to use '-z n', which produces unzipped nifti's"""


def set_cell(value, is_editable=False):
    item = QTableWidgetItem()
    item.setText(value)
    if is_editable:
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable)
    else:
        item.setFlags(QtCore.Qt.ItemIsEnabled)
        item.setForeground(QtGui.QColor(128, 128, 128))
    return item


def table_height(num_rows: int):
    """Calculates the table height for windows and linux"""

    if sys.platform == 'linux':
        num_rows *= 1.1
    else:
        num_rows *= 1.45

    height = num_rows * ROW_HEIGHT

    return height


class InspectWindow(QDialog):

    def __init__(self, filename, dicomdict):
        super().__init__()

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)
        self.setWindowTitle(f"Inspect {SOURCE} file")

        self.resize(INSPECT_WINDOW_WIDTH, INSPECT_WINDOW_HEIGHT)

        verticalLayout = QVBoxLayout(self)

        label = QLabel('Filename: ' + os.path.basename(filename))
        label.setWordWrap(True)
        verticalLayout.addWidget(label)

        label_path = QLabel('Path: ' + os.path.dirname(filename))
        label_path.setWordWrap(True)
        verticalLayout.addWidget(label_path)

        textBrowser = QTextBrowser(self)
        textBrowser.insertPlainText(str(dicomdict))
        verticalLayout.addWidget(textBrowser)

        buttonBox = QDialogButtonBox(self)
        buttonBox.setStandardButtons(QDialogButtonBox.Ok)
        buttonBox.button(QDialogButtonBox.Ok).setToolTip('Close this window')
        verticalLayout.addWidget(buttonBox)

        buttonBox.accepted.connect(self.close)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        actionQuit = QtWidgets.QAction("Quit", self)
        actionQuit.triggered.connect(self.closeEvent)

    def closeEvent(self, event):
        """Handle exit. """
        QApplication.quit()     # TODO: Do not use class method but self.something


class Ui_MainWindow(object):

    def setupUi(self, MainWindow, bidsfolder, sourcefolder, bidsmap_filename, input_bidsmap, output_bidsmap, template_bidsmap,
                selected_tab_index=BIDSMAP_TAB_INDEX, subprefix='sub-', sesprefix='ses-', reload: bool=False):

        self.MainWindow       = MainWindow
        self.bidsfolder       = bidsfolder
        self.sourcefolder     = sourcefolder
        self.bidsmap_filename = bidsmap_filename
        self.input_bidsmap    = input_bidsmap
        self.output_bidsmap   = output_bidsmap
        self.template_bidsmap = template_bidsmap
        self.subprefix        = subprefix
        self.sesprefix        = sesprefix

        self.has_edit_dialog_open = False

        # Make sure we have the correct index mapping for the first edit
        self.set_initial_file_index()

        centralwidget = QtWidgets.QWidget(self.MainWindow)
        centralwidget.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        centralwidget.setObjectName("centralwidget")

        top_layout = QtWidgets.QVBoxLayout(centralwidget)

        self.tabwidget = QtWidgets.QTabWidget(centralwidget)
        self.tabwidget.setTabPosition(QtWidgets.QTabWidget.North)
        self.tabwidget.setTabShape(QtWidgets.QTabWidget.Rounded)
        self.tabwidget.setObjectName("tabwidget")
        self.set_tab_file_browser(sourcefolder)
        self.set_tab_options()
        self.set_tab_bidsmap()
        self.tabwidget.setTabText(0, "File browser")
        self.tabwidget.setTabText(1, "Options")
        self.tabwidget.setTabText(2, "BIDS map")
        self.tabwidget.setCurrentIndex(selected_tab_index)

        top_layout.addWidget(self.tabwidget)

        buttonBox = QDialogButtonBox(self.MainWindow)
        buttonBox.setStandardButtons(QDialogButtonBox.Save | QDialogButtonBox.Reset | QDialogButtonBox.Help)
        buttonBox.button(QDialogButtonBox.Help).setToolTip('Go to the online BIDScoin documentation')
        buttonBox.button(QDialogButtonBox.Save).setToolTip('Save the Options and BIDS-map to disk')
        buttonBox.button(QDialogButtonBox.Reset).setToolTip('Reload the options and BIDS-map from disk')

        top_layout.addWidget(buttonBox)

        buttonBox.helpRequested.connect(self.get_help)
        buttonBox.button(QDialogButtonBox.Reset).clicked.connect(self.reload)
        buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.save_bidsmap_to_file)

        self.MainWindow.setCentralWidget(centralwidget)

        if not reload:
            self.MainWindow.setObjectName("MainWindow")

            icon = QtGui.QIcon()
            icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
            self.MainWindow.setWindowIcon(icon)

            self.set_menu_and_status_bar()

            self.MainWindow.resize(MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT)
            self.center()

    def set_menu_and_status_bar(self):
        """Set the menu. """
        menubar  = QtWidgets.QMenuBar(self.MainWindow)
        menuFile = QtWidgets.QMenu(menubar)
        menuHelp = QtWidgets.QMenu(menubar)

        self.MainWindow.setMenuBar(menubar)
        statusbar = QtWidgets.QStatusBar(self.MainWindow)

        # Set the statusbar
        statusbar.setToolTip("")
        statusbar.setObjectName("statusbar")
        self.MainWindow.setStatusBar(statusbar)

        # Define the menu actions
        actionExit = QtWidgets.QAction(self.MainWindow)
        actionExit.triggered.connect(self.exit_application)

        actionReload = QtWidgets.QAction(self.MainWindow)
        actionReload.triggered.connect(self.reload)

        actionSave = QtWidgets.QAction(self.MainWindow)
        actionSave.triggered.connect(self.save_bidsmap_to_file)

        actionAbout = QtWidgets.QAction(self.MainWindow)
        actionAbout.triggered.connect(self.show_about)

        actionHelp = QtWidgets.QAction(self.MainWindow)
        actionHelp.triggered.connect(self.get_help)

        actionBidsHelp = QtWidgets.QAction(self.MainWindow)
        actionBidsHelp.triggered.connect(self.get_bids_help)

        menuFile.addAction(actionReload)
        menuFile.addAction(actionSave)
        menuFile.addAction(actionExit)

        menuHelp.addAction(actionHelp)
        menuHelp.addAction(actionBidsHelp)
        menuHelp.addAction(actionAbout)

        menubar.addAction(menuFile.menuAction())
        menubar.addAction(menuHelp.menuAction())

        menuFile.setTitle("File")
        menuHelp.setTitle("Help")
        statusbar.setStatusTip("Statusbar")

        actionReload.setText("Reset")
        actionReload.setStatusTip("Reload the BIDS-map from disk")
        actionReload.setShortcut("Ctrl+R")

        actionSave.setText("Save")
        actionSave.setStatusTip("Save the BIDS-map to disk")
        actionSave.setShortcut("Ctrl+S")

        actionExit.setText("Exit")
        actionExit.setStatusTip("Exit the application")
        actionExit.setShortcut("Ctrl+X")

        actionAbout.setText("About BIDScoin")
        actionAbout.setStatusTip("Show information about the application")

        actionHelp.setText("Documentation")
        actionHelp.setStatusTip("Go to the online BIDScoin documentation")
        actionHelp.setShortcut("F1")

        actionBidsHelp.setText("BIDS specification")
        actionBidsHelp.setStatusTip("Go to the online BIDS specification documentation")
        actionBidsHelp.setShortcut("F2")

    def center(self):
        """Center the main window. """
        qr = self.MainWindow.frameGeometry()

        # Center point of screen
        cp = QDesktopWidget().availableGeometry().center()

        # Move rectangle's center point to screen's center point
        qr.moveCenter(cp)

        # Top left of rectangle becomes top left of window centering it
        self.MainWindow.move(qr.topLeft())

    def set_initial_file_index(self):
        """Obtain the mapping between the provenance and the initial file-index. """
        initial_file_index = {}
        file_index = 0
        for modality in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):
            runs = self.input_bidsmap[SOURCE][modality]
            if not runs:
                continue
            for run in runs:
                if not run['provenance']:
                    LOGGER.error(f'The bidsmap run {modality} run does not contain provenance data')
                initial_file_index[run['provenance']] = file_index
                file_index += 1

        if not hasattr(self, 'initial_file_index'):
            self.initial_file_index = initial_file_index

        return file_index

    def inspect_dicomfile(self, item):
        """When double clicked, show popup window. """
        if item.column() == 1:
            row = item.row()
            provenance = self.table.item(row, 5)
            filename = provenance.text()
            if bids.is_dicomfile(filename):
                dicomdict = pydicom.dcmread(filename, force=True)
                self.popup = InspectWindow(filename, dicomdict)
                self.popup.show()

    def set_tab_file_browser(self, sourcefolder):
        """Set the raw data folder inspector tab. """
        tab1 = QtWidgets.QWidget()
        tab1.setObjectName("filebrowser")
        tab1.layout = QVBoxLayout()
        label = QLabel(sourcefolder)
        label.setWordWrap(True)
        self.model = QFileSystemModel()
        self.model.setRootPath('')
        self.model.setFilter(QtCore.QDir.NoDotAndDotDot | QtCore.QDir.AllDirs | QtCore.QDir.Files)
        tree = QTreeView()
        tree.setModel(self.model)
        tree.setAnimated(False)
        tree.setIndentation(20)
        tree.setSortingEnabled(True)
        tree.setRootIndex(self.model.index(sourcefolder))
        tree.doubleClicked.connect(self.on_double_clicked)
        tree.header().resizeSection(0, 800)

        tab1.layout.addWidget(label)
        tab1.layout.addWidget(tree)
        tab1.setLayout(tab1.layout)
        self.tabwidget.addTab(tab1, "")

    def subses_cell_was_changed(self, row, column):
        """Subject or session value has been changed in subject-session table. """
        if column == 1:
            key = self.subses_table.item(row, 0).text()
            value = self.subses_table.item(row, 1).text()
            oldvalue = self.output_bidsmap[SOURCE][key]

            # Only if cell was actually clicked, update
            if key and value!=oldvalue:
                LOGGER.info(f"User has set {SOURCE}['{key}'] from '{oldvalue}' to '{value}'")
                self.output_bidsmap[SOURCE][key] = value
                self.update_subses_and_samples(self.output_bidsmap)

    def tool_cell_was_changed(self, tool, idx, row, column):
        """Option value has been changed tool options table. """
        if column == 2:
            table = self.tables_options[idx]  # Select the selected table
            key = table.item(row, 1).text()
            value = table.item(row, 2).text()
            oldvalue = self.output_bidsmap["Options"][tool][key]

            # Only if cell was actually clicked, update
            if key and value!=oldvalue:
                LOGGER.info(f"User has set {SOURCE}['Options']['{key}'] from '{oldvalue}' to '{value}'")
                self.output_bidsmap["Options"][tool][key] = value

    def handle_click_test_plugin(self, plugin: str):
        """Test the bidsmap plugin and show the result in a pop-up window

        :param plugin:    Name of the plugin that is being tested in bidsmap['PlugIns']
         """
        if bids.test_plugins(plugin):
            result = 'Passed'
        else:
            result = 'Failed'
        QMessageBox.information(self.MainWindow, 'Test', f"Test {plugin}: {result}\n"
                                                         f"See terminal output for more info")

    def handle_click_test_tool(self, tool: str):
        """Test the bidsmap tool and show the result in a pop-up window

        :param tool:    Name of the tool that is being tested in bidsmap['Options']
         """
        if bids.test_tooloptions(tool, self.output_bidsmap['Options'][tool]):
            result = 'Passed'
        else:
            result = 'Failed'
        QMessageBox.information(self.MainWindow, 'Test', f"Test {tool}: {result}\n"
                                                         f"See terminal output for more info")

    def handle_click_plugin_add(self):
        """
        Add a plugin by letting the user select a plugin-file
        :return:
        """
        plugin = QFileDialog.getOpenFileNames(self.MainWindow, 'Select the plugin-file(s)', directory=os.path.join(self.bidsfolder, 'code', 'bidscoin'), filter='Python files (*.py *.pyc *.pyo);; All files (*)')
        LOGGER.info(f'Added plugins: {plugin[0]}')
        self.output_bidsmap['PlugIns'] += plugin[0]
        self.update_plugintable()

    def plugin_cell_was_changed(self, row, column):
        """
        Add / edit a plugin or delete if cell is empty
        :param row:
        :return:
        """
        if column==1:
            plugin = self.plugintable.item(row, column).text()
            if plugin and row == len(self.output_bidsmap['PlugIns']):
                LOGGER.info(f"Added plugin: '{plugin}'")
                self.output_bidsmap['PlugIns'].append(plugin)
            elif plugin:
                LOGGER.info(f"Edited plugin: '{self.output_bidsmap['PlugIns'][row]}' -> '{plugin}'")
                self.output_bidsmap['PlugIns'][row] = plugin
            elif row < len(self.output_bidsmap['PlugIns']):
                LOGGER.info(f"Deleted plugin: '{self.output_bidsmap['PlugIns'][row]}'")
                del self.output_bidsmap['PlugIns'][row]
            else:
                LOGGER.error(f"Unexpected cell change for {plugin}")

            self.update_plugintable()

    def update_plugintable(self):
        """Plots an extendable table of plugins from self.output_bidsmap['PlugIns']"""
        plugins  = self.output_bidsmap['PlugIns']
        num_rows = len(plugins) + 1
        num_cols = 3  # Always three columns (i.e. path, plugin, test-button)

        plugintable = self.plugintable
        plugintable.disconnect()
        plugintable.setRowCount(num_rows)
        plugintable.setColumnCount(num_cols)

        for i, plugin in enumerate(plugins + ['']):
            plugintable.setRowHeight(i, ROW_HEIGHT)
            for j in range(3):
                if j==0:
                    item = set_cell('path', is_editable=False)
                    plugintable.setItem(i, j, item)
                elif j==1:
                    item = set_cell(plugin, is_editable=True)
                    item.setToolTip('Double-click to edit the name of the plugin in the heuristics folder or the full pathname of the plugin in a custom location')
                    plugintable.setItem(i, j, item)
                elif j==2:                  # Add the test-button cell
                    test_button = QPushButton('Test')
                    test_button.clicked.connect(partial(self.handle_click_test_plugin, plugin))
                    test_button.setToolTip(f'Click to test {plugin}')
                    plugintable.setCellWidget(i, j, test_button)

        # Append the Add-button cell
        add_button = QPushButton('Select')
        add_button.setToolTip('Click to interactively add a plugin')
        plugintable.setCellWidget(num_rows - 1, 2, add_button)
        add_button.clicked.connect(self.handle_click_plugin_add)

        horizontal_header = plugintable.horizontalHeader()
        horizontal_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        horizontal_header.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        horizontal_header.setVisible(False)

        plugintable.verticalHeader().setVisible(False)

        plugintable.setMaximumHeight(table_height(num_rows))

        plugintable.cellChanged.connect(self.plugin_cell_was_changed)

    def set_tab_options(self):
        """Set the options tab.  """
        tab2 = QtWidgets.QWidget()
        tab2.layout = QVBoxLayout()
        tab2.setObjectName("Options")

        bidsmap_options = self.output_bidsmap['Options']

        tool_list = []
        tool_options = {}
        for tool, parameters in bidsmap_options.items():
            # Set the tools
            if tool == "bidscoin":
                tooltip_text = OPTIONS_TOOLTIP_BIDSCOIN
            elif tool == "dcm2niix":
                tooltip_text = OPTIONS_TOOLTIP_DCM2NIIX
            else:
                tooltip_text = tool
            tool_list.append({
                "tool": tool,
                "tooltip_text": tooltip_text
            })
            # Store the options for each tool
            tool_options[tool] = []
            for key, value in parameters.items():
                tool_options[tool].append([
                    {
                        "value": tool,
                        "is_editable": False,
                        "tooltip_text": None
                    },
                    {
                        "value": key,
                        "is_editable": False,
                        "tooltip_text": tooltip_text
                    },
                    {
                        "value": value,
                        "is_editable": True,
                        "tooltip_text": "Double-click to edit the option"
                    }
                ])

        labels = []
        self.tables_options = []

        for n, tool_item in enumerate(tool_list):
            tool = tool_item['tool']
            tooltip_text = tool_item['tooltip_text']
            data = tool_options[tool]

            label = QLabel(tool)
            label.setToolTip(tooltip_text)

            table = QTableWidget()

            num_rows = len(data)
            num_cols = len(data[0]) + 1     # Always three columns (i.e. tool, key, value) + test-button
            table.setRowCount(num_rows)
            table.setColumnCount(num_cols)
            table.setColumnHidden(0, True)  # Hide tool column
            table.setMouseTracking(True)

            for i, row in enumerate(data):

                table.setRowHeight(i, ROW_HEIGHT)
                for j, element in enumerate(row):
                    value = element.get("value", "")
                    if value == "None":
                        value = ""
                    is_editable = element.get("is_editable", False)
                    tooltip_text = element.get("tooltip_text", None)
                    item = set_cell(value, is_editable=is_editable)
                    table.setItem(i, j, item)
                    if tooltip_text:
                        table.item(i, j).setToolTip(tooltip_text)

                table.setItem(i, num_cols-1, QTableWidgetItem())            # Add the test-button cell
                table.item(i, num_cols-1).setFlags(QtCore.Qt.NoItemFlags)

            test_button = QPushButton('Test')
            test_button.clicked.connect(partial(self.handle_click_test_tool, tool))
            test_button.setToolTip(f'Click to test the {tool} options')
            table.setCellWidget(0, num_cols-1, test_button)

            horizontal_header = table.horizontalHeader()
            horizontal_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            horizontal_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            horizontal_header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
            horizontal_header.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
            horizontal_header.setVisible(False)

            table.verticalHeader().setVisible(False)

            table.setAlternatingRowColors(False)
            table.setShowGrid(False)

            table.setMaximumHeight(table_height(num_rows))

            table.cellChanged.connect(partial(self.tool_cell_was_changed, tool, n))

            labels.append(label)
            self.tables_options.append(table)

        plugintable = QTableWidget()
        pluginlabel = QLabel('Plugins')
        pluginlabel.setToolTip('List of plugins')
        plugintable.setMouseTracking(True)
        plugintable.setAlternatingRowColors(False)
        plugintable.setShowGrid(False)

        self.plugintable = plugintable
        self.update_plugintable()

        for label, table in zip(labels, self.tables_options):
            tab2.layout.addWidget(label)
            tab2.layout.addWidget(table)

        tab2.layout.addWidget(pluginlabel)
        tab2.layout.addWidget(plugintable)
        tab2.layout.addStretch(1)
        tab2.setLayout(tab2.layout)

        self.tabwidget.addTab(tab2, "tab2")

    def update_subses_and_samples(self, output_bidsmap):
        """(Re)populates the sample list with bidsnames according to the bidsmap"""
        self.output_bidsmap = output_bidsmap  # input main window / output from edit window -> output main window

        item = set_cell("subject", is_editable=False)
        self.subses_table.setItem(0, 0, item)
        item = set_cell(self.output_bidsmap[SOURCE]['subject'], is_editable=True)
        self.subses_table.setItem(0, 1, item)
        item = set_cell("session", is_editable=False)
        self.subses_table.setItem(1, 0, item)
        item = set_cell(self.output_bidsmap[SOURCE]['session'], is_editable=True)
        self.subses_table.setItem(1, 1, item)

        idx = 0
        for modality in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):
            runs = self.output_bidsmap[SOURCE][modality]
            if not runs:
                continue
            for run in runs:
                provenance = run['provenance']
                provenance_file = os.path.basename(provenance)

                initial_file_index = self.initial_file_index[provenance]

                bids_name = bids.get_bidsname(output_bidsmap[SOURCE]['subject'], output_bidsmap[SOURCE]['session'],
                                              modality, run, '', self.subprefix, self.sesprefix)
                subid = bids.set_bidsvalue(bids_name, 'sub')
                sesid = bids.set_bidsvalue(bids_name, 'ses')
                session = os.path.join(self.bidsfolder, f'sub-{subid}', f'ses-{sesid}')

                self.table.setItem(idx, 0, QTableWidgetItem(f"{initial_file_index+1:03d}"))
                self.table.setItem(idx, 1, QTableWidgetItem(provenance_file))
                self.table.setItem(idx, 2, QTableWidgetItem(modality))                          # Hidden column
                self.table.setItem(idx, 3, QTableWidgetItem(os.path.join(modality, bids_name + '.*')))
                self.table.setItem(idx, 5, QTableWidgetItem(provenance))                        # Hidden column

                self.table.item(idx, 1).setToolTip('Double-click to inspect the header information')
                self.table.item(idx, 1).setStatusTip(os.path.dirname(provenance) + os.sep)
                self.table.item(idx, 0).setFlags(QtCore.Qt.NoItemFlags)
                self.table.item(idx, 2).setFlags(QtCore.Qt.ItemIsEnabled)
                self.table.item(idx, 3).setFlags(QtCore.Qt.ItemIsEnabled)
                self.table.item(idx, 3).setStatusTip(session + os.sep)

                self.edit_button = QPushButton('Edit')
                if self.table.item(idx, 3):
                    if modality == bids.unknownmodality:
                        self.table.item(idx, 3).setForeground(QtGui.QColor(255, 0, 0))
                    elif modality == bids.ignoremodality:
                        self.table.item(idx, 1).setForeground(QtGui.QColor(128, 128, 128))
                        self.table.item(idx, 3).setForeground(QtGui.QColor(128, 128, 128))
                        f = self.table.item(idx, 3).font()
                        f.setStrikeOut(True)
                        self.table.item(idx, 3).setFont(f)
                    else:
                        self.table.item(idx, 3).setForeground(QtGui.QColor(0, 128, 0))
                self.edit_button.clicked.connect(self.handle_edit_button_clicked)
                self.edit_button.setToolTip('Click to see more details and edit the BIDS output name')
                self.table.setCellWidget(idx, 4, self.edit_button)

                idx += 1

        self.table.sortByColumn(0, QtCore.Qt.AscendingOrder)

    def set_tab_bidsmap(self):
        """Set the SOURCE file sample listing tab.  """
        self.tab3 = QtWidgets.QWidget()
        self.tab3.layout = QVBoxLayout()
        self.tab3.setObjectName("BIDSmapping")

        subses_label = QLabel('Participant labels')
        subses_label.setToolTip('Subject/session mapping')

        self.subses_table = QTableWidget()
        self.subses_table.setMouseTracking(True)
        self.subses_table.setAlternatingRowColors(False)
        self.subses_table.setShowGrid(False)
        self.subses_table.setRowCount(2)
        self.subses_table.setColumnCount(2)
        horizontal_header = self.subses_table.horizontalHeader()
        horizontal_header.setVisible(False)
        horizontal_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.subses_table.verticalHeader().setVisible(False)
        self.subses_table.setAlternatingRowColors(False)
        self.subses_table.setShowGrid(False)
        self.subses_table.cellChanged.connect(self.subses_cell_was_changed)

        self.subses_table.setMaximumHeight(table_height(2))
        self.subses_table.setRowHeight(0, ROW_HEIGHT)
        self.subses_table.setRowHeight(1, ROW_HEIGHT)

        label = QLabel('Data samples')
        label.setToolTip('List of unique source-data samples')

        self.table = QTableWidget()
        self.table.itemDoubleClicked.connect(self.inspect_dicomfile)
        self.table.setMouseTracking(True)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(True)

        # Make sure we have the correct index mapping for the next edit
        num_files = self.set_initial_file_index()

        self.table.setColumnCount(6)
        self.table.setRowCount(num_files)

        self.update_subses_and_samples(self.output_bidsmap)

        self.table.setHorizontalHeaderLabels(['', f'{SOURCE} input', 'BIDS modality', 'BIDS output', 'Action', 'Provenance'])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.table.setColumnHidden(2, True)
        self.table.setColumnHidden(5, True)

        self.table.verticalHeader().setVisible(False)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.tab3.layout.addWidget(subses_label)
        self.tab3.layout.addWidget(self.subses_table)
        self.tab3.layout.addWidget(label)
        self.tab3.layout.addWidget(self.table)

        self.tab3.setLayout(self.tab3.layout)
        self.tabwidget.addTab(self.tab3, "")

    def get_help(self):
        """Get online help. """
        webbrowser.open(MAIN_HELP_URL)

    def get_bids_help(self):
        """Get online help. """
        webbrowser.open(HELP_URL_DEFAULT)

    def reload(self):
        """Reset button: reload the original input BIDS map. """
        if self.has_edit_dialog_open:
            self.dialog_edit.reject(confirm=False)

        LOGGER.info('User reloads the bidsmap')
        selected_tab_index = self.tabwidget.currentIndex()
        self.output_bidsmap, _ = bids.load_bidsmap(self.bidsmap_filename)
        self.setupUi(self.MainWindow,
                     self.bidsfolder,
                     self.sourcefolder,
                     self.bidsmap_filename,
                     self.input_bidsmap,
                     self.output_bidsmap,
                     self.template_bidsmap,
                     selected_tab_index=selected_tab_index,
                     reload=True)

    def save_bidsmap_to_file(self):
        """Save the BIDSmap to file. """
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(
            self.tab3,
            "Save File",
            os.path.join(self.bidsfolder, 'code', 'bidscoin', 'bidsmap.yaml'),
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=options)
        if filename:
            bids.save_bidsmap(filename, self.output_bidsmap)

    def handle_edit_button_clicked(self):
        """Make sure that index map has been updated. """
        button = self.MainWindow.focusWidget()
        rowindex = self.table.indexAt(button.pos()).row()
        modality = self.table.item(rowindex, 2).text()
        provenance = self.table.item(rowindex, 5).text()

        self.open_edit_dialog(provenance, modality)

    def on_double_clicked(self, index):
        filename = self.model.fileInfo(index).absoluteFilePath()
        if bids.is_dicomfile(filename):
            dicomdict = pydicom.dcmread(filename, force=True)
            self.popup = InspectWindow(filename, dicomdict)
            self.popup.show()

    def show_about(self):
        """ """
        about = f"BIDS editor\n{bids.version()}"
        QMessageBox.about(self.MainWindow, 'About', about)

    def open_edit_dialog(self, provenance, modality, exec=False):
        """Check for open edit window, find the right modality index and open the edit window"""

        if not self.has_edit_dialog_open:
            # Find the source index of the run in the list of runs (using the provenance) and open the edit window
            for run in self.output_bidsmap[SOURCE][modality]:
                if run['provenance']==provenance:
                    self.dialog_edit = EditDialog(provenance, modality, self.output_bidsmap, self.template_bidsmap, self.subprefix, self.sesprefix)
                    self.has_edit_dialog_open = True
                    self.dialog_edit.done_edit.connect(self.update_subses_and_samples)
                    self.dialog_edit.finished.connect(self.release_edit_dialog)
                    if exec:
                        self.dialog_edit.exec()
                    else:
                        self.dialog_edit.show()
                    break

        else:
            # Ask the user if he wants to save his results first before opening a new edit window
            self.dialog_edit.reject()
            if self.has_edit_dialog_open:
                return

            self.open_edit_dialog(provenance, modality, exec)

    def release_edit_dialog(self):
        """Allow a new edit window to be opened"""
        self.has_edit_dialog_open = False

    def exit_application(self):
        """Handle exit. """
        self.MainWindow.close()


class EditDialog(QDialog):
    """
    EditDialog().result() == 1: done with result, i.e. done_edit -> new bidsmap
    EditDialog().result() == 2: done without result
    """

    # Emit the new bidsmap when done
    done_edit = QtCore.pyqtSignal(dict)

    def __init__(self, provenance, modality, bidsmap, template_bidsmap, subprefix='sub-', sesprefix='ses-'):
        super().__init__()

        self.source_modality  = modality
        self.target_modality  = modality
        self.current_modality = modality
        self.source_bidsmap   = bidsmap
        self.target_bidsmap   = copy.deepcopy(bidsmap)
        self.template_bidsmap = template_bidsmap
        self.subprefix        = subprefix
        self.sesprefix        = sesprefix

        for run in bidsmap[SOURCE][modality]:
            if run['provenance'] == provenance:
                self.source_run = run

        self.target_run = copy.deepcopy(self.source_run)

        self.get_allowed_suffixes()

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)

        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.setWindowTitle("Edit BIDS mapping")

        layout_all = QVBoxLayout(self)

        layout_tables = QHBoxLayout(self)

        data_provenance, data_dicom, data_bids = self.get_editwin_data()

        self.label_provenance = QLabel()
        self.label_provenance.setText("Provenance")
        self.view_provenance = self.set_table(data_provenance, maximum=True)

        self.label_dicom = QLabel()
        self.label_dicom.setText("Attributes")
        self.view_dicom = self.set_table(data_dicom)

        self.set_modality_dropdown_section()

        self.label_bids = QLabel()
        self.label_bids.setText("Labels")
        self.view_bids = self.set_table(data_bids)

        self.set_bids_name_section()

        groupbox1 = QGroupBox(SOURCE + ' input')
        layout1 = QVBoxLayout()
        layout1.addWidget(self.label_provenance)
        layout1.addWidget(self.view_provenance)
        layout1.addWidget(self.label_dicom)
        layout1.addWidget(self.view_dicom)
        groupbox1.setLayout(layout1)

        groupbox2 = QGroupBox("BIDS output")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.label_dropdown)
        layout2.addWidget(self.modality_dropdown)
        layout2.addWidget(self.label_bids)
        layout2.addWidget(self.view_bids)
        layout2.addWidget(self.label_bids_name)
        layout2.addWidget(self.view_bids_name)
        groupbox2.setLayout(layout2)

        buttonBox = QDialogButtonBox(self)
        buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset | QDialogButtonBox.Help)
        buttonBox.button(QDialogButtonBox.Reset).setToolTip('Reset the edits you made')
        buttonBox.button(QDialogButtonBox.Ok).setToolTip('Apply the edits you made and close this window')
        buttonBox.button(QDialogButtonBox.Cancel).setToolTip('Discard the edits you made and close this window')
        buttonBox.button(QDialogButtonBox.Help).setToolTip('Go to the online BIDScoin documentation')

        layout_tables.addWidget(groupbox1)
        layout_tables.addWidget(groupbox2)

        self.view_provenance.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view_provenance.cellDoubleClicked.connect(self.inspect_dicomfile)
        self.view_dicom.cellChanged.connect(self.dicom_cell_was_changed)
        self.view_bids.cellChanged.connect(self.bids_cell_was_changed)

        buttonBox.accepted.connect(self.update_run)
        buttonBox.rejected.connect(partial(self.reject, False))
        buttonBox.helpRequested.connect(self.get_help)
        buttonBox.button(QDialogButtonBox.Reset).clicked.connect(self.reset)

        layout_all.addLayout(layout_tables)
        layout_all.addWidget(buttonBox)

        self.resize(EDIT_WINDOW_WIDTH, EDIT_WINDOW_HEIGHT)
        self.center()

        finish = QtWidgets.QAction(self)
        finish.triggered.connect(self.closeEvent)

    def center(self):
        """Center the edit window. """
        qr = self.frameGeometry()

        # Center point of screen
        cp = QDesktopWidget().availableGeometry().center()

        # Move rectangle's center point to screen's center point
        qr.moveCenter(cp)

        # Top left of rectangle becomes top left of window centering it
        self.move(qr.topLeft())

    def get_allowed_suffixes(self):
        """Derive the possible suffixes for each modality from the template. """
        allowed_suffixes = {}
        for modality in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):
            allowed_suffixes[modality] = []
            runs = self.template_bidsmap[SOURCE][modality]
            if not runs:
                continue
            for run in runs:
                suffix = run['bids'].get('suffix', None)
                if suffix and suffix not in allowed_suffixes[modality]:
                    allowed_suffixes[modality].append(suffix)

        # Sort the allowed suffixes alphabetically
        for modality in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):
            allowed_suffixes[modality] = sorted(allowed_suffixes[modality])

        self.allowed_suffixes = allowed_suffixes

    def get_editwin_data(self):
        """
        Derive the tabular data from the target_run, needed to render the edit window.

        :return: (data_provenance, data_dicom, data_bids)
        """
        data_provenance = [
            [
                {
                    "value": "path",
                    "is_editable": False
                },
                {
                    "value": os.path.dirname(self.target_run['provenance']),
                    "is_editable": False
                },
            ],
            [
                {
                    "value": "filename",
                    "is_editable": False
                },
                {
                    "value": os.path.basename(self.target_run['provenance']),
                    "is_editable": True
                },
            ]
        ]

        data_dicom = []
        for key, value in self.target_run['attributes'].items():
            data_dicom.append([
                {
                    "value": key,
                    "is_editable": False
                },
                {
                    "value": str(value),
                    "is_editable": True
                }
            ])

        data_bids = []
        for bidslabel in bids.bidslabels:
            if bidslabel in self.target_run['bids']:
                if self.target_modality in bids.bidsmodalities and bidslabel=='suffix':
                    is_editable = False
                else:
                    is_editable = True

                data_bids.append([
                    {
                        "value": bidslabel,
                        "is_editable": False
                    },
                    {
                        "value": self.target_run['bids'][bidslabel],
                        "is_editable": is_editable
                    }
                ])

        return data_provenance, data_dicom, data_bids

    def inspect_dicomfile(self, row=None, column=None):
        """When double clicked, show popup window. """
        if row == 1 and column == 1:
            filename = self.target_run['provenance']
            if bids.is_dicomfile(filename):
                dicomdict = pydicom.dcmread(filename, force=True)
                self.popup = InspectWindow(filename, dicomdict)
                self.popup.exec()

    def dicom_cell_was_changed(self, row, column):
        """DICOM attribute value has been changed. """
        if column == 1:
            key = self.view_dicom.item(row, 0).text()
            value = self.view_dicom.item(row, 1).text()
            oldvalue = self.target_run['attributes'].get(key, None)

            # Only if cell was actually clicked, update (i.e. not when BIDS modality changes). TODO: fix
            if key and value!=oldvalue:
                LOGGER.info(f"User has set {SOURCE}['{key}'] from '{oldvalue}' to '{value}' for {self.target_run['provenance']}")
                self.target_run['attributes'][key] = value

    def bids_cell_was_changed(self, row, column):
        """BIDS attribute value has been changed. """
        if column == 1:
            key = self.view_bids.item(row, 0).text()
            value = self.view_bids.item(row, 1).text()
            oldvalue = self.target_run['bids'].get(key, None)

            # Only if cell was actually clicked, update (i.e. not when BIDS modality changes). TODO: fix
            if key and value!=oldvalue:
                # Validate user input against BIDS or replace the (dynamic) bids-value if it is a run attribute
                if not (value.startswith('<<') and value.endswith('>>')):
                    value = bids.cleanup_value(bids.replace_bidsvalue(value, self.target_run['provenance']))
                LOGGER.info(f"User has set bids['{key}'] from '{oldvalue}' to '{value}' for {self.target_run['provenance']}")

                self.target_run['bids'][key] = value
                self.view_bids.item(row, 1).setText(value)
                self.refresh_bidsname()

    def fill_table(self, table, data, maximum: bool=False):
        """
        Fill the table with data.

        :param table:
        :param data:
        :return:
        """

        table.blockSignals(True)
        table.clearContents()

        num_rows = len(data)
        table.setRowCount(num_rows)
        if maximum:
            table.setMaximumHeight(table_height(num_rows))

        for i, row in enumerate(data):
            table.setRowHeight(i, ROW_HEIGHT)
            key = row[0]["value"]
            if self.target_modality in bids.bidsmodalities and key == 'suffix':
                item = set_cell("suffix", is_editable=False)
                table.setItem(i, 0, item)
                labels = self.allowed_suffixes[self.target_modality]
                self.suffix_dropdown = QComboBox()
                self.suffix_dropdown.addItems(labels)
                self.suffix_dropdown.setCurrentIndex(self.suffix_dropdown.findText(self.target_run['bids']['suffix']))
                self.suffix_dropdown.currentIndexChanged.connect(self.selection_suffix_dropdown_change)
                table.setCellWidget(i, 1, self.suffix_dropdown)
                continue
            for j, element in enumerate(row):
                value = element.get("value", "")
                if value == "None":
                    value = ""
                is_editable = element.get("is_editable", False)
                item = set_cell(value, is_editable=is_editable)
                table.setItem(i, j, item)

        table.blockSignals(False)

    def set_table(self, data, maximum: bool=False):
        """Return a table widget from the data. """
        table = QTableWidget()

        table.setColumnCount(2) # Always two columns (i.e. key, value)

        self.fill_table(table, data, maximum=maximum)

        horizontal_header = table.horizontalHeader()
        horizontal_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        horizontal_header.setVisible(False)

        table.verticalHeader().setVisible(False)

        table.setAlternatingRowColors(False)
        table.setShowGrid(False)

        return table

    def set_modality_dropdown_section(self):
        """Dropdown select modality list section. """
        self.label_dropdown = QLabel()
        self.label_dropdown.setText("Modality")

        self.modality_dropdown = QComboBox()
        self.modality_dropdown.addItems(bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality))
        self.modality_dropdown.setCurrentIndex(self.modality_dropdown.findText(self.target_modality))

        self.modality_dropdown.currentIndexChanged.connect(self.selection_modality_dropdown_change)

    def set_bids_name_section(self):
        """Set non-editable BIDS output name section. """
        self.label_bids_name = QLabel()
        self.label_bids_name.setText("Output name")

        self.view_bids_name = QTextBrowser()

        self.view_bids_name.setMaximumHeight(45)

        self.refresh_bidsname()

    def refresh_bidsname(self):
        bidsname = os.path.join(self.target_modality, bids.get_bidsname(self.target_bidsmap[SOURCE]['subject'], self.target_bidsmap[SOURCE]['session'],
                                                                        self.target_modality, self.target_run, '', self.subprefix, self.sesprefix)) + '.*'
        html_bids_name = bidsname.replace('<', '&lt;').replace('>', '&gt;')

        self.view_bids_name.clear()
        if self.target_modality == bids.ignoremodality:
            self.view_bids_name.textCursor().insertHtml('<font color="#808080"><s>%s</s></font>' % html_bids_name)
        else:
            self.view_bids_name.textCursor().insertHtml('<font color="#808080">%s</font>' % html_bids_name)

    def refresh(self, suffix_idx):
        """
        Refresh the edit dialog window with a new target_run from the template bidsmap.

        :param suffix_idx: The suffix or index number that will used to extract the run from the template bidsmap
        :return:
        """

        # Get the new target_run
        self.target_run = bids.get_run(self.template_bidsmap, SOURCE, self.target_modality, suffix_idx, self.target_run['provenance'])

        # Insert the new target_run in our target_bidsmap
        self.target_bidsmap = bids.update_bidsmap(self.target_bidsmap,
                                                  self.current_modality,
                                                  self.target_run['provenance'],
                                                  self.target_modality,
                                                  self.target_run)

        # Now that we have updated the bidsmap, we can also update the current_modality
        self.current_modality = self.target_modality

        # Refresh the edit window
        self.reset(refresh=True)

    def reset(self, refresh: bool=False):
        """Resets the edit with the target_run if refresh=True or otherwise with the original source_run (=default)"""

        # Reset the target_run to the source_run
        if not refresh:
            LOGGER.info('User resets the BIDS mapping')
            self.current_modality = self.source_modality
            self.target_modality  = self.source_modality
            self.target_run       = copy.deepcopy(self.source_run)
            self.target_bidsmap   = copy.deepcopy(self.source_bidsmap)

            # Reset the modality dropdown menu
            self.modality_dropdown.setCurrentIndex(self.modality_dropdown.findText(self.target_modality))

        # Refresh the DICOM attributes and BIDS values with data from the target_run
        _, data_dicom, data_bids = self.get_editwin_data()

        # Refresh the existing tables
        self.fill_table(self.view_dicom, data_dicom)
        self.fill_table(self.view_bids, data_bids)

        # Refresh the BIDS output name
        self.refresh_bidsname()

    def selection_modality_dropdown_change(self):
        """Update the BIDS values and BIDS output name section when the dropdown selection has been taking place. """
        self.target_modality = self.modality_dropdown.currentText()

        LOGGER.info(f"User has changed the BIDS modality from '{self.current_modality}' to '{self.target_modality}' for {self.target_run['provenance']}")

        self.refresh(0)

    def selection_suffix_dropdown_change(self):
        """Update the BIDS values and BIDS output name section when the dropdown selection has been taking place. """
        target_suffix = self.suffix_dropdown.currentText()

        LOGGER.info(f"User has changed the BIDS suffix from '{self.target_run['bids']['suffix']}' to '{target_suffix}' for {self.target_run['provenance']}")

        self.refresh(target_suffix)

    def get_help(self):
        """Open web page for help. """
        help_url = HELP_URLS.get(self.target_modality, HELP_URL_DEFAULT)
        webbrowser.open(help_url)

    def reject(self, confirm=True):
        """Ask if the user really wants to close the window"""
        if confirm:
            self.raise_()
            answer = QMessageBox.question(self, 'Edit BIDS mapping', "Closing window, do you want to save the changes you made?",
                                          QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Cancel)
            if answer == QMessageBox.Yes:
                self.update_run()
                return
            if answer == QMessageBox.No:
                self.done(2)
                LOGGER.info(f'User has discarded the edit')
                return
            if answer == QMessageBox.Cancel:
                return

        LOGGER.info(f'User has canceled the edit')

        super(EditDialog, self).reject()

    def update_run(self):
        LOGGER.info(f'User has approved the edit')

        """Save the changes to the target_bidsmap and send it back to the main window: Finished! """
        self.target_bidsmap = bids.update_bidsmap(self.target_bidsmap,
                                                  self.current_modality,
                                                  self.target_run['provenance'],
                                                  self.target_modality,
                                                  self.target_run)

        self.done_edit.emit(self.target_bidsmap)
        self.done(1)


def bidseditor(bidsfolder: str, sourcefolder: str='', bidsmapfile: str='', templatefile: str='', subprefix='sub-', sesprefix='ses-'):
    """

    :param bidsfolder:
    :param bidsmapfile:
    :param templatefile:
    :return:
    """

    # Start logging
    bids.setup_logging(os.path.join(bidsfolder, 'code', 'bidscoin', 'bidseditor.log'))
    LOGGER.info('')
    LOGGER.info('------------ START BIDSeditor ------------')

    # Obtain the initial bidsmap info
    template_bidsmap, _        = bids.load_bidsmap(templatefile, os.path.join(bidsfolder,'code','bidscoin'))
    input_bidsmap, bidsmapfile = bids.load_bidsmap(bidsmapfile,  os.path.join(bidsfolder,'code','bidscoin'))
    output_bidsmap             = copy.deepcopy(input_bidsmap)

    # Parse the sourcefolder from the bidsmap provenance info
    if not sourcefolder:

        # Loop through all bidsmodalities and runs until we find provenance info
        for modality in bids.bidsmodalities + (bids.unknownmodality, bids.ignoremodality):
            if input_bidsmap[SOURCE][modality] is None:
                continue

            for run in input_bidsmap[SOURCE][modality]:
                if run['provenance']:
                    sourcefolder = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(run['provenance']))))
                    LOGGER.info(f'Source: {sourcefolder}')
                    break

            if sourcefolder:
                break

    # Start the Qt-application
    app = QApplication(sys.argv)
    app.setApplicationName('BIDS editor')
    mainwin = MainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(mainwin, bidsfolder, sourcefolder, bidsmapfile, input_bidsmap, output_bidsmap, template_bidsmap, subprefix=subprefix, sesprefix=sesprefix)
    mainwin.show()
    app.exec()

    LOGGER.info('------------ FINISHED! -------------------')
    LOGGER.info('')


if __name__ == "__main__":

    # Parse the input arguments and run bidseditor
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog=textwrap.dedent("""
                                         examples:
                                           bidseditor.py /project/foo/bids
                                           bidseditor.py /project/foo/bids -t bidsmap_dccn.yaml
                                           bidseditor.py /project/foo/bids -b my/custom/bidsmap.yaml

                                         Here are a few tips & tricks:
                                         -----------------------------

                                         DICOM Attributes
                                           An (DICOM) attribute label can also be a list, in which case the BIDS labels / mapping
                                           are applies if a (DICOM) attribute value is in this list. If the attribute value is
                                           empty it is not used to identify the run. Wildcards can also be given, either as a single
                                           '*', or enclosed by '*'. Examples:
                                                SequenceName: '*'
                                                SequenceName: '*epfid*'
                                                SequenceName: ['epfid2d1rs', 'fm2d2r']
                                                SequenceName: ['*epfid*', 'fm2d2r']

                                         Dynamic BIDS labels
                                           The BIDS labels can be static, in which case the label is just a normal string, or dynamic,
                                           when the string is enclosed with pointy brackets like `<attribute name>` or
                                           `<<argument1><argument2>>`. In case of single pointy brackets the label will be replaced
                                           during bidsmapper, bidseditor and bidscoiner runtime by the value of the (DICOM) attribute
                                           with that name. In case of double pointy brackets, the label will be updated for each
                                           subject/session during bidscoiner runtime. For instance, then the `run` label `<<1>>` in
                                           the bids name will be replaced with `1` or increased to `2` if a file with runindex `1`
                                           already exists in that directory.

                                         Fieldmaps: IntendedFor
                                           You can use the `IntendedFor` field to indicate for which runs (DICOM series) a fieldmap
                                           was intended. The dynamic label of the `IntendedFor` field can be a list of string patterns
                                           that is used to include all runs in a session that have that string pattern in their BIDS
                                           file name. Example: use `<<task>>` to include all functional runs or `<<Stop*Go><Reward>>`
                                           to include "Stop1Go"-, "Stop2Go"- and "Reward"-runs.

                                         Manual editing / inspection of the bidsmap
                                           You can of course also directly edit or inspect the `bidsmap.yaml` file yourself with any
                                           text editor. For instance to add a dynamic `participant` value like `<<PatientID>>`. 
                                           See ./docs/bidsmap.md for more information."""))

    parser.add_argument('bidsfolder',           help='The destination folder with the (future) bids data')
    parser.add_argument('-s','--sourcefolder',  help='The source folder containing the raw data. If empty, it is derived from the bidsmap provenance information')
    parser.add_argument('-b','--bidsmap',       help='The bidsmap YAML-file with the study heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-t','--template',      help='The bidsmap template with the default heuristics (this could be provided by your institute). If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap_template.yaml', default='bidsmap_template.yaml')
    parser.add_argument('-n','--subprefix',     help="The prefix common for all the source subject-folders. Default: 'sub-'", default='sub-')
    parser.add_argument('-m','--sesprefix',     help="The prefix common for all the source session-folders. Default: 'ses-'", default='ses-')
    args = parser.parse_args()

    bidseditor(bidsfolder   = args.bidsfolder,
               sourcefolder = args.sourcefolder,
               bidsmapfile  = args.bidsmap,
               templatefile = args.template,
               subprefix    = args.subprefix,
               sesprefix    = args.sesprefix)
