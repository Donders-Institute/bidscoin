# -*- coding: utf-8 -*-

import os
import sys
import ruamel.yaml as yaml

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileSystemModel, QTreeView, QVBoxLayout, QLabel, QPushButton, QDialog, QPlainTextEdit
from PyQt5.Qsci import QsciScintilla, QsciLexerYAML


def read_yaml():
    """ """
    contents = ""
    filename = os.path.join("..", "tests", "testdata", "bidsmap_example_new.yaml")
    with open(filename) as fp:
        contents = fp.read()
    return contents


def derive_list_unknowns(example_yaml):
    """Derive the list of unknown files. """
    list_unknown = []

    contents = {}
    try:
        contents = yaml.safe_load(example_yaml)
    except yaml.YAMLError as exc:
        raise InvalidUsage('Error: %s' % exc, status_code=410)

    contents = contents.get('DICOM', {})
    for item in contents.get('extra_data', []):
        provenance = item.get('provenance', None)
        if provenance:
            list_unknown.append({
                "provenance_path": os.path.dirname(provenance),
                "provenance_file": os.path.basename(provenance)
            })
    return list_unknown


class Ui_MainWindow(object):

    def setupUi(self, MainWindow, example_yaml, list_unknowns):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1024, 580)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap("brain.ico"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        MainWindow.setWindowIcon(icon)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        self.centralwidget.setObjectName("centralwidget")

        self.bidscoin = QtWidgets.QTabWidget(self.centralwidget)
        self.bidscoin.setGeometry(QtCore.QRect(0, 0, 1021, 541))
        self.bidscoin.setTabPosition(QtWidgets.QTabWidget.North)
        self.bidscoin.setTabShape(QtWidgets.QTabWidget.Rounded)
        self.bidscoin.setObjectName("bidscoin")

        self.tab1 = QtWidgets.QWidget()
        self.tab1.layout = QVBoxLayout(self.centralwidget)
        self.label = QLabel()
        self.label.setText("Raw folder: M:\\bidscoin\\raw")
        self.model = QFileSystemModel()
        self.model.setRootPath('')
        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setAnimated(False)
        self.tree.setIndentation(20)
        self.tree.setSortingEnabled(True)
        self.tree.setRootIndex(self.model.index("M:\\bidscoin\\raw"))
        self.tab1.layout.addWidget(self.label)
        self.tab1.layout.addWidget(self.tree)
        self.filebrowser = QtWidgets.QWidget()
        self.filebrowser.setLayout(self.tab1.layout)
        self.filebrowser.setObjectName("filebrowser")
        self.bidscoin.addTab(self.filebrowser, "")

        self.tab2 = QtWidgets.QWidget()
        self.tab2.layout = QVBoxLayout(self.centralwidget)
        self.labelBidstrainer = QLabel()
        self.labelBidstrainer.setText("Action needed:")
        self.unknownsText = QPlainTextEdit()
        self.mapButton = QtWidgets.QPushButton()
        self.mapButton.setGeometry(QtCore.QRect(20, 20, 93, 28))
        self.mapButton.setObjectName("mapButton")
        self.tab2.layout.addWidget(self.mapButton)
        self.tab2.layout.addWidget(self.labelBidstrainer)
        self.tab2.layout.addWidget(self.unknownsText)
        self.bidstrainer = QtWidgets.QWidget()
        self.bidstrainer.setObjectName("bidstrainer")
        self.bidstrainer.setLayout(self.tab2.layout)
        self.bidscoin.addTab(self.bidstrainer, "")

        self.bidsmap = QtWidgets.QWidget()
        self.bidsmap.setObjectName("bidsmap")
        self.plainTextEdit = QsciScintilla(self.bidsmap)
        self.__lexer = QsciLexerYAML()
        self.plainTextEdit.setLexer(self.__lexer)
        self.plainTextEdit.setUtf8(True)  # Set encoding to UTF-8
        self.__myFont = QFont("Courier")
        self.__myFont.setPointSize(10)
        self.plainTextEdit.setFont(self.__myFont)
        self.__lexer.setFont(self.__myFont)
        self.plainTextEdit.setGeometry(QtCore.QRect(20, 60, 831, 441))
        self.plainTextEdit.setObjectName("syntaxHighlighter")
        self.pushButton = QtWidgets.QPushButton(self.bidsmap)
        self.pushButton.setGeometry(QtCore.QRect(20, 20, 93, 28))
        self.pushButton.setObjectName("pushButton")
        self.bidscoin.addTab(self.bidsmap, "")

        self.bidscoiner = QtWidgets.QWidget()
        self.bidscoiner.setObjectName("bidscoiner")
        self.convertButton = QtWidgets.QPushButton(self.bidscoiner)
        self.convertButton.setGeometry(QtCore.QRect(20, 20, 93, 28))
        self.convertButton.setObjectName("convertButton")
        self.bidscoin.addTab(self.bidscoiner, "")

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
        self.statusbar.setToolTip("")
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.actionNew = QtWidgets.QAction(MainWindow)
        self.actionNew.setObjectName("actionNew")

        self.actionExit = QtWidgets.QAction(MainWindow)
        self.actionExit.setObjectName("actionExit")
        self.actionExit.triggered.connect(MainWindow.close)

        self.actionAbout = QtWidgets.QAction(MainWindow)
        self.actionAbout.setObjectName("actionAbout")
        self.actionAbout.triggered.connect(self.showAbout)

        self.menuFile.addAction(self.actionExit)
        self.menuHelp.addAction(self.actionAbout)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())

        self.retranslateUi(MainWindow, example_yaml, list_unknowns)
        self.bidscoin.setCurrentIndex(1)

        QtCore.QMetaObject.connectSlotsByName(MainWindow)


    def retranslateUi(self, MainWindow, example_yaml, list_unknowns):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "BIDScoin"))
        self.bidscoin.setToolTip(_translate("MainWindow", "<html><head/><body><p>bidscoiner</p></body></html>"))

        self.plainTextEdit.setText(_translate("MainWindow", example_yaml))

        unknowns = "\n".join([x["provenance_file"] for x in list_unknowns])
        self.unknownsText.setPlainText(_translate("MainWindow", unknowns))

        self.bidscoin.setTabText(self.bidscoin.indexOf(self.filebrowser), _translate("MainWindow", "Filebrowser"))

        self.bidscoin.setTabText(self.bidscoin.indexOf(self.bidstrainer), _translate("MainWindow", "BIDStrainer"))
        self.mapButton.setText(_translate("MainWindow", "Commit changes"))

        self.bidscoin.setTabText(self.bidscoin.indexOf(self.bidsmap), _translate("MainWindow", "BIDSmap"))
        self.pushButton.setText(_translate("MainWindow", "Save"))

        self.bidscoin.setTabText(self.bidscoin.indexOf(self.bidscoiner), _translate("MainWindow", "BIDScoiner"))
        self.convertButton.setText(_translate("MainWindow", "Convert"))

        self.menuFile.setTitle(_translate("MainWindow", "File"))
        self.menuHelp.setTitle(_translate("MainWindow", "Help"))
        self.statusbar.setStatusTip(_translate("MainWindow", "Text in statusbar"))
        self.actionExit.setText(_translate("MainWindow", "Exit"))
        self.actionExit.setStatusTip(_translate("MainWindow", "Click to exit the application"))
        self.actionExit.setShortcut(_translate("MainWindow", "Ctrl+X"))
        self.actionAbout.setText(_translate("MainWindow", "About"))


    def showAbout(self):
        """ """
        self.dlg = AboutDialog()
        self.dlg.show()


class AboutDialog(QDialog):
    def __init__(self):
        QDialog.__init__(self)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        label = QLabel()
        label.setText("BIDScoin GUI")
        self.pushButton = QPushButton("OK")
        self.pushButton.setToolTip("Close dialog")
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        layout.addWidget(self.pushButton)
        self.pushButton.clicked.connect(self.close)



if __name__ == "__main__":
    example_yaml = read_yaml()
    list_unknowns = derive_list_unknowns(example_yaml)

    app = QApplication(sys.argv)
    mainwin = QMainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(mainwin, example_yaml, list_unknowns)
    mainwin.show()
    sys.exit(app.exec_())
