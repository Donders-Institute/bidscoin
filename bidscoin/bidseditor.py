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
import json
import logging

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileSystemModel,
    QTreeView, QVBoxLayout, QLabel, QDialog, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QPushButton, QComboBox, QTextEdit)
from PyQt5.Qsci import QsciScintilla, QsciLexerYAML

import bids
import bidsutils


logger = logging.getLogger('bidscoin')


class Ui_MainWindow(object):

    def setupUi(self, MainWindow, rawfolder, inputbidsmap, bidsmap_yaml, bidsmap_info):

        self.bidsmap_info = bidsmap_info

        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1280, 800)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(os.path.join(os.path.dirname(os.path.realpath(__file__)), "icons", "brain.ico")), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        MainWindow.setWindowIcon(icon)

        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        self.centralwidget.setObjectName("centralwidget")

        self.bidscoin = QtWidgets.QTabWidget(self.centralwidget)
        self.bidscoin.setGeometry(QtCore.QRect(0, 0, 1280, 760))
        self.bidscoin.setTabPosition(QtWidgets.QTabWidget.North)
        self.bidscoin.setTabShape(QtWidgets.QTabWidget.Rounded)
        self.bidscoin.setObjectName("bidscoin")
        self.bidscoin.setToolTip("<html><head/><body><p>bidscoiner</p></body></html>")

        # TAB 1 - Raw data folder inspector
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

        self.filebrowser = QtWidgets.QWidget()
        self.filebrowser.setLayout(self.tab1.layout)
        self.filebrowser.setObjectName("filebrowser")
        self.bidscoin.addTab(self.filebrowser, "")

        # TAB 2 - Initial BIDSmap inspector
        self.tab2 = QtWidgets.QWidget()
        self.tab2.layout = QVBoxLayout(self.centralwidget)
        self.label_bidsmap = QLabel()
        self.label_bidsmap.setText("Inspect input BIDS map file: {}".format(inputbidsmap))
        self.plainTextEdit = QsciScintilla()
        self.__lexer = QsciLexerYAML()
        self.plainTextEdit.setLexer(self.__lexer)
        self.plainTextEdit.setUtf8(True)  # Set encoding to UTF-8
        self.__myFont = QFont("Courier")
        self.__myFont.setPointSize(10)
        self.plainTextEdit.setFont(self.__myFont)
        self.__lexer.setFont(self.__myFont)
        self.plainTextEdit.setObjectName("syntaxHighlighter")
        self.plainTextEdit.setText(bidsmap_yaml)
        self.plainTextEdit.setReadOnly(True)
        self.tab2.layout.addWidget(self.label_bidsmap)
        self.tab2.layout.addWidget(self.plainTextEdit)

        self.bidsmap = QtWidgets.QWidget()
        self.bidsmap.setLayout(self.tab2.layout)
        self.bidsmap.setObjectName("bidsmap")
        self.bidscoin.addTab(self.bidsmap, "")

        self.list_dicom_files, self.list_bids_names = bidsutils.get_list_files(bidsmap_info)

        # TAB 3 - BIDS editor
        self.tab3 = QtWidgets.QWidget()
        self.tab3.layout = QVBoxLayout(self.centralwidget)
        self.tableButton = QtWidgets.QPushButton()
        self.tableButton.setGeometry(QtCore.QRect(20, 20, 93, 28))
        self.tableButton.setObjectName("tableButton")
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setRowCount(len(self.list_dicom_files))
        self.table.setAlternatingRowColors(True)

        for index in range(len(self.list_dicom_files)):
            item1 = QTableWidgetItem(self.list_dicom_files[index])
            self.table.setItem(index, 0, item1)
            item2 = QTableWidgetItem(self.list_bids_names[index])
            self.table.setItem(index, 1, item2)
            text = 'Edit'
            self.btn_select = QPushButton(text)
            if self.list_bids_names[index] == '':
                self.btn_select.setStyleSheet('QPushButton {color: red;}')
                self.table.item(index, 0).setForeground(QtGui.QColor(255,0,0))
            else:
                self.btn_select.setStyleSheet('QPushButton {color: green;}')
            self.btn_select.clicked.connect(self.handleButtonClicked)
            self.table.setCellWidget(index, 2, self.btn_select)
        self.table.setHorizontalHeaderLabels(['DICOM file', 'BIDS name', 'Action'])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.tab3.layout.addWidget(self.tableButton)
        self.tab3.layout.addWidget(self.table)
        self.filelister = QtWidgets.QWidget()
        self.filelister.setLayout(self.tab3.layout)
        self.filelister.setObjectName("filelister")
        self.tableButton.setText("Commit changes")
        self.bidscoin.addTab(self.filelister, "")

        self.bidscoin.setTabText(self.bidscoin.indexOf(self.filebrowser), "Raw data folder inspector")
        self.bidscoin.setTabText(self.bidscoin.indexOf(self.bidsmap), "Initial BIDSmap inspector")
        self.bidscoin.setTabText(self.bidscoin.indexOf(self.filelister), "BIDS editor")
        self.bidscoin.setCurrentIndex(2)

        # Set the menu
        MainWindow.setCentralWidget(self.centralwidget)

        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 997, 26))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menuHelp = QtWidgets.QMenu(self.menubar)
        self.menuHelp.setObjectName("menuHelp")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)

        # Set the statusbar
        self.statusbar.setToolTip("")
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        # Define the menu actions
        self.actionNew = QtWidgets.QAction(MainWindow)
        self.actionNew.setObjectName("actionNew")

        self.actionExit = QtWidgets.QAction(MainWindow)
        self.actionExit.setObjectName("actionExit")
        self.actionExit.triggered.connect(MainWindow.close)

        self.actionAbout = QtWidgets.QAction(MainWindow)
        self.actionAbout.setObjectName("actionAbout")
        self.actionAbout.triggered.connect(self.showAbout)

        self.actionEdit = QtWidgets.QAction(MainWindow)
        self.actionEdit.setObjectName("actionEdit")

        self.menuFile.addAction(self.actionExit)
        self.menuHelp.addAction(self.actionAbout)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.menuFile.setTitle("File")
        self.menuHelp.setTitle("Help")
        self.statusbar.setStatusTip("Text in statusbar")
        self.actionExit.setText("Exit")
        self.actionExit.setStatusTip("Click to exit the application")
        self.actionExit.setShortcut("Ctrl+X")
        self.actionAbout.setText("About")

        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def handleButtonClicked(self):
        button = QApplication.focusWidget()
        index = self.table.indexAt(button.pos())
        if index.isValid():
            i = int(index.row())
            # print(self.list_dicom_files[i])
            self.showEdit(i, )

    def on_clicked(self, index):
        # print(self.model.fileInfo(index).absoluteFilePath())
        pass

    def showAbout(self):
        """ """
        self.dlg = AboutDialog()
        self.dlg.show()

    def showEdit(self, i):
        """ """
        info = self.bidsmap_info[i]
        self.dlg2 = EditDialog(info)
        self.dlg2.show()


class AboutDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self)
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
    def __init__(self, info):
        QDialog.__init__(self)
        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint)
        self.setWindowTitle("Edit Dialog")
        self.resize(1024, 800)

        # Non-editable provenance section
        self.label_provenance = QLabel()
        self.label_provenance.setText("PROVENANCE")
        self.model_provenance = QtGui.QStandardItemModel()

        provenance_file = info['provenance']['filename']
        provenance_path = info['provenance']['path']
        data_provenance = [{'level': 0, 'dbID': 0, 'parent_ID': 6, 'short_name': 'filename', 'long_name': provenance_file},
                           {'level': 0, 'dbID': 1, 'parent_ID': 6, 'short_name': 'path', 'long_name': provenance_path}]

        self.setupProvenanceModelData(data_provenance)
        self.model_provenance.setHorizontalHeaderLabels(['Item', 'Value'])
        self.view_provenance = QTreeView()
        self.view_provenance.setModel(self.model_provenance)
        self.view_provenance.setWindowTitle("PROVENANCE")
        self.view_provenance.expandAll()
        self.view_provenance.resizeColumnToContents(0)
        self.view_provenance.setIndentation(0)
        self.view_provenance.setAlternatingRowColors(True)
        self.view_provenance.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view_provenance.resize(1024, 100)

        # Non-editable DICOM attributes section
        self.label_dicom = QLabel()
        self.label_dicom.setText("DICOM attributes")
        self.model_dicom = QtGui.QStandardItemModel()
        data_dicom = [{'level': 0, 'dbID': 0, 'parent_ID': 6, 'short_name': 'DICOM', 'long_name': '', 'order': 1, 'pos': 0} ,
                {'level': 1, 'dbID': 88, 'parent_ID': 0, 'short_name': 'DICOM attributes', 'long_name': '', 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 90, 'parent_ID': 88, 'short_name': 'SeriesDescription', 'long_name': 'localizer AANGEPAST 11 SLICES', 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 91, 'parent_ID': 88, 'short_name': 'SequenceVariant', 'long_name': "['SP', 'OSP']", 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 92, 'parent_ID': 88, 'short_name': 'SequenceName', 'long_name': '*fl2d1', 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 93, 'parent_ID': 88, 'short_name': 'ScanningSequence', 'long_name': 'GR', 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 933, 'parent_ID': 88, 'short_name': 'MRAcquisitionType', 'long_name': '2D', 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 934, 'parent_ID': 88, 'short_name': 'FlipAngle', 'long_name': '20', 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 935, 'parent_ID': 88, 'short_name': 'EchoNumbers', 'long_name': '1', 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 936, 'parent_ID': 88, 'short_name': 'EchoTime', 'long_name': '4', 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 937, 'parent_ID': 88, 'short_name': 'RepetitionTime', 'long_name': '8.6', 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 938, 'parent_ID': 88, 'short_name': 'ImageType', 'long_name': "['ORIGINAL', 'PRIMARY', 'M', 'NORM', 'DIS2D']", 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 939, 'parent_ID': 88, 'short_name': 'ProtocolName', 'long_name': 'localizer AANGEPAST 11 SLICES', 'order': 2, 'pos': 1},
                {'level': 2, 'dbID': 940, 'parent_ID': 88, 'short_name': 'PhaseEncodingDirection', 'long_name': '', 'order': 2, 'pos': 1}
              ]
        self.setupDicomModelData(data_dicom)
        self.model_dicom.setHorizontalHeaderLabels(['Item', 'Value'])
        self.view_dicom = QTreeView()
        self.view_dicom.setModel(self.model_dicom)
        self.view_dicom.setWindowTitle("DICOM attributes")
        self.view_dicom.expandAll()
        self.view_dicom.resizeColumnToContents(0)
        self.view_dicom.setIndentation(0)
        self.view_dicom.setAlternatingRowColors(True)

        self.cblabel = QLabel()
        self.cblabel.setText("MODALITY")
        self.cb = QComboBox()
        self.cb.addItems(["anat", "func", "dwi", "fmap", "beh", "pet"])
        self.cb.currentIndexChanged.connect(self.selectionchange)

        self.label_bids = QLabel()
        self.label_bids .setText("BIDS values")

        self.model_bids = QtGui.QStandardItemModel()
        data = [{'level': 0, 'dbID': 0, 'parent_ID': 6, 'short_name': 'N/A', 'long_name': '', 'order': 1, 'pos': 0}]
        self.model_bids.setHorizontalHeaderLabels(['Item', 'Value'])
        self.view_bids = QTreeView()
        self.view_bids.setModel(self.model_bids)
        self.view_bids.setWindowTitle("BIDS values")
        self.view_bids.expandAll()
        self.view_bids.resizeColumnToContents(0)
        # self.view_dicom.setIndentation(0)
        self.view_bids.setAlternatingRowColors(True)
        self.view_bids.clicked.connect(self.bids_on_clicked)

        self.label_bidsname = QLabel()
        self.label_bidsname.setText("BIDSNAME")

        self.view_bidsname = QTextEdit()
        self.view_bidsname.setReadOnly(True)
        self.view_bidsname.textCursor().insertHtml('N/A')

        self.mapButton = QtWidgets.QPushButton()
        self.mapButton.setObjectName("mapButton")
        self.mapButton.setText("Save")

        layout = QVBoxLayout(self)
        layout.addWidget(self.label_provenance)
        layout.addWidget(self.view_provenance)
        layout.addWidget(self.label_dicom)
        layout.addWidget(self.view_dicom)
        layout.addWidget(self.cblabel)
        layout.addWidget(self.cb)
        layout.addWidget(self.label_bids)
        layout.addWidget(self.view_bids)
        layout.addWidget(self.label_bidsname)
        layout.addWidget(self.view_bidsname)
        layout.addWidget(self.mapButton)

        self.mapButton.clicked.connect(self.close)

    def selectionchange(self, i):
        print("Current index", i, "selection changed ", self.cb.currentText())

        data2 = [{'level': 0, 'dbID': 0, 'parent_ID': 6, 'short_name': 'BIDS', 'long_name': '', 'order': 1, 'pos': 0} ,
                {'level': 1, 'dbID': 94, 'parent_ID': 0, 'short_name': 'BIDS values', 'long_name': '', 'order': 2, 'pos': 1} ,
                {'level': 2, 'dbID': 95, 'parent_ID': 94, 'short_name': 'acq_label', 'long_name': 'localizerAANGEPAST11SLICES', 'order': 2, 'pos': 1} ,
                {'level': 2, 'dbID': 96, 'parent_ID': 94, 'short_name': 'rec_label', 'long_name': '', 'order': 2, 'pos': 1} ,
                {'level': 2, 'dbID': 97, 'parent_ID': 94, 'short_name': 'ce_label', 'long_name': '', 'order': 2, 'pos': 1} ,
                {'level': 2, 'dbID': 971, 'parent_ID': 94, 'short_name': 'task_label', 'long_name': '', 'order': 2, 'pos': 1} ,
                {'level': 2, 'dbID': 972, 'parent_ID': 94, 'short_name': 'echo_index', 'long_name': '', 'order': 2, 'pos': 1} ,
                {'level': 2, 'dbID': 973, 'parent_ID': 94, 'short_name': 'echo_index', 'long_name': '', 'order': 2, 'pos': 1} ,
                {'level': 2, 'dbID': 974, 'parent_ID': 94, 'short_name': 'dir_label', 'long_name': '', 'order': 2, 'pos': 1} ,
                {'level': 2, 'dbID': 975, 'parent_ID': 94, 'short_name': 'run_index', 'long_name': '<<1>>', 'order': 2, 'pos': 1} ,
                {'level': 2, 'dbID': 976, 'parent_ID': 94, 'short_name': 'suffix', 'long_name': '', 'order': 2, 'pos': 1} ,
                {'level': 2, 'dbID': 976, 'parent_ID': 94, 'short_name': 'mod_label', 'long_name': '', 'order': 2, 'pos': 1} ,
                {'level': 2, 'dbID': 976, 'parent_ID': 94, 'short_name': 'modality_label', 'long_name': '', 'order': 2, 'pos': 1} ,
                {'level': 1, 'dbID': 100, 'parent_ID': 0, 'short_name': 'BIDSNAME', 'long_name': 'sub-003_ses-mri01_task-Choice_run-1_echo-1_bold.nii.gz', 'order': 2, 'pos': 1}
              ]

    def bids_on_clicked(self, index):
        item = self.view_bids.selectedIndexes()[0]
        # print(item.model().itemFromIndex(index).text())

    def setupProvenanceModelData(self, lines, root=None):
        self.model_provenance.setRowCount(0)
        if root is None:
            root = self.model_provenance.invisibleRootItem()
        seen = {}
        values = deque(lines)
        while values:
            value = values.popleft()
            if value['level'] == 0:
                parent = root
            else:
                pid = value['parent_ID']
                if pid not in seen:
                    values.append(value)
                    continue
                parent = seen[pid]
            dbid = value['dbID']
            item = QtGui.QStandardItem(value['short_name'])
            item.setEditable(False)
            item2 = QtGui.QStandardItem(value['long_name'])
            item2.setEditable(True)
            parent.appendRow([item, item2])
            seen[dbid] = parent.child(parent.rowCount() - 1)

    def setupDicomModelData(self, lines, root=None):
        self.model_dicom.setRowCount(0)
        if root is None:
            root = self.model_dicom.invisibleRootItem()
        seen = {}
        values = deque(lines)
        while values:
            value = values.popleft()
            if value['level'] == 0:
                parent = root
            else:
                pid = value['parent_ID']
                if pid not in seen:
                    values.append(value)
                    continue
                parent = seen[pid]
            dbid = value['dbID']
            item = QtGui.QStandardItem(value['short_name'])
            item.setEditable(False)
            item2 = QtGui.QStandardItem(value['long_name'])
            item2.setEditable(True)
            parent.appendRow([item, item2])
            seen[dbid] = parent.child(parent.rowCount() - 1)


if __name__ == "__main__":
    default_raw_folder = "M:\\bidscoin\\raw"
    default_input_bidsmap_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
    default_output_bidsmap_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_output.yaml")

    # Parse the input arguments and run bidseditor
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog='examples:\n'
                                            '  bidseditor.py /raw/data/folder /input/bidsmap.yaml /output/bidsmap.yaml\n')
    parser.add_argument('rawfolder', help='The root folder of the directory tree containing the raw files', nargs='?', default=default_raw_folder)
    parser.add_argument('inputbidsmap', help='The input bidsmap YAML-file with the BIDS heuristics', nargs='?', default=default_input_bidsmap_filename)
    parser.add_argument('outputbidsmap', help='The output bidsmap YAML-file with the BIDS heuristics', nargs='?', default=default_output_bidsmap_filename)
    args = parser.parse_args()

    # Validate the arguments
    if not os.path.exists(args.rawfolder):
        raise Exception("Raw folder not found: {}".format(args.rawfolder))

    # Obtain the initial bidsmap info
    filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "tests", "testdata", "bidsmap_example_new.yaml")
    input_bidsmap_yaml = bidsutils.obtain_initial_bidsmap_yaml(args.inputbidsmap)
    input_bidsmap_info = bidsutils.obtain_initial_bidsmap_info(input_bidsmap_yaml)

    # Start the application
    app = QApplication(sys.argv)
    app.setApplicationName("BIDS editor")
    mainwin = QMainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(mainwin, args.rawfolder, args.inputbidsmap, input_bidsmap_yaml, input_bidsmap_info)
    mainwin.show()
    sys.exit(app.exec_())
