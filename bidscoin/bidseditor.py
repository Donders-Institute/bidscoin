#!/usr/bin/env python
"""
Allows updating the BIDSmap via a GUI.
The user needs to fill in the BIDS values for files that are unidentified.
"""

import os
import sys
import argparse
import textwrap
import logging
import copy

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileSystemModel, QFileDialog,
                             QTreeView, QHBoxLayout, QVBoxLayout, QLabel, QDialog,
                             QTableWidget, QTableWidgetItem, QGroupBox,
                             QAbstractItemView, QPushButton, QComboBox, QTextEdit)

try:
    from bidscoin import bids, bidsutils
except ImportError:
    import bids, bidsutils          # This should work if bidscoin was not pip-installed


LOGGER = logging.getLogger('bidscoin')

MAIN_WINDOW_WIDTH   = 1280
MAIN_WINDOW_HEIGHT  = 800

EDIT_WINDOW_WIDTH   = 1024
EDIT_WINDOW_HEIGHT  = 800

ABOUT_WINDOW_WIDTH  = 200
ABOUT_WINDOW_HEIGHT = 140

ICON_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "icons", "brain.ico")


class Ui_MainWindow(object):

    def setupUi(self, MainWindow, sourcefolder, bidsmap_filename, bidsmap, output_bidsmap):

        self.MainWindow = MainWindow
        self.bidsmap_filename = bidsmap_filename
        self.bidsmap = bidsmap
        self.output_bidsmap = output_bidsmap
        self.sourcefolder = sourcefolder

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
        self.set_tab_file_browser(sourcefolder)
        self.set_tab_file_sample_listing()
        self.tabwidget.setTabText(0, "File browser")
        self.tabwidget.setTabText(1, "DICOM samples")
        self.tabwidget.setCurrentIndex(1)

        self.set_menu_and_status_bar()

    def update_list(self, the_sample):
        """ """
        self.output_bidsmap = the_sample

        self.table.setColumnCount(5)
        self.table.setRowCount(len(the_sample) + 1)

        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(True)

        for i, series in enumerate(the_sample):
            provenance_file = series['provenance_file']
            modality = series['modality']
            bids_name = series['bids_name']

            item_id = QTableWidgetItem(str(i + 1))
            item_provenance_file = QTableWidgetItem(provenance_file)
            item_modality = QTableWidgetItem(modality)
            item_bids_name = QTableWidgetItem(bids_name)

            self.table.setItem(i, 0, item_id)
            self.table.setItem(i, 1, item_provenance_file)
            self.table.setItem(i, 2, item_modality)
            self.table.setItem(i, 3, item_bids_name)

            self.button_select = QPushButton('Edit')
            if modality == bids.unknownmodality:
                self.button_select.setStyleSheet('QPushButton {color: red;}')
                self.table.item(i, 1).setForeground(QtGui.QColor(255, 0, 0))
            else:
                self.button_select.setStyleSheet('QPushButton {color: green;}')
                self.table.item(i, 1).setForeground(QtGui.QColor(0, 128, 0))
            self.button_select.clicked.connect(self.handle_button_clicked)
            self.table.setCellWidget(i, 4, self.button_select)

        self.save_button = QtWidgets.QPushButton()
        self.save_button.setText("Save")
        self.save_button.setStyleSheet('QPushButton {color: blue;}')
        self.table.setCellWidget(len(the_sample), 4, self.save_button)

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

        self.save_button.clicked.connect(self.save_bidsmap_to_file)

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

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setRowCount(len(self.output_bidsmap) + 1)

        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(True)

        for i, series in enumerate(self.bidsmap['DICOM']):
            print(series)
            provenance_file = series['provenance']
            modality = series['modality']
            bids_name = series['bids_name']

            item_id = QTableWidgetItem(str(i + 1))
            item_provenance_file = QTableWidgetItem(provenance_file)
            item_modality = QTableWidgetItem(modality)
            item_bids_name = QTableWidgetItem(bids_name)

            self.table.setItem(i, 0, item_id)
            self.table.setItem(i, 1, item_provenance_file)
            self.table.setItem(i, 2, item_modality)
            self.table.setItem(i, 3, item_bids_name)

            self.button_select = QPushButton('Edit')
            if modality == bids.unknownmodality:
                self.button_select.setStyleSheet('QPushButton {color: red;}')
                self.table.item(i, 1).setForeground(QtGui.QColor(255, 0, 0))
            else:
                self.button_select.setStyleSheet('QPushButton {color: green;}')
            self.button_select.clicked.connect(self.handle_button_clicked)
            self.table.setCellWidget(i, 4, self.button_select)

        self.save_button = QtWidgets.QPushButton()
        self.save_button.setText("Save")
        self.save_button.setStyleSheet('QPushButton {color: blue;}')
        self.table.setCellWidget(len(self.output_bidsmap), 4, self.save_button)

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
        options = QFileDialog.Options()
        filename, _ = QFileDialog.getSaveFileName(
            self.tab2,
            "Save File",
            self.sourcefolder,
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=options)
        if filename:
            bids.save_bidsmap(filename, self.output_bidsmap)

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
        self.dialog_edit.got_sample.connect(self.update_list)

    def exit_application(self):
        """ """
        LOGGER.info('Exit application')
        self.MainWindow.close()


class AboutDialog(QDialog):

    def __init__(self):
        QDialog.__init__(self)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint)

        layout = QtWidgets.QVBoxLayout(self)
        scrollArea = QtWidgets.QScrollArea()
        layout.addWidget(scrollArea)

        top_widget = QtWidgets.QWidget()
        top_layout = QtWidgets.QVBoxLayout()

        label = QLabel()
        label.setText("BIDS editor")

        label_version = QLabel()
        label_version.setText("v" + str(bids.version()))

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
        scrollArea.setWidget(top_widget)
        self.resize(ABOUT_WINDOW_WIDTH, ABOUT_WINDOW_HEIGHT)


class EditDialog(QDialog):

    got_sample = QtCore.pyqtSignal(dict)

    def __init__(self, i, modality, output_bidsmap):
        QDialog.__init__(self)

        self.source_bidsmap = copy.deepcopy(output_bidsmap)         # TODO: Check if deepcopy is needed
        self.source_index = i
        self.source_modality = modality
        self.source_sample = output_bidsmap['DICOM'][modality][i]

        self.target_bidsmap = copy.deepcopy(output_bidsmap)
        self.target_modality = modality
        self.target_sample = copy.deepcopy(self.source_sample)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(ICON_FILENAME), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)

        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint)
        self.setWindowTitle("Edit")

        layout = QtWidgets.QVBoxLayout(self)
        scrollArea = QtWidgets.QScrollArea()
        layout.addWidget(scrollArea)

        top_widget = QtWidgets.QWidget()
        top_layout = QtWidgets.QVBoxLayout()
        top_widget.setFixedWidth(EDIT_WINDOW_WIDTH-50)

        self.set_provenance_section()
        self.set_dicom_attributes_section()
        self.set_dropdown_section()
        self.set_bids_values_section()
        self.set_bids_name_section()

        self.ok_button = QtWidgets.QPushButton()
        self.ok_button.setText("OK")
        hbox = QHBoxLayout()
        hbox.addStretch(1)
        hbox.addWidget(self.ok_button)

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
        groupbox2.setLayout(layout2)

        top_layout.addWidget(groupbox1)
        top_layout.addWidget(groupbox2)
        top_layout.addStretch(1)
        top_layout.addLayout(hbox)

        self.view_bids.cellChanged.connect(self.cell_was_clicked)
        self.ok_button.clicked.connect(self.update_sample)

        top_widget.setLayout(top_layout)
        scrollArea.setWidget(top_widget)
        self.resize(EDIT_WINDOW_WIDTH, EDIT_WINDOW_HEIGHT)

    def update_sample(self):
        """Save the changes. """
        self.target_bidsmap = bidsutils.update_bidsmap(self.source_bidsmap,
                                                       self.source_modality,
                                                       self.source_index,
                                                       self.target_modality,
                                                       self.target_sample)

        self.got_sample.emit(self.target_bidsmap)
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

    def get_table(self, data, num_rows=2):
        """Return a table widget from the data. """
        table = QTableWidget()

        table.setRowCount(num_rows)
        table.setColumnCount(2) # Always two columns (i.e. key, value)
        row_height = 24

        for i, row in enumerate(data):
            table.setRowHeight(i, row_height)
            key = row[0]["value"]
            if self.target_modality in ['anat', bids.unknownmodality] and key == 'modality_label':
                self.modality_label_dropdown = QComboBox()
                self.modality_label_dropdown.addItems(bidsutils.MODALITY_LABELS)
                self.modality_label_dropdown.setCurrentIndex(self.modality_label_dropdown.findText(self.target_modality_label))
                self.modality_label_dropdown.currentIndexChanged.connect(self.selection_modality_label_dropdown_change)
                item = self.set_cell("modality_label", is_editable=False)
                table.setItem(i, 0, QTableWidgetItem(item))
                item = self.set_cell("", is_editable=True)
                table.setCellWidget(i, 1, self.modality_label_dropdown)
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
        table_height = num_rows * (row_height + extra_space) + 2 * table.frameWidth()
        table.setMinimumHeight(table_height)
        table.setMaximumHeight(table_height)

        return table

    def set_provenance_section(self):
        """Set provenance section. """
        provenance = self.source_sample['provenance']
        provenance_file = os.path.basename(provenance)
        provenance_path = os.path.dirname(provenance)

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
        """Set DICOM attributes section. """
        dicom_attributes = self.source_sample['attributes']

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
        self.label_dicom.setText("DICOM attributes")

        self.view_dicom = self.get_table(data, len(data))

    def set_dropdown_section(self):
        """Dropdown select modality list section. """
        self.label_dropdown = QLabel()
        self.label_dropdown.setText("Modality")

        self.view_dropdown = QComboBox()
        self.view_dropdown.addItems(bidsutils.MODALITIES)
        self.view_dropdown.setCurrentIndex(self.view_dropdown.findText(self.target_modality))

        self.view_dropdown.currentIndexChanged.connect(self.selection_dropdown_change)

    def get_bids_values_data(self):
        """# Given the input BIDS attributes, derive the target BIDS attributes. """
        source_bids_attributes = self.target_sample.get('bids', {})
        target_bids_attributes = bidsutils.get_bids_attributes(self.target_modality, source_bids_attributes)
        if target_bids_attributes is not None:
            bids_values = target_bids_attributes
        else:
            bids_values = {}

        data = []
        for key, value in bids_values.items():
            if self.target_modality in ['anat', bids.unknownmodality] and key == 'modality_label':
                value = self.target_modality_label
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

        return bids_values, data

    def set_bids_values_section(self):
        """Set editable BIDS values section. """
        # For anat and extra_data, set the default target modality label (i.e T1w)
        self.target_modality_label = bidsutils.MODALITY_LABELS[0]

        _, data = self.get_bids_values_data()

        self.label_bids = QLabel()
        self.label_bids.setText("BIDS values")

        self.view_bids = self.get_table(data)

    def set_bids_name_section(self):
        """Set non-editable BIDS name section. """
        bids_values, _ = self.get_bids_values_data()

        subid = '*'
        sesid = '*'
        bids_name = bids.get_bidsname(subid, sesid, self.target_modality, self.target_sample)

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

        # Given the input BIDS attributes, derive the target BIDS attributes (i.e map them to the target attributes)
        bids_values, data = self.get_bids_values_data()

        # Update the BIDS values
        table = self.view_bids
        for i, row in enumerate(data):
            key = row[0]["value"]
            if self.target_modality in ['anat', bids.unknownmodality] and key == 'modality_label':
                self.modality_label_dropdown = QComboBox()
                self.modality_label_dropdown.addItems(bidsutils.MODALITY_LABELS)
                self.modality_label_dropdown.setCurrentIndex(self.modality_label_dropdown.findText(self.target_modality_label))
                self.modality_label_dropdown.currentIndexChanged.connect(self.selection_modality_label_dropdown_change)
                item = self.set_cell("modality_label", is_editable=False)
                table.setItem(i, 0, QTableWidgetItem(item))
                table.setCellWidget(i, 1, self.modality_label_dropdown)
                continue
            for j, element in enumerate(row):
                value = element.get("value", "")
                if value == "None":
                    value = ""
                is_editable = element.get("is_editable", False)
                table.removeCellWidget(i, j)
                item = self.set_cell(value, is_editable=is_editable)
                table.setItem(i, j, QTableWidgetItem(item))
        for i in range(len(data)):
            for j, element in enumerate(row):
                table.removeCellWidget(i, j)
                item = self.set_cell('', is_editable=False)
                table.setItem(i, j, QTableWidgetItem(item))

        self.view_bids = table

        bids_values['modality_label'] = self.target_modality_label

        # Update the BIDS name
        subid = '*'
        sesid = '*'
        bids_name = bids.get_bidsname(subid, sesid, self.target_modality, self.target_sample)

        self.view_bids_name.clear()
        self.view_bids_name.textCursor().insertText(bids_name)

    def selection_modality_label_dropdown_change(self, i):
        """Update the BIDS values and BIDS name section when the dropdown selection has been taking place. """
        self.target_modality_label = self.modality_label_dropdown.currentText()

        bids_values, data = self.get_bids_values_data()
        bids_values['modality_label'] = self.target_modality_label

        # Update the BIDS name
        subid = '*'
        sesid = '*'
        bids_name = bids.get_bidsname(subid, sesid, self.target_modality, self.source_sample)

        self.view_bids_name.clear()
        self.view_bids_name.textCursor().insertText(bids_name)


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
    template_bidsmap = bids.load_bidsmap(templatefile, os.path.join(bidsfolder,'code'))
    input_bidsmap    = bids.load_bidsmap(bidsmapfile, os.path.join(bidsfolder,'code'))
    output_bidsmap   = copy.deepcopy(input_bidsmap)

    # Parse the sourcefolder from the bidsmap provenance info
    if not sourcefolder:

        # Loop through all bidsmodalities and series until we find provenance info
        for modality in bids.bidsmodalities + (bids.unknownmodality,):
            if input_bidsmap['DICOM'][modality] is None: continue

            for series in input_bidsmap['DICOM'][modality]:
                if series['provenance']:
                    sourcefolder = os.path.dirname(os.path.dirname(series['provenance']))
                    LOGGER.info(f'Source: {sourcefolder}')
                    break
            if sourcefolder: break

    # Start the Qt-application
    app = QApplication(sys.argv)
    app.setApplicationName("BIDS editor")
    mainwin = QMainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(mainwin, sourcefolder, bidsmapfile, input_bidsmap, output_bidsmap, template_bidsmap)
    mainwin.show()
    sys.exit(app.exec_())

    LOGGER.info('------------ FINISHED! ------------')


if __name__ == "__main__":

    # Parse the input arguments and run bidseditor
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidseditor.py /project/bids\n'
                                            '  bidseditor.py /project/bids -b my/custom/bidsmap.yaml\n')
    parser.add_argument('bidsfolder',           help='The destination folder with the (future) bids data')
    parser.add_argument('-s','--sourcefolder',  help='The source folder containing the raw data. If empty, it is derived from the bidsmap provenance information')
    parser.add_argument('-b','--bidsmap',       help='The bidsmap YAML-file with the study heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-t','--template',      help='The bidsmap template with the study heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/. Default: bidsmap_template.yaml')
    args = parser.parse_args()

    bidseditor(bidsfolder   = args.bidsfolder,
               sourcefolder = args.sourcefolder,
               bidsmapfile  = args.bidsmap,
               templatefile = args.template)
