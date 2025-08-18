# -*- coding: utf-8 -*-
"""
plaid - plot azimuthally integrated ata
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides the main application window for plotting azimuthally integrated data,
including loading files, displaying heatmaps and patterns, and managing auxiliary data.
"""
import sys
import os
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QDockWidget,
                             QSizePolicy, QFileDialog, QMessageBox, QProgressDialog, QCheckBox)
from PyQt6.QtGui import QAction, QIcon
from PyQt6 import QtCore
import pyqtgraph as pg
import h5py as h5
from datetime import datetime
import argparse
try:
    import requests
    import packaging.version
    HAS_UPDATE_CHECKER = True
except ImportError:
    HAS_UPDATE_CHECKER = False

script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from plaid.trees import FileTreeWidget, CIFTreeWidget
from plaid.dialogs import H5Dialog, ExportSettingsDialog, ColorCycleDialog
from plaid.reference import Reference
from plaid.plot_widgets import HeatmapWidget, PatternWidget, AuxiliaryPlotWidget
from plaid.misc import q_to_tth, tth_to_q
from plaid.data_containers import AzintData, AuxData
from plaid import __version__ as CURRENT_VERSION
import plaid.resources




# # debug fn to show who is calling what and when to find out why.
# import inspect
# def print_stack(context=True):
#     print('>----|')
#     if context:
#         print('\n'.join([f"{x.lineno:>5}| {x.function} > {''.join(x.code_context).strip()}" for x in inspect.stack()][1:][::-1]))
#     else:
#         print('\n'.join([f"{x.lineno:>5}| {x.function}" for x in inspect.stack()][1:][::-1]))


# TODO/IDEAS
# - Clean up the code and restructure
# - Expand the Help menu 
# - Export patterns
#     > Add an "Export average pattern" toolbar button
#     > Add an "Export selected pattern(s)" toolbar button
#     > Add an "Export all patterns" toolbar button
# - handle arbitrary .h5 file drag drop
#     > if the dropped file is recognized as a azint file, load it and add it to the file tree
#     > if not, prompt the user to load it as auxiliary data. Future versions could allow for custom azint readers?
# - add an option to "group"  data files in the file tree. Perhaps "append file below" and "insert file above" actions to group files together?
#     > Find a way to handle I0 data
# - save additional settings like default path(s), dock widget positions, etc.
# - optimize memory usage and performance for large datasets
# - add more tooltips

ALLOW_EXPORT_ALL_PATTERNS = True
PLOT_I0 = True

colors = [
        '#AAAA00',  # Yellow
        '#AA00AA',  # Magenta
        '#00AAAA',  # Cyan
        '#AA0000',  # Red
        '#00AA00',  # Green
        "#0066FF",  # Blue
        '#AAAAAA',  # Light Gray
        ]

# Update checking
def check_for_updates():
    """
    Check if a newer version is available on PyPI.
    Returns the latest version string if an update is available, None otherwise.
    """
    if not HAS_UPDATE_CHECKER:
        return None
        
    try:
        response = requests.get("https://pypi.org/pypi/plaid-xrd/json", timeout=5)
        if response.status_code == 200:
            data = response.json()
            latest_version = data['info']['version']
            if packaging.version.parse(latest_version) > packaging.version.parse(CURRENT_VERSION):
                return latest_version
    except Exception:
        # Silently fail if network is unavailable or other issues
        pass
    return None

def read_settings():
    """Read the application settings from a file."""
    settings = QtCore.QSettings("plaid", "plaid")
    print(settings.allKeys())

def write_settings():
    """Write the application settings to a file."""
    settings = QtCore.QSettings("plaid", "plaid")
    settings.beginGroup("MainWindow")
    settings.setValue("recent-files", [])
    settings.setValue("recent-references", [])

def save_recent_files_settings(recent_files):
    """
    Save the recent files settings.
    Save up to 10 recent files, avoid duplicates, and remove any empty entries.
    If the list exceeds 10 files, remove the oldest file.
    """
    settings = QtCore.QSettings("plaid", "plaid")
    settings.beginGroup("MainWindow")
    # Read the existing recent files
    existing_files = settings.value("recent-files", [], type=list)
    # Remove duplicates while preserving order
    recent_files = list(dict.fromkeys(recent_files[::-1] + existing_files))
    recent_files = [f for f in recent_files if f]  # Remove empty entries
    # Limit to the last 10 files
    if len(recent_files) > 10:
        recent_files = recent_files[-10:]
    # Save the recent files
    settings.setValue("recent-files", recent_files)
    settings.endGroup()

def read_recent_files_settings():
    """Read the recent files settings from a file."""
    settings = QtCore.QSettings("plaid", "plaid")
    settings.beginGroup("MainWindow")
    recent_files = settings.value("recent-files", [], type=list)
    settings.endGroup()
    return recent_files

def clear_recent_files_settings():
    """Clear the recent files settings."""
    settings = QtCore.QSettings("plaid", "plaid")
    settings.beginGroup("MainWindow")
    settings.setValue("recent-files", [])
    settings.endGroup()

def save_recent_refs_settings(recent_refs):
    """
    Save the recent references settings.
    Save up to 10 recent references, avoid duplicates, and remove any empty entries.
    If the list exceeds 10 references, remove the oldest reference.
    """
    settings = QtCore.QSettings("plaid", "plaid")
    settings.beginGroup("MainWindow")
    # Read the existing recent references
    existing_refs = settings.value("recent-references", [], type=list)
    # Remove duplicates and empty entries
    recent_refs = list(dict.fromkeys(recent_refs[::-1] + existing_refs))
    recent_refs = [r for r in recent_refs if r]  # Remove empty entries
    # Limit to the last 10 references
    if len(recent_refs) > 10:
        recent_refs = recent_refs[-10:]
    # Save the recent references
    settings.setValue("recent-references", recent_refs)
    settings.endGroup()

def read_recent_refs_settings():
    """Read the recent references settings from a file."""
    settings = QtCore.QSettings("plaid", "plaid")
    settings.beginGroup("MainWindow")
    recent_refs = settings.value("recent-references", [], type=list)
    settings.endGroup()
    return recent_refs

def clear_recent_refs_settings():
    """Clear the recent references settings."""
    settings = QtCore.QSettings("plaid", "plaid")
    settings.beginGroup("MainWindow")
    settings.setValue("recent-references", [])
    settings.endGroup()

def clear_all_settings():
    """Clear all saved settings."""
    settings = QtCore.QSettings("plaid", "plaid")
    settings.clear()
    print("All settings cleared.")


class MainWindow(QMainWindow):
    """plaid - Main application window for plotting azimuthally integrated data."""
    def __init__(self):
        super().__init__()

        self.setWindowTitle("plaid - plot azimuthally integrated data")
        self.statusBar().showMessage("")
        # Set the window icon
        self.setWindowIcon(QIcon(":/icons/plaid.png"))
    
        self.E = None  # Energy in keV
        self.is_Q = False # flag to indicate if the data is in Q space (True) or 2theta space (False)

        self.azint_data = AzintData()
        self.aux_data = {}
        
        self._load_color_cycle()
        if not self.color_cycle:
            self.color_cycle = colors

        # create the export settings dialog
        self.export_settings_dialog = ExportSettingsDialog(self)
        self.export_settings_dialog.set_settings(self._load_export_settings())
        self.export_settings_dialog.sigSaveAsDefault.connect(self._save_export_settings)

        self.color_dialog = ColorCycleDialog(self,initial_colors=self.color_cycle)
        self.color_dialog.colorCycleChanged.connect(self._update_color_cycle)

        # Create the main layout
        main_layout = QHBoxLayout()
        #tree_layout = QVBoxLayout()
        plot_layout = QVBoxLayout()
        #main_layout.addLayout(tree_layout,1)
        main_layout.addLayout(plot_layout,4)
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        self.centralWidget().setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Create the heatmap widget
        self.heatmap = HeatmapWidget(self)

        # Create the PatternWidget
        self.pattern = PatternWidget(self)

        # Add the widgets to the main layout
        plot_layout.addWidget(self.heatmap,1)
        plot_layout.addWidget(self.pattern,1, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)# | QtCore.Qt.AlignmentFlag.AlignTop, )

        # Create the dock widgets
        self._init_file_tree()
        self._init_cif_tree()
        self._init_auxiliary_plot()
        # Add the dock widgets to the main window
        self._init_dock_widget_settings()

        # initialize the widget connections
        # This connects the signals and slots between the widgets
        self._init_connections()

        # add initial horizontal and vertical lines to the heatmap and auxiliary plot
        self.heatmap.addHLine()
        #self.auxiliary_plot.addVLine()

        # initialize the menu bar menus
        self._init_menu_bar()

        # override the resize event to update the pattern width
        self.centralWidget().resizeEvent = self.resizeEvent

        # set the initial widths of the dock widgets
        self.resizeDocks([self.file_tree_dock, self.cif_tree_dock, self.auxiliary_plot_dock],
                         [250, 250, 250], 
                         QtCore.Qt.Orientation.Horizontal)

        # ensure color cycle is updated
        self._update_color_cycle(self.color_dialog.get_colors())

        # Check for updates on startup (non-blocking)
        self._check_for_updates_on_startup()

    def _init_file_tree(self):
        """Initialize the file tree widget. Called by self.__init__()."""
        # Create the file tree widget
        self.file_tree = FileTreeWidget()
        # create a dock widget for the file tree
        file_tree_dock = QDockWidget("File Tree", self)
        file_tree_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        file_tree_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        file_tree_dock.setWidget(self.file_tree)
        self.file_tree_dock = file_tree_dock

    def _init_cif_tree(self):
        """Initialize the CIF tree widget. Called by self.__init__()."""
        # Create the CIF tree widget
        self.cif_tree = CIFTreeWidget(self)
        # create a dock widget for the CIF tree
        cif_tree_dock = QDockWidget("CIF Tree", self)
        cif_tree_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        cif_tree_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        cif_tree_dock.setWidget(self.cif_tree)
        self.cif_tree_dock = cif_tree_dock

    def _init_auxiliary_plot(self):
        """Initialize the auxiliary plot widget. Called by self.__init__()."""
        self.auxiliary_plot = AuxiliaryPlotWidget()
        # create a dock widget for the auxiliary plot
        auxiliary_plot_dock = QDockWidget("Auxiliary Plot", self)
        auxiliary_plot_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        auxiliary_plot_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        auxiliary_plot_dock.setWidget(self.auxiliary_plot)
        self.auxiliary_plot_dock = auxiliary_plot_dock

    def _init_dock_widget_settings(self):
        """Initialize the dock widgets based on previously saved settings. Called by self.__init__()."""
        # get the current dock widget settings (if any)
        left, right = self._load_dock_settings()
        # if settings for all three dock widgets are available
        if len(left) + len(right) == 3:
            dock_widgets = {self.file_tree_dock.windowTitle(): self.file_tree_dock,
                            self.cif_tree_dock.windowTitle(): self.cif_tree_dock,
                            self.auxiliary_plot_dock.windowTitle(): self.auxiliary_plot_dock}
            for [key,is_visible] in left:
                dock = dock_widgets[key]
                self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)
                dock.setVisible(is_visible)
            for [key,is_visible] in right:
                dock = dock_widgets[key]
                self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
                dock.setVisible(is_visible)
        else:
            self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.file_tree_dock)
            self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.cif_tree_dock)
            self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.auxiliary_plot_dock)
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks)

    def _init_connections(self):
        """Initialize the connections between the widgets. Called by self.__init__()."""
        # Connect the file tree signals to the appropriate slots
        self.file_tree.sigItemDoubleClicked.connect(self.load_file)
        self.file_tree.sigGroupDoubleClicked.connect(self.load_file)
        self.file_tree.sigItemRemoved.connect(self.remove_file)
        self.file_tree.sigI0DataRequested.connect(self.load_I0_data)
        self.file_tree.sigAuxiliaryDataRequested.connect(self.load_auxiliary_data)
        # Connect the CIF tree signals to the appropriate slots
        self.cif_tree.sigItemAdded.connect(self.add_reference)
        self.cif_tree.sigItemChecked.connect(self.toggle_reference)
        self.cif_tree.sigItemDoubleClicked.connect(self.rescale_reference)
        # Connect the heatmap signals to the appropriate slots
        self.heatmap.sigHLineMoved.connect(self.hline_moved)
        self.heatmap.sigXRangeChanged.connect(self.pattern.set_xrange)
        self.heatmap.sigImageDoubleClicked.connect(self.add_pattern)
        self.heatmap.sigImageHovered.connect(self._update_status_bar)
        self.heatmap.sigHLineRemoved.connect(self.remove_pattern)
        # Connect the pattern signals to the appropriate slots
        self.pattern.sigXRangeChanged.connect(self.heatmap.set_xrange)
        self.pattern.sigPatternHovered.connect(self.update_status_bar)
        # Connect the auxiliary plot signals to the appropriate slots
        self.auxiliary_plot.sigVLineMoved.connect(self.vline_moved)
        self.auxiliary_plot.sigAuxHovered.connect(self.update_status_bar_aux)

    def _init_menu_bar(self):
        """Initialize the menu bar with the necessary menus and actions. Called by self.__init__()."""
        # Create a menu bar
        menu_bar = self.menuBar()
        self._init_file_menu(menu_bar)
        self._init_view_menu(menu_bar)
        self._init_export_menu(menu_bar)
        self._init_help_menu(menu_bar)

    def _init_file_menu(self, menu_bar):
        """Initialize the File menu with actions for loading files and references. Called by self._init_menu_bar()."""
        # Create a file menu
        file_menu = menu_bar.addMenu("&File")
        # Add an action to load azimuthal integration data
        open_action = QAction("&Open", self)
        open_action.setToolTip("Open an HDF5 file")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        # add a menu with actions to open recent files
        recent_files = read_recent_files_settings()
        recent_menu = file_menu.addMenu("Open &Recent")
        if recent_files:
            recent_menu.setEnabled(True)
            recent_menu.setToolTip("Open a recent file")
            for file in recent_files:
                action = QAction(file, self)
                action.setToolTip(f"Open {file}")
                # action.triggered.connect(lambda checked, f=file: self.file_tree.add_file(f))
                action.triggered.connect(lambda checked, f=file: self.open_file(f))
                action.setDisabled(not os.path.exists(file))  # Disable if file does not exist
                recent_menu.addAction(action)
        else:
            recent_menu.setEnabled(False)
            recent_menu.setToolTip("No recent files available")

        file_menu.addSeparator()

        # add an action to load a reference from a cif
        load_cif_action = QAction("Load &CIF",self)
        load_cif_action.setToolTip("Load a reference from a CIF file")
        load_cif_action.triggered.connect(self.open_cif_file)
        file_menu.addAction(load_cif_action)

        # add a menu to load recent references
        recent_refs = read_recent_refs_settings()
        recent_references_menu = file_menu.addMenu("&Load Recent")
        if recent_refs:
            recent_references_menu.setEnabled(True)
            recent_references_menu.setToolTip("Load a recent reference")
            for ref in recent_refs:
                action = QAction(ref, self)
                action.setToolTip(f"Load {ref}")
                action.triggered.connect(lambda checked, r=ref: self.cif_tree.add_file(r))
                action.setDisabled(not os.path.exists(ref))
                recent_references_menu.addAction(action)
        else:
            recent_references_menu.setEnabled(False)
            recent_references_menu.setToolTip("No recent references available")

    def _init_view_menu(self, menu_bar):
        """Initialize the View menu with actions to toggle visibility of dock widgets and auxiliary plots. Called by self._init_menu_bar()."""
        # create a view menu
        view_menu = menu_bar.addMenu("&View")
        # Add an action to toggle the file tree visibility
        toggle_file_tree_action = self.file_tree_dock.toggleViewAction()
        toggle_file_tree_action.setText("Show &File Tree")
        view_menu.addAction(toggle_file_tree_action)
        # Add an action to toggle the CIF tree visibility
        toggle_cif_tree_action = self.cif_tree_dock.toggleViewAction()
        toggle_cif_tree_action.setText("Show &CIF Tree")
        view_menu.addAction(toggle_cif_tree_action)
        # Add an action to toggle the auxiliary plot visibility
        toggle_auxiliary_plot_action = self.auxiliary_plot_dock.toggleViewAction()
        toggle_auxiliary_plot_action.setText("Show &Auxiliary Plot")
        view_menu.addAction(toggle_auxiliary_plot_action)
        # add a separator
        view_menu.addSeparator()
        # add a toggle Q action
        toggle_q_action = QAction("&Q (Å-1)",self)
        toggle_q_action.setCheckable(True)
        toggle_q_action.setChecked(self.is_Q)
        toggle_q_action.triggered.connect(self.toggle_q)
        view_menu.addAction(toggle_q_action)
        self.toggle_q_action = toggle_q_action
        # add a separator
        view_menu.addSeparator()
        # add a change color cycle action
        change_color_cycle_action = QAction("&Change Color Cycle", self)
        change_color_cycle_action.triggered.connect(self.show_color_cycle_dialog)
        view_menu.addAction(change_color_cycle_action)

    def _init_export_menu(self, menu_bar):
        """Initialize the Export menu with actions to export patterns and settings. Called by self._init_menu_bar()."""
        # create an export menu
        export_menu = menu_bar.addMenu("&Export")
        # Add an action to export the average pattern
        export_average_action = QAction("&Export Average Pattern", self)
        export_average_action.setToolTip("Export the average pattern to a double-column file")
        export_average_action.triggered.connect(self.export_average_pattern)
        export_menu.addAction(export_average_action)
        
        # Add an action to export the current pattern(s)
        export_pattern_action = QAction("Export &Pattern(s)", self)
        export_pattern_action.setToolTip("Export the current pattern(s) to double-column file(s)")
        export_pattern_action.triggered.connect(self.export_pattern)
        export_menu.addAction(export_pattern_action)

        # add an action to export all patterns
        export_all_action = QAction("Export &All Patterns", self)
        export_all_action.setToolTip("Export all patterns to double-column files")
        export_all_action.triggered.connect(self.export_all_patterns)
        export_all_action.setEnabled(ALLOW_EXPORT_ALL_PATTERNS)  # Enable only if allowed
        export_menu.addAction(export_all_action) 

        export_menu.addSeparator()
        
        # Add an action to open the export settings dialog
        export_settings_action = QAction("Export &settings", self)
        export_settings_action.setToolTip("Open the export settings dialog")
        export_settings_action.triggered.connect(self.export_settings_dialog.open)
        export_menu.addAction(export_settings_action)

    def _init_help_menu(self, menu_bar):
        """Initialize the Help menu with actions to show help and about dialogs. Called by self._init_menu_bar()."""
        # create a help menu
        help_menu = menu_bar.addMenu("&Help")
        # Add an action to show the help dialog
        help_action = QAction("&Help", self)
        help_action.setToolTip("Show help dialog")
        help_action.triggered.connect(self.show_help_dialog)
        help_menu.addAction(help_action)
        
        # Add separator
        help_menu.addSeparator()
        
        # Add action to check for updates
        update_action = QAction("Check for &Updates", self)
        update_action.setToolTip("Check for newer versions on PyPI")
        update_action.triggered.connect(self.check_for_updates_manual)
        update_action.setEnabled(HAS_UPDATE_CHECKER)  # Only enable if requests is available
        help_menu.addAction(update_action)
        
        # Add separator
        help_menu.addSeparator()
        
        # Add an action to show the about dialog
        about_action = QAction("&About", self)
        about_action.setToolTip("Show about dialog")
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def add_pattern(self, pos):
        """
        Add a horizontal line to the heatmap and an accompanying pattern.
        This method is called when the user double-clicks on the heatmap, 
        using the position of the double-click to determine which frame to plot.
        """
        index = int(np.clip(pos[1], 0, self.azint_data.shape[0]-1))
        y = self.azint_data.get_I(index=index)  # Get the intensity data for the current frame
        self.heatmap.addHLine(pos=index)
        self.pattern.add_pattern()
        self.pattern.set_data(y=y, index=len(self.pattern.pattern_items)-1)
        self.pattern.set_pattern_name(name=f"frame {index}", index=len(self.pattern.pattern_items)-1)

        # add a vertical line to the auxiliary plot
        if self.auxiliary_plot.n is not None:
            self.auxiliary_plot.addVLine(pos=index)

    def remove_pattern(self, index):
        """
        Remove a pattern from the pattern plot.  
        Called when a horizontal line is removed from the heatmap.
        """
        self.pattern.remove_pattern(index)
        self.auxiliary_plot.remove_v_line(index)

    def remove_file(self, file):
        """
        Handle the removal of a file from the file tree, by
        clearing the azint_data and auxiliary plot if relevant.
        Called when a file is removed from the file tree.
        """
        if self.azint_data.fnames is not None and file in self.azint_data.fnames:
            self.azint_data = AzintData(self)
            self.heatmap.clear()
            self.pattern.clear()
            self.auxiliary_plot.clear()

        if file in self.aux_data.keys():
            del self.aux_data[file]

    def resizeEvent(self, event):
        """Handle the resize event to update the pattern width."""
        super().resizeEvent(event)
        self.update_pattern_geometry()

    def update_pattern_geometry(self):
        """Update the geometry of the pattern widget to match the heatmap."""
        self.pattern.plot_widget.setFixedWidth(self.heatmap.plot_widget.width())

    def _update_status_bar(self, pos):
        """
        Update the status bar with the current position in the heatmap
        by passing the x and y indices to the update_status_bar method.
        This method is called when the user hovers over the heatmap.
        """
        if pos is None:
            self.update_status_bar(None)
            return
        x_idx, y_idx = pos
        if self.azint_data.x is None:
            return
        if self.is_Q:
            x_value = self.azint_data.get_q()[x_idx]
        else:
            x_value = self.azint_data.get_tth()[x_idx]
        #y_value = self.azint_data.I[y_idx, x_idx] if self.azint_data.I is not None else 0
        y_value = self.azint_data.get_I(index=y_idx)[x_idx] if self.azint_data.I is not None else 0
        self.update_status_bar((x_value, y_value))

    def update_status_bar(self, pos):
        """
        Update the status bar with the current cursor position for the heatmap
        and pattern plots. Includes both Q and d-spacing if the energy is available.
        """
        if pos is None:
            self.statusBar().showMessage(self.azint_data.get_info_string())
            return
        x_value, y_value = pos
        if self.azint_data.x is None:
            return
        if self.is_Q:
            Q = x_value
            tth = q_to_tth(Q, self.E) if self.E is not None else 0
        else:
            tth = x_value
            Q = tth_to_q(tth, self.E) if self.E is not None else 0
        d = 2* np.pi / Q if Q != 0 else 0
        status_text = f"2θ: {tth:6.2f}, Q: {Q:6.3f}, d: {d:6.3f}, Intensity: {y_value:7.1f}"
        self.statusBar().showMessage(status_text)

    def update_status_bar_aux(self, pos):
        """Update the status bar with the auxiliary plot position."""
        if pos is None:
            self.statusBar().showMessage(self.azint_data.get_info_string())
            return
        x_value, y_value = pos
        # determine which string formatting to use based on the values
        status_text = f"X: {x_value:7.1f}, "   
        if np.abs(y_value) < 1e-3 or np.abs(y_value) >= 1e4:
            # use scientific notation for very small or very large values
            status_text += f"Y: {y_value:.3e}" 
        else:
            # use normal float formatting for other values
            status_text += f"Y: {y_value:7.3f}"
        self.statusBar().showMessage(status_text)
        
    def open_file(self,file_path=None):
        """
        Open the optional provided file path or a file dialog to select an azimuthal 
        integration file and add it to the file tree.
        """
        if not file_path:
            # prompt the user to select a file
            if self.file_tree.files and self.file_tree.files[-1] is not None:
                default_dir = os.path.dirname(self.file_tree.files[-1])
            else:
                default_dir = os.path.expanduser("~")
            file_path, ok = QFileDialog.getOpenFileName(self, "Select Azimuthal Integration File", default_dir, "HDF5 Files (*.h5);;All Files (*)")
            if not ok or not file_path:
                return
        self.load_file(file_path)
        shape  = self.azint_data.shape
        if shape is not None:
            # add the file to the file tree
            item = self.file_tree.add_file(file_path,shape)

            self.file_tree.set_target_item_status_tip(self.azint_data.get_info_string(), item)

            # # if the file was loaded with I0 data (nxmonitor), set the status tip
            # # of the file tree item to indicate that it has I0 data
            # if self.azint_data.I0 is not None:
            #     # if the azint_data has I0 data, add it to the file tree item
            #     self.file_tree.set_target_item_status_tip("I0 corrected", item)
        
    def load_file(self, file_path, item=None):
        """
        Load the selected file and update the heatmap and pattern.
        This method is called both when a new file is add by the 
        open_file method and when a file is reloaded, for instance
        when a file is double-clicked in the file tree.
        If the file is alreadyl loaded, it will be reloaded.
        """
        if isinstance(file_path, str):
            file_path = [file_path]  # Ensure file_path is a list
        file_path = [os.path.abspath(f) for f in file_path]  # Convert to absolute paths
        # Check if this is the initial load or a reload, i.e. is the method called
        # with an item from the file tree
        is_initial_load = item is None  
        self.azint_data = AzintData(self,file_path)
        if not self.azint_data.load(look_for_I0=is_initial_load):
            QMessageBox.critical(self, "Error", f"Failed to load file: {file_path[0]}")
            return
        
        # clear the auxiliary plot and check for I0 and auxiliary data
        self.auxiliary_plot.clear()  # Clear the previous plot
        aux_plot_key = None

        # check if the azint_data already has I0 data from a nxmonitor dataset
        # and if so, set the I0 data of the corresponding aux_data. The I0 data
        # of the azint_data is overwritten in the next step, but this ensures that
        # the I0 data conforms to the aux_data I0 format.
        if is_initial_load and isinstance(self.azint_data.I0, np.ndarray):
            if not file_path[0] in self.aux_data:
                # if the file is not already in the aux_data, add it
                self.aux_data[file_path[0]] = AuxData(self)
            self.aux_data[file_path[0]].set_I0(self.azint_data.I0)
            I0 = self.aux_data[file_path[0]].get_data('I0')
            if I0 is not None:
                self.azint_data.set_I0(I0)
                aux_plot_key = file_path[0]
            
        if item is not None and not isinstance(item, list): # for now, only handle a single item
            # check if the item has I0 data
            if item.toolTip(0) in self.aux_data:
                I0 = self.aux_data[item.toolTip(0)].get_data('I0')
                if I0 is not None:
                    self.azint_data.set_I0(I0)
                if len(self.aux_data[item.toolTip(0)].keys()) > 0:
                    # if there are more keys, plot the auxiliary data
                    aux_plot_key = item.toolTip(0)

        elif isinstance(item, list):
            # check if grouped auxiliary data already exists
            group_path = ";".join([i.toolTip(0) for i in item])
            if group_path in self.aux_data:
                aux_data = self.aux_data[group_path]
           
            # if no grouped auxiliary data exists, but any of the items
            # have auxiliary data, append the data to the aux_data dict
            elif any(i.toolTip(0) in self.aux_data for i in item):
                self.aux_data[group_path] = AuxData()
                aliases = [self.aux_data[i.toolTip(0)].keys() for i in item if i.toolTip(0) in self.aux_data]
                aliases = set().union(*aliases)  # Flatten the list of lists and remove duplicates
                aliases = list(aliases)  # Convert back to a list
                for alias in aliases:
                    data = np.array([])
                    for i in item:
                        # get the shape of the filetree item
                        _n = self.file_tree.get_item_shape(i)[0]
                        if i.toolTip(0) in self.aux_data and alias in self.aux_data[i.toolTip(0)].keys():
                            _data = self.aux_data[i.toolTip(0)].get_data(alias)
                        else:
                            _data = None
                        if _data is None:
                            _data = np.full((_n,), np.nan)  # Fill with NaN if no data is available
                        data = np.append(data, _data)
                    self.aux_data[group_path].add_data(alias, data)
                I0 = self.aux_data[group_path].I0
                if I0 is not None:
                    I0[np.isnan(I0)] = 1. # Replace NaN with 1
                self.aux_data[group_path].set_I0(I0)
                aux_data = self.aux_data[group_path]
            else:
                aux_data = None
            if aux_data is not None:
                I0 = aux_data.get_data('I0')
                if I0 is not None:
                    self.azint_data.set_I0(I0)
                if len(aux_data.keys()) > 0:
                    # if there are more keys, plot the auxiliary data
                    aux_plot_key = group_path
        
        x = self.azint_data.get_tth() if not self.azint_data.is_q else self.azint_data.get_q()
        I = self.azint_data.get_I()
        y_avg = self.azint_data.get_average_I()
        is_q = self.azint_data.is_q
        self.is_Q = is_q
        self.toggle_q_action.setChecked(is_q)
        if self.azint_data.E is not None:
            self.E = self.azint_data.E
        
        # Update the heatmap with the new data
        self.heatmap.set_data(x, I.T)
        # self.heatmap.set_data(x_edge, y_edge, I)
        self.heatmap.set_xlabel("2theta (deg)" if not is_q else "q (1/A)")


        # Update the pattern with the first frame
        self.pattern.set_data(x, I[0])
        self.pattern.set_avg_data(y_avg)
        self.update_all_patterns()
        self.pattern.set_xlabel("2theta (deg)" if not is_q else "q (1/A)")
        self.pattern.set_xrange((x[0], x[-1]))
        if not aux_plot_key is None:
            # if a selected item is provided, add the auxiliary plot for that item
            self.add_auxiliary_plot(aux_plot_key)

    def hline_moved(self, index, pos):
        """Handle the horizontal line movement in the heatmap."""
        self.update_pattern(index, pos)
        self.auxiliary_plot.set_v_line_pos(index, pos)

    def vline_moved(self, index, pos):
        """Handle the vertical line movement in the auxiliary plot."""
        pos = int(np.clip(pos, 0, self.azint_data.shape[0]-1))
        self.update_pattern(index, pos)
        self.heatmap.set_h_line_pos(index, pos)

    def update_pattern(self, index, pos):
        """Update the pattern plot with the data from the selected frame in the heatmap.
        This method is called when a horizontal line is moved in the heatmap or when a new pattern is added."""
        # Get the selected frame from the heatmap
        y = self.azint_data.get_I(index=pos)
        self.pattern.set_data(y=y, index=index)
        self.pattern.set_pattern_name(name=f"frame {pos}", index=index)

    def update_all_patterns(self):
        """Update all patterns with the current data. Called when a new file is (re)loaded."""
        for i,pos in enumerate(self.heatmap.get_h_line_positions()):
            self.update_pattern(i,pos)

    def open_cif_file(self):
        """Open a file dialog to select a cif file and add it to the cif tree."""
        # prompt the user to select a file
        if self.cif_tree.files and self.cif_tree.files[-1] is not None:
            default_dir = os.path.dirname(self.cif_tree.files[-1])
        else:
            default_dir = os.path.expanduser("~")
        file_path, ok = QFileDialog.getOpenFileName(self, "Select Crystallographic Information File", default_dir, "CIF Files (*.cif);;All Files (*)")
        if not ok or not file_path:
            return
        # add the file to the file tree
        self.cif_tree.add_file(file_path)

    def add_reference(self, cif_file, Qmax=None):
        """Add a reference pattern from a CIF file to the pattern plot."""
        if self.E is None:
            self.E = self.azint_data.user_E_dialog()
            if self.E is None:
                QMessageBox.critical(self, "Error", "Energy not set. Cannot add reference pattern.")
                return
        if Qmax is None:
            Qmax = self.getQmax()
        self.ref = Reference(cif_file,E=self.E, Qmax=Qmax)
        self.plot_reference()
        tooltip = f"{self.ref.get_spacegroup_info()}\n{self.ref.get_cell_parameter_info()}"
        self.cif_tree.set_latest_item_tooltip(tooltip)

    def plot_reference(self, Qmax=None, dmin=None):
        """Plot the reference pattern in the pattern plot."""
        if Qmax is None:
            Qmax = self.getQmax()
        hkl, d, I = self.ref.get_reflections(Qmax=Qmax, dmin=dmin)
        if len(hkl) == 0:
            QMessageBox.warning(self, "No Reflections", "No reflections found in the reference pattern.")
            return
        
        if self.is_Q:
            # Convert d to Q
            x = 4*np.pi/d
        else:
            # Convert d to 2theta
            x = np.degrees(2 * np.arcsin((12.398 / self.E) / (2 * d)))
        self.pattern.add_reference(hkl, x, I)

    def toggle_reference(self, index, is_checked):
        """
        Toggle the visibility of the reference pattern.
        Called when a reference item is checked or unchecked in the CIF tree.
        """
        self.pattern.toggle_reference(index, is_checked)

    def rescale_reference(self,index,name):
        """
        Rescale the intensity of the indexed reference to the current y-max.
        This method is called when a reference item is double-clicked in the CIF tree.
        """
        self.pattern.rescale_reference(index)

    def load_I0_data(self, aname=None, fname=None):
        """Load auxillary data as I0. Called when the user requests I0 data from the file tree."""
        self.load_auxiliary_data(aname=aname, is_I0=True)

    def load_auxiliary_data(self, aname=None, fname=None, is_I0=False):
        """
        Open a an HDF5 file dialog to select auxiliary/I0 data.
        Once the dialog is closed, the selected data is added to the AuxData
        instance as either I0 data or auxiliary data.
        If an azimuthal data file name (aname) is provided, it is used to
        look for a raw file location, assuming the structure
        */process/azint/*/*.h5 -> */raw/*/*.h5
        """
        if fname is None:
            # prompt the user to select a file
            if aname is not None:
                # look for a default "raw" directory based on the file name
                # of the azimuthal integration data (aname), assuming the
                # structure */process/azint/*/*.h5 -> */raw/*/*.h5

                # get the absolute directory of the azint file
                adir = os.path.dirname(os.path.abspath(aname))
                # look for the raw directory in both Windows and Unix style paths
                if os.path.exists(adir.replace("\\process\\azint", "\\raw")):
                    default_dir = adir.replace("\\process\\azint", "\\raw")
                elif os.path.exists(adir.replace("/process/azint", "/raw")):
                    default_dir = adir.replace("/process/azint", "/raw")
                elif os.path.exists(adir):
                    # if the default directory does not exist, use the directory of the azint file
                    default_dir = adir
            else:
                default_dir = os.path.expanduser("~")
            fname, ok = QFileDialog.getOpenFileName(self, "Select Auxiliary Data File", default_dir, "HDF5 Files (*.h5);;All Files (*)")
            if not ok or not fname:
                return
        
        self.h5dialog = H5Dialog(self, fname)
        self.h5dialog.open_1d()
        if is_I0:
            self.h5dialog.finished.connect(self.add_I0_data)
        else:
            self.h5dialog.finished.connect(self.add_auxiliary_data)

    def add_I0_data(self,is_ok=True):
        """Add I0 data from the h5dialog to the azint data instance."""
        if not is_ok:
            return

        # Assume the first selected item is the I0 data
        # ignore any other possible selections
        with h5.File(self.h5dialog.file_path, 'r') as f:
            I0 =  f[self.h5dialog.selected_items[0][1]][:]
        
        target_name, target_shape = self.file_tree.get_aux_target_name()
        if not target_name in self.aux_data.keys():
            self.aux_data[target_name] = AuxData(self)
        # check if the target shape matches the I0 shape
        # and account for a possible +-1 mismatch
        if abs(target_shape[0] - I0.shape[0]) == 1:
            # if the I0 shape is one more than the target shape, remove the last element
            if target_shape[0] < I0.shape[0]:
                message = (f"The I0 shape {I0.shape} does not match the data shape {target_shape}.\n"
                            f"Trimming the I0 data to match the target shape.")
                I0 = I0[:-1]
            # if the I0 shape is one less than the target shape, append with the last element
            elif target_shape[0] > I0.shape[0]:
                message = (f"The I0 shape {I0.shape} does not match the target shape {target_shape}.\n"
                            f"Padding the I0 data to match the target shape.")
                I0 = np.append(I0, I0[-1])
            QMessageBox.warning(self, "Shape Mismatch", message)
        elif target_shape[0] != I0.shape[0]:
            QMessageBox.critical(self, "Shape Mismatch", f"The I0 shape {I0.shape} does not match the data shape {target_shape}.")
            return
        # add the I0 data to the auxiliary data
        # to ensure that it is available if the 
        # azint data is cleared
        self.aux_data[target_name].set_I0(I0)

        # update the file tree item status tip
        self.file_tree.set_target_item_status_tip("I0 corrected")

        # if the I0 was added to the current azint data,
        # update the azint data instance
        if target_name in self.azint_data.fnames:
            # if the target name is already in the azint data, update it
            self.load_file(self.azint_data.fnames[0],self.file_tree.get_aux_target_item())

    def add_auxiliary_data(self,is_ok):
        """Add auxiliary data from the h5dialog to the azint data instance."""
        if not is_ok:
            return
        aux_data = {}
        target_name, target_shape = self.file_tree.get_aux_target_name()
        if not target_name in self.aux_data.keys():
            self.aux_data[target_name] = AuxData(self)
        with h5.File(self.h5dialog.get_file_path(), 'r') as f:
            for [alias,file_path,shape] in self.h5dialog.get_selected_items():
                aux_data[alias] =  f[file_path][:]
                self.file_tree.add_auxiliary_item(alias,shape)
                self.aux_data[target_name].add_data(alias, f[file_path][:])
        
        #self.azint_data.set_auxiliary_data(aux_data)
        # Update the auxiliary plot with the new data
        self.add_auxiliary_plot(target_name)

    def add_auxiliary_plot(self, selected_item):
        """Add an auxiliary plot"""
        if not selected_item in self.aux_data:
            QMessageBox.warning(self, "No Auxiliary Data", f"No auxiliary data available for {selected_item}.")
            return
        self.auxiliary_plot.clear_plot()  # Clear the previous plot
        for alias, data in self.aux_data[selected_item].get_dict().items():
            if not PLOT_I0 and alias == 'I0':
                # Skip I0 data for the auxiliary plot
                continue
            if data is not None and data.ndim == 1:
                # If the data is 1D, plot it directly
                self.auxiliary_plot.set_data(data, label=alias)
        # ensure that a v line exists for each h line in the heatmap
        for i,pos in enumerate(self.heatmap.get_h_line_positions()):
            if len(self.auxiliary_plot.v_lines) <= i:
                self.auxiliary_plot.addVLine(pos=pos)
            self.auxiliary_plot.set_v_line_pos(i, pos)

    def getQmax(self):
        """Get the maximum Q value of the current pattern"""
        if self.pattern.x is None:
            return 6.28  # Default Qmax if no pattern is loaded
        if self.is_Q:
            return np.max(self.pattern.x)
        else:
            # Convert 2theta to Q
            return 4 * np.pi / (12.398 / self.E) * np.sin(np.radians(np.max(self.pattern.x)) / 2)
        
    def toggle_q(self):
        """Toggle between Q and 2theta in the heatmap and pattern plots."""
        # Toggle between q and 2theta
        if self.E is None:
            self.E = self.azint_data.user_E_dialog()
            if self.E is None:
                QMessageBox.critical(self, "Error", "Energy not set. Cannot toggle between q and 2theta.")
                return
        self.is_Q = not self.is_Q
        self.toggle_q_action.setChecked(self.is_Q)
        if self.is_Q:
            self.heatmap.set_xlabel("q (1/A)")
            self.pattern.set_xlabel("q (1/A)")
            x = self.azint_data.get_q()
            self.heatmap.set_data(x, self.azint_data.get_I().T)
            self.pattern.x = x
            self.pattern.avg_pattern_item.setData(x=x, y=self.azint_data.get_average_I())
            for pattern_item in self.pattern.pattern_items:
                _x, y = pattern_item.getData()
                pattern_item.setData(x=x, y=y)
            for ref_item in self.pattern.reference_items:
                _x, _y = ref_item.getData()
                _x = tth_to_q(_x, self.E)
                ref_item.setData(x=_x, y=_y)

        else:
            self.heatmap.set_xlabel("2theta (deg)")
            self.pattern.set_xlabel("2theta (deg)")
            x = self.azint_data.get_tth()
            self.heatmap.set_data(x, self.azint_data.get_I().T)
            self.pattern.x = x
            self.pattern.avg_pattern_item.setData(x=x, y=self.azint_data.get_average_I())
            for pattern_item in self.pattern.pattern_items:
                _x, y = pattern_item.getData()
                pattern_item.setData(x=x, y=y)
            for ref_item in self.pattern.reference_items:
                _x, _y = ref_item.getData()
                _x = q_to_tth(_x, self.E)
                ref_item.setData(x=_x, y=_y)

    def _prepare_export_settings(self):
        """
        Prepare the export settings for exporting patterns, based
        on the current export settings dialog.
        Returns:
            ext (str): The file extension for the export.
            pad (int): The number of leading zeros for the file name.
            is_Q (bool): Whether to export in Q or 2theta.
            I0_normalized (bool): Whether to normalize the intensity by I0.
            kwargs (dict): Additional keyword arguments for np.savetxt.
        """
        # get a dictionary of the export settings
        export_settings = self.export_settings_dialog.get_settings()
        # extension
        ext = export_settings['extension_edit']
        # leading zeros
        pad = export_settings['leading_zeros_spinbox']
        
        # determine if the export is in Q or 2theta
        if export_settings['native_radio']:
            # native export, use the azint_data.is_q attribute
            is_Q = self.azint_data.is_q
        elif export_settings['tth_radio']:
            # export in 2theta
            is_Q = False
        else:
            # export in Q
            is_Q = True
        
        # header
        if export_settings['header_checkbox']:
            header = ("plaid - plot azimuthally integrated data\n"
                        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"exported from {self.azint_data.fnames[0]}\n")
            if self.E is not None:
                header += f"energy keV: {self.E:.4}\n"
                header += f"wavelength A: {12.398 / self.E:.6f}\n" 
            # if export_settings['tth_radio']:
            if is_Q:
                col_header = f'{"q":^7}_{"intensity":>10}'
            else:
                col_header = f'{"2theta":>7}_{"intensity":>10}'
            if self.azint_data.I_error is not None:
                col_header += f'_{"error":>10}'
            if export_settings['space_radio']:
                col_header = col_header.replace('_', ' ')
            else:
                col_header = col_header.replace('_', '\t')
            header += col_header
        else:
            header = ''
        # data format
        if export_settings['scientific_checkbox']:
            fmt = '%.6e'
        else:
            fmt = ['%7.4f', '%10.2f']
            if self.azint_data.I_error is not None:
                fmt.append('%10.2f')
        # delimiter
        if export_settings['space_radio']:
            delimiter = ' '
        else:
            delimiter = '\t'
        
        # prepare kwargs for the export function, passed to np.savetxt
        kwargs = {'header': header, 'fmt': fmt, 'delimiter': delimiter}
        
        # I0 normalization
        I0_normalized = export_settings['I0_checkbox']

        return ext, pad, is_Q, I0_normalized, kwargs

    def export_pattern(self):
        """Export the current pattern(s) to a file."""
        if not self.azint_data.fnames:
            QMessageBox.warning(self, "No Data", "No azimuthal integration data loaded.")
            return
        ext, pad, is_Q, I0_normalized, kwargs = self._prepare_export_settings()

        indices = self.heatmap.get_h_line_positions()
        for index in indices:
            ending = "_{index:0{pad}d}.{ext}".format(index=index, pad=pad, ext=ext)
            fname = self.azint_data.fnames[0].replace('.h5', ending)
            fname, ok = QFileDialog.getSaveFileName(self, "Save Pattern", fname, f"{ext.upper()} Files (*.{ext});;All Files (*)")
            if ok:
                if fname:
                    successful = self.azint_data.export_pattern(fname,index,is_Q, I0_normalized=I0_normalized,kwargs=kwargs)
                    if not successful:
                        QMessageBox.critical(self, "Error", f"Failed to export pattern to {fname}.")
            else:
                break  # Exit the loop if the user cancels the save dialog

    def export_average_pattern(self):
        """Export the average pattern to a file."""
        if not self.azint_data.fnames:
            QMessageBox.warning(self, "No Data", "No azimuthal integration data loaded.")
            return
        ext, pad, is_Q, I0_normalized, kwargs = self._prepare_export_settings()

        fname = self.azint_data.fnames[0].replace('.h5', f"_avg.{ext}")
        fname, ok = QFileDialog.getSaveFileName(self, "Save Average Pattern", fname, f"{ext.upper()} Files (*.{ext});;All Files (*)")
        if ok:
            if fname:
                successful = self.azint_data.export_average_pattern(fname,is_Q, I0_normalized=I0_normalized,kwargs=kwargs)
                if not successful:
                    QMessageBox.critical(self, "Error", f"Failed to export average pattern to {fname}.")

    def export_all_patterns(self):
        """
        Export all patterns to double-column files.
        This method prompts the user for a directory to save the files,
        and then exports each pattern in the azint_data to a file.
        This method can be disabled by setting the ALLOW_EXPORT_ALL_PATTERNS 
        variable to False in the plaid.py module or by passing the --limit-export
        command line argument when running the application.
        """
        if not ALLOW_EXPORT_ALL_PATTERNS:
            QMessageBox.warning(self, "Export Not Allowed", "Exporting all patterns is not allowed in this version.")
            return
        if not self.azint_data.fnames:
            QMessageBox.warning(self, "No Data", "No azimuthal integration data loaded.")
            return
        ext, pad, is_Q, I0_normalized, kwargs = self._prepare_export_settings()
        # prompt for a directory to save the files
        dst = os.path.dirname(self.azint_data.fnames[0]) if self.azint_data.fnames else os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(self, "Select Directory to Save Patterns", dst)
        if not directory:
            return  # User cancelled the dialog
        # give the user a chance to cancel the export
        msg = (f"You are about to export {self.azint_data.shape[0]} patterns to:\n"
               f"{directory}\n"
               "Do you want to continue?")
        reply = QMessageBox.question(self, "Export Patterns",msg)
        if reply != QMessageBox.StandardButton.Yes:
            return  # User cancelled the export
        
        # define the root file path
        root_file_path = os.path.join(os.path.abspath(directory), os.path.basename(self.azint_data.fnames[0]).replace('.h5', ''))
        progress_dialog = QProgressDialog("Exporting patterns...", "Cancel", 0, self.azint_data.shape[0], self)
        progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        for index in range(self.azint_data.shape[0]):
            if progress_dialog.wasCanceled():
                QMessageBox.information(self, "Cancelled", f"Export cancelled after {index} patterns.")
                return
            ending = "_{index:0{pad}d}.{ext}".format(index=index, pad=pad, ext=ext)
            fname = f"{root_file_path}{ending}"
            # Update the progress dialog
            progress_dialog.setValue(index)
            progress_dialog.setLabelText(f"{fname}")
            # Export the pattern
            successful = self.azint_data.export_pattern(fname, index, is_Q, I0_normalized=I0_normalized, kwargs=kwargs)
            if not successful:
                QMessageBox.critical(self, "Error", f"Failed to export pattern to {fname}.")
                progress_dialog.cancel()  # Cancel the progress dialog
                return
        progress_dialog.setValue(self.azint_data.shape[0])  # Set to maximum value to close the dialog
        # inform the user that the export is done
        QMessageBox.information(self, "Complete", f"Complete!\nExported {self.azint_data.shape[0]} patterns to:\n{directory}")

    def dragEnterEvent(self, event):
        """Handle drag and drop events for the main window."""
        if event.mimeData().hasUrls():
            if all(url.toLocalFile().endswith('.cif') for url in event.mimeData().urls()):
                self.cif_tree.dragEnterEvent(event)
            elif all(url.toLocalFile().endswith('.h5') for url in event.mimeData().urls()):
                self.file_tree.dragEnterEvent(event)
    
    def dropEvent(self, event):
        """Handle drop events for the main window."""
        if event.mimeData().hasUrls():
            if all(url.toLocalFile().endswith('.cif') for url in event.mimeData().urls()):
                self.cif_tree.dropEvent(event)
            elif all(url.toLocalFile().endswith('.h5') for url in event.mimeData().urls()):
                #self.file_tree.dropEvent(event)
                for url in event.mimeData().urls():
                    file_path = url.toLocalFile()
                    if file_path.endswith('.h5'):
                        self.open_file(file_path)
                event.acceptProposedAction()

    def keyReleaseEvent(self, event):
        """Handle key release events."""
        if event.key() == QtCore.Qt.Key.Key_L:
            # Toggle the log scale for the heatmap
            self.heatmap.use_log_scale = not self.heatmap.use_log_scale
            I = self.azint_data.get_I()
            x = self.heatmap.x
            # y = np.arange(I.shape[0])
            self.heatmap.set_data(x, I.T)

        elif event.key() == QtCore.Qt.Key.Key_Q:
            # Toggle between q and 2theta
            self.toggle_q()

        elif event.key() == QtCore.Qt.Key.Key_Up:
            # Move the selected line one increment up
            self.heatmap.move_active_h_line(1)
        elif event.key() == QtCore.Qt.Key.Key_Down:
            # Move the selected line one increment down
            self.heatmap.move_active_h_line(-1)
        elif event.key() == QtCore.Qt.Key.Key_Right:
            # Move the selected line 5% up
            delta = self.heatmap.n// 20  # 5% of the total number of lines
            self.heatmap.move_active_h_line(delta)
        elif event.key() == QtCore.Qt.Key.Key_Left:
            # Move the selected line 5% down
            delta = self.heatmap.n// 20  # 5% of the total number of lines
            self.heatmap.move_active_h_line(-delta)

        # # DEBUG
        elif event.key() == QtCore.Qt.Key.Key_Space:
            
            # h5dialog = H5Dialog(self, self.azint_data.fnames[0])
            # if h5dialog.exec_1d_2d_pair():
            #     selected = h5dialog.get_selected_items()
            #     axis = [item for item in selected if not "×" in item[2]][0]
            #     signal = [item for item in selected if "×" in item[2]][0]
            # print('axis:', axis)
            # print('signal:', signal)
            # fname = self.azint_data.fnames[0] 
            # dialog = H5Dialog(self, fname)
            # if not dialog.exec_1d_2d_pair():
            #     print( None, None, None, None)

            # selected = dialog.get_selected_items() # list of tuples with (alias, full_path, shape)
            # axis = [item for item in selected if not "×" in item[2]][0] 
            # signal = [item for item in selected if "×" in item[2]][0]
            # # Check if the shape of the axis and signal match
            # if not axis[2] in signal[2].split("×")[1]:
            #     print(f"Error: The shape of the axis {axis[2]} does not match the shape of the signal {signal[2]}.")
            #     print( None, None, None, None)
            # with h5.File(fname, 'r') as f:
            #     x = f[axis[1]][:]
            #     I = f[signal[1]][:]
            #     # attempt to guess if the axis is q or 2theta
            #     is_q = 'q' in axis[0].lower() or 'q' in f[axis[1]].attrs.get('long_name', '').lower()
            # print(x, I, is_q, None)
            
            # ## TEST COLORDIALOG
            pass

    def show_color_cycle_dialog(self):
        # get the first pattern (if available)
        x,y = self.pattern.pattern_items[0].getData() if self.pattern.pattern_items else [None, None]
        self.color_dialog.set_preview_data(y,x=x)
        self.color_dialog.show()

    def _update_color_cycle(self, color_cycle):
            self.color_cycle = color_cycle
            #self.color_cycle = self.color_dialog.get_colors()
            self.heatmap.set_color_cycle(self.color_cycle)
            self.pattern.set_color_cycle(self.color_cycle)
            self.auxiliary_plot.set_color_cycle(self.color_cycle)
            self.cif_tree.set_color_cycle(self.color_cycle[::-1]) # flip the cycle for the CIF tree

    def _save_dock_settings(self):
        """Save the dock widget settings."""
        settings = QtCore.QSettings("plaid", "plaid")
        settings.beginGroup("MainWindow")
        settings.beginGroup("DockWidgets")
        # Find all dock widgets and sort them by area
        dock_widgets = self.findChildren(QDockWidget)
        left = [dock for dock in dock_widgets if self.dockWidgetArea(dock) == QtCore.Qt.DockWidgetArea.LeftDockWidgetArea]
        right = [dock for dock in dock_widgets if self.dockWidgetArea(dock) == QtCore.Qt.DockWidgetArea.RightDockWidgetArea]
        # Sort the dock widgets by their y position
        left = sorted(left, key=lambda dock: dock.geometry().y())
        right = sorted(right, key=lambda dock: dock.geometry().y())
        # Save the left and right dock widget positions as lists of tuples
        settings.setValue("left_docks", [(dock.windowTitle(), dock.isVisible()) for dock in left])
        settings.setValue("right_docks", [(dock.windowTitle(), dock.isVisible()) for dock in right])
        settings.endGroup()  # End DockWidgets group
        settings.endGroup()  # End MainWindow group
        
    def _load_dock_settings(self):
        """Load the dock widget settings (relative position and isVisible)."""
        settings = QtCore.QSettings("plaid", "plaid")
        settings.beginGroup("MainWindow")
        settings.beginGroup("DockWidgets")
        # Load the left and right dock widget positions
        left_docks = settings.value("left_docks", [], type=list)
        right_docks = settings.value("right_docks", [], type=list)
        settings.endGroup()
        settings.endGroup()  # End MainWindow group
        return left_docks, right_docks

    def _save_export_settings(self,settings):
        """Save the export settings."""
        export_settings = QtCore.QSettings("plaid", "plaid")
        export_settings.beginGroup("ExportSettings")
        for key, value in settings.items():
            export_settings.setValue(key, value)
        export_settings.endGroup()

    def _load_export_settings(self):
        """Load the export settings."""
        export_settings = QtCore.QSettings("plaid", "plaid")
        export_settings.beginGroup("ExportSettings")
        settings = {}
        for key in export_settings.allKeys():
            settings[key] = export_settings.value(key)
        export_settings.endGroup()
        return settings
    
    def _save_color_cycle(self):
        """Save the color cycle settings."""
        settings = QtCore.QSettings("plaid", "plaid")
        settings.beginGroup("ColorCycle")
        settings.setValue("colors", self.color_cycle)
        settings.endGroup()

    def _load_color_cycle(self):
        """Load the color cycle settings."""
        settings = QtCore.QSettings("plaid", "plaid")
        settings.beginGroup("ColorCycle")
        self.color_cycle = settings.value("colors", [], type=list)
        settings.endGroup()

    def show_help_dialog(self):
        """Show the help dialog."""
        help_text = (
            "<h2>Help - plot azimuthally integrated data</h2>"
            "<p>This application allows you to visualize azimuthally integrated data "
            "from HDF5 files and compare them with reference patterns from CIF files.</p>"
            "<h3>Usage</h3>"
            "<ol>"
            "<li>Add a new HDF5 file by drag/drop or from 'File' -> 'Open'.</li>"
            "<li>Double-click on a file in the file tree to load it.</li>"
            "<li>Right-click on a file in the file tree to add I0 or auxiliary data.</li>"
            "<li>Right-click on two or more selected files to group them.</li>"
            "<li>Double-click on the heatmap to add a moveable selection line.</li>"
            "<li>Right-click on the moveable line to remove it.</li>"
            "<li>Use the file tree to manage your files and auxiliary data.</li>"
            "<li>Use the CIF tree to add reference patterns from CIF files.</li>"
            "<li>Click on a reference line to show its reflection index in the pattern.</li>"
            "</ol>"
            "<h3>Keyboard Shortcuts</h3>"
            "<ul>"
            "<li><b>L</b>: Toggle log scale for the heatmap.</li>"
            "<li><b>Q</b>: Toggle between q and 2theta axes.</li>"
            "</ul>"
        )
        # Show the help dialog with the specified text
        QMessageBox.about(self, "Help", help_text)
    
    def show_about_dialog(self):
        """Show the about dialog."""
        about_text = (
            "<h2>plaid - plot azimuthally integrated data</h2>"
            f"<p>Version {plaid.__version__}</p>"
            f"<p>{plaid.__description__}</p>"
            f"<p>Developed by: <a href='mailto:{plaid.__email__}'>{plaid.__author__}</a><br>"
            f"{plaid.__institution__.replace('& ', '&<br>')}</p>"
            f"<p>License: {plaid.__license__}</p>"
            f"<p>For more information, visit the <a href='{plaid.__url__}'>GitHub repository</a>.</p>"
        )
        # Show the about dialog with the specified text
        QMessageBox.about(self, "About", about_text)

    def _check_for_updates_on_startup(self):
        """
        Check for updates on startup and show a notification if available.
        Uses QTimer to make the check non-blocking and delay it slightly.
        """
        # Check if user has disabled update checking
        settings = QtCore.QSettings("plaid", "plaid")
        if not settings.value("check_for_updates", True, type=bool):
            return
            
        def perform_update_check():
            latest_version = check_for_updates()
            if latest_version:
                self._show_update_notification(latest_version)
        
        # Delay the update check by 2 seconds to avoid blocking startup
        QtCore.QTimer.singleShot(2000, perform_update_check)
    
    def _show_update_notification(self, latest_version):
        """Show a notification about available updates."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("Update Available")
        msg.setText(f"A newer version of plaid is available!")
        msg.setInformativeText(
            f"Current version: {CURRENT_VERSION}\n"
            f"Latest version: {latest_version}\n\n"
            f"You can update using:\npip install --upgrade plaid-xrd"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # Add a "Don't show again" checkbox
        checkbox = QCheckBox("Don't check for updates on startup")
        msg.setCheckBox(checkbox)
        # get the current state of the checkbox
        settings = QtCore.QSettings("plaid", "plaid")
        check_for_updates = settings.value("check_for_updates", True, type=bool)
        checkbox.setChecked(not check_for_updates)

        result = msg.exec()
        settings.setValue("check_for_updates", not checkbox.isChecked())

    def check_for_updates_manual(self):
        """Manually check for updates when requested by user."""
        if not HAS_UPDATE_CHECKER:
            QMessageBox.warning(self, "Update Check Unavailable", 
                              "Update checking requires the 'requests' and 'packaging' libraries.\n"
                              "Install them with: pip install requests packaging")
            return
        
        # Show a progress indicator
        self.statusBar().showMessage("Checking for updates...")
        
        def perform_check():
            latest_version = check_for_updates()
            if latest_version:
                self._show_update_notification(latest_version)
            else:
                QMessageBox.information(self, "No Updates", 
                                      f"You are running the latest version ({CURRENT_VERSION}).")
            self.statusBar().clearMessage()
        
        # Use QTimer to make it non-blocking
        QtCore.QTimer.singleShot(100, perform_check)

    def show(self):
        """Override the show method to update the pattern geometry."""
        super().show()
        self.update_pattern_geometry()

    def closeEvent(self, event):
        """Handle the close event to save settings."""
        recent_files = self.file_tree.files
        save_recent_files_settings(recent_files)
        recent_refs = self.cif_tree.files
        save_recent_refs_settings(recent_refs)
        self._save_dock_settings()
        self._save_color_cycle()
        event.accept()

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Plot azimuthally integrated data from HDF5 files.")
    # Add an argument for opening a file on startup
    parser.add_argument("-f", "--file", nargs='*', 
                        help="File(s) to open on startup. Can be multiple files.")
    # Add an argument for limiting the export options
    parser.add_argument("-l", "--limit-export", action="store_true", 
                        help="Limit the export options to individual patterns.")
    # add an argument for the clearing the recent files
    parser.add_argument("-c", "--clear-recent-files", action="store_true", 
                        help="Clear the recent files list on startup.")
    # add an argument for the clearing the recent references
    parser.add_argument("-r", "--clear-recent-refs", action="store_true",
                         help="Clear the recent references list on startup.")
    # add an argument for clearing all settings
    parser.add_argument("--clear-all-settings", action="store_true", 
                        help="Clear all saved settings including recent files without starting the application.")

    return parser.parse_args()


def main():
    """Main function to run the application."""
    global ALLOW_EXPORT_ALL_PATTERNS
    # Parse command line arguments
    args = parse_args()
    
    if args.limit_export:
        ALLOW_EXPORT_ALL_PATTERNS = False
    if args.clear_all_settings:
        # clear all settings and close the application
        clear_all_settings()
        sys.exit()

    if args.clear_recent_files:
        # clear the recent files list on startup
        clear_recent_files_settings()
    if args.clear_recent_refs:
        # clear the recent references list on startup
        clear_recent_refs_settings()
    # if files are provided, open them on startup
    if args.file:
        files = [f for f in args.file if os.path.isfile(f)]
    else:
        files = None

    # Create the application and main window
    app = QApplication(sys.argv)
    # app.setStyle("Fusion")
    # get the application palette colors
    foreground_color = app.palette().text().color().darker(150).name()
    background_color = app.palette().window().color().darker(110).name()

    pg.setConfigOptions(antialias=True,
                        foreground=foreground_color,
                        background=background_color,
                        )
    # Create the main window
    window = MainWindow()
    # open any files provided in the command line arguments
    if isinstance(files, list):
        for file in files:
            window.open_file(file)
    # show the main window
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()