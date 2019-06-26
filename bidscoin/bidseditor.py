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
import subprocess
from functools import partial
from collections import OrderedDict

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileSystemModel, QFileDialog,
                             QTreeView, QHBoxLayout, QVBoxLayout, QLabel, QDialog,
                             QTableWidget, QTableWidgetItem, QGroupBox, QPlainTextEdit,
                             QAbstractItemView, QPushButton, QComboBox, QTextEdit, QDesktopWidget)

try:
    from bidscoin import bids
except ImportError:
    import bids             # This should work if bidscoin was not pip-installed

SOURCE = 'DICOM'            # TODO: allow for non-DICOM (e.g. PAR/REC) edits

LOGGER = logging.getLogger('bidscoin')

MAIN_WINDOW_WIDTH   = 1024
MAIN_WINDOW_HEIGHT  = 500

EDIT_WINDOW_WIDTH   = 900
EDIT_WINDOW_HEIGHT  = 600

ABOUT_WINDOW_WIDTH  = 100
ABOUT_WINDOW_HEIGHT = 90

INSPECT_WINDOW_WIDTH = 650
INSPECT_WINDOW_HEIGHT = 290

TEST_WINDOW_WIDTH  = 250
TEST_WINDOW_HEIGHT = 90

MAX_NUM_PROVENANCE_ATTRIBUTES = 2
MAX_NUM_BIDS_ATTRIBUTES = 9

OPTION_BIDSCOIN_VERSION_DISPLAY = "BIDScoin version"
OPTION_DCM2NIIX_PATH_DISPLAY = "dcm2niix path"
OPTION_DCM2NIIX_ARGS_DISPLAY = "dcm2niix args"

DEFAULT_TAB_INDEX = 2

ICON_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "icons", "brain.ico")

MAIN_HELP_URL = "https://github.com/Donders-Institute/bidscoin/blob/master/README.md"

HELP_URL_DEFAULT = "https://bids-specification.readthedocs.io/en/latest/"

HELP_URLS = {
    "anat": "https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#anatomy-imaging-data",
    "beh": "https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/07-behavioral-experiments.html",
    "dwi": "https://bids-specification.readthedocs.io/en/stable/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#diffusion-imaging-data",
    "fmap": "https://bids-specification.readthedocs.io/en/latest/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data",
    "func": "https://bids-specification.readthedocs.io/en/latest/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#task-including-resting-state-imaging-data",
    "pet": "https://docs.google.com/document/d/1mqMLnxVdLwZjDd4ZiWFqjEAmOmfcModA_R535v3eQs0/edit",
    bids.unknownmodality: HELP_URL_DEFAULT
}

OPTIONS_TOOLTIP_BIDSCOIN = """bidscoin\n
version (should correspond with the version in ../bidscoin/version.txt)"""

OPTIONS_TOOLTIP_DCM2NIXX = """dcm2nixx\n
See dcm2niix -h and https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage#General_Usage for more info.
Command to set the path to dcm2niix (note the semi-colon),\ne.g. module add dcm2niix/1.0.20180622;
or PATH=/opt/dcm2niix/bin:$PATH;
or /opt/dcm2niix/bin/
or '\"C:\\Program Files\\dcm2niix\"' (note the quotes to deal with the whitespace)"""


def update_bidsmap(source_bidsmap, target_bidsmap, source_modality, source_index, target_modality, target_series):
    """Update the BIDS map:
    1. Remove the source series from the source modality section
    2. Start new series dictionary and store key values without comments and references
    3. Add the target series to the target modality section
    """
    if not source_modality in bids.bidsmodalities + (bids.unknownmodality,):
        raise ValueError(f"invalid modality '{source_modality}'")

    if not target_modality in bids.bidsmodalities + (bids.unknownmodality,):
        raise ValueError(f"invalid modality '{target_modality}'")

    # First check if the target series already exists.    TODO: figure out what to do with this situation
    if source_modality != target_modality and bids.exist_series(target_bidsmap, SOURCE, target_modality, target_series):
        LOGGER.warning('That entry already exists...')

    # Delete the source series
    target_bidsmap = bids.delete_series(target_bidsmap, SOURCE, source_modality, source_index)

    # Copy the values from the target_series to the empty dict
    series = dict(provenance={}, attributes={}, bids={})  # The CommentedMap API is not guaranteed for the future so keep this line as an alternative
    for attrkey in target_series['attributes']:
        series['attributes'][attrkey] = target_series['attributes'][attrkey]
    for key in target_series['bids']:
        series['bids'][key] = target_series['bids'][key]
    series['provenance'] = target_series['provenance']

    # Append the cleaned-up target series
    target_bidsmap = bids.append_series(target_bidsmap, SOURCE, target_modality, series)

    return target_bidsmap


def get_allowed_suffixes(template_bidsmap):
    """Derive the possible suffixes for each modality from the template. """
    allowed_suffixes = {}
    for modality in bids.bidsmodalities + (bids.unknownmodality,):
        allowed_suffixes[modality] = []
        series_list = template_bidsmap[SOURCE][modality]
        if not series_list:
            continue
        for series in series_list:
            suffix = series['bids'].get('suffix', None)
            if suffix and suffix not in allowed_suffixes[modality]:
                allowed_suffixes[modality].append(suffix)

    # Sort the allowed suffixes alphabetically
    for modality in bids.bidsmodalities + (bids.unknownmodality,):
        allowed_suffixes[modality] = sorted(allowed_suffixes[modality])

    return allowed_suffixes


def get_bids_attributes(template_bidsmap, allowed_suffixes, modality, source_series):
    """Return the target BIDS attributes (i.e. the key, value pairs)
    given the keys from the template
    given the values from the source BIDS attributes. """
    template_bids_attributes = template_bidsmap[SOURCE][modality][0]['bids']

    bids_attributes = OrderedDict()
    for key, template_value in template_bids_attributes.items():
        if not template_value:
            template_value = ''
            # If not free choice, select the first possible option from the list of allowed suffixes
            if key == 'suffix' and modality in bids.bidsmodalities:
                template_value = allowed_suffixes[modality][0]

        source_value = source_series['bids'].get(key, None)
        if source_value:
            # Set the value from the source attributes
            bids_attributes[key] = source_value
        else:
            # Set the default value from the template
            bids_attributes[key] = bids.replace_bidsvalue(template_value, source_series['provenance'])

    return bids_attributes


def get_html_bidsname(bidsname):
    """Clean bidsname . """
    return bidsname.replace('<', '&lt;').replace('>', '&gt;')


def get_index_mapping(bidsmap):
    """Obtain the mapping between file_index and the series ndex for each modality. """
    index_mapping = {}
    file_index = 0
    for modality in bids.bidsmodalities + (bids.unknownmodality,):
        series_list = bidsmap[SOURCE][modality]
        index_mapping[modality] = {}
        if not series_list:
            continue
        for series_index, _ in enumerate(series_list):
            index_mapping[modality][file_index] = series_index
            file_index += 1
    return index_mapping


def test_tooloptions(tool: str, opts: dict) -> bool:
    """
    Performs tests of the user tool parameters set in the bidsmap Options-tab

    :param tool:    Name of the tool that is being tested in bidsmap['Options']
    :param opts:    The key-value dictionary from bidsmap['Options'][tool]
    :return:        True if the tool generated the expected result, False if there
                    was a tool error, None if this function has an implementation error
    """

    succes = None
    if tool == 'dcm2niix':
        command = f"{opts['path']}dcm2niix -h"
    elif tool == 'bidscoin':
        command = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'bidscoin.py -v')
    else:
        LOGGER.info(f'Testing of {tool} not supported')
        return succes

    LOGGER.info('Testing: ' + command)
    process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.stdout.decode('utf-8'):
        LOGGER.info('Test result:\n' + process.stdout.decode('utf-8'))
        succes = True
    if process.stderr.decode('utf-8'):
        LOGGER.error('Test result:\n' + process.stderr.decode('utf-8'))
        succes = False
    if process.returncode!=0:
        LOGGER.error(f'Test result:\nFailed to run {command} (errorcode {process.returncode})')
        succes = False

    return succes


class InspectWindow(QDialog):

    def __init__(self, filename, dicomdict):
        QDialog.__init__(self)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)
        self.setWindowTitle("Inspect DICOM file")

        top_widget = QtWidgets.QWidget(self)
        top_layout = QtWidgets.QVBoxLayout(self)

        label = QLabel(top_widget)
        label.setText("Filename: " + os.path.basename(filename))

        label_path = QLabel(top_widget)
        label_path.setText("Path: " + os.path.dirname(filename))

        text_area = QPlainTextEdit(top_widget)
        text_area.insertPlainText(str(dicomdict))

        pushButton = QPushButton("OK")
        pushButton.setToolTip("Close dialog")
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(pushButton)

        top_layout.addWidget(label_path)
        top_layout.addWidget(label)
        top_layout.addWidget(text_area)
        top_layout.addStretch(1)
        top_layout.addLayout(hbox)

        pushButton.clicked.connect(self.close)

        top_widget.setLayout(top_layout)
        top_widget.resize(top_widget.sizeHint())

        self.setMinimumSize(INSPECT_WINDOW_WIDTH, INSPECT_WINDOW_HEIGHT)
        self.setMaximumSize(INSPECT_WINDOW_WIDTH, INSPECT_WINDOW_HEIGHT)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        actionQuit = QtWidgets.QAction("Quit", self)
        actionQuit.triggered.connect(self.closeEvent)

    def closeEvent(self, event):
        """Handle exit. """
        LOGGER.info('------------ FINISHED! ------------')
        QApplication.quit()


class Ui_MainWindow(object):

    def setupUi(self, MainWindow, bidsfolder, sourcefolder, bidsmap_filename,
                input_bidsmap, output_bidsmap, template_bidsmap, selected_tab_index=DEFAULT_TAB_INDEX):

        self.has_edit_dialog_open = False

        self.MainWindow = MainWindow

        self.bidsfolder = bidsfolder
        self.sourcefolder = sourcefolder
        self.bidsmap_filename = bidsmap_filename
        self.input_bidsmap = input_bidsmap
        self.output_bidsmap = output_bidsmap
        self.template_bidsmap = template_bidsmap

        # Make sure we have the correct index mapping for the first edit
        self.index_mapping = get_index_mapping(input_bidsmap)

        self.MainWindow.setObjectName("MainWindow")

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.MainWindow.setWindowIcon(icon)

        self.centralwidget = QtWidgets.QWidget(self.MainWindow)
        self.centralwidget.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        self.centralwidget.setObjectName("centralwidget")

        top_widget = QtWidgets.QWidget(self.centralwidget)
        top_layout = QtWidgets.QVBoxLayout(self.centralwidget)

        self.tabwidget = QtWidgets.QTabWidget(top_widget)
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

        self.MainWindow.setCentralWidget(self.centralwidget)
        self.set_menu_and_status_bar()

        self.MainWindow.setMinimumSize(MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT)
        self.center()

    def set_menu_and_status_bar(self):
        """Set the menu. """
        self.menubar = QtWidgets.QMenuBar(self.MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 997, 26))
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuHelp = QtWidgets.QMenu(self.menubar)

        self.MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(self.MainWindow)

        # Set the statusbar
        self.statusbar.setToolTip("")
        self.statusbar.setObjectName("statusbar")
        self.MainWindow.setStatusBar(self.statusbar)

        # Define the menu actions
        self.actionExit = QtWidgets.QAction(self.MainWindow)
        self.actionExit.triggered.connect(self.exit_application)

        self.actionReload = QtWidgets.QAction(self.MainWindow)
        self.actionReload.triggered.connect(self.reload)

        self.actionSave = QtWidgets.QAction(self.MainWindow)
        self.actionSave.triggered.connect(self.save_bidsmap_to_file)

        self.actionAbout = QtWidgets.QAction(self.MainWindow)
        self.actionAbout.triggered.connect(self.show_about)

        self.actionEdit = QtWidgets.QAction(self.MainWindow)

        self.actionHelp = QtWidgets.QAction(self.MainWindow)
        self.actionHelp.triggered.connect(self.get_help)

        self.actionBidsHelp = QtWidgets.QAction(self.MainWindow)
        self.actionBidsHelp.triggered.connect(self.get_bids_help)

        self.menuFile.addAction(self.actionReload)
        self.menuFile.addAction(self.actionSave)
        self.menuFile.addAction(self.actionExit)

        self.menuHelp.addAction(self.actionAbout)
        self.menuHelp.addAction(self.actionHelp)
        self.menuHelp.addAction(self.actionBidsHelp)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())

        self.menuFile.setTitle("File")
        self.menuHelp.setTitle("Help")
        self.statusbar.setStatusTip("Statusbar")

        self.actionReload.setText("Reload")
        self.actionReload.setStatusTip("Reload the BIDSmap from disk")
        self.actionReload.setShortcut("Ctrl+R")

        self.actionSave.setText("Save")
        self.actionSave.setStatusTip("Save the BIDSmap to disk")
        self.actionSave.setShortcut("Ctrl+S")

        self.actionExit.setText("Exit")
        self.actionExit.setStatusTip("Exit the application")
        self.actionExit.setShortcut("Ctrl+X")

        self.actionAbout.setText("About")
        self.actionAbout.setStatusTip("Show information about the application")

        self.actionHelp.setText("Documentation")
        self.actionHelp.setStatusTip("Go to the online BIDScoin documentation")
        self.actionHelp.setShortcut("F1")

        self.actionBidsHelp.setText("BIDS specification")
        self.actionBidsHelp.setStatusTip("Go to the online BIDS specification documentation")
        self.actionBidsHelp.setShortcut("F2")

    def center(self):
        """Center the main window. """
        qr = self.MainWindow.frameGeometry()

        # Center point of screen
        cp = QDesktopWidget().availableGeometry().center()

        # Move rectangle's center point to screen's center point
        qr.moveCenter(cp)

        # Top left of rectangle becomes top left of window centering it
        self.MainWindow.move(qr.topLeft())

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
        self.tab1 = QtWidgets.QWidget()
        self.tab1.layout = QVBoxLayout()
        self.label = QLabel()
        self.label.setText("Inspect source data folder: {}".format(sourcefolder))
        self.model = QFileSystemModel()
        self.model.setRootPath('')
        self.model.setFilter(QtCore.QDir.NoDotAndDotDot | QtCore.QDir.AllDirs | QtCore.QDir.Files)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setAnimated(False)
        self.tree.setIndentation(20)
        self.tree.setSortingEnabled(True)
        self.tree.setRootIndex(self.model.index(sourcefolder))
        self.tree.doubleClicked.connect(self.on_double_clicked)
        self.tab1.layout.addWidget(self.label)
        self.tab1.layout.addWidget(self.tree)
        self.tree.header().resizeSection(0, 800)

        self.file_browser = QtWidgets.QWidget()
        self.file_browser.setLayout(self.tab1.layout)
        self.file_browser.setObjectName("filebrowser")
        self.tabwidget.addTab(self.file_browser, "")

    def set_cell(self, value, is_editable=False):
        item = QTableWidgetItem()
        item.setText(value)
        if is_editable:
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable)
        else:
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            item.setForeground(QtGui.QColor(128, 128, 128))
        return item

    def cell_was_changed_bidscoin(self, row, column):
        """Option value has been changed in BIDScoin tool options table. """
        if column == 2:
            table = self.tables_options[0]  # Select the first table
            tool = table.item(row, 0).text()
            key = table.item(row, 1).text()
            value = table.item(row, 2).text()

            # Only if cell was actually clicked, update
            if key != '':
                self.output_bidsmap["Options"][tool][key] = value

    def cell_was_changed_dcm2niix(self, row, column):
        """Option value has been changed in dcm2niix tool options table. """
        if column == 2:
            table = self.tables_options[1] # Select the second table
            tool = table.item(row, 0).text()
            key = table.item(row, 1).text()
            value = table.item(row, 2).text()

            # Only if cell was actually clicked, update
            if key != '':
                self.output_bidsmap["Options"][tool][key] = value

    def handle_click_test(self, tool: str):
        """Test the bidsmap tool and show the result in a pop-up window

        :param tool:    Name of the tool that is being tested in bidsmap['Options']
         """
        opts = self.output_bidsmap['Options'][tool]
        if test_tooloptions(tool, opts):
            result = 'Passed'
        else:
            result = 'Failed'
        self.dialog_test = TestDialog(tool, result)
        self.dialog_test.show()

    def set_tab_options(self):
        """Set the options tab.  """
        self.tab2 = QtWidgets.QWidget()
        self.tab2.layout = QVBoxLayout()

        help_button = QtWidgets.QPushButton()
        help_button.setText("Help")
        help_button.setStatusTip("Go to the online BIDScoin documentation")

        reload_button = QtWidgets.QPushButton()
        reload_button.setText("Reload")
        reload_button.setStatusTip("Reload Options from disk")

        save_button = QtWidgets.QPushButton()
        save_button.setText("Save")
        save_button.setStatusTip("Save Options to disk")

        bidsmap_options = self.output_bidsmap['Options']

        tool_list = []
        tool_options = {}
        for tool, parameters in bidsmap_options.items():
            # Set the tools
            if tool == "bidscoin":
                tooltip_text = OPTIONS_TOOLTIP_BIDSCOIN
            elif tool == "dcm2niix":
                tooltip_text = OPTIONS_TOOLTIP_DCM2NIXX
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
                        "tooltip_text": None
                    },
                    {
                        "value": value,
                        "is_editable": True,
                        "tooltip_text": tooltip_text
                    }
                ])

        labels = []
        self.tables_options = []
        for tool_item in tool_list:
            tool = tool_item['tool']
            tooltip_text = tool_item['tooltip_text']
            data = tool_options[tool]

            label = QLabel()
            label.setText(tool)
            label.setToolTip(tooltip_text)

            table = QTableWidget()

            num_rows = len(data)
            num_cols = len(data[0]) + 1     # Always three columns (i.e. tool, key, value) + test-button
            table.setRowCount(num_rows)
            table.setColumnCount(num_cols)
            table.setColumnHidden(0, True)  # Hide tool column
            table.setMouseTracking(True)
            row_height = 24

            for i, row in enumerate(data):

                table.setRowHeight(i, row_height)
                for j, element in enumerate(row):
                    value = element.get("value", "")
                    if value == "None":
                        value = ""
                    is_editable = element.get("is_editable", False)
                    tooltip_text = element.get("tooltip_text", None)
                    item = self.set_cell(value, is_editable=is_editable)
                    table.setItem(i, j, QTableWidgetItem(item))
                    if tooltip_text:
                        table.item(i, j).setToolTip(tooltip_text)
                    if is_editable:
                        table.item(i, j).setStatusTip("Double-click to edit the option")

                table.setItem(i, num_cols-1, QTableWidgetItem())
                table.item(i, num_cols-1).setFlags(QtCore.Qt.NoItemFlags)

            button_test = QPushButton('Test')
            button_test.clicked.connect(partial(self.handle_click_test, tool))
            button_test.setStatusTip(f'Click to test the {tool} options')
            table.setCellWidget(0, num_cols-1, button_test)

            horizontal_header = table.horizontalHeader()
            horizontal_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            horizontal_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            horizontal_header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
            horizontal_header.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
            horizontal_header.setVisible(False)

            vertical_header = table.verticalHeader()
            vertical_header.setVisible(False)

            table.setAlternatingRowColors(False)
            table.setShowGrid(False)

            extra_space = 6
            table_height = num_rows * (row_height + extra_space) + 2 * table.frameWidth()
            table.setMinimumHeight(table_height)
            table.setMaximumHeight(table_height)

            if tool == "bidscoin":
                table.cellChanged.connect(self.cell_was_changed_bidscoin)
            elif tool == "dcm2niix":
                table.cellChanged.connect(self.cell_was_changed_dcm2niix)
            else:
                LOGGER.warning(f"Unsupported tool{tool}")

            labels.append(label)
            self.tables_options.append(table)

        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(help_button)
        hbox.addWidget(reload_button)
        hbox.addWidget(save_button)

        vbox = QVBoxLayout()
        for label, table in zip(labels, self.tables_options):
            vbox.addWidget(label)
            vbox.addWidget(table)
        vbox.addStretch(1)
        vbox.addLayout(hbox)

        self.tab2.layout.addLayout(vbox)

        self.options = QtWidgets.QWidget()
        self.options.setLayout(self.tab2.layout)
        self.options.setObjectName("Options")

        self.tabwidget.addTab(self.options, "")

        help_button.clicked.connect(self.get_help)
        reload_button.clicked.connect(self.reload_via_options)
        save_button.clicked.connect(self.save_bidsmap_to_file)

    def update_list(self, output_bidsmap):
        """ """
        self.output_bidsmap = output_bidsmap  # output main window / output from edit window -> output main window

        num_files = 0
        for modality in bids.bidsmodalities + (bids.unknownmodality,):
            series_list = self.input_bidsmap[SOURCE][modality]
            if not series_list:
                continue
            for _ in series_list:
                num_files += 1

        self.table.setColumnCount(6)
        self.table.setRowCount(num_files)

        idx = 0
        for modality in bids.bidsmodalities + (bids.unknownmodality,):
            series_list = self.output_bidsmap[SOURCE][modality]
            if not series_list:
                continue
            for series in series_list:
                provenance = series['provenance']
                provenance_file = os.path.basename(provenance)
                run = series['bids'].get('run', '')

                subid = bids.replace_bidsvalue(self.output_bidsmap[SOURCE]['participant'], series['provenance'])
                sesid = bids.replace_bidsvalue(self.output_bidsmap[SOURCE]['session'], series['provenance'])
                bids_name = bids.get_bidsname(subid, sesid, modality, series, run)

                item_id = QTableWidgetItem(str(idx + 1))
                item_provenance_file = QTableWidgetItem(provenance_file)
                item_modality = QTableWidgetItem(modality)
                item_bids_name = QTableWidgetItem(bids_name)
                item_provenance = QTableWidgetItem(provenance)

                self.table.setItem(idx, 0, item_id)
                self.table.setItem(idx, 1, item_provenance_file)
                self.table.setItem(idx, 2, item_modality)
                self.table.setItem(idx, 3, item_bids_name)
                self.table.setItem(idx, 5, item_provenance)

                self.table.item(idx, 1).setToolTip(os.path.dirname(provenance))
                self.table.item(idx, 1).setStatusTip('Double-click to inspect the header information')
                self.table.item(idx, 0).setFlags(QtCore.Qt.NoItemFlags)
                self.table.item(idx, 2).setFlags(QtCore.Qt.ItemIsEnabled)
                self.table.item(idx, 3).setFlags(QtCore.Qt.ItemIsEnabled)

                self.button_select = QPushButton('Edit')
                if modality == bids.unknownmodality:
                    self.button_select.setStyleSheet('QPushButton {color: red;}')
                    if self.table.item(idx, 2):
                        self.table.item(idx, 2).setForeground(QtGui.QColor(255, 0, 0))
                else:
                    self.button_select.setStyleSheet('QPushButton {color: black;}')
                    if self.table.item(idx, 2):
                        self.table.item(idx, 2).setForeground(QtGui.QColor(0, 128, 0))
                self.button_select.clicked.connect(self.handle_button_clicked)
                self.button_select.setStatusTip('Click to edit the BIDS output name')
                self.table.setCellWidget(idx, 4, self.button_select)

                idx += 1

        # Done editing
        self.has_edit_dialog_open = False

        # Make sure we have the correct index mapping for the next edit
        self.index_mapping = get_index_mapping(self.output_bidsmap)

    def set_tab_bidsmap(self):
        """Set the SOURCE file sample listing tab.  """
        self.tab3 = QtWidgets.QWidget()
        self.tab3.layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.itemDoubleClicked.connect(self.inspect_dicomfile)
        self.table.setMouseTracking(True)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(True)

        self.update_list(self.output_bidsmap)

        self.table.setHorizontalHeaderLabels(['', 'DICOM input sample', 'BIDS modality', 'BIDS output name', 'Action'])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.table.setColumnHidden(5, True)

        vertical_header = self.table.verticalHeader()
        vertical_header.setVisible(False)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        help_button = QtWidgets.QPushButton()
        help_button.setText("Help")
        help_button.setStatusTip("Go to the online BIDScoin documentation")

        reload_button = QtWidgets.QPushButton()
        reload_button.setText("Reload")
        reload_button.setStatusTip("Reload the BIDSmap from disk")

        save_button = QtWidgets.QPushButton()
        save_button.setText("Save")
        save_button.setStatusTip("Save the BIDSmap to disk")

        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(help_button)
        hbox.addWidget(reload_button)
        hbox.addWidget(save_button)

        self.tab3.layout.addWidget(self.table)
        self.tab3.layout.addLayout(hbox)

        self.file_sample_listing = QtWidgets.QWidget()
        self.file_sample_listing.setLayout(self.tab3.layout)
        self.file_sample_listing.setObjectName("filelister")

        self.tabwidget.addTab(self.file_sample_listing, "")

        help_button.clicked.connect(self.get_help)
        reload_button.clicked.connect(self.reload)
        save_button.clicked.connect(self.save_bidsmap_to_file)

    def get_help(self):
        """Get online help. """
        webbrowser.open(MAIN_HELP_URL)

    def get_bids_help(self):
        """Get online help. """
        webbrowser.open(HELP_URL_DEFAULT)

    def reload_via_options(self):
        """Reset button: reload the original input BIDS map. From the options tab. """
        self.output_bidsmap, _ = bids.load_bidsmap(self.bidsmap_filename)
        self.setupUi(self.MainWindow,
                     self.bidsfolder,
                     self.sourcefolder,
                     self.bidsmap_filename,
                     self.input_bidsmap,
                     self.output_bidsmap,
                     self.template_bidsmap,
                     selected_tab_index=1)

    def reload(self):
        """Reset button: reload the original input BIDS map. """
        self.output_bidsmap, _ = bids.load_bidsmap(self.bidsmap_filename)
        self.setupUi(self.MainWindow,
                     self.bidsfolder,
                     self.sourcefolder,
                     self.bidsmap_filename,
                     self.input_bidsmap,
                     self.output_bidsmap,
                     self.template_bidsmap)

    def save_bidsmap_to_file(self):
        """Save the BIDSmap to file. """
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(
            self.tab3,
            "Save File",
            os.path.join(self.bidsfolder, 'code', 'bidsmap.yaml'),
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=options)
        if filename:
            bids.save_bidsmap(filename, self.output_bidsmap)

    def handle_button_clicked(self):
        button = QApplication.focusWidget()
        index = self.table.indexAt(button.pos())
        if index.isValid():
            idx = int(index.row())
            filename = self.table.item(idx, 1).text()
            modality = self.table.item(idx, 2).text()
            file_index = idx # i.e. the item in the file list
            # Obtain the source index of the series in the list of series in the bidsmap for this modality
            source_index = self.index_mapping[modality][file_index]
            self.show_edit(file_index, source_index, modality)

    def on_double_clicked(self, index):
        filename = self.model.fileInfo(index).absoluteFilePath()
        if bids.is_dicomfile(filename):
            dicomdict = pydicom.dcmread(filename, force=True)
            self.popup = InspectWindow(filename, dicomdict)
            self.popup.show()

    def show_about(self):
        """ """
        self.dialog_about = AboutDialog()
        self.dialog_about.show()

    def show_edit(self, file_index, source_index, modality):
        """Allow only one edit window to be open."""
        if not self.has_edit_dialog_open:
            self.dialog_edit = EditDialog(file_index, source_index, modality, self.output_bidsmap, self.template_bidsmap)
            self.dialog_edit.show()
            self.has_edit_dialog_open = True
            self.dialog_edit.got_sample.connect(self.update_list)

    def exit_application(self):
        """Handle exit. """
        self.MainWindow.close()


class AboutDialog(QDialog):

    def __init__(self):
        QDialog.__init__(self)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint)

        top_widget = QtWidgets.QWidget(self)
        top_layout = QtWidgets.QVBoxLayout(self)

        label = QLabel(top_widget)
        label.setText("BIDS editor")

        label_version = QLabel(top_widget)
        label_version.setText("version: " + bids.version())

        pushButton = QPushButton("OK")
        pushButton.setToolTip("Close dialog")
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(pushButton)

        top_layout.addWidget(label)
        top_layout.addWidget(label_version)
        top_layout.addStretch(1)
        top_layout.addLayout(hbox)

        pushButton.clicked.connect(self.close)

        top_widget.setLayout(top_layout)
        top_widget.resize(top_widget.sizeHint())

        self.setMinimumSize(ABOUT_WINDOW_WIDTH, ABOUT_WINDOW_HEIGHT)
        self.setMaximumSize(ABOUT_WINDOW_WIDTH, ABOUT_WINDOW_HEIGHT)


class TestDialog(QDialog):

    def __init__(self, tool: str, result: str):
        QDialog.__init__(self)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint)

        top_widget = QtWidgets.QWidget(self)
        top_layout = QtWidgets.QVBoxLayout(self)

        label_result = QLabel(top_widget)
        label_result.setText(f"Test {tool}: {result}")

        label_info = QLabel(top_widget)
        label_info.setText('See terminal output for more info')

        pushButton = QPushButton("OK")
        pushButton.setToolTip("Close dialog")
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(pushButton)

        top_layout.addWidget(label_result)
        top_layout.addWidget(label_info)
        top_layout.addStretch(1)
        top_layout.addLayout(hbox)

        pushButton.clicked.connect(self.close)

        top_widget.setLayout(top_layout)
        top_widget.resize(top_widget.sizeHint())

        self.setWindowTitle("Options")

        self.setMinimumSize(TEST_WINDOW_WIDTH, TEST_WINDOW_HEIGHT)
        self.setMaximumSize(TEST_WINDOW_WIDTH, TEST_WINDOW_HEIGHT)


class EditDialog(QDialog):

    got_sample = QtCore.pyqtSignal(dict)

    def __init__(self, file_index, index, modality, output_bidsmap, template_bidsmap):
        QDialog.__init__(self)

        self.source_bidsmap = output_bidsmap    # output from main window -> input edit window
        self.source_file_index = file_index
        self.source_index = index
        self.source_modality = modality
        self.source_series = self.source_bidsmap[SOURCE][modality][index]

        self.target_bidsmap = copy.deepcopy(output_bidsmap)
        self.target_file_index = file_index # Stays the same
        self.target_index = index # To be updated, depends on target modality
        self.target_modality = modality
        self.target_series = copy.deepcopy(self.source_series)
        self.target_suffix = ''

        self.template_bidsmap = template_bidsmap
        self.allowed_suffixes = get_allowed_suffixes(template_bidsmap)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)

        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.setWindowTitle("Edit")

        layout_all = QVBoxLayout(self)

        scrollarea = QtWidgets.QScrollArea(self)
        scrollarea.setWidgetResizable(True)

        top_widget = QtWidgets.QWidget()
        scrollarea.setWidget(top_widget)
        layout_scrollarea = QVBoxLayout(top_widget)

        self.set_provenance_section()
        self.set_dicom_attributes_section()
        self.set_dropdown_section()
        self.set_bids_values_section()
        self.set_bids_name_section()

        help_button = QtWidgets.QPushButton()
        help_button.setText("Help")
        cancel_button = QtWidgets.QPushButton()
        cancel_button.setText("Cancel")
        ok_button = QtWidgets.QPushButton()
        ok_button.setText("OK")

        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(help_button)
        hbox.addWidget(cancel_button)
        hbox.addWidget(ok_button)

        groupbox1 = QGroupBox(SOURCE)
        layout1 = QVBoxLayout(top_widget)
        layout1.addWidget(self.label_provenance)
        layout1.addWidget(self.view_provenance)
        layout1.addWidget(self.label_dicom)
        layout1.addWidget(self.view_dicom)
        layout1.addStretch(1)
        groupbox1.setLayout(layout1)

        groupbox2 = QGroupBox("BIDS")
        layout2 = QVBoxLayout(top_widget)
        layout2.addWidget(self.label_dropdown)
        layout2.addWidget(self.view_dropdown)
        layout2.addWidget(self.label_bids)
        layout2.addWidget(self.view_bids)
        layout2.addStretch(1)
        layout2.addWidget(self.label_bids_name)
        layout2.addWidget(self.view_bids_name)
        groupbox2.setLayout(layout2)

        layout_scrollarea.addWidget(groupbox1)
        layout_scrollarea.addWidget(groupbox2)
        layout_scrollarea.addStretch(1)
        layout_scrollarea.addLayout(hbox)

        self.view_provenance.cellDoubleClicked.connect(self.inspect_dicomfile)
        self.view_bids.cellChanged.connect(self.cell_was_changed)

        help_button.clicked.connect(self.get_help)
        cancel_button.clicked.connect(self.reject)
        ok_button.clicked.connect(self.update_series)

        layout_all.addWidget(scrollarea)

        self.setMinimumWidth(EDIT_WINDOW_WIDTH)
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

    def get_help(self):
        """Open web page for help. """
        help_url = HELP_URLS.get(self.target_modality, HELP_URL_DEFAULT)
        webbrowser.open(help_url)

    def closeEvent(self, event):
        """Make sure we set has_edit_dialog_open to false in main window. """
        self.got_sample.emit(self.target_bidsmap)
        self.close()

    def reject(self):
        """Make sure we set has_edit_dialog_open to false in main window. """
        self.got_sample.emit(self.source_bidsmap)
        self.close()

    def update_series(self):
        """Save the changes. """
        self.target_bidsmap = update_bidsmap(self.source_bidsmap,
                                             self.target_bidsmap,
                                             self.source_modality,
                                             self.source_index,
                                             self.target_modality,
                                             self.target_series)

        self.got_sample.emit(self.target_bidsmap)
        self.close()

    def inspect_dicomfile(self, row=None, column=None):
        """When double clicked, show popup window. """
        if row == 1 and column == 1:
            filename = self.source_series['provenance']
            if bids.is_dicomfile(filename):
                dicomdict = pydicom.dcmread(filename, force=True)
                self.popup = InspectWindow(filename, dicomdict)
                self.popup.show()

    def cell_was_changed(self, row, column):
        """BIDS attribute value has been changed. """
        if column == 1:
            key = self.view_bids.item(row, 0).text()
            value = self.view_bids.item(row, 1).text()

            # Only if cell was actually clicked, update (i.e. not when BIDS modality changes)
            if key != '':
                # Validate user input against BIDS or replace the (dynamic) bids-value if it is a series attribute
                value = bids.replace_bidsvalue(value, self.target_series['provenance'])

                self.view_bids.item(row, 1).setText(value)
                self.target_series['bids'][key] = value

                self.update_bidsname()

    def set_cell(self, value, is_editable=False):
        item = QTableWidgetItem()
        item.setText(value)
        if is_editable:
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable)
        else:
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            item.setForeground(QtGui.QColor(128, 128, 128))
        return item

    def get_table(self, data, num_rows=1):
        """Return a table widget from the data. """
        table = QTableWidget()

        table.setRowCount(num_rows)
        table.setColumnCount(2) # Always two columns (i.e. key, value)
        row_height = 24

        for i, row in enumerate(data):
            table.setRowHeight(i, row_height)
            key = row[0]["value"]
            if self.target_modality != bids.unknownmodality and key == 'suffix':
                labels = self.allowed_suffixes[self.target_modality]
                self.suffix_dropdown = QComboBox(self)
                self.suffix_dropdown.addItems(labels)
                self.suffix_dropdown.setCurrentIndex(self.suffix_dropdown.findText(self.target_suffix))
                self.suffix_dropdown.currentIndexChanged.connect(self.selection_suffix_dropdown_change)
                item = self.set_cell("suffix", is_editable=False)
                table.setItem(i, 0, QTableWidgetItem(item))
                table.setCellWidget(i, 1, self.suffix_dropdown)
                continue
            for j, element in enumerate(row):
                value = element.get("value", "")
                if value == "None":
                    value = ""
                is_editable = element.get("is_editable", False)
                item = self.set_cell(value, is_editable=is_editable)
                table.setItem(i, j, QTableWidgetItem(item))

        horizontal_header = table.horizontalHeader()
        horizontal_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        horizontal_header.setVisible(False)

        vertical_header = table.verticalHeader()
        vertical_header.setVisible(False)

        table.setAlternatingRowColors(False)
        table.setShowGrid(False)

        extra_space = 6
        table_height = num_rows * (row_height + extra_space) + extra_space
        table.setMinimumHeight(table_height)
        table.setMaximumHeight(table_height)

        return table

    def set_provenance_section(self):
        """Set provenance section. """
        provenance = self.source_series['provenance']
        provenance_file = os.path.basename(provenance)
        provenance_path = os.path.dirname(provenance)

        data = [
            [
                {
                    "value": "path",
                    "is_editable": False
                },
                {
                    "value": provenance_path,
                    "is_editable": False
                },
            ],
            [
                {
                    "value": "filename",
                    "is_editable": False
                },
                {
                    "value": provenance_file,
                    "is_editable": True
                },
            ]
        ]

        self.label_provenance = QLabel()
        self.label_provenance.setText("Provenance")

        self.view_provenance = self.get_table(data, num_rows=MAX_NUM_PROVENANCE_ATTRIBUTES)

        self.view_provenance.doubleClicked.connect(self.inspect_dicomfile)

    def set_dicom_attributes_section(self):
        """Set SOURCE attributes section. """
        dicom_attributes = self.source_series['attributes']

        data = []
        for key in dicom_attributes:
            data.append([
                {
                    "value": key,
                    "is_editable": False
                },
                {
                    "value": str(dicom_attributes[key]),
                    "is_editable": True
                }
            ])

        self.label_dicom = QLabel()
        self.label_dicom.setText("Attributes")

        self.view_dicom = self.get_table(data, num_rows=len(data))

    def set_dropdown_section(self):
        """Dropdown select modality list section. """
        self.label_dropdown = QLabel()
        self.label_dropdown.setText("Modality")

        self.view_dropdown = QComboBox()
        self.view_dropdown.addItems(bids.bidsmodalities + (bids.unknownmodality,))
        self.view_dropdown.setCurrentIndex(self.view_dropdown.findText(self.target_modality))

        self.view_dropdown.currentIndexChanged.connect(self.selection_dropdown_change)

    def get_bids_values_data(self):
        """# Given the input BIDS attributes, derive the target BIDS attributes. """
        target_bids_attributes = get_bids_attributes(self.template_bidsmap,
                                                     self.allowed_suffixes,
                                                     self.target_modality,
                                                     self.source_series)
        if target_bids_attributes is not None:
            bids_values = target_bids_attributes
        else:
            bids_values = {}

        data = []
        for key, value in bids_values.items():
            if self.target_modality in bids.bidsmodalities and key == 'suffix':
                value = self.target_suffix
                data.append([
                    {
                        "value": str(key),
                        "is_editable": False
                    },
                    {
                        "value": str(value),
                        "is_editable": False
                    }
                ])
            else:
                key_show = str(key)
                key_show = key_show.split('_')[0]
                data.append([
                    {
                        "value": key_show,
                        "is_editable": False
                    },
                    {
                        "value": str(value),
                        "is_editable": True
                    }
                ])

        return bids_values, data

    def set_bids_values_section(self):
        """Set editable BIDS values section. """
        if self.target_modality == bids.unknownmodality:
            # Free field
            self.target_suffix = ''
        else:
            # Fixed list of options
            if not self.allowed_suffixes[self.target_modality]:
                raise Exception(f'allowed suffixes empty for modality {self.target_modality}')
            self.target_suffix = self.source_series['bids']['suffix']

        bids_values, data = self.get_bids_values_data()
        self.target_series['bids'] = bids_values

        self.label_bids = QLabel()
        self.label_bids.setText("Labels")

        self.view_bids = self.get_table(data, num_rows=MAX_NUM_BIDS_ATTRIBUTES)

    def set_bids_name_section(self):
        """Set non-editable BIDS output name section. """
        self.label_bids_name = QLabel()
        self.label_bids_name.setText("Output name")

        self.view_bids_name = QTextEdit()
        self.view_bids_name.setReadOnly(True)

        height = 24
        extra_space = 6
        self.view_bids_name.setFixedHeight(height + extra_space)

        self.update_bidsname()

    def selection_dropdown_change(self, i):
        """Update the BIDS values and BIDS output name section when the dropdown selection has been taking place. """
        self.target_modality = self.view_dropdown.currentText()

        if self.target_modality == bids.unknownmodality:
            # Free field
            self.target_suffix = ''
        else:
            # Fixed list of options
            if not self.allowed_suffixes[self.target_modality]:
                raise Exception(f'allowed suffixes empty for modality {self.target_modality}')
            self.target_suffix = self.allowed_suffixes[self.target_modality][0]

        # Given the input BIDS attributes, derive the target BIDS attributes (i.e map them to the target attributes)
        bids_values, data = self.get_bids_values_data()

        # Update the BIDS values
        table = self.view_bids

        for i, row in enumerate(data):
            key = row[0]["value"]
            if self.target_modality != bids.unknownmodality and key == 'suffix':
                labels = self.allowed_suffixes[self.target_modality]
                self.suffix_dropdown = QComboBox()
                self.suffix_dropdown.addItems(labels)
                self.suffix_dropdown.setCurrentIndex(self.suffix_dropdown.findText(self.target_suffix))
                self.suffix_dropdown.currentIndexChanged.connect(self.selection_suffix_dropdown_change)
                item = self.set_cell("suffix", is_editable=False)
                table.setItem(i, 0, QTableWidgetItem(item))
                table.setCellWidget(i, 1, self.suffix_dropdown)
                continue
            for j, element in enumerate(row):
                value = element.get("value", "")
                if value == "None":
                    value = ""
                is_editable = element.get("is_editable", False)
                table.removeCellWidget(i, j)
                item = self.set_cell(value, is_editable=is_editable)
                table.setItem(i, j, QTableWidgetItem(item))
        for i in range(len(data), MAX_NUM_BIDS_ATTRIBUTES):
            for j, element in enumerate(row):
                table.removeCellWidget(i, j)
                item = self.set_cell('', is_editable=False)
                table.setItem(i, j, QTableWidgetItem(item))

        self.view_bids = table

        if self.target_modality != bids.unknownmodality:
            bids_values['suffix'] = self.target_suffix

        # Update the BIDS output name
        self.target_series['bids'] = bids_values
        self.update_bidsname()

    def selection_suffix_dropdown_change(self, i):
        """Update the BIDS values and BIDS output name section when the dropdown selection has been taking place. """
        self.target_suffix = self.suffix_dropdown.currentText()

        bids_values, data = self.get_bids_values_data()
        bids_values['suffix'] = self.target_suffix

        # Update the BIDS output name
        self.target_series['bids'] = bids_values
        self.update_bidsname()

    def update_bidsname(self):
        subid = bids.replace_bidsvalue(self.target_bidsmap[SOURCE]['participant'], self.target_series['provenance'])
        sesid = bids.replace_bidsvalue(self.target_bidsmap[SOURCE]['session'], self.target_series['provenance'])
        run = self.target_series['bids'].get('run', '')
        bids_name = bids.get_bidsname(subid, sesid, self.target_modality, self.target_series, run)
        html_bids_name = get_html_bidsname(bids_name)

        self.view_bids_name.clear()
        self.view_bids_name.textCursor().insertHtml('<font color="#808080">%s</font>' % html_bids_name)


def bidseditor(bidsfolder: str, sourcefolder: str='', bidsmapfile: str='', templatefile: str=''):
    """

    :param bidsfolder:
    :param bidsmapfile:
    :param templatefile:
    :return:
    """

    # Start logging
    bids.setup_logging(os.path.join(bidsfolder, 'code', 'bidseditor.log'))
    LOGGER.info('------------ START BIDSeditor ------------')

    # Obtain the initial bidsmap info
    template_bidsmap, _        = bids.load_bidsmap(templatefile, os.path.join(bidsfolder,'code'))
    input_bidsmap, bidsmapfile = bids.load_bidsmap(bidsmapfile,  os.path.join(bidsfolder,'code'))
    output_bidsmap             = copy.deepcopy(input_bidsmap)

    # Parse the sourcefolder from the bidsmap provenance info
    if not sourcefolder:

        # Loop through all bidsmodalities and series until we find provenance info
        for modality in bids.bidsmodalities + (bids.unknownmodality,):
            if input_bidsmap[SOURCE][modality] is None:
                continue

            for series in input_bidsmap[SOURCE][modality]:
                if series['provenance']:
                    sourcefolder = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(series['provenance']))))
                    LOGGER.info(f'Source: {sourcefolder}')
                    break

            if sourcefolder:
                break

    # Start the Qt-application
    app = QApplication(sys.argv)
    app.setApplicationName("BIDS editor")
    mainwin = MainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(mainwin, bidsfolder, sourcefolder, bidsmapfile, input_bidsmap, output_bidsmap, template_bidsmap)
    mainwin.show()
    sys.exit(app.exec_())


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
                                           empty it is not used to identify the series. Example: SequenceName: [epfid2d1rs, '*fm2d2r']

                                         Dynamic BIDS labels
                                           The BIDS labels can be static, in which case the label is just a normal string, or dynamic,
                                           when the string is enclosed with pointy brackets like `<attribute name>` or
                                           `<<argument1><argument2>>`. In case of single pointy brackets the label will be replaced
                                           during bidsmapper, bidseditor and bidscoiner runtime by the value of the (DICOM) attribute
                                           with that name. In case of double pointy brackets, the label will be updated for each
                                           subject/session during bidscoiner runtime. For instance, then the `run` label `<<1>>` in
                                           the bids name will be replaced with `1` or increased to `2` if a file with runindex `1`
                                           already exists in that directory.

                                         Field maps: IntendedFor
                                           You can use the `IntendedFor` field to indicate for which runs (DICOM series) a fieldmap
                                           was intended. The dynamic label of the `IntendedFor` field can be a list of string patterns
                                           that is used to include all runs in a session that have that string pattern in their BIDS
                                           file name. Example: use `<<task>>` to include all functional runs or `<<Stop*Go><Reward>>`
                                           to include "Stop1Go"-, "Stop2Go"- and "Reward"-runs.

                                         Manual editing / inspection of the bidsmap
                                           You can of course also directly edit or inspect the `bidsmap.yaml` file yourself with any
                                           text editor. For instance to change the `Options` to your needs or to add a dynamic
                                           `participant` value like `<<PatientID>>`. See ./docs/bidsmap.md for more information."""))

    parser.add_argument('bidsfolder',           help='The destination folder with the (future) bids data')
    parser.add_argument('-s','--sourcefolder',  help='The source folder containing the raw data. If empty, it is derived from the bidsmap provenance information')
    parser.add_argument('-b','--bidsmap',       help='The bidsmap YAML-file with the study heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-t','--template',      help='The bidsmap template with the default heuristics (this could be provided by your institute). If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/. Default: bidsmap_template.yaml', default='bidsmap_template.yaml')
    args = parser.parse_args()

    bidseditor(bidsfolder   = args.bidsfolder,
               sourcefolder = args.sourcefolder,
               bidsmapfile  = args.bidsmap,
               templatefile = args.template)
