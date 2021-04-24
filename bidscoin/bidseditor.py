#!/usr/bin/env python3
"""
This tool launches a graphical user interface for editing the bidsmap.yaml file
that is produced by the bidsmapper. The user can fill in or change the BIDS labels
for entries that are unidentified or sub-optimal, such that meaningful and nicely
readable BIDS output names will be generated. The saved bidsmap.yaml output file
will be used by the bidscoiner to actually convert the source data to BIDS.

You can hoover with your mouse over items to get help text (pop-up tooltips).
"""

import sys
import argparse
import textwrap
import logging
import copy
import webbrowser
import pydicom
from pathlib import Path
from functools import partial
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileSystemModel, QFileDialog, QDialogButtonBox,
                             QTreeView, QHBoxLayout, QVBoxLayout, QLabel, QDialog, QMessageBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QTextBrowser,
                             QAbstractItemView, QPushButton, QComboBox, QDesktopWidget, QAction)

try:
    from bidscoin import bidscoin, bids
except ImportError:
    import bidscoin, bids             # This should work if bidscoin was not pip-installed


ROW_HEIGHT       = 22
BIDSCOIN_LOGO    = Path(__file__).parent/'bidscoin_logo.png'
BIDSCOIN_ICON    = Path(__file__).parent/'bidscoin.ico'
RIGHTARROW       = Path(__file__).parent/'rightarrow.png'

MAIN_HELP_URL    = f"https://bidscoin.readthedocs.io/en/{bidscoin.version()}"
HELP_URL_DEFAULT = f"https://bids-specification.readthedocs.io/en/v{bidscoin.bidsversion()}"
HELP_URLS        = {
    'anat': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#anatomy-imaging-data",
    'dwi' : f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#diffusion-imaging-data",
    'fmap': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data",
    'func': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#task-including-resting-state-imaging-data",
    'perf': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#arterial-spin-labeling-perfusion-data",
    'eeg' : f"{HELP_URL_DEFAULT}/04-modality-specific-files/03-electroencephalography.html",
    'ieeg': f"{HELP_URL_DEFAULT}/04-modality-specific-files/04-intracranial-electroencephalography.html",
    'beh' : f"{HELP_URL_DEFAULT}/04-modality-specific-files/07-behavioral-experiments.html",
    'pet' : f"{HELP_URL_DEFAULT}/04-modality-specific-files/09-positron-emission-tomography.html",
    bids.unknowndatatype: HELP_URL_DEFAULT,
    bids.ignoredatatype : HELP_URL_DEFAULT
}

TOOLTIP_BIDSCOIN = """BIDScoin
version:    should correspond with the version in ../bidscoin/version.txt
bidsignore: Semicolon-separated list of entries that are added to the .bidsignore file
            (for more info, see BIDS specifications), e.g. extra_data/;myfile.txt;yourfile.csv"""

TOOLTIP_DCM2NIIX = """dcm2niix
path: Command to set the path to dcm2niix, e.g.:
      module add dcm2niix/1.0.20180622; (note the semi-colon at the end)
      PATH=/opt/dcm2niix/bin:$PATH; (note the semi-colon at the end)
      /opt/dcm2niix/bin/  (note the slash at the end)
      '\"C:\\Program Files\\dcm2niix\"' (note the quotes to deal with the whitespace)
args: Argument string that is passed to dcm2niix. Click [Test] and see the terminal output for usage
      Tip: SPM users may want to use '-z n', which produces unzipped nifti's"""


class MyQTableWidget(QTableWidget):

    def __init__(self, minimum: bool=True):
        super().__init__()

        self.setAlternatingRowColors(False)
        self.setShowGrid(False)

        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.setMinimumHeight(2 * (ROW_HEIGHT + 8))
        self.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)

        self.minimizeheight(minimum)

    def minimizeheight(self, minimum: bool=True):
        """Set the vertical QSizePolicy to Minimum"""

        self.minimum = minimum

        if minimum:
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        else:
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)


class MyWidgetItem(QTableWidgetItem):

    def __init__(self, value: str='', iseditable: bool=True):
        """A QTableWidgetItem that is editable or not"""
        super().__init__()

        if isinstance(value, int):
            value = str(value)
        self.setText(value)
        self.seteditable(iseditable)

    def seteditable(self, iseditable: bool=True):
        """Make the WidgetItem editable"""

        self.iseditable = iseditable

        if iseditable:
            self.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable)
            self.setForeground(QtGui.QColor('black'))
        else:
            self.setFlags(QtCore.Qt.ItemIsEnabled)
            self.setForeground(QtGui.QColor('gray'))


class InspectWindow(QDialog):

    def __init__(self, filename: Path):
        super().__init__()

        if bids.is_dicomfile(filename):
            text = str(pydicom.dcmread(filename, force=True))
        elif bids.is_parfile(filename):
            text = filename.read_text()
        else:
            text = f"Could not inspect: {filename}"
            LOGGER.info(text)

        self.setWindowIcon(QtGui.QIcon(str(BIDSCOIN_ICON)))
        self.setWindowTitle(str(filename))

        layout = QVBoxLayout(self)

        textbrowser = QTextBrowser(self)
        textbrowser.setFont(QtGui.QFont("Courier New"))
        textbrowser.insertPlainText(text)
        textbrowser.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        self.scrollbar = textbrowser.verticalScrollBar()        # For setting the slider to the top (can only be done after self.show()
        layout.addWidget(textbrowser)

        buttonbox = QDialogButtonBox(self)
        buttonbox.setStandardButtons(QDialogButtonBox.Ok)
        buttonbox.button(QDialogButtonBox.Ok).setToolTip('Close this window')
        buttonbox.accepted.connect(self.close)
        layout.addWidget(buttonbox)

        # Set the layout-width to the width of the text
        fontmetrics = QtGui.QFontMetrics(textbrowser.font())
        textwidth   = fontmetrics.size(0, text).width()
        self.resize(min(textwidth + 70, 1200), self.height())


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        actionquit = QAction('Quit', self)
        actionquit.triggered.connect(self.closeEvent)

        self.setWindowIcon(QtGui.QIcon(str(BIDSCOIN_ICON)))

    def closeEvent(self, event):
        """Handle exit. """
        QApplication.quit()     # TODO: Do not use class method but self.something


class UiMainWindow(MainWindow):

    def setupui(self, MainWindow, bidsfolder, bidsmap_filename, input_bidsmap, output_bidsmap, template_bidsmap,
                subprefix='sub-', sesprefix='ses-', reload: bool=False):

        # Set the input data
        self.MainWindow       = MainWindow
        self.bidsfolder       = Path(bidsfolder)
        self.bidsmap_filename = Path(bidsmap_filename)
        self.input_bidsmap    = input_bidsmap
        self.output_bidsmap   = output_bidsmap
        self.template_bidsmap = template_bidsmap
        self.subprefix        = subprefix
        self.sesprefix        = sesprefix
        self.dataformats      = [dataformat for dataformat in input_bidsmap if dataformat not in ('Options', 'PlugIns') and bids.dir_bidsmap(input_bidsmap, dataformat)]

        self.has_editwindow_open = None

        # Set-up the tabs
        tabwidget = self.tabwidget = QtWidgets.QTabWidget()
        tabwidget.setTabPosition(QtWidgets.QTabWidget.North)
        tabwidget.setTabShape(QtWidgets.QTabWidget.Rounded)

        self.subses_table       = {}
        self.samples_table      = {}
        self.ordered_file_index = {}
        for dataformat in self.dataformats:
            self.set_tab_bidsmap(dataformat)
        self.set_tab_options()
        self.set_tab_file_browser()

        # Set-up the buttons
        buttonbox = QDialogButtonBox()
        buttonbox.setStandardButtons(QDialogButtonBox.Save | QDialogButtonBox.Reset | QDialogButtonBox.Help)
        buttonbox.button(QDialogButtonBox.Help).setToolTip('Go to the online BIDScoin documentation')
        buttonbox.button(QDialogButtonBox.Save).setToolTip('Save the Options and BIDSmap to disk if you are satisfied with all the BIDS output names')
        buttonbox.button(QDialogButtonBox.Reset).setToolTip('Reload the Options and BIDSmap from disk')
        buttonbox.helpRequested.connect(self.get_help)
        buttonbox.button(QDialogButtonBox.Reset).clicked.connect(self.reload)
        buttonbox.button(QDialogButtonBox.Save).clicked.connect(self.save_bidsmap)

        # Set-up the main layout
        centralwidget = QtWidgets.QWidget()
        top_layout = QtWidgets.QVBoxLayout(centralwidget)
        top_layout.addWidget(tabwidget)
        top_layout.addWidget(buttonbox)
        tabwidget.setCurrentIndex(0)

        MainWindow.setCentralWidget(centralwidget)

        # Restore the samples_table stretching after the main window has been sized / current tabindex has been set (otherwise the main window can become too narrow)
        for dataformat in self.dataformats:
            header = self.samples_table[dataformat].horizontalHeader()
            header.setSectionResizeMode(1, QHeaderView.Interactive)

        if not reload:

            self.set_menu_and_status_bar()

            # Center the main window to the center point of screen
            MainWindow.adjustSize()
            cp = QDesktopWidget().availableGeometry().center()
            qr = MainWindow.frameGeometry()
            qr.moveCenter(cp)
            MainWindow.move(qr.topLeft())            # Top left of rectangle becomes top left of window centering it

    def set_menu_and_status_bar(self):
        # Set the menus
        menubar  = QtWidgets.QMenuBar(self.MainWindow)
        menufile = QtWidgets.QMenu(menubar)
        menufile.setTitle('File')
        menubar.addAction(menufile.menuAction())
        menuhelp = QtWidgets.QMenu(menubar)
        menuhelp.setTitle('Help')
        menubar.addAction(menuhelp.menuAction())
        self.MainWindow.setMenuBar(menubar)

        # Set the file menu actions
        actionreload = QAction(self.MainWindow)
        actionreload.setText('Reset')
        actionreload.setStatusTip('Reload the BIDSmap from disk')
        actionreload.setShortcut('Ctrl+R')
        actionreload.triggered.connect(self.reload)
        menufile.addAction(actionreload)

        actionsave = QAction(self.MainWindow)
        actionsave.setText('Save')
        actionsave.setStatusTip('Save the BIDSmap to disk')
        actionsave.setShortcut('Ctrl+S')
        actionsave.triggered.connect(self.save_bidsmap)
        menufile.addAction(actionsave)

        actionexit = QAction(self.MainWindow)
        actionexit.setText('Exit')
        actionexit.setStatusTip('Exit the application')
        actionexit.setShortcut('Ctrl+X')
        actionexit.triggered.connect(self.exit_application)
        menufile.addAction(actionexit)

        # Set help menu actions
        actionhelp = QAction(self.MainWindow)
        actionhelp.setText('Documentation')
        actionhelp.setStatusTip('Go to the online BIDScoin documentation')
        actionhelp.setShortcut('F1')
        actionhelp.triggered.connect(self.get_help)
        menuhelp.addAction(actionhelp)

        actionbidshelp = QAction(self.MainWindow)
        actionbidshelp.setText('BIDS specification')
        actionbidshelp.setStatusTip('Go to the online BIDS specification documentation')
        actionbidshelp.setShortcut('F2')
        actionbidshelp.triggered.connect(self.get_bids_help)
        menuhelp.addAction(actionbidshelp)

        actionabout = QAction(self.MainWindow)
        actionabout.setText('About BIDScoin')
        actionabout.setStatusTip('Show information about the application')
        actionabout.triggered.connect(self.show_about)
        menuhelp.addAction(actionabout)

        # Set the statusbar
        statusbar = QtWidgets.QStatusBar(self.MainWindow)
        statusbar.setStatusTip('Statusbar')
        self.MainWindow.setStatusBar(statusbar)

    def set_tab_bidsmap(self, dataformat):
        """Set the SOURCE file sample listing tab.  """

        # Set the Participant labels table
        subses_label = QLabel('Participant labels')
        subses_label.setToolTip('Subject/session mapping')

        subses_table = MyQTableWidget()
        subses_table.setToolTip(f"Use '<<SourceFilePath>>' to parse the subject and (optional) session label from the pathname\n"
                                f"Use a dynamic {dataformat} attribute (e.g. '<PatientID>') to extract the subject and (optional) session label from the {dataformat} header")
        subses_table.setMouseTracking(True)
        subses_table.setRowCount(2)
        subses_table.setColumnCount(2)
        horizontal_header = subses_table.horizontalHeader()
        horizontal_header.setVisible(False)
        horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QHeaderView.Stretch)
        subses_table.cellChanged.connect(self.subsescell2bidsmap)
        self.subses_table[dataformat] = subses_table

        # Set the BIDSmap table
        provenance = bids.dir_bidsmap(self.input_bidsmap, dataformat)
        ordered_file_index = {}                                         # The mapping between the ordered provenance and an increasing file-index
        num_files = 0
        for file_index, file_name in enumerate(provenance):
            ordered_file_index[file_name] = file_index
            num_files = file_index + 1

        self.ordered_file_index[dataformat] = ordered_file_index

        label = QLabel('Data samples')
        label.setToolTip('List of unique source-data samples')

        samples_table = MyQTableWidget(minimum=False)
        samples_table.setMouseTracking(True)
        samples_table.setShowGrid(True)
        samples_table.setColumnCount(6)
        samples_table.setRowCount(num_files)
        samples_table.setHorizontalHeaderLabels(['', f'{dataformat} input', 'BIDS data type', 'BIDS output', 'Action', 'Provenance'])
        samples_table.setSortingEnabled(True)
        samples_table.sortByColumn(0, QtCore.Qt.AscendingOrder)
        samples_table.setColumnHidden(2, True)
        samples_table.setColumnHidden(5, True)
        samples_table.itemDoubleClicked.connect(self.inspect_sourcefile)
        header = samples_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)                 # Temporarily set it to Stretch to have Qt set the right window width -> set to Interactive in setupUI -> not reload
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.samples_table[dataformat] = samples_table

        layout = QVBoxLayout()
        layout.addWidget(subses_label)
        layout.addWidget(subses_table)
        layout.addWidget(label)
        layout.addWidget(samples_table)
        tab = QtWidgets.QWidget()
        tab.setObjectName(dataformat)                                       # NB: Serves to identify the dataformat for the tables in a tab
        tab.setLayout(layout)
        self.tabwidget.addTab(tab, f"{dataformat} mappings")
        self.tabwidget.setCurrentWidget(tab)

        self.update_subses_and_samples(self.output_bidsmap)

    def set_tab_options(self):
        """Set the options tab.  """

        # Create the tool tables
        tool_list = []
        tool_options = {}
        for tool, parameters in self.output_bidsmap['Options'].items():
            # Set the tools
            if tool == 'BIDScoin':
                tooltip_text = TOOLTIP_BIDSCOIN
            elif tool == 'dcm2niix':
                tooltip_text = TOOLTIP_DCM2NIIX
            else:
                tooltip_text = tool
            tool_list.append({
                'tool': tool,
                'tooltip_text': tooltip_text
            })
            # Store the options for each tool
            tool_options[tool] = []
            for key, value in parameters.items():
                if value is None:
                    value = ''
                tool_options[tool].append([
                    {
                        'value': tool,
                        'iseditable': False,
                        'tooltip_text': None
                    },
                    {
                        'value': key,
                        'iseditable': False,
                        'tooltip_text': tooltip_text
                    },
                    {
                        'value': value,
                        'iseditable': True,
                        'tooltip_text': 'Double-click to edit the option'
                    }
                ])

        labels = []
        self.tables_options = []

        for n, tool_item in enumerate(tool_list):
            tool         = tool_item['tool']
            tooltip_text = tool_item['tooltip_text']
            data         = tool_options[tool]
            num_rows     = len(data)
            num_cols     = len(data[0]) + 1     # Always three columns (i.e. tool, key, value) + test-button

            label = QLabel(tool)
            label.setToolTip(tooltip_text)

            tool_table = MyQTableWidget()
            tool_table.setRowCount(num_rows)
            tool_table.setColumnCount(num_cols)
            tool_table.setColumnHidden(0, True)  # Hide tool column
            tool_table.setMouseTracking(True)
            horizontal_header = tool_table.horizontalHeader()
            horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            horizontal_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            horizontal_header.setSectionResizeMode(2, QHeaderView.Stretch)
            horizontal_header.setSectionResizeMode(3, QHeaderView.Fixed)
            horizontal_header.setVisible(False)

            for i, row in enumerate(data):
                for j, item in enumerate(row):
                    value = item.get('value', '')
                    if value is None:
                        value = ''
                    iseditable = item.get('iseditable', False)
                    tooltip_text = item.get('tooltip_text')
                    tool_table.setItem(i, j, MyWidgetItem(value, iseditable=iseditable))
                    if tooltip_text:
                        tool_table.item(i, j).setToolTip(tooltip_text)

            # Add the test-button cell
            test_button = QPushButton('Test')
            test_button.clicked.connect(partial(self.test_tool, tool))
            test_button.setToolTip(f'Click to test the {tool} installation')
            tool_table.setCellWidget(0, num_cols-1, test_button)

            tool_table.cellChanged.connect(partial(self.toolcell2bidsmap, tool, n))

            labels.append(label)
            self.tables_options.append(tool_table)

        # Create the plugin table
        plugin_table = MyQTableWidget(minimum=False)
        plugin_label = QLabel('Plugins')
        plugin_label.setToolTip('List of plugins')
        plugin_table.setMouseTracking(True)
        plugin_table.setColumnCount(3)   # Always three columns (i.e. path, plugin, test-button)
        horizontal_header = plugin_table.horizontalHeader()
        horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QHeaderView.Stretch)
        horizontal_header.setSectionResizeMode(2, QHeaderView.Fixed)
        horizontal_header.setVisible(False)

        self.plugin_table = plugin_table
        self.update_plugintable()

        # Set-up the tab layout and add the tables
        layout = QVBoxLayout()
        for label, tool_table in zip(labels, self.tables_options):
            layout.addWidget(label)
            layout.addWidget(tool_table)
        layout.addWidget(plugin_label)
        layout.addWidget(plugin_table)
        layout.addStretch(1)

        tab = QtWidgets.QWidget()
        tab.setLayout(layout)

        self.tabwidget.addTab(tab, 'Options')

    def set_tab_file_browser(self):
        """Set the raw data folder inspector tab. """

        rootfolder = str(self.bidsfolder.parent)
        label = QLabel(rootfolder)
        label.setWordWrap(True)

        self.model = QFileSystemModel()
        model = self.model
        model.setRootPath(rootfolder)
        model.setFilter(QtCore.QDir.NoDotAndDotDot | QtCore.QDir.AllDirs | QtCore.QDir.Files)
        tree = QTreeView()
        tree.setModel(model)
        tree.setRootIndex(model.index(rootfolder))
        tree.setAnimated(False)
        tree.setSortingEnabled(True)
        tree.sortByColumn(0, QtCore.Qt.AscendingOrder)
        tree.setExpanded(model.index(str(self.bidsfolder)), True)
        tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        tree.header().setStretchLastSection(False)
        tree.doubleClicked.connect(self.open_inspectwindow)

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(tree)
        tab = QtWidgets.QWidget()
        tab.setLayout(layout)

        self.tabwidget.addTab(tab, 'Data browser')

    def update_subses_and_samples(self, output_bidsmap):
        """(Re)populates the sample list with bidsnames according to the bidsmap"""

        dataformat = self.tabwidget.widget(self.tabwidget.currentIndex()).objectName()

        self.output_bidsmap = output_bidsmap  # input main window / output from edit window -> output main window

        # Update the subject / session table
        subitem = MyWidgetItem('subject', iseditable=False)
        subitem.setToolTip(bids.get_bidshelp('sub'))
        sesitem = MyWidgetItem('session', iseditable=False)
        sesitem.setToolTip(bids.get_bidshelp('ses'))
        subses_table = self.subses_table[dataformat]
        subses_table.setItem(0, 0, subitem)
        subses_table.setItem(1, 0, sesitem)
        subses_table.setItem(0, 1, MyWidgetItem(output_bidsmap[dataformat]['subject']))
        subses_table.setItem(1, 1, MyWidgetItem(output_bidsmap[dataformat]['session']))

        # Update the run samples table
        idx = 0
        samples_table = self.samples_table[dataformat]
        samples_table.blockSignals(True)
        samples_table.setSortingEnabled(False)
        samples_table.clearContents()
        for datatype in bids.bidscoindatatypes + (bids.unknowndatatype, bids.ignoredatatype):
            runs = output_bidsmap.get(dataformat, {}).get(datatype, [])

            if not runs: continue
            for run in runs:

                # Check the run
                loglevel = LOGGER.level
                LOGGER.setLevel('ERROR')
                validrun = bids.check_run(datatype, run, validate=False)
                LOGGER.setLevel(loglevel)

                provenance   = Path(run['provenance'])
                subid, sesid = bids.get_subid_sesid(provenance,
                                                    output_bidsmap[dataformat]['subject'],
                                                    output_bidsmap[dataformat]['session'],
                                                    self.subprefix, self.sesprefix)
                bidsname     = bids.get_bidsname(subid, sesid, run)
                if run['bids']['suffix'] in bids.get_derivatives(datatype):
                    session  = self.bidsfolder/'derivatives'/'[manufacturer]'/subid/sesid
                else:
                    session  = self.bidsfolder/subid/sesid
                row_index    = self.ordered_file_index[dataformat][provenance]

                samples_table.setItem(idx, 0, QTableWidgetItem(f"{row_index+1:03d}"))
                samples_table.setItem(idx, 1, QTableWidgetItem(provenance.name))
                samples_table.setItem(idx, 2, QTableWidgetItem(datatype))                           # Hidden column
                samples_table.setItem(idx, 3, QTableWidgetItem(str(Path(datatype)/bidsname) + '.*'))
                samples_table.setItem(idx, 5, QTableWidgetItem(str(provenance)))                    # Hidden column

                samples_table.item(idx, 0).setFlags(QtCore.Qt.NoItemFlags)
                samples_table.item(idx, 1).setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
                samples_table.item(idx, 2).setFlags(QtCore.Qt.ItemIsEnabled)
                samples_table.item(idx, 3).setFlags(QtCore.Qt.ItemIsEnabled)
                samples_table.item(idx, 1).setToolTip('Double-click to inspect the header information (Copy: Ctrl+C)')
                samples_table.item(idx, 1).setStatusTip(str(provenance.parent) + str(Path('/')))
                samples_table.item(idx, 3).setStatusTip(str(session) + str(Path('/')))

                if samples_table.item(idx, 3):
                    if not validrun or datatype == bids.unknowndatatype:
                        samples_table.item(idx, 3).setForeground(QtGui.QColor('red'))
                        samples_table.item(idx, 3).setToolTip(f"Red: This {datatype} data type is not part of BIDS but will be converted to BIDS-like data. You should edit this item or make sure it is in your bidsignore list ([Options] tab)")
                    elif datatype == bids.ignoredatatype:
                        samples_table.item(idx, 1).setForeground(QtGui.QColor('gray'))
                        samples_table.item(idx, 3).setForeground(QtGui.QColor('gray'))
                        f = samples_table.item(idx, 3).font()
                        f.setStrikeOut(True)
                        samples_table.item(idx, 3).setFont(f)
                        samples_table.item(idx, 3).setToolTip('Gray / Strike-out: This imaging data type will be ignored and not converted BIDS')
                    else:
                        samples_table.item(idx, 3).setForeground(QtGui.QColor('green'))
                        samples_table.item(idx, 3).setToolTip(f"Green: This '{datatype}' data type is part of BIDS")

                if validrun:
                    edit_button = QPushButton('Edit')
                    edit_button.setToolTip('Click to see more details and edit the BIDS output name')
                else:
                    edit_button = QPushButton('Edit*')
                    edit_button.setToolTip('*: Contains invalid / missing values! Click to see more details and edit the BIDS output name')
                edit_button.clicked.connect(self.open_editwindow)
                edit_button.setCheckable(not sys.platform.startswith('darwin'))
                edit_button.setAutoExclusive(True)
                if provenance.name and str(provenance)==self.has_editwindow_open:    # Highlight the previously opened item
                    edit_button.setChecked(True)
                else:
                    edit_button.setChecked(False)
                samples_table.setCellWidget(idx, 4, edit_button)

                idx += 1

        samples_table.setSortingEnabled(True)
        samples_table.blockSignals(False)

    def subsescell2bidsmap(self, row: int, column:int):
        """Subject or session value has been changed in subject-session table. """
        dataformat = self.tabwidget.widget(self.tabwidget.currentIndex()).objectName()
        if column == 1:
            key      = self.subses_table[dataformat].item(row, 0).text()
            value    = self.subses_table[dataformat].item(row, 1).text()
            oldvalue = self.output_bidsmap[dataformat][key]

            # Only if cell was actually clicked, update
            if key and value != oldvalue:
                LOGGER.warning(f"Expert usage: User has set {dataformat}['{key}'] from '{oldvalue}' to '{value}'")
                self.output_bidsmap[dataformat][key] = value
                self.update_subses_and_samples(self.output_bidsmap)

    def open_editwindow(self, provenance: Path=Path(), datatype: str= ''):
        """Make sure that index map has been updated. """
        if not datatype:
            dataformat    = self.tabwidget.widget(self.tabwidget.currentIndex()).objectName()
            samples_table = self.samples_table[dataformat]
            button        = self.MainWindow.focusWidget()
            rowindex      = samples_table.indexAt(button.pos()).row()
            datatype      = samples_table.item(rowindex, 2).text()
            provenance    = Path(samples_table.item(rowindex, 5).text())

        # Check for open edit window, find the right datatype index and open the edit window
        if not self.has_editwindow_open:
            # Find the source index of the run in the list of runs (using the provenance) and open the edit window
            dataformat = self.tabwidget.widget(self.tabwidget.currentIndex()).objectName()
            for run in self.output_bidsmap[dataformat][datatype]:
                if run['provenance']==str(provenance):
                    LOGGER.info(f'User is editing {provenance}')
                    self.editwindow = EditWindow(dataformat, provenance, datatype, self.output_bidsmap, self.template_bidsmap, self.subprefix, self.sesprefix)
                    if provenance.name:
                        self.has_editwindow_open = str(provenance)
                    else:
                        self.has_editwindow_open = True
                    self.editwindow.done_edit.connect(self.update_subses_and_samples)
                    self.editwindow.finished.connect(self.release_editwindow)
                    self.editwindow.show()
                    return
            LOGGER.exception(f"Could not find {provenance} run-item")

        else:
            # Ask the user if he wants to save his results first before opening a new edit window
            self.editwindow.reject()
            if self.has_editwindow_open:
                return
            self.open_editwindow(provenance, datatype)

    def release_editwindow(self):
        """Allow a new edit window to be opened"""
        self.has_editwindow_open = None

    def update_plugintable(self):
        """Plots an extendable table of plugins from self.output_bidsmap['PlugIns']"""
        plugins  = self.output_bidsmap['PlugIns']
        num_rows = len(plugins) + 1

        # Fill the rows of the plugin table
        plugintable = self.plugin_table
        plugintable.disconnect()
        plugintable.setRowCount(num_rows)
        for i, plugin in enumerate(plugins + ['']):
            for j in range(3):
                if j==0:
                    item = MyWidgetItem('path', iseditable=False)
                    plugintable.setItem(i, j, item)
                elif j==1:
                    item = MyWidgetItem(plugin)
                    item.setToolTip('Double-click to edit/delete the plugin, which can be the basename of the plugin in the heuristics folder or a custom full pathname')
                    plugintable.setItem(i, j, item)
                elif j==2:                  # Add the test-button cell
                    test_button = QPushButton('Test')
                    test_button.clicked.connect(partial(self.test_plugin, plugin))
                    test_button.setToolTip(f"Click to test the {plugin} plugin")
                    plugintable.setCellWidget(i, j, test_button)

        # Append the Add-button cell
        add_button = QPushButton('Select')
        add_button.setToolTip('Click to interactively add a plugin')
        plugintable.setCellWidget(num_rows - 1, 2, add_button)
        add_button.clicked.connect(self.addedplugin2bidsmap)

        plugintable.cellChanged.connect(self.changedplugin2bidsmap)

    def addedplugin2bidsmap(self):
        """Add a plugin by letting the user select a plugin-file"""
        plugin = QFileDialog.getOpenFileNames(self.MainWindow, 'Select the plugin-file(s)', directory=str(self.bidsfolder/'code'/'bidscoin'), filter='Python files (*.py *.pyc *.pyo);; All files (*)')
        LOGGER.info(f'Added plugins: {plugin[0]}')
        self.output_bidsmap['PlugIns'] += plugin[0]
        self.update_plugintable()

    def changedplugin2bidsmap(self, row: int, column: int):
        """Add / edit a plugin or delete if cell is empty"""
        if column==1:
            plugin = self.plugin_table.item(row, column).text()
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

    def toolcell2bidsmap(self, tool: str, idx: int, row: int, column: int):
        """Option value has been changed tool options table. """
        if column == 2:
            table = self.tables_options[idx]  # Select the selected table
            key = table.item(row, 1).text()
            value = table.item(row, 2).text()
            oldvalue = self.output_bidsmap['Options'][tool][key]

            # Only if cell was actually clicked, update
            if key and value!=oldvalue:
                LOGGER.info(f"User has set ['Options']['{tool}']['{key}'] from '{oldvalue}' to '{value}'")
                self.output_bidsmap['Options'][tool][key] = value

    def test_tool(self, tool: str):
        """Test the bidsmap tool and show the result in a pop-up window

        :param tool:    Name of the tool that is being tested in bidsmap['Options']
         """
        if self.test_tooloptions(tool, self.output_bidsmap['Options'][tool]):
            QMessageBox.information(self.MainWindow, 'Tool test', f"Execution of {tool}: Passed\n"
                                                                   'See terminal output for more info')
        else:
            QMessageBox.warning(self.MainWindow, 'Tool test', f"Execution of {tool}: Failed\n"
                                                               'See terminal output for more info')

    @staticmethod
    def test_tooloptions(tool: str, opts: dict) -> bool:
        """
        Performs shell tests of the user tool parameters set in bidsmap['Options']

        :param tool:    Name of the tool that is being tested in bidsmap['Options']
        :param opts:    The editable options belonging to the tool
        :return:        True if the tool generated the expected result, False if there was a tool error, None if not tested
        """

        if tool=='dcm2niix':
            command = f"{opts['path']}dcm2niix -u"
        elif tool=='bidsmapper':
            command = 'bidsmapper -v'
        elif tool in ('bidscoin', 'bidscoiner'):
            command = 'bidscoiner -v'
        else:
            LOGGER.warning(f"Testing of '{tool}' not supported")
            return True

        LOGGER.info(f"Testing: '{tool}'")

        return bidscoin.run_command(command)

    def test_plugin(self, plugin: str):
        """Test the bidsmap plugin and show the result in a pop-up window

        :param plugin:    Name of the plugin that is being tested in bidsmap['PlugIns']
         """
        if bidscoin.test_plugins(Path(plugin)):
            QMessageBox.information(self.MainWindow, 'Plugin test', f"Import of {plugin}: Passed\n"
                                                                     'See terminal output for more info')
        else:
            QMessageBox.warning(self.MainWindow, 'Plugin test', f"Import of {plugin}: Failed\n"
                                                                 'See terminal output for more info')

    def reload(self):
        """Reset button: reload the original input BIDS map. """
        if self.has_editwindow_open:
            self.editwindow.reject(confirm=False)

        if not self.bidsmap_filename.is_file():
            LOGGER.info('Could not reload the bidsmap')
            QMessageBox.warning(self.MainWindow, 'Reset', f"Could not find and reload the bidsmap file:\n{self.bidsmap_filename}")
            return
        LOGGER.info('User reloads the bidsmap')
        self.output_bidsmap, _ = bids.load_bidsmap(self.bidsmap_filename)
        self.setupui(self.MainWindow,
                     self.bidsfolder,
                     self.bidsmap_filename,
                     self.input_bidsmap,
                     self.output_bidsmap,
                     self.template_bidsmap,
                     reload=True)

        # Start with a fresh errorlog
        for filehandler in LOGGER.handlers:
            if filehandler.name=='errorhandler' and Path(filehandler.baseFilename).stat().st_size:
                errorfile = filehandler.baseFilename
                LOGGER.info(f"Resetting {errorfile}")
                with open(errorfile, 'w'):          # TODO: This works but it is a hack that somehow prefixes a lot of whitespace to the first LOGGER call
                    pass

    def save_bidsmap(self):
        """Check and save the BIDSmap to file. """
        for dataformat in self.dataformats:
            if self.output_bidsmap[dataformat].get('fmap'):
                for run in self.output_bidsmap[dataformat]['fmap']:
                    if not run['meta'].get('IntendedFor'):
                        LOGGER.warning(f"IntendedFor fieldmap value is empty for {dataformat} run-item: {run['provenance']}")

        filename, _ = QFileDialog.getSaveFileName(self.MainWindow, 'Save File',
                        str(self.bidsfolder/'code'/'bidscoin'/'bidsmap.yaml'),
                        'YAML Files (*.yaml *.yml);;All Files (*)')
        if filename:
            bids.save_bidsmap(Path(filename), self.output_bidsmap)
            QtCore.QCoreApplication.setApplicationName(f"{filename} - BIDS editor")

    def inspect_sourcefile(self, item):
        """When source file is double clicked in the samples_table, show popup window. """
        if item.column() == 1:
            dataformat = self.tabwidget.widget(self.tabwidget.currentIndex()).objectName()
            sourcefile = self.samples_table[dataformat].item(item.row(), 5)
            self.popup = InspectWindow(Path(sourcefile.text()))
            self.popup.show()
            self.popup.scrollbar.setValue(0)  # This can only be done after self.popup.show()

    def open_inspectwindow(self, index: int):
        """Opens the inspect window when a data file in the file-tree tab is double-clicked"""
        datafile = Path(self.model.fileInfo(index).absoluteFilePath())
        if bids.is_dicomfile(datafile) or bids.is_parfile(datafile):
            self.popup = InspectWindow(datafile)
            self.popup.show()
            self.popup.scrollbar.setValue(0)  # This can only be done after self.popup.show()
        elif datafile.is_file():
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(datafile)))

    def show_about(self):
        """Shows a pop-up window with the BIDScoin version"""
        version, message = bidscoin.version(check=True)
        # QMessageBox.about(self.MainWindow, 'About', f"BIDS editor {version}\n\n{message}")    # Has an ugly / small icon image
        messagebox = QMessageBox(self.MainWindow)
        messagebox.setText(f"\n\nBIDS editor {version}\n\n{message}")
        messagebox.setWindowTitle('About')
        messagebox.setIconPixmap(QtGui.QPixmap(str(BIDSCOIN_LOGO)).scaled(150, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        messagebox.show()

    @staticmethod
    def get_help():
        """Get online help. """
        webbrowser.open(MAIN_HELP_URL)

    @staticmethod
    def get_bids_help():
        """Get online help. """
        webbrowser.open(HELP_URL_DEFAULT)

    def exit_application(self):
        """Handle exit. """
        self.MainWindow.close()


class EditWindow(QDialog):
    """
    EditWindow().result() == 1: done with result, i.e. done_edit -> new bidsmap
    EditWindow().result() == 2: done without result
    """

    # Emit the new bidsmap when done (see docstring)
    done_edit = QtCore.pyqtSignal(dict)

    def __init__(self, dataformat: str, provenance: Path, datatype: str, bidsmap: dict, template_bidsmap: dict, subprefix='sub-', sesprefix='ses-'):
        super().__init__()

        # Set the data
        self.dataformat       = dataformat
        self.source_datatype  = datatype
        self.target_datatype  = datatype
        self.current_datatype = datatype
        self.source_bidsmap   = bidsmap
        self.target_bidsmap   = copy.deepcopy(bidsmap)
        self.template_bidsmap = template_bidsmap
        for run in bidsmap[self.dataformat][datatype]:
            if run['provenance'] == str(provenance):
                self.source_run = run
        self.target_run = copy.deepcopy(self.source_run)
        self.get_allowed_suffixes()
        self.subid, self.sesid = bids.get_subid_sesid(Path(self.source_run['provenance']),
                                                      bidsmap[dataformat]['subject'],
                                                      bidsmap[dataformat]['session'],
                                                      subprefix, sesprefix)

        # Set-up the window
        self.setWindowIcon(QtGui.QIcon(str(BIDSCOIN_ICON)))
        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.setWindowTitle('Edit BIDS mapping')

        # Get data for the tables
        data_provenance, data_attributes, data_bids, data_meta = self.run2data()

        # Set-up the provenance table
        self.provenance_label = QLabel()
        self.provenance_label.setText('Provenance')
        self.provenance_table = self.set_table(data_provenance, 'provenance')
        self.provenance_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.provenance_table.setToolTip(f"The {self.dataformat} source file from which the attributes were taken (Copy: Ctrl+C)")
        self.provenance_table.cellDoubleClicked.connect(self.inspect_sourcefile)

        # Set-up the attributes table
        self.attributes_label = QLabel()
        self.attributes_label.setText('Attributes')
        self.attributes_table = self.set_table(data_attributes, 'attributes', minimum=False)
        self.attributes_table.cellChanged.connect(self.attributescell2run)
        self.attributes_table.setToolTip(f"The {self.dataformat} attributes that are used to uniquely identify source files. NB: Expert usage (e.g. using '*string*' wildcards, see documentation), only change these if you know what you are doing!")

        # Set-up the datatype dropdown menu
        self.datatype_label = QLabel()
        self.datatype_label.setText('Data type')
        self.datatype_dropdown = QComboBox()
        self.datatype_dropdown.addItems(bids.bidscoindatatypes + (bids.unknowndatatype, bids.ignoredatatype))
        self.datatype_dropdown.setCurrentIndex(self.datatype_dropdown.findText(self.target_datatype))
        self.datatype_dropdown.currentIndexChanged.connect(self.datatype_dropdown_change)
        self.datatype_dropdown.setToolTip('The BIDS data type. First make sure this one is correct, then choose the right suffix')

        # Set-up the BIDS table
        self.bids_label = QLabel()
        self.bids_label.setText('Entities')
        self.bids_table = self.set_table(data_bids, 'bids', minimum=False)
        self.bids_table.setToolTip(f"The BIDS entities that are used to construct the BIDS output filename. You are encouraged to change their default values to be more meaningful and readable")
        self.bids_table.cellChanged.connect(self.bidscell2run)

        # Set-up the meta table
        self.meta_label = QLabel()
        self.meta_label.setText('Meta data')
        self.meta_table = self.set_table(data_meta, 'meta', minimum=False)
        self.meta_table.setShowGrid(True)
        self.meta_table.cellChanged.connect(self.metacell2run)
        self.meta_table.setToolTip(f"Key-value pairs that will be appended to the (e.g. dcm2niix-produced) json sidecar file")

        # Set-up non-editable BIDS output name section
        self.bidsname_label = QLabel()
        self.bidsname_label.setText('Data filename')
        self.bidsname_textbox = QTextBrowser()
        self.bidsname_textbox.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.bidsname_textbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.bidsname_textbox.setMinimumHeight(ROW_HEIGHT + 2)
        self.refresh_bidsname()

        # Group the tables in boxes
        sizepolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizepolicy.setHorizontalStretch(1)

        groupbox1 = QGroupBox(self.dataformat + ' input')
        groupbox1.setSizePolicy(sizepolicy)
        layout1 = QVBoxLayout()
        layout1.addWidget(self.provenance_label)
        layout1.addWidget(self.provenance_table)
        layout1.addWidget(self.attributes_label)
        layout1.addWidget(self.attributes_table)
        groupbox1.setLayout(layout1)

        groupbox2 = QGroupBox('BIDS output')
        groupbox2.setSizePolicy(sizepolicy)
        layout2 = QVBoxLayout()
        layout2.addWidget(self.datatype_label)
        layout2.addWidget(self.datatype_dropdown, alignment=QtCore.Qt.AlignLeft)
        # layout2.addWidget(self.bids_label)
        layout2.addWidget(self.bids_table)
        layout2.addWidget(self.bidsname_label)
        layout2.addWidget(self.bidsname_textbox)
        layout2.addWidget(self.meta_label)
        layout2.addWidget(self.meta_table)
        groupbox2.setLayout(layout2)

        # Add a box1 -> box2 arrow
        arrow = QLabel()
        arrow.setPixmap(QtGui.QPixmap(str(RIGHTARROW)).scaled(30, 30, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))

        # Add the boxes to the layout
        layout_tables = QHBoxLayout()
        layout_tables.addWidget(groupbox1)
        layout_tables.addWidget(arrow)
        layout_tables.addWidget(groupbox2)

        # Set-up buttons
        buttonBox    = QDialogButtonBox()
        exportbutton = buttonBox.addButton('Export', QDialogButtonBox.ActionRole)
        exportbutton.setIcon(QtGui.QIcon.fromTheme('document-save'))
        exportbutton.setToolTip('Export this run item to an existing (template) bidsmap')
        exportbutton.clicked.connect(self.export_run)
        buttonBox.setStandardButtons(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Reset | QDialogButtonBox.Help)
        buttonBox.button(QDialogButtonBox.Reset).setToolTip('Reset the edits you made')
        buttonBox.button(QDialogButtonBox.Ok).setToolTip('Apply the edits you made and close this window')
        buttonBox.button(QDialogButtonBox.Cancel).setToolTip('Discard the edits you made and close this window')
        buttonBox.button(QDialogButtonBox.Help).setToolTip('Go to the online BIDS specification for more info')
        buttonBox.accepted.connect(self.accept_run)
        buttonBox.rejected.connect(partial(self.reject, False))
        buttonBox.helpRequested.connect(self.get_help)
        buttonBox.button(QDialogButtonBox.Reset).clicked.connect(self.reset)

        # Set-up the main layout
        layout_all = QVBoxLayout(self)
        layout_all.addLayout(layout_tables)
        layout_all.addWidget(buttonBox)

        self.center()

        finish = QAction(self)
        finish.triggered.connect(self.closeEvent)

    def get_allowed_suffixes(self):
        """Derive the possible suffixes for each datatype from the template. """
        allowed_suffixes = {}
        for datatype in bids.bidscoindatatypes + (bids.unknowndatatype, bids.ignoredatatype):
            allowed_suffixes[datatype] = []
            runs = self.template_bidsmap.get(self.dataformat, {}).get(datatype, [])
            if not runs: continue
            for run in runs:
                suffix = run['bids'].get('suffix')
                if suffix and suffix not in allowed_suffixes.get(datatype, []):
                    allowed_suffixes[datatype].append(suffix)

        self.allowed_suffixes = allowed_suffixes

    def run2data(self) -> tuple:
        """
        Derive the tabular data from the target_run, needed to render the edit window.

        :return: (data_provenance, data_attributes, data_bids, data_meta)
        """

        data_provenance = [
            [
                {
                    'value': 'path',
                    'iseditable': False
                },
                {
                    'value': str(Path(self.target_run['provenance']).parent),
                    'iseditable': False
                },
            ],
            [
                {
                    'value': 'filename',
                    'iseditable': False
                },
                {
                    'value': Path(self.target_run['provenance']).name,
                    'iseditable': True
                },
            ],
            [
                {
                    'value': 'size',
                    'iseditable': False
                },
                {
                    'value': format_bytes(Path(self.target_run['provenance']).stat().st_size),
                    'iseditable': False
                },
            ]
        ]

        data_attributes = []
        for key, value in self.target_run['attributes'].items():
            if value is None:
                value = ''
            data_attributes.append([
                {
                    'value': key,
                    'iseditable': False
                },
                {
                    'value': str(value),
                    'iseditable': True
                }
            ])

        data_bids = []
        for key in [bids.entities[entity]['entity'] for entity in bids.entities if entity not in ('subject','session')] + ['suffix']:   # Impose the BIDS-specified order + suffix
            if key in self.target_run['bids']:
                value = self.target_run['bids'].get(key,'')
                if value is None:
                    value = ''
                if (self.target_datatype in bids.bidscoindatatypes and key=='suffix') or isinstance(value, list):
                    iseditable = False
                else:
                    iseditable = True

                data_bids.append([
                    {
                        'value': key,
                        'iseditable': False
                    },
                    {
                        'value': value,                     # NB: This can be a (menu) list
                        'iseditable': iseditable
                    }
                ])

        data_meta = []
        for key, value in self.target_run['meta'].items():
            if value is None:
                value = ''
            data_meta.append([
                {
                    'value': key,
                    'iseditable': True
                },
                {
                    'value': str(value),
                    'iseditable': True
                }
            ])

        return data_provenance, data_attributes, data_bids, data_meta

    def set_table(self, data, name, minimum: bool=True) -> QTableWidget:
        """Return a table widget from the data. """
        table = MyQTableWidget(minimum=minimum)
        table.setColumnCount(2)                         # Always two columns (i.e. key, value)
        table.setObjectName(name)                       # NB: Serves to identify the tables in fill_table()
        table.setHorizontalHeaderLabels(('key', 'value'))
        horizontal_header = table.horizontalHeader()
        horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QHeaderView.Stretch)
        horizontal_header.setVisible(False)

        self.fill_table(table, data)

        return table

    def fill_table(self, table, data):
        """Fill the table with data"""

        table.blockSignals(True)
        table.clearContents()
        addrow = []
        if table.objectName() == 'meta':
            addrow = [[{'value':'', 'iseditable': True}, {'value':'', 'iseditable': True}]]
        table.setRowCount(len(data + addrow))

        for i, row in enumerate(data + addrow):
            key = row[0]['value']
            if table.objectName()=='bids' and key=='suffix' and self.target_datatype in bids.bidscoindatatypes:
                table.setItem(i, 0, MyWidgetItem('suffix', iseditable=False))
                suffixes = self.allowed_suffixes.get(self.target_datatype, [''])
                suffix_dropdown = self.suffix_dropdown = QComboBox()
                suffix_dropdown.addItems(suffixes)
                suffix_dropdown.setCurrentIndex(suffix_dropdown.findText(self.target_run['bids']['suffix']))
                suffix_dropdown.currentIndexChanged.connect(self.suffix_dropdown_change)
                suffix_dropdown.setToolTip('The suffix that sets the different run types apart. First make sure the "Data type" dropdown-menu is set correctly before chosing the right suffix here')
                table.setCellWidget(i, 1, self.spacedwidget(suffix_dropdown))
                continue
            for j, item in enumerate(row):
                value = item.get('value', '')
                if table.objectName()=='bids' and isinstance(value, list):
                    value_dropdown = QComboBox()
                    value_dropdown.addItems(value[0:-1])
                    value_dropdown.setCurrentIndex(value[-1])
                    value_dropdown.currentIndexChanged.connect(partial(self.bidscell2run, i, j))
                    if j == 0:
                        value_dropdown.setToolTip(bids.get_bidshelp(key))
                    table.setCellWidget(i, j, self.spacedwidget(value_dropdown))
                else:
                    value_item = MyWidgetItem(value, iseditable=item['iseditable'])
                    if table.objectName()=='bids' and j==0:
                        value_item.setToolTip(bids.get_bidshelp(key))
                    table.setItem(i, j, value_item)

        table.blockSignals(False)

    def attributescell2run(self, row: int, column: int):
        """Source attribute value has been changed. """
        if column == 1:
            key      = self.attributes_table.item(row, 0).text()
            value    = self.attributes_table.item(row, 1).text()
            oldvalue = self.target_run['attributes'].get(key)

            # Only if cell was actually clicked, update (i.e. not when BIDS datatype changes)
            if key and value!=oldvalue:
                LOGGER.warning(f"Expert usage: User has set {self.dataformat}['{key}'] from '{oldvalue}' to '{value}' for {self.target_run['provenance']}")
                self.target_run['attributes'][key] = value

    def bidscell2run(self, row: int, column: int):
        """BIDS attribute value has been changed. """
        if column == 1:
            key = self.bids_table.item(row, 0).text()
            if hasattr(self.bids_table.cellWidget(row, 1), 'spacedwidget'):
                dropdown = self.bids_table.cellWidget(row, 1).spacedwidget
                value    = [dropdown.itemText(n) for n in range(len(dropdown))] + [dropdown.currentIndex()]
                oldvalue = self.target_run['bids'].get(key)
            else:
                value    = self.bids_table.item(row, 1).text()
                oldvalue = self.target_run['bids'].get(key)

            # Only if cell was actually clicked, update (i.e. not when BIDS datatype changes) and store the data in the target_run
            if key and value != oldvalue:
                # Validate user input against BIDS or replace the (dynamic) bids-value if it is a run attribute
                if isinstance(value, str) and not (value.startswith('<<') and value.endswith('>>')):
                    value = bids.cleanup_value(bids.get_dynamicvalue(value, Path(self.target_run['provenance'])))
                    self.bids_table.item(row, 1).setText(value)
                if key == 'run':
                    LOGGER.warning(f"Expert usage: User has set bids['{key}'] from '{oldvalue}' to '{value}' for {self.target_run['provenance']}")
                else:
                    LOGGER.info(f"User has set bids['{key}'] from '{oldvalue}' to '{value}' for {self.target_run['provenance']}")
                self.target_run['bids'][key] = value
                self.refresh_bidsname()

    def metacell2run(self, row: int, column: int):
        """Source meta value has been changed. """
        key      = self.meta_table.item(row, 0).text()
        value    = self.meta_table.item(row, 1).text()
        oldvalue = self.target_run['meta'].get(key)
        if value != oldvalue:
            # Replace the (dynamic) value
            if not (value.startswith('<<') and value.endswith('>>')):
                value = bids.get_dynamicvalue(value, Path(self.target_run['provenance']), cleanup=False)
                self.meta_table.item(row, 1).setText(value)
            LOGGER.info(f"User has set meta['{key}'] from '{oldvalue}' to '{value}' for {self.target_run['provenance']}")

        # Read all the meta-data from the table and store it in the target_run
        self.target_run['meta'] = {}
        for n in range(self.meta_table.rowCount()):
            _key   = self.meta_table.item(n, 0).text()
            _value = self.meta_table.item(n, 1).text()
            if _key and not _key.isspace():
                self.target_run['meta'][_key] = _value
            elif _value:
                QMessageBox.warning(self, 'Input error', f"Please enter a key-name (left cell) for the '{_value}' value in row {n+1}")

        # Refresh the table if needed, i.e. delete empty rows or add a new row if a key is defined on the last row
        if (not key and not value) or (key and not key.isspace() and row + 1 == self.meta_table.rowCount()):
            _, _, _, data_meta = self.run2data()
            self.fill_table(self.meta_table, data_meta)

    def change_run(self, suffix_idx):
        """
        Resets the edit dialog window with a new target_run from the template bidsmap after a datatype_dropdown_change.

        :param suffix_idx: The suffix or index number that will used to extract the run from the template bidsmap
        :return:
        """

        # Get the new target_run
        self.target_run = bids.get_run(self.template_bidsmap, self.dataformat, self.target_datatype, suffix_idx, Path(self.target_run['provenance']))

        # Insert the new target_run in our target_bidsmap
        bids.update_bidsmap(self.target_bidsmap, self.current_datatype, Path(self.target_run['provenance']), self.target_datatype, self.target_run, self.dataformat)

        # Now that we have updated the bidsmap, we can also update the current_datatype
        self.current_datatype = self.target_datatype

        # Reset the edit window with the new target_run
        self.reset(refresh=True)

    def datatype_dropdown_change(self):
        """Update the BIDS values and BIDS output name section when the dropdown selection has been taking place. """
        self.target_datatype = self.datatype_dropdown.currentText()

        LOGGER.info(f"User has changed the BIDS data type from '{self.current_datatype}' to '{self.target_datatype}' for {self.target_run['provenance']}")

        self.change_run(0)

    def suffix_dropdown_change(self):
        """Update the BIDS values and BIDS output name section when the dropdown selection has been taking place. """
        target_suffix = self.suffix_dropdown.currentText()

        LOGGER.info(f"User has changed the BIDS suffix from '{self.target_run['bids']['suffix']}' to '{target_suffix}' for {self.target_run['provenance']}")

        self.change_run(target_suffix)

    def refresh_bidsname(self):
        """Updates the bidsname with the current (edited) bids values"""
        bidsname = (Path(self.target_datatype)/bids.get_bidsname(self.subid, self.sesid, self.target_run)).with_suffix('.*')

        font = self.bidsname_textbox.font()
        if self.target_datatype==bids.unknowndatatype:
            self.bidsname_textbox.setToolTip(f"Red: This imaging data type is not part of BIDS but will be converted to a BIDS-like entry in the '{bids.unknowndatatype}' folder. Click 'OK' if you want your BIDS output data to look like this")
            self.bidsname_textbox.setTextColor(QtGui.QColor('red'))
            font.setStrikeOut(False)
        elif self.target_datatype == bids.ignoredatatype:
            self.bidsname_textbox.setToolTip("Gray / Strike-out: This imaging data type will be ignored and not converted BIDS. Click 'OK' if you want your BIDS output data to look like this")
            self.bidsname_textbox.setTextColor(QtGui.QColor('gray'))
            font.setStrikeOut(True)
        elif not bids.check_run(self.target_datatype, self.target_run):
            self.bidsname_textbox.setToolTip(f"Red: This name is not valid according to the BIDS standard")
            self.bidsname_textbox.setTextColor(QtGui.QColor('red'))
            font.setStrikeOut(False)
        else:
            self.bidsname_textbox.setToolTip(f"Green: This '{self.target_datatype}' imaging data type is part of BIDS. Click 'OK' if you want your BIDS output data to look like this")
            self.bidsname_textbox.setTextColor(QtGui.QColor('green'))
            font.setStrikeOut(False)
        self.bidsname_textbox.setFont(font)
        self.bidsname_textbox.clear()
        self.bidsname_textbox.textCursor().insertText(str(bidsname))

    def reset(self, refresh: bool=False):
        """Resets the edit with the target_run if refresh=True or otherwise with the original source_run (=default)"""

        # Reset the target_run to the source_run
        if not refresh:
            LOGGER.info('User resets the BIDS mapping')
            self.current_datatype = self.source_datatype
            self.target_datatype  = self.source_datatype
            self.target_run       = copy.deepcopy(self.source_run)
            self.target_bidsmap   = copy.deepcopy(self.source_bidsmap)

            # Reset the datatype dropdown menu
            self.datatype_dropdown.setCurrentIndex(self.datatype_dropdown.findText(self.target_datatype))

        # Refresh the source attributes and BIDS values with data from the target_run
        _, data_attributes, data_bids, data_meta = self.run2data()

        # Refresh the existing tables
        self.fill_table(self.attributes_table, data_attributes)
        self.fill_table(self.bids_table, data_bids)
        self.fill_table(self.meta_table, data_meta)

        # Refresh the BIDS output name
        self.refresh_bidsname()

    def accept_run(self):
        """Save the changes to the target_bidsmap and send it back to the main window: Finished! """

        if not bids.check_run(self.target_datatype, self.target_run):
            answer = QMessageBox.question(self, 'Edit BIDS mapping', f'The "{self.target_datatype}/*_{self.target_run["bids"]["suffix"]}" run is not valid according to the BIDS standard. Do you want to go back and edit the run?',
                                          QMessageBox.Yes | QMessageBox.No | QMessageBox.Yes)
            if answer == QMessageBox.Yes:
                return
            LOGGER.warning(f'The "{self.bidsname_textbox.toPlainText()}" run is not valid according to the BIDS standard")')

        if self.target_datatype=='fmap' and not self.target_run['meta'].get('IntendedFor'):
            answer = QMessageBox.question(self, 'Edit BIDS mapping', "The 'IntendedFor' bids-label was not set, which can make that your fieldmap won't be used when "
                                                                     "pre-processing / analyzing the associated imaging data (e.g. fMRI data). Do you want to go back "
                                                                     "and set this label?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Yes)
            if answer == QMessageBox.Yes:
                return
            LOGGER.warning(f"'IntendedFor' fieldmap value was not set")

        LOGGER.info(f'User has approved the edit')
        bids.update_bidsmap(self.target_bidsmap, self.current_datatype, self.target_run['provenance'], self.target_datatype, self.target_run, self.dataformat)

        self.done_edit.emit(self.target_bidsmap)
        self.done(1)

    def export_run(self):

        yamlfile, _ = QFileDialog.getOpenFileName(self, 'Export run item to (template) bidsmap',
                        str(bids.bidsmap_template), 'YAML Files (*.yaml *.yml);;All Files (*)')
        if yamlfile:
            LOGGER.info(f'Exporting run item: bidsmap[{self.dataformat}][{self.target_datatype}] -> {yamlfile}')
            yamlfile   = Path(yamlfile)
            bidsmap, _ = bids.load_bidsmap(yamlfile, Path(), False)
            bids.append_run(bidsmap, self.dataformat, self.target_datatype, self.target_run)
            bids.save_bidsmap(yamlfile, bidsmap)
            QMessageBox.information(self, 'Edit BIDS mapping', f"Successfully exported:\n\nbidsmap[{self.dataformat}][{self.target_datatype}] -> {yamlfile}")

    def reject(self, confirm=True):
        """Ask if the user really wants to close the window"""
        if confirm:
            self.raise_()
            answer = QMessageBox.question(self, 'Edit BIDS mapping', 'Closing window, do you want to save the changes you made?',
                                          QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Cancel)
            if answer == QMessageBox.Yes:
                self.accept_run()
                return
            if answer == QMessageBox.No:
                self.done(2)
                LOGGER.info(f'User has discarded the edit')
                return
            if answer == QMessageBox.Cancel:
                return

        LOGGER.info(f'User has canceled the edit')

        super(EditWindow, self).reject()

    def inspect_sourcefile(self, row: int=None, column: int=None):
        """When double clicked, show popup window. """
        if row == 1 and column == 1:
            self.popup = InspectWindow(Path(self.target_run['provenance']))
            self.popup.show()
            self.popup.scrollbar.setValue(0)  # This can only be done after self.popup.show()

    @staticmethod
    def spacedwidget(leftwidget):
        widget = QtWidgets.QWidget()
        layout = QHBoxLayout()
        layout.addWidget(leftwidget)
        layout.addStretch()
        layout.setContentsMargins(0, 0, 0, 0)
        widget.setLayout(layout)
        widget.spacedwidget = leftwidget
        return widget

    def get_help(self):
        """Open web page for help. """
        help_url = HELP_URLS.get(self.target_datatype, HELP_URL_DEFAULT)
        webbrowser.open(help_url)

    def center(self):
        """Center the edit window. """
        cp = QDesktopWidget().availableGeometry().center()  # Center point of screen
        qr = self.frameGeometry()                           # Get the rectangular geometry
        qr.moveCenter(cp)                                   # Move rectangle's center point to screen's center point
        self.move(qr.topLeft())                             # Top left of rectangle becomes top left of window centering it


def format_bytes(size):
    """
    Converts bytes into a human-readable B, KB, MG, GB, TB format

    :param size:    size in bytes
    :return:        Human-friedly string
    """

    power = 2**10       # 2**10 = 1024
    label = {0:'', 1:'k', 2:'M', 3:'G', 4:'T'}
    n = 0
    while size > power and n < len(label):
        size /= power
        n += 1

    return f"{size:.2f} {label[n]}B"


def bidseditor(bidsfolder: str, bidsmapfile: str='', templatefile: str='', subprefix='sub-', sesprefix='ses-'):
    """
    Collects input and launches the bidseditor GUI

    :param bidsfolder:
    :param bidsmapfile:
    :param templatefile:
    :param subprefix:
    :param sesprefix:
    :return:
    """

    bidsfolder   = Path(bidsfolder).resolve()
    bidsmapfile  = Path(bidsmapfile)
    templatefile = Path(templatefile)

    # Start logging
    bidscoin.setup_logging(bidsfolder/'code'/'bidscoin'/'bidseditor.log')
    LOGGER.info('')
    LOGGER.info('-------------- START BIDSeditor ------------')
    LOGGER.info(f">>> bidseditor bidsfolder={bidsfolder} bidsmap={bidsmapfile} template={templatefile}"
                f"subprefix={subprefix} sesprefix={sesprefix}")

    # Obtain the initial bidsmap info
    template_bidsmap, templatefile = bids.load_bidsmap(templatefile, bidsfolder/'code'/'bidscoin')
    input_bidsmap, bidsmapfile     = bids.load_bidsmap(bidsmapfile,  bidsfolder/'code'/'bidscoin')
    output_bidsmap                 = copy.deepcopy(input_bidsmap)
    if not input_bidsmap:
        LOGGER.error(f'No bidsmap file found in {bidsfolder}. Please run the bidsmapper first and / or use the correct bidsfolder')
        return

    # Start the Qt-application
    app = QApplication(sys.argv)
    app.setApplicationName(f"{bidsmapfile} - BIDS editor {bidscoin.version()}")
    mainwin = MainWindow()
    gui = UiMainWindow()
    gui.setupui(mainwin, bidsfolder, bidsmapfile, input_bidsmap, output_bidsmap, template_bidsmap, subprefix=subprefix, sesprefix=sesprefix)
    mainwin.show()
    app.exec()

    LOGGER.info('-------------- FINISHED! -------------------')
    LOGGER.info('')

    bidscoin.reporterrors()


def main():
    """Console script usage"""

    # Parse the input arguments and run bidseditor
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=textwrap.dedent(__doc__),
                                     epilog=textwrap.dedent("""
                                         examples:
                                           bidseditor /project/foo/bids
                                           bidseditor /project/foo/bids -t bidsmap_template.yaml
                                           bidseditor /project/foo/bids -b my/custom/bidsmap.yaml"""))

    parser.add_argument('bidsfolder',           help='The destination folder with the (future) bids data')
    parser.add_argument('-b','--bidsmap',       help='The study bidsmap file with the mapping heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-t','--template',      help='The template bidsmap file with the default heuristics (this could be provided by your institute). If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap_dccn.yaml', default='bidsmap_dccn.yaml')
    parser.add_argument('-n','--subprefix',     help="The prefix common for all the source subject-folders. Default: 'sub-'", default='sub-')
    parser.add_argument('-m','--sesprefix',     help="The prefix common for all the source session-folders. Default: 'ses-'", default='ses-')
    args = parser.parse_args()

    bidseditor(bidsfolder   = args.bidsfolder,
               bidsmapfile  = args.bidsmap,
               templatefile = args.template,
               subprefix    = args.subprefix,
               sesprefix    = args.sesprefix)


if __name__ == '__main__':
    LOGGER = logging.getLogger(f"bidscoin.{Path(__file__).stem}")
    main()

else:
    LOGGER = logging.getLogger(__name__)
