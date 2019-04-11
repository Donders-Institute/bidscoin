# -*- coding: utf-8 -*-

import os
import sys

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileSystemModel, QTreeView, QVBoxLayout, QLabel
from PyQt5.Qsci import QsciScintilla, QsciLexerYAML


def read_yaml():
    """ """
    contents = ""
    filename = os.path.join("..", "tests", "testdata", "bidsmap_example_new.yaml")
    with open(filename) as fp:
        contents = fp.read()
    return contents


class Ui_MainWindow(object):

    def setupUi(self, MainWindow, example_yaml):
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

        self.bidstrainer = QtWidgets.QWidget()
        self.bidstrainer.setObjectName("bidstrainer")
        self.bidscoin.addTab(self.bidstrainer, "")

        self.bidsmapper = QtWidgets.QWidget()
        self.bidsmapper.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        self.bidsmapper.setObjectName("bidsmapper")
        self.bidscoin.addTab(self.bidsmapper, "")

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
        self.actionABout = QtWidgets.QAction(MainWindow)
        self.actionABout.setObjectName("actionABout")
        self.menuFile.addAction(self.actionExit)
        self.menuHelp.addAction(self.actionABout)
        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())

        self.retranslateUi(MainWindow)
        self.bidscoin.setCurrentIndex(1)
        self.actionExit.triggered.connect(MainWindow.close)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "BIDScoin"))
        self.bidscoin.setToolTip(_translate("MainWindow", "<html><head/><body><p>bidscoiner</p></body></html>"))
        self.plainTextEdit.setText(_translate("MainWindow", example_yaml))


        self.bidscoin.setTabText(self.bidscoin.indexOf(self.filebrowser), _translate("MainWindow", "Filebrowser"))

        self.bidscoin.setTabText(self.bidscoin.indexOf(self.bidstrainer), _translate("MainWindow", "BIDStrainer"))
        self.bidsmapper.setToolTip(_translate("MainWindow", "bidsmapper"))

        self.bidscoin.setTabText(self.bidscoin.indexOf(self.bidsmapper), _translate("MainWindow", "BIDSmapper"))

        self.bidscoin.setTabText(self.bidscoin.indexOf(self.bidsmap), _translate("MainWindow", "BIDSmap"))
        self.pushButton.setText(_translate("MainWindow", "Save"))

        self.bidscoin.setTabText(self.bidscoin.indexOf(self.bidscoiner), _translate("MainWindow", "BIDScoiner"))

        self.menuFile.setTitle(_translate("MainWindow", "File"))
        self.menuHelp.setTitle(_translate("MainWindow", "Help"))
        self.statusbar.setStatusTip(_translate("MainWindow", "Text in statusbar"))
        self.actionNew.setText(_translate("MainWindow", "New"))
        self.actionNew.setShortcut(_translate("MainWindow", "Ctrl+N"))
        self.actionExit.setText(_translate("MainWindow", "Exit"))
        self.actionExit.setStatusTip(_translate("MainWindow", "Click to exit the application"))
        self.actionExit.setShortcut(_translate("MainWindow", "Ctrl+X"))
        self.actionABout.setText(_translate("MainWindow", "About"))

if __name__ == "__main__":
    example_yaml = read_yaml()
    app = QApplication(sys.argv)
    mainwin = QMainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(mainwin, example_yaml)
    mainwin.show()
    sys.exit(app.exec_())
