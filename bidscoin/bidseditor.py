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
    from bidscoin import bids
except ImportError:
    import bids             # This should work if bidscoin was not pip-installed

LOGGER = logging.getLogger('bidscoin')

ROW_HEIGHT       = 22
ICON_FILENAME    = Path(__file__).parent/'bidscoin.ico'

MAIN_HELP_URL    = f"https://bidscoin.readthedocs.io/en/{bids.version()}"
HELP_URL_DEFAULT = f"https://bids-specification.readthedocs.io/en/v{bids.bidsversion()}"
HELP_URLS        = {
    'anat': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#anatomy-imaging-data",
    'dwi' : f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#diffusion-imaging-data",
    'fmap': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#fieldmap-data",
    'func': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#task-including-resting-state-imaging-data",
    'perf': f"{HELP_URL_DEFAULT}/04-modality-specific-files/01-magnetic-resonance-imaging-data.html#arterial-spin-labeling-perfusion-data",
    'eeg' : f"{HELP_URL_DEFAULT}/04-modality-specific-files/03-electroencephalography.html",
    'ieeg': f"{HELP_URL_DEFAULT}/04-modality-specific-files/04-intracranial-electroencephalography.html",
    'beh' : f"{HELP_URL_DEFAULT}/04-modality-specific-files/07-behavioral-experiments.html",
    'pet' : 'https://docs.google.com/document/d/1mqMLnxVdLwZjDd4ZiWFqjEAmOmfcModA_R535v3eQs0',
    bids.unknowndatatype: HELP_URL_DEFAULT,
    bids.ignoredatatype : HELP_URL_DEFAULT
}

TOOLTIP_BIDSCOIN = """BIDScoin
version:    should correspond with the version in ../bidscoin/version.txt
bidsignore: Semicolon-separated list of entries that are added to the .bidsignore file
            (for more info, see BIDS specifications), e.g. extra_data/;pet/;myfile.txt;yourfile.csv"""

TOOLTIP_DCM2NIIX = """dcm2niix
path: Command to set the path to dcm2niix, e.g.:
      module add dcm2niix/1.0.20180622; (note the semi-colon at the end)
      PATH=/opt/dcm2niix/bin:$PATH; (note the semi-colon at the end)
      /opt/dcm2niix/bin/  (note the slash at the end)
      '\"C:\\Program Files\\dcm2niix\"' (note the quotes to deal with the whitespace)
args: Argument string that is passed to dcm2niix. Click [Test] and see the terminal output for usage
      Tip: SPM users may want to use '-z n', which produces unzipped nifti's"""


class myQTableWidget(QTableWidget):

    def __init__(self, minimum: bool=True):
        super().__init__()

        self.setAlternatingRowColors(False)
        self.setShowGrid(False)

        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.setMinimumHeight(2 * (ROW_HEIGHT + 5))
        self.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)

        self.minimizeHeight(minimum)

    def minimizeHeight(self, minimum: bool=True):
        """Set the vertical QSizePolicy to Minimum"""

        self.minimum = minimum

        if minimum:
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        else:
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)


class myWidgetItem(QTableWidgetItem):

    def __init__(self, value: str='', iseditable: bool=True):
        """A QTableWidgetItem that is editable or not"""
        super().__init__()

        if isinstance(value, int):
            value = str(value)
        self.setText(value)
        self.setEditable(iseditable)

    def setEditable(self, iseditable: bool=True):
        """Make the WidgetItem editable"""

        self.iseditable = iseditable

        if iseditable:
            self.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable)
            self.setForeground(QtGui.QColor('black'))
        else:
            self.setFlags(QtCore.Qt.ItemIsEnabled)
            self.setForeground(QtGui.QColor('gray'))


class InspectWindow(QDialog):

    def __init__(self, filename: Path, sourcedict, dataformat: str):
        super().__init__()

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(str(ICON_FILENAME)), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)
        self.setWindowTitle(f"Inspect {dataformat} file")

        layout = QVBoxLayout(self)

        label_path = QLabel(f"Path: {filename.parent}")
        label_path.setWordWrap(True)
        label_path.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(label_path)

        label = QLabel(f"Filename: {filename.name}")
        label.setWordWrap(True)
        label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(label)

        text        = str(sourcedict)
        textBrowser = QTextBrowser(self)
        textBrowser.setFont(QtGui.QFont("Courier New"))
        textBrowser.insertPlainText(text)
        textBrowser.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)
        self.scrollbar = textBrowser.verticalScrollBar()        # For setting the slider to the top (can only be done after self.show()
        layout.addWidget(textBrowser)

        buttonBox = QDialogButtonBox(self)
        buttonBox.setStandardButtons(QDialogButtonBox.Ok)
        buttonBox.button(QDialogButtonBox.Ok).setToolTip('Close this window')
        layout.addWidget(buttonBox)

        # Set the width to the width of the text
        fontMetrics = QtGui.QFontMetrics(textBrowser.font())
        textwidth   = fontMetrics.size(0, text).width()
        self.resize(min(textwidth + 70, 1200), self.height())

        buttonBox.accepted.connect(self.close)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        actionQuit = QAction('Quit', self)
        actionQuit.triggered.connect(self.closeEvent)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(str(ICON_FILENAME)), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)

    def closeEvent(self, event):
        """Handle exit. """
        QApplication.quit()     # TODO: Do not use class method but self.something


class Ui_MainWindow(MainWindow):

    def setupUi(self, MainWindow, bidsfolder, bidsmap_filename, input_bidsmap, output_bidsmap, template_bidsmap,
                dataformat, selected_tab_index=2, subprefix='sub-', sesprefix='ses-', reload: bool=False):

        # Set the input data
        self.MainWindow       = MainWindow
        self.bidsfolder       = Path(bidsfolder)
        self.bidsmap_filename = Path(bidsmap_filename)
        self.input_bidsmap    = input_bidsmap
        self.output_bidsmap   = output_bidsmap
        self.template_bidsmap = template_bidsmap
        self.dataformat       = dataformat
        self.subprefix        = subprefix
        self.sesprefix        = sesprefix

        self.has_edit_dialog_open = None

        # Set-up the tabs
        self.tabwidget = QtWidgets.QTabWidget()
        tabwidget = self.tabwidget
        tabwidget.setTabPosition(QtWidgets.QTabWidget.North)
        tabwidget.setTabShape(QtWidgets.QTabWidget.Rounded)
        tabwidget.setObjectName('tabwidget')

        self.set_tab_file_browser()
        self.set_tab_options()
        self.set_tab_bidsmap()
        tabwidget.setTabText(0, 'File browser')
        tabwidget.setTabText(1, 'Options')
        tabwidget.setTabText(2, 'BIDS map')
        tabwidget.setCurrentIndex(selected_tab_index)

        # Set-up the buttons. TODO: Add validate bidsmap button
        buttonBox = QDialogButtonBox()
        buttonBox.setStandardButtons(QDialogButtonBox.Save | QDialogButtonBox.Reset | QDialogButtonBox.Help)
        buttonBox.button(QDialogButtonBox.Help).setToolTip('Go to the online BIDScoin documentation')
        buttonBox.button(QDialogButtonBox.Save).setToolTip('Save the Options and BIDS-map to disk if you are satisfied with all the BIDS output names')
        buttonBox.button(QDialogButtonBox.Reset).setToolTip('Reload the options and BIDS-map from disk')
        buttonBox.helpRequested.connect(self.get_help)
        buttonBox.button(QDialogButtonBox.Reset).clicked.connect(self.reload)
        buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.save_bidsmap_to_file)

        # Set-up the main layout
        centralwidget = QtWidgets.QWidget(self.MainWindow)
        centralwidget.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        centralwidget.setObjectName('centralwidget')
        top_layout = QtWidgets.QVBoxLayout(centralwidget)
        top_layout.addWidget(tabwidget)
        top_layout.addWidget(buttonBox)

        self.MainWindow.setCentralWidget(centralwidget)

        # Restore the samples_table stretching after the main window has been sized / current tabindex has been set (otherwise the main window can become too narrow)
        header = self.samples_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        if not reload:
            self.setObjectName('MainWindow')

            self.set_menu_and_status_bar()

            # Center the main window to the center point of screen
            self.MainWindow.adjustSize()
            cp = QDesktopWidget().availableGeometry().center()
            qr = self.MainWindow.frameGeometry()
            qr.moveCenter(cp)
            self.MainWindow.move(qr.topLeft())            # Top left of rectangle becomes top left of window centering it

    def set_menu_and_status_bar(self):
        # Set the menus
        menubar  = QtWidgets.QMenuBar(self.MainWindow)
        menuFile = QtWidgets.QMenu(menubar)
        menuFile.setTitle('File')
        menubar.addAction(menuFile.menuAction())
        menuHelp = QtWidgets.QMenu(menubar)
        menuHelp.setTitle('Help')
        menubar.addAction(menuHelp.menuAction())
        self.MainWindow.setMenuBar(menubar)

        # Set the file menu actions
        actionReload = QAction(self.MainWindow)
        actionReload.setText('Reset')
        actionReload.setStatusTip('Reload the BIDS-map from disk')
        actionReload.setShortcut('Ctrl+R')
        actionReload.triggered.connect(self.reload)
        menuFile.addAction(actionReload)

        actionSave = QAction(self.MainWindow)
        actionSave.setText('Save')
        actionSave.setStatusTip('Save the BIDS-map to disk')
        actionSave.setShortcut('Ctrl+S')
        actionSave.triggered.connect(self.save_bidsmap_to_file)
        menuFile.addAction(actionSave)

        actionExit = QAction(self.MainWindow)
        actionExit.setText('Exit')
        actionExit.setStatusTip('Exit the application')
        actionExit.setShortcut('Ctrl+X')
        actionExit.triggered.connect(self.exit_application)
        menuFile.addAction(actionExit)

        # Set help menu actions
        actionHelp = QAction(self.MainWindow)
        actionHelp.setText('Documentation')
        actionHelp.setStatusTip('Go to the online BIDScoin documentation')
        actionHelp.setShortcut('F1')
        actionHelp.triggered.connect(self.get_help)
        menuHelp.addAction(actionHelp)

        actionBidsHelp = QAction(self.MainWindow)
        actionBidsHelp.setText('BIDS specification')
        actionBidsHelp.setStatusTip('Go to the online BIDS specification documentation')
        actionBidsHelp.setShortcut('F2')
        actionBidsHelp.triggered.connect(self.get_bids_help)
        menuHelp.addAction(actionBidsHelp)

        actionAbout = QAction(self.MainWindow)
        actionAbout.setText('About BIDScoin')
        actionAbout.setStatusTip('Show information about the application')
        actionAbout.triggered.connect(self.show_about)
        menuHelp.addAction(actionAbout)

        # Set the statusbar
        statusbar = QtWidgets.QStatusBar(self.MainWindow)
        statusbar.setObjectName('statusbar')
        statusbar.setStatusTip('Statusbar')
        self.MainWindow.setStatusBar(statusbar)

    def inspect_sourcefile(self, item):
        """When double clicked, show popup window. """
        if item.column() == 1:
            row  = item.row()
            cell = self.samples_table.item(row, 5)
            sourcefile = Path(cell.text())
            if bids.is_dicomfile(sourcefile):
                sourcedata = pydicom.dcmread(sourcefile, force=True)
            elif bids.is_parfile(sourcefile):
                with open(sourcefile, 'r') as parfid:
                    sourcedata = parfid.read()
            else:
                LOGGER.warning(f"Could not read {self.dataformat} file: {sourcefile}")
                return
            self.popup = InspectWindow(sourcefile, sourcedata, self.dataformat)
            self.popup.show()
            self.popup.scrollbar.setValue(0)     # This can only be done after self.popup.show()

    def set_tab_file_browser(self):
        """Set the raw data folder inspector tab. """
        # Parse the sourcefolder from the bidsmap provenance info
        sourcefolder = Path('/').resolve()
        for provenance in bids.dir_bidsmap(self.input_bidsmap, self.dataformat):
            sourcefolder = Path(provenance.parents[min(3, len(provenance.parents)-1)])
            break

        label = QLabel(str(sourcefolder))
        label.setWordWrap(True)

        self.model = QFileSystemModel()
        model = self.model
        model.setRootPath('')
        model.setFilter(QtCore.QDir.NoDotAndDotDot | QtCore.QDir.AllDirs | QtCore.QDir.Files)
        tree = QTreeView()
        tree.setModel(model)
        tree.setAnimated(False)
        tree.setIndentation(20)
        tree.sortByColumn(0, QtCore.Qt.AscendingOrder)
        tree.setSortingEnabled(True)
        tree.setRootIndex(model.index(str(sourcefolder)))
        tree.doubleClicked.connect(self.on_double_clicked)
        tree.header().resizeSection(0, 800)

        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(tree)
        tab1 = QtWidgets.QWidget()
        tab1.setObjectName('filebrowser')
        tab1.setLayout(layout)

        self.tabwidget.addTab(tab1, '')

    def subses_cell_was_changed(self, row: int, column:int):
        """Subject or session value has been changed in subject-session table. """
        if column == 1:
            key = self.subses_table.item(row, 0).text()
            value = self.subses_table.item(row, 1).text()
            oldvalue = self.output_bidsmap[self.dataformat][key]

            # Only if cell was actually clicked, update
            if key and value!=oldvalue:
                LOGGER.warning(f"Expert usage: User has set {self.dataformat}['{key}'] from '{oldvalue}' to '{value}'")
                self.output_bidsmap[self.dataformat][key] = value
                self.update_subses_and_samples(self.output_bidsmap)

    def tool_cell_was_changed(self, tool: str, idx: int, row: int, column: int):
        """Option value has been changed tool options table. """
        if column == 2:
            table = self.tables_options[idx]  # Select the selected table
            key = table.item(row, 1).text()
            value = table.item(row, 2).text()
            oldvalue = self.output_bidsmap['Options'][tool][key]

            # Only if cell was actually clicked, update
            if key and value!=oldvalue:
                LOGGER.info(f"User has set {self.dataformat}['Options']['{key}'] from '{oldvalue}' to '{value}'")
                self.output_bidsmap['Options'][tool][key] = value

    def handle_click_test_plugin(self, plugin: str):
        """Test the bidsmap plugin and show the result in a pop-up window

        :param plugin:    Name of the plugin that is being tested in bidsmap['PlugIns']
         """
        if bids.test_plugins(Path(plugin)):
            result = 'Passed'
        else:
            result = 'Failed'
        QMessageBox.information(self.MainWindow, 'Test', f"Test {plugin}: {result}\n"
                                                         f"See terminal output for more info")

    def handle_click_test_tool(self, tool: str):
        """Test the bidsmap tool and show the result in a pop-up window

        :param tool:    Name of the tool that is being tested in bidsmap['Options']
         """
        if bids.test_tooloptions(tool, self.output_bidsmap['Options'][tool]):
            result = 'Passed'
        else:
            result = 'Failed'
        QMessageBox.information(self.MainWindow, 'Test', f"Test {tool}: {result}\n"
                                                         f"See terminal output for more info")

    def handle_click_plugin_add(self):
        """Add a plugin by letting the user select a plugin-file"""
        plugin = QFileDialog.getOpenFileNames(self.MainWindow, 'Select the plugin-file(s)', directory=str(self.bidsfolder/'code'/'bidscoin'), filter='Python files (*.py *.pyc *.pyo);; All files (*)')
        LOGGER.info(f'Added plugins: {plugin[0]}')
        self.output_bidsmap['PlugIns'] += plugin[0]
        self.update_plugintable()

    def plugin_cell_was_changed(self, row: int, column: int):
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
                    item = myWidgetItem('path', iseditable=False)
                    plugintable.setItem(i, j, item)
                elif j==1:
                    item = myWidgetItem(plugin)
                    item.setToolTip('Double-click to edit/delete the plugin, which can be the basename of the plugin in the heuristics folder or a custom full pathname')
                    plugintable.setItem(i, j, item)
                elif j==2:                  # Add the test-button cell
                    test_button = QPushButton('Test')
                    test_button.clicked.connect(partial(self.handle_click_test_plugin, plugin))
                    test_button.setToolTip(f"Click to test {plugin}")
                    plugintable.setCellWidget(i, j, test_button)

        # Append the Add-button cell
        add_button = QPushButton('Select')
        add_button.setToolTip('Click to interactively add a plugin')
        plugintable.setCellWidget(num_rows - 1, 2, add_button)
        add_button.clicked.connect(self.handle_click_plugin_add)

        plugintable.cellChanged.connect(self.plugin_cell_was_changed)

    def set_tab_options(self):
        """Set the options tab.  """

        # Create the tool tables
        bidsmap_options = self.output_bidsmap['Options']

        tool_list = []
        tool_options = {}
        for tool, parameters in bidsmap_options.items():
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
            tool = tool_item['tool']
            tooltip_text = tool_item['tooltip_text']
            data = tool_options[tool]
            num_rows = len(data)
            num_cols = len(data[0]) + 1     # Always three columns (i.e. tool, key, value) + test-button

            label = QLabel(tool)
            label.setToolTip(tooltip_text)

            tool_table = myQTableWidget()
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
                    if value == 'None':
                        value = ''
                    iseditable = item.get('iseditable', False)
                    tooltip_text = item.get('tooltip_text')
                    tool_table.setItem(i, j, myWidgetItem(value, iseditable=iseditable))
                    if tooltip_text:
                        tool_table.item(i, j).setToolTip(tooltip_text)

            # Add the test-button cell
            test_button = QPushButton('Test')
            test_button.clicked.connect(partial(self.handle_click_test_tool, tool))
            test_button.setToolTip(f'Click to test the {tool} options')
            tool_table.setCellWidget(0, num_cols-1, test_button)

            tool_table.cellChanged.connect(partial(self.tool_cell_was_changed, tool, n))

            labels.append(label)
            self.tables_options.append(tool_table)

        # Create the plugin table
        plugin_table = myQTableWidget(minimum=False)
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

        tab2 = QtWidgets.QWidget()
        tab2.setObjectName('Options')
        tab2.setLayout(layout)

        self.tabwidget.addTab(tab2, '')

    def update_subses_and_samples(self, output_bidsmap):
        """(Re)populates the sample list with bidsnames according to the bidsmap"""

        self.output_bidsmap = output_bidsmap  # input main window / output from edit window -> output main window

        # Update the subject / session table
        subitem = myWidgetItem('subject', iseditable=False)
        subitem.setToolTip(bids.get_bidshelp('sub'))
        sesitem = myWidgetItem('session', iseditable=False)
        sesitem.setToolTip(bids.get_bidshelp('ses'))
        subses_table = self.subses_table
        subses_table.setItem(0, 0, subitem)
        subses_table.setItem(1, 0, sesitem)
        subses_table.setItem(0, 1, myWidgetItem(output_bidsmap[self.dataformat]['subject']))
        subses_table.setItem(1, 1, myWidgetItem(output_bidsmap[self.dataformat]['session']))

        # Update the run samples table
        idx = 0
        samples_table = self.samples_table
        samples_table.blockSignals(True)
        samples_table.setSortingEnabled(False)
        samples_table.clearContents()
        for datatype in bids.bidsdatatypes + (bids.unknowndatatype, bids.ignoredatatype):
            runs = output_bidsmap.get(self.dataformat, {}).get(datatype, [])

            if not runs: continue
            for run in runs:
                provenance   = Path(run['provenance'])
                subid, sesid = bids.get_subid_sesid(provenance,
                                                    output_bidsmap[self.dataformat]['subject'],
                                                    output_bidsmap[self.dataformat]['session'],
                                                    self.subprefix, self.sesprefix)
                bidsname     = bids.get_bidsname(subid, sesid, run)
                if run['bids']['suffix'] in bids.get_derivatives(datatype):
                    session  = self.bidsfolder/'derivatives'/'[manufacturer]'/subid/sesid
                else:
                    session  = self.bidsfolder/subid/sesid
                row_index    = self.ordered_file_index[provenance]

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
                    if datatype == bids.unknowndatatype:
                        samples_table.item(idx, 3).setForeground(QtGui.QColor('red'))
                        samples_table.item(idx, 3).setToolTip(f"Red: This imaging data type is not part of BIDS but will be converted to a BIDS-like entry in the '{bids.unknowndatatype}' folder")
                    elif datatype == bids.ignoredatatype:
                        samples_table.item(idx, 1).setForeground(QtGui.QColor('gray'))
                        samples_table.item(idx, 3).setForeground(QtGui.QColor('gray'))
                        f = samples_table.item(idx, 3).font()
                        f.setStrikeOut(True)
                        samples_table.item(idx, 3).setFont(f)
                        samples_table.item(idx, 3).setToolTip('Gray / Strike-out: This imaging data type will be ignored and not converted BIDS')
                    else:
                        samples_table.item(idx, 3).setForeground(QtGui.QColor('green'))
                        samples_table.item(idx, 3).setToolTip(f"Green: This '{datatype}' imaging data type is part of BIDS")

                edit_button = QPushButton('Edit')
                edit_button.setToolTip('Click to see more details and edit the BIDS output name')
                edit_button.clicked.connect(self.handle_edit_button_clicked)
                edit_button.setCheckable(not sys.platform.startswith('darwin'))
                edit_button.setAutoExclusive(True)
                if provenance.name and str(provenance)==self.has_edit_dialog_open:    # Highlight the previously opened item
                    edit_button.setChecked(True)
                else:
                    edit_button.setChecked(False)
                samples_table.setCellWidget(idx, 4, edit_button)

                idx += 1

        samples_table.setSortingEnabled(True)
        samples_table.blockSignals(False)

    def set_tab_bidsmap(self):
        """Set the SOURCE file sample listing tab.  """

        # Set the Participant labels table
        subses_label = QLabel('Participant labels')
        subses_label.setToolTip('Subject/session mapping')

        self.subses_table = myQTableWidget()
        subses_table = self.subses_table
        subses_table.setToolTip(f"Use <<SourceFilePath>> to parse the subject and (optional) session label from the pathname\n"
                                f"Use <Your{self.dataformat}FieldName> (e.g. <PatientID>) to extract the subject and (optional) session label from the {self.dataformat} header")
        subses_table.setMouseTracking(True)
        subses_table.setRowCount(2)
        subses_table.setColumnCount(2)
        horizontal_header = subses_table.horizontalHeader()
        horizontal_header.setVisible(False)
        horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QHeaderView.Stretch)
        subses_table.cellChanged.connect(self.subses_cell_was_changed)

        # Set the BIDSmap table
        provenance = bids.dir_bidsmap(self.input_bidsmap, self.dataformat)
        ordered_file_index = {}                                         # The mapping between the ordered provenance and an increasing file-index
        num_files = 0
        for file_index, file_name in enumerate(provenance):
            ordered_file_index[file_name] = file_index
            num_files = file_index + 1

        self.ordered_file_index = ordered_file_index

        label = QLabel('Data samples')
        label.setToolTip('List of unique source-data samples')

        self.samples_table = myQTableWidget(minimum=False)
        samples_table = self.samples_table
        samples_table.setMouseTracking(True)
        samples_table.setShowGrid(True)
        samples_table.setColumnCount(6)
        samples_table.setRowCount(num_files)
        samples_table.setHorizontalHeaderLabels(['', f'{self.dataformat} input', 'BIDS data type', 'BIDS output', 'Action', 'Provenance'])
        samples_table.setSortingEnabled(True)
        samples_table.sortByColumn(0, QtCore.Qt.AscendingOrder)
        samples_table.setColumnHidden(2, True)
        samples_table.setColumnHidden(5, True)
        samples_table.itemDoubleClicked.connect(self.inspect_sourcefile)
        header = samples_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)             # Temporarily set it to Stretch to have Qt set the right window width -> set to Stretch in setupUI -> not reload
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.update_subses_and_samples(self.output_bidsmap)

        layout = QVBoxLayout()
        layout.addWidget(subses_label)
        layout.addWidget(subses_table)
        layout.addWidget(label)
        layout.addWidget(samples_table)
        tab3 = QtWidgets.QWidget()
        tab3.setObjectName('BIDSmapping')
        tab3.setLayout(layout)

        self.tabwidget.addTab(tab3, '')

    def get_help(self):
        """Get online help. """
        webbrowser.open(MAIN_HELP_URL)

    def get_bids_help(self):
        """Get online help. """
        webbrowser.open(HELP_URL_DEFAULT)

    def reload(self):
        """Reset button: reload the original input BIDS map. """
        if self.has_edit_dialog_open:
            self.dialog_edit.reject(confirm=False)

        LOGGER.info('User reloads the bidsmap')
        current_tab_index = self.tabwidget.currentIndex()
        self.output_bidsmap, _ = bids.load_bidsmap(self.bidsmap_filename)
        self.setupUi(self.MainWindow,
                     self.bidsfolder,
                     self.bidsmap_filename,
                     self.input_bidsmap,
                     self.output_bidsmap,
                     self.template_bidsmap,
                     self.dataformat,
                     selected_tab_index=current_tab_index,
                     reload=True)

        # Start with a fresh errorlog
        for filehandler in LOGGER.handlers:
            if filehandler.name=='errorhandler' and Path(filehandler.baseFilename).stat().st_size:
                errorfile = filehandler.baseFilename
                LOGGER.info(f"Resetting {errorfile}")
                with open(errorfile, 'w'):          # TODO: This works but it is a hack that somehow prefixes a lot of whitespace to the first LOGGER call
                    pass

    def save_bidsmap_to_file(self):
        """Check and save the BIDSmap to file. """
        if self.output_bidsmap[self.dataformat].get('fmap'):
            for run in self.output_bidsmap[self.dataformat]['fmap']:
                if not run['bids']['IntendedFor']:
                    LOGGER.warning(f"IntendedFor fieldmap value is empty for {run['provenance']}")

        filename, _ = QFileDialog.getSaveFileName(self.MainWindow, 'Save File',
                        str(self.bidsfolder/'code'/'bidscoin'/'bidsmap.yaml'),
                        'YAML Files (*.yaml *.yml);;All Files (*)')
        if filename:
            bids.save_bidsmap(Path(filename), self.output_bidsmap)
            QtCore.QCoreApplication.setApplicationName(f"{filename} - BIDS editor")

    def handle_edit_button_clicked(self):
        """Make sure that index map has been updated. """
        button     = self.MainWindow.focusWidget()
        rowindex   = self.samples_table.indexAt(button.pos()).row()
        datatype   = self.samples_table.item(rowindex, 2).text()
        provenance = Path(self.samples_table.item(rowindex, 5).text())

        self.open_edit_dialog(provenance, datatype)

    def on_double_clicked(self, index: int):
        """Opens the inspect window when a source file in the file-tree tab is double-clicked"""
        sourcefile = Path(self.model.fileInfo(index).absoluteFilePath())
        if bids.is_dicomfile(sourcefile):
            sourcedata = pydicom.dcmread(sourcefile, force=True)
        elif bids.is_parfile(sourcefile):
            with open(sourcefile, 'r') as parfid:
                sourcedata = parfid.read()
        else:
            LOGGER.warning(f"Could not read {self.dataformat} file: {sourcefile}")
            return
        self.popup = InspectWindow(sourcefile, sourcedata, self.dataformat)
        self.popup.show()
        self.popup.scrollbar.setValue(0)  # This can only be done after self.popup.show()

    def show_about(self):
        """Shows a pop-up window with the BIDScoin version"""
        about = f"BIDS editor\n{bids.version()}"
        QMessageBox.about(self.MainWindow, 'About', about)

    def open_edit_dialog(self, provenance: Path, datatype: str, modal=False):
        """Check for open edit window, find the right datatype index and open the edit window"""

        if not self.has_edit_dialog_open:
            # Find the source index of the run in the list of runs (using the provenance) and open the edit window
            for run in self.output_bidsmap[self.dataformat][datatype]:
                if run['provenance']==str(provenance):
                    LOGGER.info(f'User is editing {provenance}')
                    self.dialog_edit = EditDialog(self.dataformat, provenance, datatype, self.output_bidsmap, self.template_bidsmap, self.subprefix, self.sesprefix)
                    if provenance.name:
                        self.has_edit_dialog_open = str(provenance)
                    else:
                        self.has_edit_dialog_open = True
                    self.dialog_edit.done_edit.connect(self.update_subses_and_samples)
                    self.dialog_edit.finished.connect(self.release_edit_dialog)
                    if modal:
                        self.dialog_edit.exec()
                    else:
                        self.dialog_edit.show()
                    break

        else:
            # Ask the user if he wants to save his results first before opening a new edit window
            self.dialog_edit.reject()
            if self.has_edit_dialog_open:
                return

            self.open_edit_dialog(provenance, datatype, modal)

    def release_edit_dialog(self):
        """Allow a new edit window to be opened"""
        self.has_edit_dialog_open = None

    def exit_application(self):
        """Handle exit. """
        self.MainWindow.close()


class EditDialog(QDialog):
    """
    EditDialog().result() == 1: done with result, i.e. done_edit -> new bidsmap
    EditDialog().result() == 2: done without result
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
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(str(ICON_FILENAME)), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)
        self.setWindowFlags(QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowCloseButtonHint | QtCore.Qt.WindowMaximizeButtonHint)
        self.setWindowTitle('Edit BIDS mapping')

        # Get data for the tables
        data_provenance, data_source, data_bids = self.get_editwin_data()

        # Set-up the provenance table
        self.provenance_label = QLabel()
        self.provenance_label.setText('Provenance')
        self.provenance_table = self.set_table(data_provenance)
        self.provenance_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.provenance_table.setToolTip(f"The {self.dataformat} source file from which the attributes were taken (Copy: Ctrl+C)")
        self.provenance_table.cellDoubleClicked.connect(self.inspect_sourcefile)

        # Set-up the source table
        self.source_label = QLabel()
        self.source_label.setText('Attributes')
        self.source_table = self.set_table(data_source, minimum=False)
        self.source_table.cellChanged.connect(self.source_cell_changed)
        self.source_table.setToolTip(f"The {self.dataformat} attributes that are used to uniquely identify source files. NB: Expert usage (e.g. using '*string*' wildcards, see documentation), only change these if you know what you are doing!")

        # Set-up the datatype dropdown menu
        self.label_dropdown = QLabel()
        self.label_dropdown.setText('Data type')
        self.datatype_dropdown = QComboBox()
        self.datatype_dropdown.addItems(bids.bidsdatatypes + (bids.unknowndatatype, bids.ignoredatatype))
        self.datatype_dropdown.setCurrentIndex(self.datatype_dropdown.findText(self.target_datatype))
        self.datatype_dropdown.currentIndexChanged.connect(self.datatype_dropdown_change)
        self.datatype_dropdown.setToolTip('The BIDS data type. First make sure this one is correct, then choose the right suffix')

        # Set-up the BIDS table
        self.bids_label = QLabel()
        self.bids_label.setText('Entities')
        self.bids_table = self.set_table(data_bids, minimum=False)
        self.bids_table.setToolTip(f"The BIDS value that is used to construct the BIDS output name. You can freely change the value to be more meaningful and readable")
        self.bids_table.cellChanged.connect(self.bids_cell_changed)

        # Set-up non-editable BIDS output name section
        self.label_bids_name = QLabel()
        self.label_bids_name.setText('Output name')
        self.view_bids_name = QTextBrowser()
        self.view_bids_name.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        self.view_bids_name.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.view_bids_name.setMinimumHeight(ROW_HEIGHT + 2)
        self.refresh_bidsname()

        # Group the tables in boxes
        sizepolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizepolicy.setHorizontalStretch(1)

        groupbox1 = QGroupBox(self.dataformat + ' input')
        groupbox1.setSizePolicy(sizepolicy)
        layout1 = QVBoxLayout()
        layout1.addWidget(self.provenance_label)
        layout1.addWidget(self.provenance_table)
        layout1.addWidget(self.source_label)
        layout1.addWidget(self.source_table)
        groupbox1.setLayout(layout1)

        groupbox2 = QGroupBox('BIDS output')
        groupbox2.setSizePolicy(sizepolicy)
        layout2 = QVBoxLayout()
        layout2.addWidget(self.label_dropdown)
        layout2.addWidget(self.datatype_dropdown)
        layout2.addWidget(self.bids_label)
        layout2.addWidget(self.bids_table)
        layout2.addWidget(self.label_bids_name)
        layout2.addWidget(self.view_bids_name)
        groupbox2.setLayout(layout2)

        # Add the boxes to the layout
        layout_tables = QHBoxLayout()
        layout_tables.addWidget(groupbox1)
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

    def center(self):
        """Center the edit window. """
        cp = QDesktopWidget().availableGeometry().center()  # Center point of screen
        qr = self.frameGeometry()                           # Get the rectangular geometry
        qr.moveCenter(cp)                                   # Move rectangle's center point to screen's center point
        self.move(qr.topLeft())                             # Top left of rectangle becomes top left of window centering it

    def get_allowed_suffixes(self):
        """Derive the possible suffixes for each datatype from the template. """
        allowed_suffixes = {}
        for datatype in bids.bidsdatatypes + (bids.unknowndatatype, bids.ignoredatatype):
            allowed_suffixes[datatype] = []
            runs = self.template_bidsmap.get(self.dataformat, {}).get(datatype, [])
            if not runs: continue
            for run in runs:
                suffix = run['bids'].get('suffix')
                if suffix and suffix not in allowed_suffixes.get(datatype, []):
                    allowed_suffixes[datatype].append(suffix)

        self.allowed_suffixes = allowed_suffixes

    def get_editwin_data(self) -> tuple:
        """
        Derive the tabular data from the target_run, needed to render the edit window.

        :return: (data_provenance, data_source, data_bids)
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
            ]
        ]

        data_source = []
        for key, value in self.target_run['attributes'].items():
            data_source.append([
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
        for bidskey in bids.bidskeys:       # Using bidskeys imposes a desired order
            if bidskey in self.target_run['bids']:
                bidsvalue = self.target_run['bids'].get(bidskey, '')
                if (self.target_datatype in bids.bidsdatatypes and bidskey=='suffix') or isinstance(bidsvalue, list):
                    iseditable = False
                else:
                    iseditable = True

                data_bids.append([
                    {
                        'value': bidskey,
                        'iseditable': False
                    },
                    {
                        'value': bidsvalue,
                        'iseditable': iseditable
                    }
                ])

        return data_provenance, data_source, data_bids

    def inspect_sourcefile(self, row: int=None, column: int=None):
        """When double clicked, show popup window. """
        if row == 1 and column == 1:
            sourcefile = Path(self.target_run['provenance'])
            if bids.is_dicomfile(sourcefile):
                sourcedata = pydicom.dcmread(sourcefile, force=True)
            elif bids.is_parfile(sourcefile):
                with open(sourcefile, 'r') as parfid:
                    sourcedata = parfid.read()
            else:
                LOGGER.warning(f"Could not read {self.dataformat} file: {sourcefile}")
                return
            self.popup = InspectWindow(sourcefile, sourcedata, self.dataformat)
            self.popup.show()
            self.popup.scrollbar.setValue(0)     # This can only be done after self.popup.show()

    def source_cell_changed(self, row: int, column: int):
        """Source attribute value has been changed. """
        if column == 1:
            key      = self.source_table.item(row, 0).text()
            value    = self.source_table.item(row, 1).text()
            oldvalue = self.target_run['attributes'].get(key)

            # Only if cell was actually clicked, update (i.e. not when BIDS datatype changes)
            if key and value!=oldvalue:
                LOGGER.warning(f"Expert usage: User has set {self.dataformat}['{key}'] from '{oldvalue}' to '{value}' for {self.target_run['provenance']}")
                self.target_run['attributes'][key] = value

    def bids_cell_changed(self, row: int, column: int):
        """BIDS attribute value has been changed. """
        if column == 1:
            key = self.bids_table.item(row, 0).text()
            if isinstance(self.bids_table.cellWidget(row, 1), QComboBox):
                widget     = self.bids_table.cellWidget(row, 1)
                value      = [widget.itemText(n) for n in range(len(widget))] + [widget.currentIndex()]
                oldvalue   = self.target_run['bids'].get(key)
            else:
                value    = self.bids_table.item(row, 1).text()
                oldvalue = self.target_run['bids'].get(key)

            # Only if cell was actually clicked, update (i.e. not when BIDS datatype changes)
            if key and value != oldvalue:
                # Validate user input against BIDS or replace the (dynamic) bids-value if it is a run attribute
                if isinstance(value, str) and not (value.startswith('<<') and value.endswith('>>')):
                    value = bids.cleanup_value(bids.get_dynamic_value(value, Path(self.target_run['provenance'])))
                    self.bids_table.item(row, 1).setText(value)
                if key == 'run':
                    LOGGER.warning(f"Expert usage: User has set bids['{key}'] from '{oldvalue}' to '{value}' for {self.target_run['provenance']}")
                else:
                    LOGGER.info(f"User has set bids['{key}'] from '{oldvalue}' to '{value}' for {self.target_run['provenance']}")
                self.target_run['bids'][key] = value
                self.refresh_bidsname()

    def fill_table(self, table, data):
        """Fill the table with data"""

        table.blockSignals(True)
        table.clearContents()
        table.setRowCount(len(data))

        # Check if data == data_bids (not very beautiful, but hey, most of us aren't ;-))
        bidstable = False
        for i, row in enumerate(data):
            if 'suffix' in row[0]['value']:
                bidstable = True

        for i, row in enumerate(data):
            key = row[0]['value']
            if self.target_datatype in bids.bidsdatatypes and key=='suffix':
                table.setItem(i, 0, myWidgetItem('suffix', iseditable=False))
                suffixes = self.allowed_suffixes.get(self.target_datatype, [''])
                suffix_dropdown = self.suffix_dropdown = QComboBox()
                suffix_dropdown.addItems(suffixes)
                suffix_dropdown.setCurrentIndex(suffix_dropdown.findText(self.target_run['bids']['suffix']))
                suffix_dropdown.currentIndexChanged.connect(self.suffix_dropdown_change)
                suffix_dropdown.setToolTip('The suffix that sets the different run types apart. First make sure the "Data type" dropdown-menu is set correctly before chosing the right suffix here')
                table.setCellWidget(i, 1, suffix_dropdown)
                continue
            for j, item in enumerate(row):
                value = item.get('value', '')
                if value == 'None':
                    value = ''
                if bidstable and isinstance(value, list):
                    value_dropdown = QComboBox()
                    value_dropdown.addItems(value[0:-1])
                    value_dropdown.setCurrentIndex(value[-1])
                    value_dropdown.currentIndexChanged.connect(partial(self.bids_cell_changed, i, j))
                    if j == 0:
                        value_dropdown.setToolTip(bids.get_bidshelp(key))
                    table.setCellWidget(i, j, value_dropdown)
                else:
                    value_item = myWidgetItem(value, iseditable=item['iseditable'])
                    if bidstable and j == 0:
                        value_item.setToolTip(bids.get_bidshelp(key))
                    table.setItem(i, j, value_item)

        table.blockSignals(False)

    def set_table(self, data, minimum: bool=True) -> QTableWidget:
        """Return a table widget from the data. """
        table = myQTableWidget(minimum=minimum)
        table.setColumnCount(2) # Always two columns (i.e. key, value)
        horizontal_header = table.horizontalHeader()
        horizontal_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        horizontal_header.setSectionResizeMode(1, QHeaderView.Stretch)
        horizontal_header.setVisible(False)

        self.fill_table(table, data)

        return table

    def refresh_bidsname(self):
        """Updates the bidsname with the current (edited) bids values"""
        bidsname = (Path(self.target_datatype)/bids.get_bidsname(self.subid, self.sesid, self.target_run)).with_suffix('.*')

        font = self.view_bids_name.font()
        if self.target_datatype==bids.unknowndatatype:
            self.view_bids_name.setToolTip(f"Red: This imaging data type is not part of BIDS but will be converted to a BIDS-like entry in the '{bids.unknowndatatype}' folder. Click 'OK' if you want your BIDS output data to look like this")
            self.view_bids_name.setTextColor(QtGui.QColor('red'))
            font.setStrikeOut(False)
        elif self.target_datatype == bids.ignoredatatype:
            self.view_bids_name.setToolTip("Gray / Strike-out: This imaging data type will be ignored and not converted BIDS. Click 'OK' if you want your BIDS output data to look like this")
            self.view_bids_name.setTextColor(QtGui.QColor('gray'))
            font.setStrikeOut(True)
        elif not bids.check_run(self.target_datatype, self.target_run):
            self.view_bids_name.setToolTip(f"Red: This name is not valid according to the BIDS standard")
            self.view_bids_name.setTextColor(QtGui.QColor('red'))
            font.setStrikeOut(False)
        else:
            self.view_bids_name.setToolTip(f"Green: This '{self.target_datatype}' imaging data type is part of BIDS. Click 'OK' if you want your BIDS output data to look like this")
            self.view_bids_name.setTextColor(QtGui.QColor('green'))
            font.setStrikeOut(False)
        self.view_bids_name.setFont(font)
        self.view_bids_name.clear()
        self.view_bids_name.textCursor().insertText(str(bidsname))

    def change_run(self, suffix_idx):
        """
        Resets the edit dialog window with a new target_run from the template bidsmap.

        :param suffix_idx: The suffix or index number that will used to extract the run from the template bidsmap
        :return:
        """

        # Get the new target_run
        self.target_run = bids.get_run(self.template_bidsmap, self.dataformat, self.target_datatype, suffix_idx, Path(self.target_run['provenance']))

        # Insert the new target_run in our target_bidsmap
        self.target_bidsmap = bids.update_bidsmap(self.target_bidsmap,
                                                  self.current_datatype,
                                                  Path(self.target_run['provenance']),
                                                  self.target_datatype,
                                                  self.target_run,
                                                  self.dataformat)

        # Now that we have updated the bidsmap, we can also update the current_datatype
        self.current_datatype = self.target_datatype

        # Reset the edit window with the new target_run
        self.reset(refresh=True)

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
        _, data_source, data_bids = self.get_editwin_data()

        # Refresh the existing tables
        self.fill_table(self.source_table, data_source)
        self.fill_table(self.bids_table, data_bids)

        # Refresh the BIDS output name
        self.refresh_bidsname()

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

    def get_help(self):
        """Open web page for help. """
        help_url = HELP_URLS.get(self.target_datatype, HELP_URL_DEFAULT)
        webbrowser.open(help_url)

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

        super(EditDialog, self).reject()

    def accept_run(self):
        """Save the changes to the target_bidsmap and send it back to the main window: Finished! """

        if not bids.check_run(self.target_datatype, self.target_run):
            answer = QMessageBox.question(self, 'Edit BIDS mapping', f'The "{self.target_datatype}/*_{self.target_run["bids"]["suffix"]}" run is not valid according to the BIDS standard. Do you want to go back and edit the run?',
                                          QMessageBox.Yes | QMessageBox.No | QMessageBox.Yes)
            if answer == QMessageBox.Yes:
                return
            LOGGER.warning(f'The "{self.view_bids_name.toPlainText()}" run is not valid according to the BIDS standard")')

        if self.target_datatype=='fmap' and not self.target_run['bids']['IntendedFor']:
            answer = QMessageBox.question(self, 'Edit BIDS mapping', "The 'IntendedFor' bids-label was not set, which can make that your fieldmap won't be used when "
                                                                     "pre-processing / analyzing the associated imaging data (e.g. fMRI data). Do you want to go back "
                                                                     "and set this label?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Yes)
            if answer == QMessageBox.Yes:
                return
            LOGGER.warning(f"'IntendedFor' fieldmap value was not set")

        LOGGER.info(f'User has approved the edit')
        self.target_bidsmap = bids.update_bidsmap(self.target_bidsmap,
                                                  self.current_datatype,
                                                  self.target_run['provenance'],
                                                  self.target_datatype,
                                                  self.target_run,
                                                  self.dataformat)

        self.done_edit.emit(self.target_bidsmap)
        self.done(1)

    def export_run(self):

        yamlfile, _ = QFileDialog.getOpenFileName(self, 'Export run item to (template) bidsmap',
                        str(bids.bidsmap_template), 'YAML Files (*.yaml *.yml);;All Files (*)')
        if yamlfile:
            LOGGER.info(f'Exporting run item: bidsmap[{self.dataformat}][{self.target_datatype}] -> {yamlfile}')
            yamlfile   = Path(yamlfile)
            bidsmap, _ = bids.load_bidsmap(yamlfile, Path(), False)
            bidsmap    = bids.append_run(bidsmap, self.dataformat, self.target_datatype, self.target_run)
            bids.save_bidsmap(yamlfile, bidsmap)
            QMessageBox.information(self, 'Edit BIDS mapping', f"Successfully exported:\n\nbidsmap[{self.dataformat}][{self.target_datatype}] -> {yamlfile}")


def bidseditor(bidsfolder: str, bidsmapfile: str='', templatefile: str='', dataformat: str='DICOM', subprefix='sub-', sesprefix='ses-'):
    """
    Collects input and launches the bidseditor GUI

    :param bidsfolder:
    :param bidsmapfile:
    :param templatefile:
    :param dataformat:
    :param subprefix:
    :param sesprefix:
    :return:
    """

    bidsfolder   = Path(bidsfolder).resolve()
    bidsmapfile  = Path(bidsmapfile)
    templatefile = Path(templatefile)

    # Start logging
    bids.setup_logging(bidsfolder/'code'/'bidscoin'/'bidseditor.log')
    LOGGER.info('')
    LOGGER.info('-------------- START BIDSeditor ------------')
    LOGGER.info(f">>> bidseditor bidsfolder={bidsfolder} bidsmap={bidsmapfile} template={templatefile}"
                f"dataformat={dataformat} subprefix={subprefix} sesprefix={sesprefix}")

    # Obtain the initial bidsmap info
    template_bidsmap, templatefile = bids.load_bidsmap(templatefile, bidsfolder/'code'/'bidscoin')
    input_bidsmap, bidsmapfile     = bids.load_bidsmap(bidsmapfile,  bidsfolder/'code'/'bidscoin')
    output_bidsmap                 = copy.deepcopy(input_bidsmap)
    if not input_bidsmap:
        LOGGER.error(f'No bidsmap file found in {bidsfolder}. Please run the bidsmapper first and / or use the correct bidsfolder')
        return

    # Start the Qt-application
    app = QApplication(sys.argv)
    app.setApplicationName(f"{bidsmapfile} - BIDS editor {bids.version()}")
    mainwin = MainWindow()
    gui = Ui_MainWindow()
    gui.setupUi(mainwin, bidsfolder, bidsmapfile, input_bidsmap, output_bidsmap, template_bidsmap, dataformat, subprefix=subprefix, sesprefix=sesprefix)
    mainwin.show()
    app.exec()

    LOGGER.info('-------------- FINISHED! -------------------')
    LOGGER.info('')

    bids.reporterrors()


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
    parser.add_argument('-b','--bidsmap',       help='The bidsmap YAML-file with the study heuristics. If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap.yaml', default='bidsmap.yaml')
    parser.add_argument('-t','--template',      help='The bidsmap template with the default heuristics (this could be provided by your institute). If the bidsmap filename is relative (i.e. no "/" in the name) then it is assumed to be located in bidsfolder/code/bidscoin. Default: bidsmap_dccn.yaml', default='bidsmap_dccn.yaml')
    parser.add_argument('-d','--dataformat',    help='The format of the source data, e.g. DICOM or PAR. Default: DICOM', default='DICOM')
    parser.add_argument('-n','--subprefix',     help="The prefix common for all the source subject-folders. Default: 'sub-'", default='sub-')
    parser.add_argument('-m','--sesprefix',     help="The prefix common for all the source session-folders. Default: 'ses-'", default='ses-')
    args = parser.parse_args()

    bidseditor(bidsfolder   = args.bidsfolder,
               bidsmapfile  = args.bidsmap,
               templatefile = args.template,
               dataformat   = args.dataformat,
               subprefix    = args.subprefix,
               sesprefix    = args.sesprefix)


if __name__ == '__main__':
    main()
