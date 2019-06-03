#!/usr/bin/env python
"""
This function launches a graphical interface for editing the bidsmap.yaml file that is e.g. produced by bidsmapper.py.
The user can fill in or change the BIDS values for entries that are unidentified or sub-optimal, such that meaningful
BIDS filenames will be generated. The resulting bidsmap.yaml file can be used for converting the data to BIDS using
bidscoiner.py
"""

import os
import sys
import argparse
import textwrap
import logging
import copy
from collections import OrderedDict

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileSystemModel, QFileDialog,
                             QTreeView, QHBoxLayout, QVBoxLayout, QLabel, QDialog,
                             QTableWidget, QTableWidgetItem, QGroupBox,
                             QAbstractItemView, QPushButton, QComboBox, QTextEdit)

try:
    from bidscoin import bids
except ImportError:
    import bids             # This should work if bidscoin was not pip-installed

SOURCE = 'DICOM'            # TODO: allow for non-DICOM (e.g. PAR/REC) edits

LOGGER = logging.getLogger('bidscoin')

MAIN_WINDOW_WIDTH   = 1280
MAIN_WINDOW_HEIGHT  = 800

EDIT_WINDOW_WIDTH   = 1024
EDIT_WINDOW_HEIGHT  = 800

ABOUT_WINDOW_WIDTH  = 200
ABOUT_WINDOW_HEIGHT = 140

MAX_NUM_PROVENANCE_ATTRIBUTES = 2
MAX_NUM_BIDS_ATTRIBUTES = 10

ICON_FILENAME = os.path.join(os.path.dirname(os.path.realpath(__file__)), "icons", "brain.ico")


def update_bidsmap(source_bidsmap, source_modality, source_index, target_modality, target_series):
    """Update the BIDS map:
    1. Remove the source series from the source modality section
    2. Add the target series to the target modality section
    """
    if not source_modality in bids.bidsmodalities + (bids.unknownmodality,):
        raise ValueError(f"invalid modality '{source_modality}'")

    if not target_modality in bids.bidsmodalities + (bids.unknownmodality,):
        raise ValueError(f"invalid modality '{target_modality}'")

    target_bidsmap = copy.deepcopy(source_bidsmap)  # TODO: check if deepcopy is needed

    # First check if the target series already exists.    TODO: figure out what to do with this situation
    if bids.exist_series(target_bidsmap, SOURCE, target_modality, target_series):
        LOGGER.warning('That entry already exists...')

    # Delete the source series
    target_bidsmap = bids.delete_series(target_bidsmap, SOURCE, source_modality, source_index)

    # Append the target series
    target_bidsmap = bids.append_series(target_bidsmap, SOURCE, target_modality, target_series)

    return target_bidsmap


def get_allowed_suffices(template_bidsmap):
    """Derive the possible suffices for each modality from the template. """

    # Scan the template
    allowed_suffices = {}
    for modality in bids.bidsmodalities + (bids.unknownmodality,):
        allowed_suffices[modality] = []
        series_list = template_bidsmap[SOURCE][modality]
        if not series_list:
            continue
        for series in series_list:
            if modality == 'anat':
                # TODO: No special case for anat
                suffix = series['bids'].get('modality_label', None)
            else:
                suffix = series['bids'].get('suffix', None)
            if suffix and suffix not in allowed_suffices[modality]:
                allowed_suffices[modality].append(suffix)

    # Scan the heuristics/samples folder
    folder = os.path.join(os.path.dirname(__file__), '..', 'heuristics', 'samples')
    for x in os.walk(folder):
        # Check the last two directories
        path = x[0]
        head, dirname2 = os.path.split(path)
        dirname1 = os.path.split(head)[1]
        if dirname1 in bids.bidsmodalities + (bids.unknownmodality,):
            modality = dirname1
            suffix = dirname2
            if suffix not in allowed_suffices[modality]:
                LOGGER.warning(f'Suffix {suffix} found in samples but not in template for modality {modality}')
                allowed_suffices[modality].append(suffix)

    # Sort the allowed suffices alphabetically
    for modality in bids.bidsmodalities + (bids.unknownmodality,):
        allowed_suffices[modality] = sorted(allowed_suffices[modality])

    return allowed_suffices


class Ui_MainWindow(object):

    def setupUi(self, MainWindow, bidsfolder, sourcefolder, bidsmap_filename, bidsmap, output_bidsmap, template_bidsmap):

        self.has_edit_dialog_open = False

        self.MainWindow = MainWindow

        self.bidsfolder = bidsfolder
        self.sourcefolder = sourcefolder
        self.bidsmap_filename = bidsmap_filename
        self.bidsmap = bidsmap
        self.output_bidsmap = output_bidsmap
        self.template_bidsmap = template_bidsmap

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
        self.tabwidget.setTabText(1, f"{SOURCE} samples")
        self.tabwidget.setCurrentIndex(1)

        self.set_menu_and_status_bar()

    def update_list(self, the_series):
        """ """
        self.output_bidsmap = the_series

        self.table.setColumnCount(5)
        self.table.setRowCount(len(the_series) + 1)

        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(True)

        idx = 0
        for modality in bids.bidsmodalities + (bids.unknownmodality,):
            series_list = self.output_bidsmap[SOURCE][modality]
            if not series_list:
                continue
            for series in series_list:
                provenance = series['provenance']
                provenance_file = os.path.basename(provenance)
                bids_name = bids.get_bidsname('001', '01', modality, series)

                item_id = QTableWidgetItem(str(idx + 1))
                item_provenance_file = QTableWidgetItem(provenance_file)
                item_modality = QTableWidgetItem(modality)
                item_bids_name = QTableWidgetItem(bids_name)

                self.table.setItem(idx, 0, item_id)
                self.table.setItem(idx, 1, item_provenance_file)
                self.table.setItem(idx, 2, item_modality)
                self.table.setItem(idx, 3, item_bids_name)

                self.button_select = QPushButton('Edit')
                if modality == bids.unknownmodality:
                    self.button_select.setStyleSheet('QPushButton {color: red;}')
                    self.table.item(idx, 1).setForeground(QtGui.QColor(255, 0, 0))
                else:
                    self.button_select.setStyleSheet('QPushButton {color: green;}')
                    self.table.item(idx, 1).setForeground(QtGui.QColor(0, 128, 0))
                self.button_select.clicked.connect(self.handle_button_clicked)
                self.table.setCellWidget(idx, 4, self.button_select)

                idx += 1

        self.save_button = QtWidgets.QPushButton()
        self.save_button.setText("Save")
        self.save_button.setStyleSheet('QPushButton {color: blue;}')
        self.table.setCellWidget(idx, 4, self.save_button)

        self.table.setHorizontalHeaderLabels(['', f'{SOURCE} file sample', 'Modality', 'BIDS name', 'Action'])
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
        self.has_edit_dialog_open = False

    def set_tab_file_browser(self, sourcefolder):
        """Set the raw data folder inspector tab. """
        self.tab1 = QtWidgets.QWidget()
        self.tab1.layout = QVBoxLayout(self.centralwidget)
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
        self.tree.clicked.connect(self.on_clicked)
        self.tab1.layout.addWidget(self.label)
        self.tab1.layout.addWidget(self.tree)
        self.tree.header().resizeSection(0, 800)

        self.file_browser = QtWidgets.QWidget()
        self.file_browser.setLayout(self.tab1.layout)
        self.file_browser.setObjectName("filebrowser")
        self.tabwidget.addTab(self.file_browser, "")

    def set_tab_file_sample_listing(self):
        """Set the SOURCE file sample listing tab.  """
        num_files = 0
        for modality in bids.bidsmodalities + (bids.unknownmodality,):
            series_list = self.bidsmap[SOURCE][modality]
            if not series_list:
                continue
            for _ in series_list:
                num_files += 1

        self.tab2 = QtWidgets.QWidget()
        self.tab2.layout = QVBoxLayout(self.centralwidget)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setRowCount(num_files + 1) # one for each file and the save button

        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(True)

        idx = 0
        for modality in bids.bidsmodalities + (bids.unknownmodality,):
            series_list = self.output_bidsmap[SOURCE][modality]
            if not series_list:
                continue
            for series in series_list:
                provenance = series['provenance']
                provenance_file = os.path.basename(provenance)
                bids_name = bids.get_bidsname('001', '01', modality, series)

                item_id = QTableWidgetItem(str(idx + 1))
                item_provenance_file = QTableWidgetItem(provenance_file)
                item_modality = QTableWidgetItem(modality)
                item_bids_name = QTableWidgetItem(bids_name)

                self.table.setItem(idx, 0, item_id)
                self.table.setItem(idx, 1, item_provenance_file)
                self.table.setItem(idx, 2, item_modality)
                self.table.setItem(idx, 3, item_bids_name)

                self.button_select = QPushButton('Edit')
                if modality == bids.unknownmodality:
                    self.button_select.setStyleSheet('QPushButton {color: red;}')
                    self.table.item(idx, 1).setForeground(QtGui.QColor(255, 0, 0))
                else:
                    self.button_select.setStyleSheet('QPushButton {color: green;}')
                self.button_select.clicked.connect(self.handle_button_clicked)
                self.table.setCellWidget(idx, 4, self.button_select)

                idx += 1

        self.save_button = QtWidgets.QPushButton()
        self.save_button.setText("Save")
        self.save_button.setStyleSheet('QPushButton {color: blue;}')
        self.table.setCellWidget(idx, 4, self.save_button)

        self.table.setHorizontalHeaderLabels(['', f'{SOURCE} file sample', 'Modality', 'BIDS name', 'Action'])
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
            modality = self.table.item(idx, 2).text()
            self.show_edit(idx, modality)

    def on_clicked(self, index):
        # print(self.model.fileInfo(index).absoluteFilePath())
        pass

    def show_about(self):
        """ """
        self.dialog_about = AboutDialog()
        self.dialog_about.show()

    def show_edit(self, idx, modality):
        """Allow only one edit window to be open."""
        if not self.has_edit_dialog_open:
            self.dialog_edit = EditDialog(idx, modality, self.output_bidsmap, self.template_bidsmap)
            self.dialog_edit.show()
            self.has_edit_dialog_open = True
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

    def __init__(self, idx, modality, output_bidsmap, template_bidsmap):
        QDialog.__init__(self)

        self.source_bidsmap = copy.deepcopy(output_bidsmap)         # TODO: Check if deepcopy is needed
        self.source_index = idx
        self.source_modality = modality
        self.source_series = self.source_bidsmap[SOURCE][modality][idx]

        self.target_bidsmap = copy.deepcopy(output_bidsmap)
        self.target_modality = modality
        self.target_series = copy.deepcopy(self.source_series)

        self.template_bidsmap = template_bidsmap
        self.allowed_suffices = get_allowed_suffices(template_bidsmap)
        self.ANAT_BIDS_MODALITY_LABELS = self.allowed_suffices['anat']

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

        groupbox1 = QGroupBox(SOURCE)
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
        self.ok_button.clicked.connect(self.update_series)

        top_widget.setLayout(top_layout)
        scrollArea.setWidget(top_widget)
        self.resize(EDIT_WINDOW_WIDTH, EDIT_WINDOW_HEIGHT)

    def update_series(self):
        """Save the changes. """
        self.target_bidsmap = update_bidsmap(self.source_bidsmap,
                                             self.source_modality,
                                             self.source_index,
                                             self.target_modality,
                                             self.target_series)

        self.got_sample.emit(self.target_bidsmap)
        self.close()

    def cell_was_clicked(self, row, column):
        """BIDS attribute value has been changed. """
        if column == 1:
            item_key = self.view_bids.item(row, 0)
            item_value = self.view_bids.item(row, 1)
            key = item_key.text()
            value = item_value.text()

            if key == 'modality_label':
                # TODO: Deal with drop down selection
                pass

            self.target_series['bids'][key] = value

            series = self.target_series
            run = series['bids'].get('run_index', '*')
            self.bids_name = bids.get_bidsname('001', '01', self.target_modality, series, run)

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

    def get_table(self, data, num_rows=1):
        """Return a table widget from the data. """
        table = QTableWidget()

        table.setRowCount(num_rows)
        table.setColumnCount(2) # Always two columns (i.e. key, value)
        row_height = 24

        for i, row in enumerate(data):
            table.setRowHeight(i, row_height)
            key = row[0]["value"]
            if self.target_modality == 'anat' and key == 'modality_label':
                self.modality_label_dropdown = QComboBox()
                self.modality_label_dropdown.addItems(self.ANAT_BIDS_MODALITY_LABELS)
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
        provenance = self.source_series['provenance']
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

        self.view_provenance = self.get_table(data, num_rows=MAX_NUM_PROVENANCE_ATTRIBUTES)

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
        self.label_dicom.setText(f"{SOURCE} attributes")

        self.view_dicom = self.get_table(data, num_rows=len(data))

    def set_dropdown_section(self):
        """Dropdown select modality list section. """
        self.label_dropdown = QLabel()
        self.label_dropdown.setText("Modality")

        self.view_dropdown = QComboBox()
        self.view_dropdown.addItems(bids.bidsmodalities + (bids.unknownmodality,))
        self.view_dropdown.setCurrentIndex(self.view_dropdown.findText(self.target_modality))

        self.view_dropdown.currentIndexChanged.connect(self.selection_dropdown_change)

    # TODO: Replace this function. Make use of template instead
    def get_bids_attributes(self, modality, source_bids_attributes):
        """Return the BIDS attributes (i.e. the key,value pairs). """
        bids_attributes = None

        if modality == 'anat':
            # acq_label: <SeriesDescription>
            # rec_label: ~
            # run_index: <<1>>
            # mod_label: ~
            # modality_label: ANAT_BIDS_MODALITY_LABELS
            # ce_label: ~
            bids_attributes = OrderedDict()
            bids_attributes['acq_label'] = source_bids_attributes.get('acq_label', '<SeriesDescription>')
            bids_attributes['rec_label'] = source_bids_attributes.get('rec_label', '')
            bids_attributes['run_index'] = source_bids_attributes.get('run_index', '<<1>>')
            bids_attributes['mod_label'] = source_bids_attributes.get('mod_label', '')
            bids_attributes['modality_label'] = source_bids_attributes.get('modality_label', self.ANAT_BIDS_MODALITY_LABELS[0])
            bids_attributes['ce_label'] = source_bids_attributes.get('ce_label', '')

        elif modality == 'func':
            # task_label: <SeriesDescription>
            # acq_label: ~
            # rec_label: ~
            # run_index: <<1>>
            # echo_index: <EchoNumbers>
            # suffix: bold
            bids_attributes = OrderedDict()
            bids_attributes['task_label'] = source_bids_attributes.get('task_label', '<SeriesDescription>')
            bids_attributes['acq_label'] = source_bids_attributes.get('acq_label', '')
            bids_attributes['rec_label'] = source_bids_attributes.get('rec_label', '')
            bids_attributes['run_index'] = source_bids_attributes.get('run_index', '<<1>>')
            bids_attributes['echo_index'] = source_bids_attributes.get('echo_index', '<EchoNumber>')
            bids_attributes['suffix'] = source_bids_attributes.get('suffix', 'bold')

        elif modality == 'dwi':
            # acq_label: <SeriesDescription>
            # run_index: <<1>>
            # suffix: [dwi, sbref]
            bids_attributes = OrderedDict()
            bids_attributes['acq_label'] = source_bids_attributes.get('acq_label', '<SeriesDescription>')
            bids_attributes['run_index'] = source_bids_attributes.get('run_index', '<<1>>')
            bids_attributes['suffix'] = source_bids_attributes.get('suffix', '')

        elif modality == 'fmap':
            # acq_label: <SeriesDescription>
            # run_index: <<1>>
            # dir_label: None, <InPlanePhaseEncodingDirection>
            # suffix: [magnitude, magnitude1, magnitude2, phasediff, phase1, phase2, fieldmap, epi]
            bids_attributes = OrderedDict()
            bids_attributes['acq_label'] = source_bids_attributes.get('acq_label', '<SeriesDescription>')
            bids_attributes['run_index'] = source_bids_attributes.get('run_index', '<<1>>')
            bids_attributes['dir_label'] = source_bids_attributes.get('dir_label', '')
            bids_attributes['suffix'] = source_bids_attributes.get('suffix', '')

        elif modality == 'beh':
            # task_name: <SeriesDescription>
            # suffix: ~
            bids_attributes = OrderedDict()
            bids_attributes['task_label'] = source_bids_attributes.get('task_label', '<SeriesDescription>')
            bids_attributes['suffix'] = source_bids_attributes.get('suffix', '')

        elif modality == 'pet':
            # task_label: <SeriesDescription>
            # acq_label: <Radiopharmaceutical>
            # rec_label: ~
            # run_index: <<1>>
            # suffix: pet
            bids_attributes = OrderedDict()
            bids_attributes['task_label'] = source_bids_attributes.get('task_label', '<SeriesDescription>')
            bids_attributes['acq_label'] = source_bids_attributes.get('acq_label', '<Radiopharmaceutical>')
            bids_attributes['rec_label'] = source_bids_attributes.get('rec_label', '')
            bids_attributes['run_index'] = source_bids_attributes.get('run_index', '<<1>>')
            bids_attributes['suffix'] = source_bids_attributes.get('suffix', 'pet')

        elif modality == bids.unknownmodality:
            # acq_label: <SeriesDescription>
            # rec_label: ~
            # ce_label: ~
            # task_label: ~
            # echo_index: ~
            # dir_label: ~
            # run_index: <<1>>
            # suffix: ~
            # mod_label: ~
            # modality_label: ~
            bids_attributes = OrderedDict()
            bids_attributes['acq_label'] = source_bids_attributes.get('acq_label', '<SeriesDescription>')
            bids_attributes['rec_label'] = source_bids_attributes.get('rec_label', '')
            bids_attributes['ce_label'] = source_bids_attributes.get('ce_label', '')
            bids_attributes['task_label'] = source_bids_attributes.get('task_label', '')
            bids_attributes['echo_index'] = source_bids_attributes.get('echo_index', '')
            bids_attributes['dir_label'] = source_bids_attributes.get('dir_label', '')
            bids_attributes['suffix'] = source_bids_attributes.get('suffix', '')
            bids_attributes['run_index'] = source_bids_attributes.get('run_index', '<<1>>')
            bids_attributes['mod_label'] = source_bids_attributes.get('mod_label', '')
            bids_attributes['modality_label'] = source_bids_attributes.get('modality_label', '')

        return bids_attributes

    def get_bids_values_data(self):
        """# Given the input BIDS attributes, derive the target BIDS attributes. """
        source_bids_attributes = self.target_series.get('bids', {})
        target_bids_attributes = self.get_bids_attributes(self.target_modality, source_bids_attributes)
        if target_bids_attributes is not None:
            bids_values = target_bids_attributes
        else:
            bids_values = {}

        data = []
        for key, value in bids_values.items():
            if self.target_modality == 'anat' and key == 'modality_label':
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
        self.target_modality_label = self.ANAT_BIDS_MODALITY_LABELS[0]

        _, data = self.get_bids_values_data()

        self.label_bids = QLabel()
        self.label_bids.setText("BIDS values")

        self.view_bids = self.get_table(data, num_rows=MAX_NUM_BIDS_ATTRIBUTES)

    def set_bids_name_section(self):
        """Set non-editable BIDS name section. """
        self.bids_name = bids.get_bidsname('001', '01', self.target_modality, self.target_series)

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
            if self.target_modality == 'anat' and key == 'modality_label':
                self.modality_label_dropdown = QComboBox()
                self.modality_label_dropdown.addItems(self.ANAT_BIDS_MODALITY_LABELS)
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
        for i in range(len(data), MAX_NUM_BIDS_ATTRIBUTES):
            for j, element in enumerate(row):
                table.removeCellWidget(i, j)
                item = self.set_cell('', is_editable=False)
                table.setItem(i, j, QTableWidgetItem(item))

        self.view_bids = table

        bids_values['modality_label'] = self.target_modality_label

        # Update the BIDS name
        bids_name = bids.get_bidsname('001', '01', self.target_modality, self.target_series)

        self.view_bids_name.clear()
        self.view_bids_name.textCursor().insertText(bids_name)

    def selection_modality_label_dropdown_change(self, i):
        """Update the BIDS values and BIDS name section when the dropdown selection has been taking place. """
        self.target_modality_label = self.modality_label_dropdown.currentText()

        bids_values, data = self.get_bids_values_data()
        bids_values['modality_label'] = self.target_modality_label

        # Update the BIDS name
        bids_name = bids.get_bidsname('001', '01', self.target_modality, self.target_series)

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
            if input_bidsmap[SOURCE][modality] is None:
                continue

            for series in input_bidsmap[SOURCE][modality]:
                if series['provenance']:
                    sourcefolder = os.path.dirname(os.path.dirname(series['provenance']))
                    LOGGER.info(f'Source: {sourcefolder}')
                    break

            if sourcefolder:
                break

    # Start the Qt-application
    app = QApplication(sys.argv)
    app.setApplicationName("BIDS editor")
    mainwin = QMainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(mainwin, bidsfolder, sourcefolder, bidsmapfile, input_bidsmap, output_bidsmap, template_bidsmap)
    mainwin.show()
    sys.exit(app.exec_())

    LOGGER.info('------------ FINISHED! ------------')


if __name__ == "__main__":

    # Parse the input arguments and run bidseditor
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidseditor.py /project/bids\n'
                                            '  bidseditor.py /project/bids -t bidsmap_dccn.yaml\n'
                                            '  bidseditor.py /project/bids -b my/custom/bidsmap.yaml\n')
    parser.add_argument('bidsfolder',           help='The destination folder with the (future) bids data')
    parser.add_argument('-s','--sourcefolder',  help='The source folder containing the raw data. If empty, it is derived from the bidsmap provenance information')
    parser.add_argument('-b','--bidsmap',       help='The bidsmap YAML-file with the study heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-t','--template',      help='The bidsmap template with the default heuristics (this could be provided by your institute). If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/. Default: bidsmap_template.yaml')
    args = parser.parse_args()

    bidseditor(bidsfolder   = args.bidsfolder,
               sourcefolder = args.sourcefolder,
               bidsmapfile  = args.bidsmap,
               templatefile = args.template)
