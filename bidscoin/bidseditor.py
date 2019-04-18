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


LOG_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidseditor.log")

ICON_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "icons", "brain.ico")
TEMPLATE_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "heuristics", "bidsmap_template.yaml")

DEFAULT_RAW_FOLDER = "C:"
DEFAULT_INPUT_BIDSMAP_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
DEFAULT_OUTPUT_BIDSMAP_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_output.yaml")


class Ui_MainWindow(object):

    def setupUi(self, MainWindow, rawfolder, inputbidsmap, outputbidsmap, bidsmap_yaml, bidsmap_info, template_info, output_bidsmap):

        self.MainWindow = MainWindow
        self.bidsmap_info = bidsmap_info
        self.template_info = template_info
        self.outputbidsmap = outputbidsmap
        self.output_bidsmap = output_bidsmap
        self.list_dicom_files, self.list_bids_names = bidsutils.get_list_files(bidsmap_info)

        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1280, 800)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        MainWindow.setWindowIcon(icon)

        self.centralwidget = QtWidgets.QWidget(MainWindow)
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

        self.set_menu_and_status_bar(MainWindow)

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
        self.tab2 = QtWidgets.QWidget()
        self.tab2.layout = QVBoxLayout(self.centralwidget)
        self.save_button = QtWidgets.QPushButton()
        self.save_button.setGeometry(QtCore.QRect(20, 20, 93, 28))
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setRowCount(len(self.list_dicom_files))
        self.table.setAlternatingRowColors(True)

        for index in range(len(self.list_dicom_files)):
            item1 = QTableWidgetItem(self.list_dicom_files[index])
            self.table.setItem(index, 0, item1)
            item3 = QTableWidgetItem(self.list_bids_names[index])
            self.table.setItem(index, 2, item3)
            text = 'Edit'
            self.button_select = QPushButton(text)
            if self.list_bids_names[index] == '':
                item2 = QTableWidgetItem("extra_data")
                self.table.setItem(index, 1, item2)
                self.button_select.setStyleSheet('QPushButton {color: red;}')
                self.table.item(index, 0).setForeground(QtGui.QColor(255,0,0))
            else:
                item2 = QTableWidgetItem("anat") # TODO derive modality
                self.table.setItem(index, 1, item2)
                self.button_select.setStyleSheet('QPushButton {color: green;}')
            self.button_select.clicked.connect(self.handle_button_clicked)
            self.table.setCellWidget(index, 3, self.button_select)
        self.table.setHorizontalHeaderLabels(['DICOM file sample', 'Modality', 'BIDS name', 'Action'])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.tab2.layout.addWidget(self.save_button)
        self.tab2.layout.addWidget(self.table)
        self.file_sample_listing = QtWidgets.QWidget()
        self.file_sample_listing.setLayout(self.tab2.layout)
        self.file_sample_listing.setObjectName("filelister")
        self.save_button.setText("Save")
        self.tabwidget.addTab(self.file_sample_listing, "")

        self.save_button.clicked.connect(self.save_bidsmap_to_file)

    def set_menu_and_status_bar(self, MainWindow):
        """Set the menu. """
        MainWindow.setCentralWidget(self.centralwidget)

        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 997, 26))
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuHelp = QtWidgets.QMenu(self.menubar)

        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)

        # Set the statusbar
        self.statusbar.setToolTip("")
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        # Define the menu actions
        self.actionNew = QtWidgets.QAction(MainWindow)

        self.actionExit = QtWidgets.QAction(MainWindow)
        self.actionExit.triggered.connect(self.exit_application)

        self.actionAbout = QtWidgets.QAction(MainWindow)
        self.actionAbout.triggered.connect(self.show_about)

        self.actionEdit = QtWidgets.QAction(MainWindow)

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
        bidsutils.save_bidsmap(self.outputbidsmap, self.output_bidsmap)
        logger.info('Saved BIDS map to file {}'.format(self.outputbidsmap))

    def handle_button_clicked(self):
        button = QApplication.focusWidget()
        index = self.table.indexAt(button.pos())
        if index.isValid():
            i = int(index.row())
            self.show_edit(i)

    def on_clicked(self, index):
        # print(self.model.fileInfo(index).absoluteFilePath())
        pass

    def show_about(self):
        """ """
        self.dlg = AboutDialog()
        self.dlg.show()

    def show_edit(self, i):
        """ """
        info = self.bidsmap_info[i]
        self.dlg2 = EditDialog(info, self.template_info)
        self.dlg2.show()

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

    def __init__(self, info, template_info):
        QDialog.__init__(self)

        self.template_info = template_info

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)

        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint)
        self.setWindowTitle("Edit Dialog")
        self.resize(1024, 800)

        self.set_provenance_section(info)
        self.set_dicom_attributes_section(info)
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
        layout2.addWidget(self.label_bidsname)
        layout2.addWidget(self.view_bidsname)
        layout2.addStretch(1)
        layout2.addWidget(self.ok_button)
        groupbox2.setLayout(layout2)

        layout = QVBoxLayout()
        layout.addWidget(groupbox1)
        layout.addWidget(groupbox2)
        self.setLayout(layout)

        self.ok_button.clicked.connect(self.close)

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

    def set_provenance_section(self, info):
        """Set provenance section. """
        provenance_file = info['provenance']['filename']
        provenance_path = info['provenance']['path']

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

    def set_dicom_attributes_section(self, info):
        """Set non-editable DICOM attributes section. """
        dicom_attributes = info['dicom_attributes']

        data = []
        for key, value in dicom_attributes.items():
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
        self.view_dropdown.addItems(["Select modality", "anat", "func", "dwi", "fmap", "beh", "pet", "extra_data"])
        self.view_dropdown.currentIndexChanged.connect(self.selection_dropdown_change)

    def set_bids_values_section(self):
        """Set editable BIDS values section. """
        self.label_bids = QLabel()
        self.label_bids.setText("BIDS values")

        self.model_bids = QtGui.QStandardItemModel()
        self.model_bids.setHorizontalHeaderLabels(['Key', 'Value'])
        self.view_bids = QTreeView()
        self.view_bids.header().hide()
        self.view_bids.setModel(self.model_bids)
        self.view_bids.setWindowTitle("BIDS values")
        self.view_bids.expandAll()
        self.view_bids.resizeColumnToContents(0)
        self.view_bids.setIndentation(0)
        self.view_bids.setAlternatingRowColors(True)
        self.view_bids.clicked.connect(self.bids_changed)

    def set_bids_name_section(self):
        """Set non-editable BIDS name section. """
        self.label_bidsname = QLabel()
        self.label_bidsname.setText("BIDS name")

        self.view_bidsname = QTextEdit()
        self.view_bidsname.setReadOnly(True)
        self.view_bidsname.textCursor().insertHtml('<b>N/A</b>')
        height = 24
        extra_space = 6
        self.view_bidsname.setFixedHeight(height + extra_space)

    def selection_dropdown_change(self, i):
        """Update the BIDS values and BIDS name section when the dropdown selection has been taking place. """
        if i == 0:
            # Handle case when "Select modality" is selected
            self.model_bids.clear()
            self.view_bidsname.clear()
            self.view_bidsname.textCursor().insertHtml('<b>N/A</b>')

        else:
            selected_modality = self.view_dropdown.currentText()

            # Update the BIDS values
            data_bids = self.get_data_bids(selected_modality)
            self.model_bids.clear()
            self.setupBidsModelData(data_bids)

            # Update the BIDS name
            self.view_bidsname.clear()
            self.view_bidsname.textCursor().insertHtml('<b>New name</b>')

    def bids_changed(self, index):
        item = self.view_bids.selectedIndexes()[0]
        # print(item.model().itemFromIndex(index).text())

    def setupBidsModelData(self, lines, root=None):
        self.model_bids.setRowCount(0)
        if root is None:
            root = self.model_bids.invisibleRootItem()
        seen = {}
        values = deque(lines)
        while values:
            value = values.popleft()
            if value['level'] == 0:
                parent = root
            else:
                pid = value['parent_id']
                if pid not in seen:
                    values.append(value)
                    continue
                parent = seen[pid]
            dbid = value['db_id']
            item = QtGui.QStandardItem(value['short_name'])
            item.setEditable(False)
            item2 = QtGui.QStandardItem(value['long_name'])
            item2.setEditable(True)
            parent.appendRow([item, item2])
            seen[dbid] = parent.child(parent.rowCount() - 1)

    def get_data_bids(self, selected_modality):
        """Obtain the bids values from the template info. """
        bids_values = {}
        for item in self.template_info:
            if item['modality'] == selected_modality:
                bids_values = item['bids_values']
                break

        data_bids = []
        counter = 10
        for key, value in bids_values.items():
            # Skip IntendedFor
            if key != "IntendedFor":
                if value != "None":
                    modified_value = value
                else:
                    modified_value = ""
                data_bids.append({
                    'level': 0,
                    'db_id': counter,
                    'parent_id': 0,
                    'short_name': key,
                    'long_name': modified_value
                })
                counter += 1
        return data_bids


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
    input_bidsmap_info = bidsutils.obtain_initial_bidsmap_info(input_bidsmap_yaml)

    # Obtain the template info
    template_yaml = bidsutils.read_yaml_as_string(TEMPLATE_FILENAME)
    template_info = bidsutils.obtain_template_info(template_yaml)

    output_bidsmap = copy.deepcopy(input_bidsmap)

    logger.info('Input raw data folder: {}'.format(args.rawfolder))
    logger.info('Input BIDS map {}'.format(args.inputbidsmap))
    logger.info('Output BIDS map {}'.format(args.outputbidsmap))

    # Start the application
    app = QApplication(sys.argv)
    app.setApplicationName("BIDS editor")
    mainwin = QMainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(mainwin, args.rawfolder, args.inputbidsmap, args.outputbidsmap, input_bidsmap_yaml, input_bidsmap_info, template_info, output_bidsmap)
    mainwin.show()
    sys.exit(app.exec_())
