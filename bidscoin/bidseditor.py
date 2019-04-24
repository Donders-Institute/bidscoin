#!/usr/bin/env python
"""
Allows updating the BIDSmap via a GUI.
The user needs to fill in the BIDS values for files that are unidentified.
"""

import os
import sys
from collections import deque
import argparse
import textwrap
import logging
import copy

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileSystemModel,
                             QTreeView, QVBoxLayout, QLabel, QDialog,
                             QTableWidget, QTableWidgetItem, QGroupBox,
                             QAbstractItemView, QPushButton, QComboBox, QTextEdit)

import bids
import bidsutils


logger = logging.getLogger('bidscoin')

MAIN_WINDOW_WIDTH = 1280
MAIN_WINDOW_HEIGHT = 800

LOG_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidseditor.log")

ICON_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "icons", "brain.ico")
TEMPLATE_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "heuristics", "bidsmap_template.yaml")

DEFAULT_RAW_FOLDER = os.path.join(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_INPUT_BIDSMAP_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
DEFAULT_OUTPUT_BIDSMAP_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_output.yaml")


class Ui_MainWindow(object):

    def setupUi(self, MainWindow, rawfolder, bidsmap_filename, output_bidsmap_filename, bidsmap, output_bidsmap):

        self.MainWindow = MainWindow
        self.bidsmap_filename = bidsmap_filename
        self.bidsmap = bidsmap
        self.output_bidsmap_filename = output_bidsmap_filename
        self.output_bidsmap = output_bidsmap

        self.MainWindow.setObjectName("MainWindow")
        self.MainWindow.resize(MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.MainWindow.setWindowIcon(icon)

        self.centralwidget = QtWidgets.QWidget(self.MainWindow)
        self.centralwidget.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        self.centralwidget.setObjectName("centralwidget")

        self.tabwidget = QtWidgets.QTabWidget(self.centralwidget)
        self.tabwidget.setGeometry(QtCore.QRect(0, 0, 1280, 760))
        self.tabwidget.setTabPosition(QtWidgets.QTabWidget.North)
        self.tabwidget.setTabShape(QtWidgets.QTabWidget.Rounded)
        self.tabwidget.setObjectName("tabwidget")
        self.set_tab_file_browser(rawfolder)
        self.set_tab_file_sample_listing()
        self.tabwidget.setTabText(0, "File browser")
        self.tabwidget.setTabText(1, "File sample listing")
        self.tabwidget.setCurrentIndex(1)

        self.set_menu_and_status_bar()

    def set_tab_file_browser(self, rawfolder):
        """Set the raw data folder inspector tab. """
        self.tab1 = QtWidgets.QWidget()
        self.tab1.layout = QVBoxLayout(self.centralwidget)
        self.label = QLabel()
        self.label.setText("Inspect raw data folder: {}".format(rawfolder))
        self.model = QFileSystemModel()
        self.model.setRootPath('')
        self.model.setFilter(QtCore.QDir.NoDotAndDotDot | QtCore.QDir.AllDirs | QtCore.QDir.Files)
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setAnimated(False)
        self.tree.setIndentation(20)
        self.tree.setSortingEnabled(True)
        self.tree.setRootIndex(self.model.index(rawfolder))
        self.tree.clicked.connect(self.on_clicked)
        self.tab1.layout.addWidget(self.label)
        self.tab1.layout.addWidget(self.tree)
        self.tree.header().resizeSection(0, 800)

        self.file_browser = QtWidgets.QWidget()
        self.file_browser.setLayout(self.tab1.layout)
        self.file_browser.setObjectName("filebrowser")
        self.tabwidget.addTab(self.file_browser, "")

    def set_tab_file_sample_listing(self):
        """Set the DICOM file sample listing tab.  """
        list_summary = bidsutils.get_list_summary(self.output_bidsmap)

        self.tab2 = QtWidgets.QWidget()
        self.tab2.layout = QVBoxLayout(self.centralwidget)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setRowCount(len(list_summary) + 1)

        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(True)

        for i, element in enumerate(list_summary):
            provenance_file = element['provenance_file']
            modality = element['modality']
            bids_name = element['bids_name']

            item_id = QTableWidgetItem(str(i + 1))
            item_provenance_file = QTableWidgetItem(provenance_file)
            item_modality = QTableWidgetItem(modality)
            item_bids_name = QTableWidgetItem(bids_name)

            self.table.setItem(i, 0, item_id)
            self.table.setItem(i, 1, item_provenance_file)
            self.table.setItem(i, 2, item_modality)
            self.table.setItem(i, 3, item_bids_name)

            text = 'Edit'
            self.button_select = QPushButton(text)
            if modality == 'extra_data':
                self.button_select.setStyleSheet('QPushButton {color: red;}')
                self.table.item(i, 1).setForeground(QtGui.QColor(255, 0, 0))
            else:
                self.button_select.setStyleSheet('QPushButton {color: green;}')
            self.button_select.clicked.connect(self.handle_button_clicked)
            self.table.setCellWidget(i, 4, self.button_select)

        self.save_button = QtWidgets.QPushButton()
        self.save_button.setText("Save")
        self.save_button.setStyleSheet('QPushButton {color: blue;}')
        self.table.setCellWidget(len(list_summary), 4, self.save_button)

        self.table.setHorizontalHeaderLabels(['', 'DICOM file sample', 'Modality', 'BIDS name', 'Action'])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)

        vertical_header = self.table.verticalHeader()
        vertical_header.setVisible(False)

        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.tab2.layout.addWidget(self.table)
        self.file_sample_listing = QtWidgets.QWidget()
        self.file_sample_listing.setLayout(self.tab2.layout)
        self.file_sample_listing.setObjectName("filelister")

        self.tabwidget.addTab(self.file_sample_listing, "")

        self.save_button.clicked.connect(self.save_bidsmap_to_file)

    def set_menu_and_status_bar(self):
        """Set the menu. """
        self.MainWindow.setCentralWidget(self.centralwidget)

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

        self.actionAbout = QtWidgets.QAction(self.MainWindow)
        self.actionAbout.triggered.connect(self.show_about)

        self.actionEdit = QtWidgets.QAction(self.MainWindow)

        self.menuFile.addAction(self.actionExit)
        self.menuHelp.addAction(self.actionAbout)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.menuFile.setTitle("File")
        self.menuHelp.setTitle("Help")
        self.statusbar.setStatusTip("Statusbar")
        self.actionExit.setText("Exit")
        self.actionExit.setStatusTip("Click to exit the application")
        self.actionExit.setShortcut("Ctrl+X")
        self.actionAbout.setText("About")
        self.actionAbout.setStatusTip("Click to get more information about the application")

    def save_bidsmap_to_file(self):
        """Save the BIDSmap to file. """
        bidsutils.save_bidsmap(self.output_bidsmap_filename, self.output_bidsmap)
        logger.info('Saved BIDS map to file {}'.format(self.output_bidsmap_filename))

    def handle_button_clicked(self):
        button = QApplication.focusWidget()
        index = self.table.indexAt(button.pos())
        if index.isValid():
            i = int(index.row())
            modality = self.table.item(i, 2).text()
            self.show_edit(i, modality)

    def on_clicked(self, index):
        # print(self.model.fileInfo(index).absoluteFilePath())
        pass

    def show_about(self):
        """ """
        self.dialog_about = AboutDialog()
        self.dialog_about.show()

    def show_edit(self, i, modality):
        """ """
        self.dialog_edit = EditDialog(i, modality, self.output_bidsmap)
        self.dialog_edit.show()

    def exit_application(self):
        """ """
        logger.info('Exit application')
        self.MainWindow.close()


class AboutDialog(QDialog):

    def __init__(self):
        QDialog.__init__(self)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint)
        self.resize(200, 100)

        label = QLabel()
        label.setText("BIDS editor")

        label_version = QLabel()
        label_version.setText("v" + str(bids.version()))

        self.pushButton = QPushButton("OK")
        self.pushButton.setToolTip("Close dialog")
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(label_version)
        layout.addWidget(self.pushButton)

        self.pushButton.clicked.connect(self.close)


class EditDialog(QDialog):

    def __init__(self, i, modality, output_bidsmap):
        QDialog.__init__(self)

        self.source_bidsmap = copy.deepcopy(output_bidsmap)
        self.source_index = i
        self.source_modality = modality
        self.source_sample = bidsutils.read_sample(output_bidsmap, modality, i)

        self.target_bidsmap = copy.deepcopy(output_bidsmap)
        self.target_modality = modality
        self.target_sample = copy.deepcopy(self.source_sample)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)

        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint)
        self.setWindowTitle("Edit")
        self.resize(1024, 800)

        self.set_provenance_section()
        self.set_dicom_attributes_section()
        self.set_dropdown_section()
        self.set_bids_values_section()
        self.set_bids_name_section()

        self.ok_button = QtWidgets.QPushButton()
        self.ok_button.setText("OK")

        groupbox1 = QGroupBox("DICOM")
        layout1 = QVBoxLayout()
        layout1.addWidget(self.label_provenance)
        layout1.addWidget(self.view_provenance)
        layout1.addWidget(self.label_dicom)
        layout1.addWidget(self.view_dicom)
        layout1.addStretch(1)
        groupbox1.setLayout(layout1)

        groupbox2 = QGroupBox("BIDS")
        layout2 = QVBoxLayout()
        layout2.addWidget(self.label_dropdown)
        layout2.addWidget(self.view_dropdown)
        layout2.addWidget(self.label_bids)
        layout2.addWidget(self.view_bids)
        layout2.addWidget(self.label_bids_name)
        layout2.addWidget(self.view_bids_name)
        layout2.addStretch(1)
        layout2.addWidget(self.ok_button)
        groupbox2.setLayout(layout2)

        layout = QVBoxLayout()
        layout.addWidget(groupbox1)
        layout.addWidget(groupbox2)
        self.setLayout(layout)

        self.view_bids.cellChanged.connect(self.cell_was_clicked)
        self.ok_button.clicked.connect(self.update_sample)

    def update_sample(self):
        """Save the changes. """
        self.target_bidsmap = bidsutils.update_bidsmap(self.source_bidsmap,
                                                       self.source_modality,
                                                       self.source_index,
                                                       self.target_modality,
                                                       self.target_sample)
        self.close()

    def cell_was_clicked(self, row, column):
        """BIDS attribute value has been changed. """
        if column == 1:
            item_key = self.view_bids.item(row, 0)
            item_value = self.view_bids.item(row, 1)
            key = item_key.text()
            value = item_value.text()

            self.target_sample['bids'][key] = value

            bids_values = self.target_sample['bids']
            subid = '*'
            sesid = '*'
            run = bids_values.get('run_index', '*')
            bids_name_array = bidsutils.get_bids_name_array(subid, sesid, self.target_modality, bids_values, run)
            bids_name = bidsutils.get_bids_name(bids_name_array)
            self.bids_name = bids_name

            self.view_bids_name.clear()
            self.view_bids_name.textCursor().insertText(self.bids_name)

    def set_cell(self, value, is_editable=False):
        item = QTableWidgetItem()
        item.setText(value)
        if is_editable:
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable)
        else:
            item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        return item

    def get_table(self, data):
        """Return a table widgte from the data. """
        table = QTableWidget()

        num_rows = len(data)
        table.setRowCount(num_rows)
        table.setColumnCount(2) # Always two columns (i.e. key, value)
        row_height = 24

        for i, row in enumerate(data):
            table.setRowHeight(i, row_height)
            for j, element in enumerate(row):
                value = element.get("value", "")
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
        table_height = num_rows * (row_height + extra_space) + 2 * table.frameWidth()
        table.setMinimumHeight(table_height)
        table.setMaximumHeight(table_height)

        return table

    def set_provenance_section(self):
        """Set provenance section. """
        provenance = self.source_sample.get('provenance', None)
        if provenance is not None:
            provenance_file = os.path.basename(provenance)
            provenance_path = os.path.dirname(provenance)
        else:
            provenance_file = ''
            provenance_path = ''

        data = [
            [
                {
                    "value": "filename",
                    "is_editable": False
                },
                {
                    "value": provenance_file,
                    "is_editable": False
                },
            ],
            [
                {
                    "value": "path",
                    "is_editable": False
                },
                {
                    "value": provenance_path,
                    "is_editable": False
                },
            ]
        ]

        self.label_provenance = QLabel()
        self.label_provenance.setText("Provenance")

        self.view_provenance = self.get_table(data)

    def set_dicom_attributes_section(self):
        """Set non-editable DICOM attributes section. """
        dicom_attributes = self.source_sample.get('attributes', None)
        if dicom_attributes is not None:
            dicom_values = dicom_attributes
        else:
            dicom_values = yaml.comments.CommentedMap()

        data = []
        for key, value in dicom_values.items():
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

        self.label_dicom = QLabel()
        self.label_dicom.setText("DICOM attributes")

        self.view_dicom = self.get_table(data)

    def set_dropdown_section(self):
        """Dropdown select modality list section. """
        self.label_dropdown = QLabel()
        self.label_dropdown.setText("Modality")

        self.view_dropdown = QComboBox()
        self.view_dropdown.addItems(bidsutils.MODALITIES)
        self.view_dropdown.setCurrentIndex(self.view_dropdown.findText(self.target_modality))

        self.view_dropdown.currentIndexChanged.connect(self.selection_dropdown_change)

    def set_bids_values_section(self):
        """Set editable BIDS values section. """
        bids_attributes = self.target_sample.get('bids', None)
        if bids_attributes is not None:
            bids_values = bids_attributes
        else:
            bids_values = yaml.comments.CommentedMap()

        data = []
        for key, value in bids_values.items():
            data.append([
                {
                    "value": str(key),
                    "is_editable": False
                },
                {
                    "value": str(value),
                    "is_editable": True
                }
            ])

        self.label_bids = QLabel()
        self.label_bids.setText("BIDS values")

        self.view_bids = self.get_table(data)

    def set_bids_name_section(self):
        """Set non-editable BIDS name section. """
        bids_attributes = self.target_sample.get('bids', None)
        if bids_attributes is not None:
            bids_values = bids_attributes
        else:
            bids_values = yaml.comments.CommentedMap()

        subid = '*'
        sesid = '*'
        run = bids_values.get('run_index', '*')
        bids_name_array = bidsutils.get_bids_name_array(subid, sesid, self.target_modality, bids_values, run)
        bids_name = bidsutils.get_bids_name(bids_name_array)

        self.bids_name = bids_name

        self.label_bids_name = QLabel()
        self.label_bids_name.setText("BIDS name")

        self.view_bids_name = QTextEdit()
        self.view_bids_name.setReadOnly(True)
        self.view_bids_name.textCursor().insertText(self.bids_name)
        height = 24
        extra_space = 6
        self.view_bids_name.setFixedHeight(height + extra_space)

    def selection_dropdown_change(self, i):
        """Update the BIDS values and BIDS name section when the dropdown selection has been taking place. """
        self.target_modality = self.view_dropdown.currentText()

        bids_attributes = self.target_sample.get('bids', None)
        if bids_attributes is not None:
            bids_values = bids_attributes
        else:
            bids_values = yaml.comments.CommentedMap()

        # Update the BIDS values
        data = []
        for key, value in bids_values.items():
            data.append([
                {
                    "value": str(key),
                    "is_editable": False
                },
                {
                    "value": str(value),
                    "is_editable": True
                }
            ])

        self.view_bids = self.get_table(data)

        # Update the BIDS name
        subid = '*'
        sesid = '*'
        run = bids_values.get('run_index', '*')
        bids_name_array = bidsutils.get_bids_name_array(subid, sesid, self.target_modality, bids_values, run)
        bids_name = bidsutils.get_bids_name(bids_name_array)

        self.view_bids_name.clear()
        self.view_bids_name.textCursor().insertText(bids_name)


def setup_logging(log_filename):
    """Setup the logging """
    # Set the format
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s %(message)s',
                                  '%Y-%m-%d %H:%M:%S')

    # Set the streamhandler
    streamhandler = logging.StreamHandler()
    streamhandler.setLevel(logging.INFO)
    streamhandler.setFormatter(formatter)

    # Set the filehandler
    filehandler = logging.FileHandler(log_filename)
    filehandler.setLevel(logging.INFO)
    filehandler.setFormatter(formatter)

    # Add the streamhandler and filehandler to the logger
    logger.addHandler(streamhandler)
    logger.addHandler(filehandler)


if __name__ == "__main__":

    setup_logging(LOG_FILE)
    logger.info('Started BIDS editor')

    # Parse the input arguments and run bidseditor
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidseditor.py /raw/data/folder /input/bidsmap.yaml /output/bidsmap.yaml\n')
    parser.add_argument('rawfolder', help='The root folder of the directory tree containing the raw files', nargs='?', default=DEFAULT_RAW_FOLDER)
    parser.add_argument('inputbidsmap', help='The input BIDS map YAML-file', nargs='?', default=DEFAULT_INPUT_BIDSMAP_FILENAME)
    parser.add_argument('outputbidsmap', help='The output BIDS map YAML-file', nargs='?', default=DEFAULT_OUTPUT_BIDSMAP_FILENAME)
    args = parser.parse_args()

    # Validate the arguments
    if not os.path.exists(args.rawfolder):
        raise Exception("Raw folder not found: {}".format(args.rawfolder))

    # Obtain the initial bidsmap info
    input_bidsmap_yaml = bidsutils.read_yaml_as_string(args.inputbidsmap)
    input_bidsmap = bidsutils.read_bidsmap(input_bidsmap_yaml)

    output_bidsmap = copy.deepcopy(input_bidsmap)

    logger.info('Input raw data folder: {}'.format(args.rawfolder))
    logger.info('Input BIDS map {}'.format(args.inputbidsmap))
    logger.info('Output BIDS map {}'.format(args.outputbidsmap))

    # Start the application
    app = QApplication(sys.argv)
    app.setApplicationName("BIDS editor")
    mainwin = QMainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(mainwin, args.rawfolder, args.inputbidsmap, args.outputbidsmap, input_bidsmap, output_bidsmap)
    mainwin.show()
    sys.exit(app.exec_())
