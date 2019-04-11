# -*- coding: utf-8 -*-

import sys

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.Qsci import QsciScintilla, QsciLexerYAML

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
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
        self.bidsprepper = QtWidgets.QWidget()
        self.bidsprepper.setObjectName("bidsprepper")

        self.plainTextEdit = QsciScintilla(self.bidsprepper)
        self.__lexer = QsciLexerYAML()
        self.plainTextEdit.setLexer(self.__lexer)
        self.plainTextEdit.setUtf8(True)  # Set encoding to UTF-8
        self.__myFont = QFont("Courier")
        self.__myFont.setPointSize(10)
        self.plainTextEdit.setFont(self.__myFont)
        self.__lexer.setFont(self.__myFont)
        self.plainTextEdit.setGeometry(QtCore.QRect(20, 60, 831, 441))
        self.plainTextEdit.setObjectName("syntaxHighlighter")

        self.pushButton = QtWidgets.QPushButton(self.bidsprepper)
        self.pushButton.setGeometry(QtCore.QRect(20, 20, 93, 28))
        self.pushButton.setObjectName("pushButton")
        self.bidscoin.addTab(self.bidsprepper, "")
        self.bidstrainer = QtWidgets.QWidget()
        self.bidstrainer.setObjectName("bidstrainer")
        self.label = QtWidgets.QLabel(self.bidstrainer)
        self.label.setGeometry(QtCore.QRect(200, 20, 55, 16))
        self.label.setObjectName("label")
        self.label_2 = QtWidgets.QLabel(self.bidstrainer)
        self.label_2.setGeometry(QtCore.QRect(730, 30, 55, 16))
        self.label_2.setObjectName("label_2")
        self.widget = QtWidgets.QWidget(self.bidstrainer)
        self.widget.setGeometry(QtCore.QRect(30, 60, 941, 451))
        self.widget.setObjectName("widget")
        self.horizontalLayout = QtWidgets.QHBoxLayout(self.widget)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.treeWidget = QtWidgets.QTreeWidget(self.widget)
        self.treeWidget.setObjectName("treeWidget")
        self.treeWidget.headerItem().setText(0, "1")
        self.horizontalLayout.addWidget(self.treeWidget)
        self.pushButton_2 = QtWidgets.QPushButton(self.widget)
        self.pushButton_2.setObjectName("pushButton_2")
        self.horizontalLayout.addWidget(self.pushButton_2)
        self.treeWidget_2 = QtWidgets.QTreeWidget(self.widget)
        self.treeWidget_2.setObjectName("treeWidget_2")
        self.treeWidget_2.headerItem().setText(0, "1")
        self.horizontalLayout.addWidget(self.treeWidget_2)
        self.bidscoin.addTab(self.bidstrainer, "")
        self.bidsmapper = QtWidgets.QWidget()
        self.bidsmapper.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        self.bidsmapper.setObjectName("bidsmapper")
        self.pushButton_3 = QtWidgets.QPushButton(self.bidsmapper)
        self.pushButton_3.setGeometry(QtCore.QRect(440, 220, 93, 28))
        self.pushButton_3.setObjectName("pushButton_3")
        self.bidscoin.addTab(self.bidsmapper, "")
        self.bidscoiner = QtWidgets.QWidget()
        self.bidscoiner.setObjectName("bidscoiner")
        self.pushButton_4 = QtWidgets.QPushButton(self.bidscoiner)
        self.pushButton_4.setGeometry(QtCore.QRect(470, 230, 93, 28))
        self.pushButton_4.setObjectName("pushButton_4")
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
        MainWindow.setTabOrder(self.bidscoin, self.pushButton)
        MainWindow.setTabOrder(self.pushButton, self.plainTextEdit)
        MainWindow.setTabOrder(self.plainTextEdit, self.treeWidget_2)
        MainWindow.setTabOrder(self.treeWidget_2, self.pushButton_2)
        MainWindow.setTabOrder(self.pushButton_2, self.treeWidget)
        MainWindow.setTabOrder(self.treeWidget, self.pushButton_3)
        MainWindow.setTabOrder(self.pushButton_3, self.pushButton_4)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "BIDScoin"))
        self.bidscoin.setToolTip(_translate("MainWindow", "<html><head/><body><p>bidscoiner</p></body></html>"))
        self.plainTextEdit.setText(_translate("MainWindow", "# --------------------------------------------------------------------------------\n"
"# This is a bidsmap YAML file with the key-value mappings for the different BIDS\n"
"# modalities (anat, func, dwi, etc). The modality attributes are the keys that map\n"
"# onto the BIDS labels. The bidsmap data-structure should be 5 levels deep:\n"
"# dict > dict > list > dict > dict\n"
"#\n"
"# NB:\n"
"# 1) Edit the bidsmap file to your needs before feeding it to bidscoiner.py\n"
"# 2) (Institute) users may create their own bidsmap_[template].yaml or\n"
"#    bidsmap_[sample].yaml file\n"
"#\n"
"# For more information, see:\n"
"# https://github.com/Donders-Institute/bidscoin\n"
"# https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html\n"
"# --------------------------------------------------------------------------------\n"
"\n"
"\n"
"Options:\n"
"# --------------------------------------------------------------------------------\n"
"# General options\n"
"# --------------------------------------------------------------------------------\n"
"  version: 1.6                    # BIDScoin version (should correspond with the version in ../bidscoin/version.txt)\n"
"  dcm2niix:                       # See dcm2niix -h and https://www.nitrc.org/plugins/mwiki/index.php/dcm2nii:MainPage#General_Usage for more info\n"
"    path: module add dcm2niix;    # Command to set the path to dcm2niix (note the semi-colon), e.g. module add dcm2niix/1.0.20180622; or PATH=/opt/dcm2niix/bin:$PATH; or /opt/dcm2niix/bin/ or \'\"C:\\Program Files\\dcm2niix\\\"\' (note the quotes to deal with the whitespace)\n"
"    args: -b y -z y -i n          # Argument string that is passed to dcm2niix. Tip: SPM users may want to use \'-z n\' (which produces unzipped nifti\'s, see dcm2niix -h for more information)\n"
"\n"
"\n"
"DICOM:\n"
"# --------------------------------------------------------------------------------\n"
"# DICOM key-value heuristics (DICOM fields that are mapped to the BIDS labels)\n"
"# --------------------------------------------------------------------------------\n"
"  participant_label: ~            # A <<DICOM attribute>> that is used as participant_label instead of the subject-label from the sourcefolder\n"
"  session_label: ~                # A <<DICOM attribute>> that is used as session_label instead of the session-label from the sourcefolder\n"
"  anat:       # ----------------------- All anatomical series --------------------\n"
"  - attributes: &anatattributes\n"
"      SeriesDescription: ~\n"
"      SequenceVariant: ~\n"
"      SequenceName: ~\n"
"      ScanningSequence: ~\n"
"      MRAcquisitionType: ~\n"
"      FlipAngle: ~\n"
"      EchoNumbers: ~\n"
"      EchoTime: ~\n"
"      RepetitionTime: ~\n"
"      ImageType: ~\n"
"      ProtocolName: ~\n"
"      PhaseEncodingDirection: ~\n"
"    bids: &anatbids\n"
"      acq_label: <SeriesDescription>\n"
"      rec_label: ~\n"
"      run_index: <<1>>\n"
"      mod_label: ~\n"
"      modality_label: T1w\n"
"      ce_label: ~\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: T2w\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: T1rho\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: T1map\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: T2map\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: T2star\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: FLAIR\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: FLASH\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: PD\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: PDmap\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: PDT2\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: inplaneT1\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: inplaneT2\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: angio\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: defacemask\n"
"  - attributes: *anatattributes\n"
"    bids:\n"
"      <<: *anatbids\n"
"      modality_label: SWImagandphase\n"
"\n"
"  func:       # ----------------------- All functional series --------------------\n"
"  - attributes: &funcattributes\n"
"      SeriesDescription: ~\n"
"      SequenceVariant: ~\n"
"      SequenceName: ~\n"
"      ScanningSequence: ~\n"
"      MRAcquisitionType: ~\n"
"      FlipAngle: ~\n"
"      EchoNumbers: ~\n"
"      EchoTime: ~\n"
"      RepetitionTime: ~\n"
"      ImageType: ~\n"
"      ProtocolName: ~\n"
"      PhaseEncodingDirection: ~\n"
"    bids: &funcbids\n"
"      task_label: <SeriesDescription>\n"
"      acq_label: ~\n"
"      rec_label: ~\n"
"      run_index: <<1>>\n"
"      echo_index: <EchoNumbers>\n"
"      suffix: bold\n"
"  - attributes: *funcattributes\n"
"    bids:\n"
"      <<: *funcbids\n"
"      suffix: sbref\n"
"\n"
"  dwi:        # ----------------------- All diffusion series ---------------------\n"
"  - attributes: &dwiattributes\n"
"      SeriesDescription: ~\n"
"      SequenceVariant: ~\n"
"      SequenceName: ~\n"
"      ScanningSequence: ~\n"
"      MRAcquisitionType: ~\n"
"      FlipAngle: ~\n"
"      EchoNumbers: ~\n"
"      EchoTime: ~\n"
"      RepetitionTime: ~\n"
"      ImageType: ~\n"
"      ProtocolName: ~\n"
"      PhaseEncodingDirection: ~\n"
"    bids: &dwibids\n"
"      acq_label: <SeriesDescription>\n"
"      run_index: <<1>>\n"
"      suffix: dwi\n"
"  - attribute: *dwiattributes\n"
"    bids:\n"
"      <<: *dwibids\n"
"      suffix: sbref\n"
"\n"
"  fmap:       # ----------------------- All fieldmap series ----------------------\n"
"  - attributes: &fmapattributes\n"
"      SeriesDescription: ~\n"
"      SequenceVariant: ~\n"
"      SequenceName: ~\n"
"      ScanningSequence: ~\n"
"      MRAcquisitionType: ~\n"
"      FlipAngle: ~\n"
"      EchoNumbers: ~\n"
"      EchoTime: ~\n"
"      RepetitionTime: ~\n"
"      ImageType: ~\n"
"      ProtocolName: ~\n"
"      PhaseEncodingDirection: ~\n"
"    bids: &fmapbids\n"
"      acq_label: <SeriesDescription>\n"
"      run_index: <<1>>\n"
"      dir_label: ~\n"
"      suffix: magnitude\n"
"      IntendedFor: ~\n"
"  - attributes: *fmapattributes\n"
"    bids:\n"
"      <<: *fmapbids\n"
"      suffix: magnitude1\n"
"  - attributes: *fmapattributes\n"
"    bids:\n"
"      <<: *fmapbids\n"
"      suffix: magnitude2\n"
"  - attributes: *fmapattributes\n"
"    bids:\n"
"      <<: *fmapbids\n"
"      suffix: phasediff\n"
"  - attributes: *fmapattributes\n"
"    bids:\n"
"      <<: *fmapbids\n"
"      suffix: phase1\n"
"  - attributes: *fmapattributes\n"
"    bids:\n"
"      <<: *fmapbids\n"
"      suffix: phase2\n"
"  - attributes: *fmapattributes\n"
"    bids:\n"
"      <<: *fmapbids\n"
"      suffix: fieldmap\n"
"  - attributes: *fmapattributes\n"
"    bids:\n"
"      <<: *fmapbids\n"
"      dir_label: <InPlanePhaseEncodingDirection>\n"
"  - attributes: *fmapattributes\n"
"    bids:\n"
"      <<: *fmapbids\n"
"      suffix: epi\n"
"    # TODO: sub-<participant_label>[_ses-<session_label>][_acq-<label>]_dir-<dir_label>[_run-<run_index>]_epi.nii[.gz]\n"
"\n"
"  beh:        # ----------------------- All behavioural data ---------------------\n"
"  - attributes: &behattributes\n"
"      SeriesDescription: ~\n"
"      SequenceVariant: ~\n"
"      SequenceName: ~\n"
"      ScanningSequence: ~\n"
"      MRAcquisitionType: ~\n"
"      FlipAngle: ~\n"
"      EchoNumbers: ~\n"
"      EchoTime: ~\n"
"      RepetitionTime: ~\n"
"      ImageType: ~\n"
"      ProtocolName: ~\n"
"    bids: &behbids\n"
"      task_name: <SeriesDescription>\n"
"      suffix: ~\n"
"\n"
"  pet:        # ----------------------- All PET series ---------------------------\n"
"  - attributes: &petattributes\n"
"      SeriesDescription: ~\n"
"      Radiopharmaceutical: ~\n"
"      SliceThickness: ~\n"
"      PixelSpacing: ~\n"
"      Rows: ~\n"
"      Columns: ~\n"
"      ImageType: ~\n"
"    bids: &petbids\n"
"      task_label: <SeriesDescription>\n"
"      acq_label: <Radiopharmaceutical>\n"
"      rec_label: ~\n"
"      run_index: <<1>>\n"
"      suffix: pet\n"
"\n"
"  extra_data: # ----------------------- All extra data ---------------------------\n"
"  - attributes:\n"
"      SeriesDescription: ~\n"
"      SequenceVariant: ~\n"
"      SequenceName: ~\n"
"      ScanningSequence: ~\n"
"      MRAcquisitionType: ~\n"
"      FlipAngle: ~\n"
"      EchoNumbers: ~\n"
"      EchoTime: ~\n"
"      RepetitionTime: ~\n"
"      ImageType: ~\n"
"      ProtocolName: ~\n"
"      PhaseEncodingDirection: ~\n"
"    bids:\n"
"      acq_label: <SeriesDescription>\n"
"      rec_label: ~\n"
"      ce_label: ~\n"
"      task_label: ~\n"
"      echo_index: ~\n"
"      dir_label: ~\n"
"      run_index: <<1>>\n"
"      suffix: ~\n"
"      mod_label: ~\n"
"      modality_label: ~\n"
"\n"
"\n"
"PAR: ~\n"
"# --------------------------------------------------------------------------------\n"
"# PAR key-value heuristics (Philips PAR fields that are mapped to the BIDS labels)\n"
"# --------------------------------------------------------------------------------\n"
"\n"
"\n"
"P7: ~\n"
"# --------------------------------------------------------------------------------\n"
"# P*.7 key-value heuristics (GE fields that are mapped to the BIDS labels)\n"
"# --------------------------------------------------------------------------------\n"
"\n"
"\n"
"Nifti: ~\n"
"# --------------------------------------------------------------------------------\n"
"# Nifti key-value heuristics (Nifti fields that are mapped to the BIDS labels)\n"
"# --------------------------------------------------------------------------------\n"
"\n"
"\n"
"FileSystem:\n"
"# --------------------------------------------------------------------------------\n"
"# File system key-value heuristics (these file- and foldernames will be mapped\n"
"# to the BIDS labels; Special substitutions can be performed using python\'s\n"
"# Format Specification Mini-Language)\n"
"# --------------------------------------------------------------------------------\n"
"  participant_label: ~\n"
"  session_label: ~\n"
"  anat:       # ----------------------- All anatomical series --------------------\n"
"  - attributes: &anatattributes_file\n"
"      FolderName: ~\n"
"      FileName: ~\n"
"      FileExt: ~\n"
"    bids: &anatbids_file\n"
"      acq_label: <FileName>\n"
"      rec_label: ~\n"
"      ce_label: ~\n"
"      task_label: ~\n"
"      echo_index: ~\n"
"      dir_label: ~\n"
"      run_index: <<1>>\n"
"      suffix: ~\n"
"      mod_label: ~\n"
"      modality_label: T1w\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: T2w\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: T1rho\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: T1map\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: T2map\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: T2star\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: FLAIR\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: FLASH\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: PD\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: PDmap\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: PDT2\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: inplaneT1\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: inplaneT2\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: angio\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: defacemask\n"
"  - attributes: *anatattributes_file\n"
"    bids:\n"
"      <<: *anatbids_file\n"
"      modality_label: SWImagandphase\n"
"\n"
"  func:       # ----------------------- All functional series --------------------\n"
"  - attributes: &funcattributes_file\n"
"      FolderName: ~\n"
"      FileName: ~\n"
"      FileExt: ~\n"
"    bids: &funcbids_file\n"
"      task_label: <FileName>\n"
"      acq_label: ~\n"
"      rec_label: ~\n"
"      run_index: <<1>>\n"
"      echo_index: ~\n"
"      suffix: bold\n"
"  - attributes: *funcattributes_file\n"
"    bids:\n"
"      <<: *funcbids_file\n"
"      suffix: sbref\n"
"  - attributes: *funcattributes_file\n"
"    bids:\n"
"      <<: *funcbids_file\n"
"      suffix: events\n"
"  - attributes: *funcattributes_file\n"
"    bids:\n"
"      <<: *funcbids_file\n"
"      recording_label: <FileName>\n"
"      suffix: physio\n"
"  - attributes: *funcattributes_file\n"
"    bids:\n"
"      <<: *funcbids_file\n"
"      recording_label: <FileName>\n"
"      suffix: stim\n"
"\n"
"  dwi:        # ----------------------- All diffusion series ---------------------\n"
"  - attributes: &dwiattributes_file\n"
"      FolderName: ~\n"
"      FileName: ~\n"
"      FileExt: ~\n"
"    bids: &dwibids_file\n"
"      acq_label: <FileName>\n"
"      run_index: <<1>>\n"
"      suffix: dwi\n"
"\n"
"  fmap:       # ----------------------- All fieldmap series ----------------------\n"
"  - attributes: &fmapattributes_file\n"
"      FolderName: ~\n"
"      FileName: ~\n"
"      FileExt: ~\n"
"    bids: &fmapbids_file\n"
"      acq_label: <FileName>\n"
"      run_index: <<1>>\n"
"      dir_label: ~\n"
"      suffix: magnitude1\n"
"      IntendedFor: ~\n"
"  - attributes: *fmapattributes_file\n"
"    bids:\n"
"      <<: *fmapbids_file\n"
"      suffix: magnitude2\n"
"  - attributes: *fmapattributes_file\n"
"    bids:\n"
"      <<: *fmapbids_file\n"
"      suffix: phasediff\n"
"  - attributes: *fmapattributes_file\n"
"    bids:\n"
"      <<: *fmapbids_file\n"
"      suffix: phase1\n"
"  - attributes: *fmapattributes_file\n"
"    bids:\n"
"      <<: *fmapbids_file\n"
"      suffix: phase2\n"
"  - attributes: *fmapattributes_file\n"
"    bids:\n"
"      <<: *fmapbids_file\n"
"      suffix: magnitude\n"
"  - attributes: *fmapattributes_file\n"
"    bids:\n"
"      <<: *fmapbids_file\n"
"      suffix: fieldmap\n"
"      # TODO: sub-<participant_label>[_ses-<session_label>][_acq-<label>]_dir-<dir_label>[_run-<run_index>]_epi.nii[.gz]\n"
"\n"
"  beh:        # ----------------------- All behavioural data ---------------------\n"
"  - attributes:\n"
"      FolderName: ~\n"
"      FileName: ~\n"
"      FileExt: ~\n"
"    bids:\n"
"      task_label: <FileName>\n"
"      suffix: ~\n"
"\n"
"  extra_data: # ----------------------- All extra data ---------------------------\n"
"  - attributes:\n"
"      FolderName: ~\n"
"      FileName: ~\n"
"      FileExt: ~\n"
"    bids:\n"
"      acq_label: <SeriesDescription>\n"
"      rec_label: ~\n"
"      ce_label: ~\n"
"      task_label: ~\n"
"      echo_index: ~\n"
"      dir_label: ~\n"
"      run_index: <<1>>\n"
"      suffix: ~\n"
"      mod_label: ~\n"
"      modality_label: ~\n"
"\n"
"\n"
"PlugIn: ~\n"
"# --------------------------------------------------------------------------------\n"
"# List of plugins to edit the key-value heuristics / perform additional operations\n"
"# --------------------------------------------------------------------------------"))
        self.pushButton.setText(_translate("MainWindow", "Save"))
        self.bidscoin.setTabText(self.bidscoin.indexOf(self.bidsprepper), _translate("MainWindow", "BIDSprepper"))
        self.label.setText(_translate("MainWindow", "Source"))
        self.label_2.setText(_translate("MainWindow", "Target"))
        self.pushButton_2.setText(_translate("MainWindow", "=>"))
        self.bidscoin.setTabText(self.bidscoin.indexOf(self.bidstrainer), _translate("MainWindow", "BIDStrainer"))
        self.bidsmapper.setToolTip(_translate("MainWindow", "bidsmapper"))
        self.pushButton_3.setText(_translate("MainWindow", "Map"))
        self.bidscoin.setTabText(self.bidscoin.indexOf(self.bidsmapper), _translate("MainWindow", "BIDSmapper"))
        self.pushButton_4.setText(_translate("MainWindow", "Coin"))
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
    app = QApplication(sys.argv)
    mainwin = QMainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(mainwin)
    mainwin.show()
    sys.exit(app.exec_())