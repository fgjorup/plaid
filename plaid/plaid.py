# -*- coding: utf-8 -*-
"""
plaid - plaid looks at integrated data
F.H. Gjørup 2025-2026
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides the main application window for plotting azimuthally integrated data,
including loading files, displaying heatmaps and patterns, and managing auxiliary data.
"""
# from operator import index
import sys
import os
import numpy as np
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
                             QDockWidget, QSizePolicy, QFileDialog, QMessageBox, 
                             QProgressDialog, QCheckBox, QSplashScreen,QInputDialog)
from PyQt6.QtGui import QAction, QIcon, QPixmap
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
from plaid.plot_widgets import HeatmapWidget, PatternWidget, AuxiliaryPlotWidget, CorrelationMapWidget, DiffractionMapWidget
from plaid.misc import q_to_tth, tth_to_q, d_to_q, d_to_tth, get_divisors, average_blocks
from plaid.data_containers import AzintData, AuxData
from plaid.io import load_file, ReadWorker
from plaid import __version__ as CURRENT_VERSION
import plaid.resources
#from plaid.qt_worker import run_in_thread


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
# - optimize memory usage and performance for large datasets
# - add a "reduction factor" option to reduce the effective time resolution of the data (I, I0, and aux data)
# - Crop data option? Perhaps save cropped .h5 copy?
# - Restructure data loading
#    > Update plots on the fly during reading?


ALLOW_EXPORT_ALL_PATTERNS = True
PLOT_I0 = True

colors = ["#C41E3A", # Crimson Red
          "#FF8C00", # Dark Orange
          "#228B22", # Forest Green
          "#4169E1", # Royal Blue
          "#8B008B", # Dark Magenta
          "#2F4F4F", # Dark Slate Gray
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
        recent_files = recent_files[:10]
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
        recent_refs = recent_refs[:10]
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

def _get_desktop_path():
    """Get the path to the user's desktop in a cross-platform way."""
    if os.name != 'nt':
        return os.path.join(os.path.expanduser("~"), "Desktop")
    else:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buf)  # 0x0000 = CSIDL_DESKTOP
        return os.path.abspath(buf.value)

def _get_default_path():
    """
    Get a sensible default path for file dialogs.
    returns the current working directory, unless it is the same as the script path,
    in which case it returns the user's home directory.
    """
    default = os.getcwd()
    if default == os.path.dirname(__file__):
        default = os.path.expanduser("~")
    return os.path.abspath(default)

class MainWindow(QMainWindow):
    """plaid - Main application window for plotting azimuthally integrated data."""
    def __init__(self):
        super().__init__()

        self.setWindowTitle("plaid - plaid looks at integrated data")
        self.statusBar().showMessage("")
        # Set the window icon
        self.setWindowIcon(QIcon(":/icons/plaid.png"))

        self.is_dark_mode = self._load_dark_mode_setting()
        
        self.E = None  # Energy in keV
        self.is_Q = False # flag to indicate if the data is in Q space (True) or 2theta space (False)

        self.azint_data = AzintData(self)
        self.aux_data = {}

        self.locked_patterns = []  # list of (is_Q, E) tuples for locked patterns
        
        # initialize the data read worker
        self.read_worker = ReadWorker()
        self.read_worker.sigFinished.connect(self._load_intensity_data_done)
        # self.read_worker.sigFinished.connect(lambda *_: _loop.quit())
        # self.read_worker.sigError.connect(lambda e: print(f"Error: {e}"))
        self.read_worker.sigProgress.connect(self._load_intensity_data_progress)
        
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
        self._init_correlation_map()
        self._init_diffraction_map()
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

        self.toggle_dark_mode(self.is_dark_mode)

        # Check for updates on startup (non-blocking)
        self._check_for_updates_on_startup()
        self._check_if_first_run()

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

    def _init_correlation_map(self):
        """Initialize the correlation map widget. Called by self.__init__()."""
        self.correlation_map = CorrelationMapWidget(self)
        # create a dock widget for the correlation map
        correlation_map_dock = QDockWidget("Auto-correlation Map", self)
        correlation_map_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        correlation_map_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        correlation_map_dock.setWidget(self.correlation_map)
        self.correlation_map_dock = correlation_map_dock
        self.correlation_map_dock.setFloating(True)
        # hide the correlation map dock by default
        self.correlation_map_dock.hide()

    def _init_diffraction_map(self):
        """Initialize the diffraction map widget. Called by self.__init__()."""
        self.diffraction_map = DiffractionMapWidget(self)
        # create a dock widget for the diffraction map
        diffraction_map_dock = QDockWidget("Diffraction Map", self)
        diffraction_map_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        diffraction_map_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        diffraction_map_dock.setWidget(self.diffraction_map)
        self.diffraction_map_dock = diffraction_map_dock
        self.diffraction_map_dock.setFloating(True)
        # hide the diffraction map dock by default
        self.diffraction_map_dock.hide()

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
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.correlation_map_dock)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.diffraction_map_dock)
        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks)

    def _init_connections(self):
        """Initialize the connections between the widgets. Called by self.__init__()."""
        # Connect the file tree signals to the appropriate slots
        self.file_tree.sigItemDoubleClicked.connect(self.open_file)                # --> str, obj
        # self.file_tree.sigItemDoubleClicked.connect(self.load_file)                # --> str, obj
        self.file_tree.sigGroupDoubleClicked.connect(self.open_file)               # --> list, list
        self.file_tree.sigItemRemoved.connect(self.remove_file)                    # --> str
        self.file_tree.sigI0DataRequested.connect(self.load_I0_data)               # --> str
        self.file_tree.sigAuxiliaryDataRequested.connect(self.load_auxiliary_data) # --> str
        self.file_tree.sigReductionRequested.connect(self.apply_reduction_factor)  # --> str
        # Connect the CIF tree signals to the appropriate slots
        self.cif_tree.sigItemAdded.connect(self.add_reference)              # --> str
        self.cif_tree.sigItemChecked.connect(self.toggle_reference)         # --> int, bool
        self.cif_tree.sigItemDoubleClicked.connect(self.rescale_reference)  # --> int, str
        self.cif_tree.sigItemRemoved.connect(self.remove_reference)         # --> int
        self.cif_tree.sigItemReloadRequested.connect(self.reload_reference) # --> int
        # Connect the heatmap signals to the appropriate slots
        self.heatmap.sigHLineMoved.connect(self.hline_moved)           # --> int, int
        self.heatmap.sigXRangeChanged.connect(self.pattern.set_xrange) # --> object
        self.heatmap.sigImageDoubleClicked.connect(self.add_pattern)   # --> object
        self.heatmap.sigImageHovered.connect(self._update_status_bar)  # --> object
        self.heatmap.sigHLineRemoved.connect(self.remove_pattern)      # --> int
        # Connect the pattern signals to the appropriate slots
        self.pattern.sigXRangeChanged.connect(self.heatmap.set_xrange)                        # --> object
        self.pattern.sigPatternHovered.connect(self.update_status_bar)                        # --> object
        self.pattern.sigLinearRegionChangedFinished.connect(self.set_diffraction_map)         # --> object
        self.pattern.sigRequestQToggle.connect(self.toggle_q)                                 # --> ()
        self.pattern.sigRequestLockPattern.connect(self.handle_lock_pattern_request)          # --> object
        self.pattern.sigRequestSubtractPattern.connect(self.set_active_pattern_as_background) # --> ()
        self.pattern.sigRequestCorrelationMap.connect(self.show_correlation_map)              # --> ()
        self.pattern.sigRequestDiffractionMap.connect(lambda: self.show_diffraction_map())    # --> ()
        self.pattern.sigRequestExportAvg.connect(self.export_average_pattern)                 # --> ()
        self.pattern.sigRequestExportCurrent.connect(self.export_pattern)                     # --> ()
        self.pattern.sigRequestExportAll.connect(self.export_all_patterns)                    # --> ()
        # Connect the auxiliary plot signals to the appropriate slots
        self.auxiliary_plot.sigVLineMoved.connect(self.vline_moved)           # --> int, int
        self.auxiliary_plot.sigAuxHovered.connect(self.update_status_bar_aux) # --> object

        self.correlation_map_dock.visibilityChanged.connect(self.update_correlation_map)        # --> bool
        self.correlation_map.sigImageDoubleClicked.connect(self.correlation_map_double_clicked) # --> object

        self.diffraction_map_dock.visibilityChanged.connect(self.update_diffraction_map)        # --> bool
        self.diffraction_map.sigImageDoubleClicked.connect(self.diffraction_map_double_clicked) # --> object

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
        file_menu.setToolTipsVisible(True)
        # Add an action to load azimuthal integration data
        open_action = QAction("&Open", self)
        open_action.setToolTip("Open an HDF5 file")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        # add a menu with actions to open recent files
        recent_files = read_recent_files_settings()
        self.recent_menu = file_menu.addMenu("Open &Recent")
        if recent_files:
            self.recent_menu.setEnabled(True)
            self.recent_menu.setToolTip("Open a recent file")
            for file in recent_files:
                self._add_recent_file_action(file)
        else:
            self.recent_menu.setEnabled(False)
            self.recent_menu.setToolTip("No recent files available")

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
    
    def _add_recent_file_action(self,file,insert_at_top=False):
        """Add a file to the recent files settings."""
        action = QAction(file, self)
        action.setToolTip(f"Open {file}")
        # action.triggered.connect(lambda checked, f=file: self.file_tree.add_file(f))
        action.triggered.connect(lambda checked, f=file: self.open_file(f))
        action.setDisabled(not os.path.exists(file))  # Disable if file does not exist
        if insert_at_top:
            self.recent_menu.insertAction(self.recent_menu.actions()[0], action)
        else:
            self.recent_menu.addAction(action)

    def _init_view_menu(self, menu_bar):
        """Initialize the View menu with actions to toggle visibility of dock widgets and auxiliary plots. Called by self._init_menu_bar()."""
        # create a view menu
        view_menu = menu_bar.addMenu("&View")
        view_menu.setToolTipsVisible(True)
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
        # Add an action to toggle the correlation map visibility
        toggle_correlation_map_action = self.correlation_map_dock.toggleViewAction()
        toggle_correlation_map_action.setText("Show Auto-correlation &Map")
        view_menu.addAction(toggle_correlation_map_action)
        # Add an action to toggle the diffraction map visibility
        toggle_diffraction_map_action = self.diffraction_map_dock.toggleViewAction()
        toggle_diffraction_map_action.setText("Show &Diffraction Map")
        view_menu.addAction(toggle_diffraction_map_action)

        # add a separator
        view_menu.addSeparator()
        # add a toggle Q action
        toggle_q_action = QAction("&Q (Å-1)",self)
        toggle_q_action.setToolTip("Toggle between Q (Å-1) and 2θ (degrees)")
        toggle_q_action.setCheckable(True)
        toggle_q_action.setChecked(self.is_Q)
        toggle_q_action.triggered.connect(self.toggle_q)
        view_menu.addAction(toggle_q_action)
        self.toggle_q_action = toggle_q_action
        # add a separator
        view_menu.addSeparator()
        # add a change color cycle action
        change_color_cycle_action = QAction("&Change Color Cycle", self)
        change_color_cycle_action.setToolTip("Open the color cycle dialog")
        change_color_cycle_action.triggered.connect(self.show_color_cycle_dialog)
        view_menu.addAction(change_color_cycle_action)
        # add a toggle dark mode action
        toggle_dark_mode_action = QAction("&Dark Mode", self)
        toggle_dark_mode_action.setToolTip("Toggle between dark and lightmode")
        toggle_dark_mode_action.setCheckable(True)
        toggle_dark_mode_action.setChecked(self.is_dark_mode)
        toggle_dark_mode_action.triggered.connect(self.toggle_dark_mode)
        view_menu.addAction(toggle_dark_mode_action)

    def _init_export_menu(self, menu_bar):
        """Initialize the Export menu with actions to export patterns and settings. Called by self._init_menu_bar()."""
        # create an export menu
        export_menu = menu_bar.addMenu("&Export")
        export_menu.setToolTipsVisible(True)
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
        help_menu.setToolTipsVisible(True)
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

        # Add action to create a desktop shortcut (Windows only)
        if os.name == 'nt':
            shortcut_action = QAction("Create &Desktop Shortcut", self)
            shortcut_action.setToolTip("Create a desktop shortcut for plaid")
            shortcut_action.triggered.connect(self.create_shortcut)
            help_menu.addAction(shortcut_action)
        
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
        # update the map cursor position
        self.update_map_cursor(index)

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
            # add the closed file to the recent files settings
            save_recent_files_settings([file])
            self._add_recent_file_action(file,insert_at_top=True)

        if file in self.aux_data.keys():
            del self.aux_data[file]

    def remove_reference(self, index):
        """
        Handle the removal of a reference from the CIF tree,
        by removing it from the pattern plot.
        Called when a reference is removed from the CIF tree.
        """
        self.pattern.remove_reference(index)

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
        
    def open_file(self,file_path=None,item=None):
        """
        Open the optional provided file path or a file dialog to select an azimuthal 
        integration file and add it to the file tree.
        """
        if not file_path:
            # prompt the user to select a file
            if self.file_tree.files and self.file_tree.files[-1] is not None:
                default_dir = os.path.dirname(self.file_tree.files[-1])
            else:
                # default_dir = os.path.expanduser("~")
                default_dir = _get_default_path()
            file_path, ok = QFileDialog.getOpenFileName(self, "Select Azimuthal Integration File", default_dir, "HDF5 Files (*.h5);;All Files (*)")
            if not ok or not file_path:
                return
        self.load_file(file_path, item=item)
        
        if isinstance(file_path, str):
            file_path = [file_path]  # Ensure file_path is a list
        if self.azint_data._shapes:
            for i,f in enumerate(file_path):
                shape  = self.azint_data._shapes[i]
                if shape is not None:
                    # add the file to the file tree
                    item = self.file_tree.add_file(f,shape)
                    self.file_tree.set_target_item_status_tip(self.azint_data.get_info_string(), item)
        
        # flag the correlation and diffraction maps for update
        self.correlation_map.fnames = None  
        self.diffraction_map.fnames = None

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

        # ensure all files are HDF5 files
        if not all(fname.endswith('.h5') for fname in self.azint_data.fnames):
            QMessageBox.critical(self, "Error", "File(s) are not HDF5 files.")
            return False
        
        # read "secondary" data and I, I_error paths and ensure consistent x shapes
        x = None
        I_paths, I_error_paths = [], []
        I0 = np.array([])
        for fname in self.azint_data.fnames:
            data_dict = load_file(fname,parent=self)
            if data_dict is None:
                QMessageBox.critical(self, "Error", "No valid load function found. Please provide a valid azimuthal integration file.")
                return False
            I_paths.append(data_dict["I"])
            I_error_paths.append(data_dict["I_error"])
            is_q = data_dict["q"] is not None
            _x = data_dict["q"] if is_q else data_dict["tth"]
            if x is not None and _x.shape != x.shape:
                QMessageBox.critical(self, "Error", f"Inconsistent x shapes in {fname}.")
                return False
            x = _x
            if data_dict["I0"] is not None:
                I0 = np.append(I0, data_dict["I0"]) if I0.size else data_dict["I0"]

        self.azint_data.set_secondary_data(data_dict)

        # read intensity data in a separate thread
        for i,fname in enumerate(self.azint_data.fnames):
            if not self._load_intensity_data(fname, I_paths[i]):
                # if the intensity data could not be loaded, clear the azint_data and return
                self.azint_data = AzintData(self,file_path)
                return
            
        # read intensity error data in a separate thread
        for i,fname in enumerate(self.azint_data.fnames):
            self._load_intensity_data(fname, I_error_paths[i])

        self.azint_data.shape = self.azint_data.I.shape if self.azint_data.I is not None else None
        # self.azint_data.y_avg = self.azint_data.I.mean(axis=0) if self.azint_data.I is not None else None

        if is_initial_load and I0.size == self.azint_data.shape[0]:
            reply = QMessageBox.question(self,"NXmonitor data found",
                                        "I0 data loaded from nxmonitor dataset. Do you want to use it?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self.azint_data.set_I0(I0)


        # clear the auxiliary plot and check for I0 and auxiliary data
        self.auxiliary_plot.clear()  # Clear the previous plot
        aux_plot_key = None

        # check if the azint_data already has I0 data from a nxmonitor dataset
        # and if so, set the I0 data of the corresponding aux_data. The I0 data
        # of the azint_data is overwritten in the next step, but this ensures that
        # the I0 data conforms to the aux_data I0 format.
        if is_initial_load:
            if not file_path[0] in self.aux_data:
                # if the file is not already in the aux_data, add it
                self.aux_data[file_path[0]] = AuxData(self)
            if isinstance(self.azint_data.I0, np.ndarray):
                self.aux_data[file_path[0]].set_I0(self.azint_data.I0)
                I0 = self.aux_data[file_path[0]].get_data('I0')
                if I0 is not None and I0.shape[0] == self.azint_data.shape[0]:
                    self.azint_data.set_I0(I0)
                    aux_plot_key = file_path[0]
            if self.azint_data.E is not None:
                self.aux_data[file_path[0]]._E = self.azint_data.E
        
        # if a file tree item is provided, i.e. the file already existed in the file tree,
        # check for I0 and auxiliary data. While the integrated data is reloaded from the 
        # file, the (much smaller) auxiliary data is stored in memory.
        if item is not None and not isinstance(item, list): # for now, only handle a single item
            # check if the item has I0 data
            if item.toolTip(0) in self.aux_data:
                I0 = self.aux_data[item.toolTip(0)].get_data('I0')
                if I0 is not None and I0.shape == self.azint_data.shape[0]:
                    self.azint_data.set_I0(I0)
                if len(self.aux_data[item.toolTip(0)].keys()) > 0:
                    # if there are more keys, plot the auxiliary data
                    aux_plot_key = item.toolTip(0)
                if self.aux_data[item.toolTip(0)]._E is not None and self.azint_data.E is None:
                    self.azint_data.E = self.aux_data[item.toolTip(0)]._E                    

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
        #if self.azint_data.E is not None:
        self.E = self.azint_data.E

        # Update the heatmap with the new data
        self.heatmap.set_data(x, I.T)
        # self.heatmap.set_data(x_edge, y_edge, I)
        self.heatmap.set_xlabel("2theta (deg)" if not is_q else "Q (1/A)")

        # Update the pattern with the first frame
        self.pattern.set_data(x, I[0])
        self.pattern.set_avg_data(y_avg)
        self.update_all_patterns()
        self.pattern.set_xlabel("2theta (deg)" if not is_q else "Q (1/A)")
        self.pattern.set_xrange((x[0], x[-1]))

        if not aux_plot_key is None:
            # if a selected item is provided, add the auxiliary plot for that item
            self.add_auxiliary_plot(aux_plot_key)
        
        self.update_correlation_map(self.correlation_map_dock.isVisible())
        #self.update_diffraction_map(self.diffraction_map_dock.isVisible())
            
    def _load_intensity_data(self, file_path, dset_path):
        """Load intensity data from a file in a separate thread."""
        if file_path is None or dset_path is None:
            return
        # show a progress dialog while loading the file
        self.progress = QProgressDialog("Loading data...", "Interrupt", 0, 10000, self)
        self.progress.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self.progress.canceled.connect(lambda: setattr(self.read_worker, 'cancelled', True))
        # disable the close button
        #self.progress.setWindowFlag(QtCore.Qt.WindowType.WindowCloseButtonHint, False)
        self.progress.setWindowTitle("Please wait")
        self.progress.show()

        self._loop = QtCore.QEventLoop()
        self.read_worker.start(fname=file_path, dataset_path=dset_path)
        self._loop.exec()
        return self.read_worker.success

    def _load_intensity_data_done(self, success, result):
        """Handle the completion of intensity data loading."""
        if success:
            # append the result to the azint_data.I array
            if len(self.azint_data._shapes) < len(self.azint_data.fnames):
                # account for the DanMAX map case
                if result.ndim == 3 and result.shape[0] - self.azint_data.x.shape[0] in (0,1):
                    result = self._reshape_danmax_map_data(result, self.azint_data.x.shape[0])
                if self.azint_data.I is None:
                    self.azint_data.I = result
                else:
                    self.azint_data.I = np.vstack((self.azint_data.I, result))
                self.azint_data._shapes.append(result.shape)
            # if the number of shapes matches the number of files, assume
            # the loaded data is I_error
            else:
                if self.azint_data.I_error is None:
                    self.azint_data.I_error = result
                else:
                    self.azint_data.I_error = np.vstack((self.azint_data.I_error, result))
        else:
            QMessageBox.critical(self, "Error", f"Failed to load intensity data from {self.read_worker.fname}.")
            print(result)
        self._loop.quit()
        self.progress.setValue(10000)

    def _load_intensity_data_progress(self, progress):
        self.progress.setValue(progress)

    def _reshape_danmax_map_data(self, I, n_rad_bins):
        # transpose and reshape I
        I = np.transpose(I, (1,2,0)).reshape(-1, I.shape[0])  # [num_patterns, radial bins]
        # in the case of xrd-ct data, an extra first column might be present as absorption data
        # in that case, remove it 
        if I.shape[1] - n_rad_bins == 1:
            I = I[:, 1:]  # Remove first column if x has one less element than I
        return I

    def hline_moved(self, index, pos):
        """Handle the horizontal line movement in the heatmap."""
        self.update_pattern(index, pos)
        self.update_map_cursor(pos)
        self.auxiliary_plot.set_v_line_pos(index, pos)


    def vline_moved(self, index, pos):
        """Handle the vertical line movement in the auxiliary plot."""
        pos = int(np.clip(pos, 0, self.azint_data.shape[0]-1))
        self.update_pattern(index, pos)
        self.update_map_cursor(pos)
        self.heatmap.set_h_line_pos(index, pos)

    def update_pattern(self, index, pos):
        """Update the pattern plot with the data from the selected frame in the heatmap.
        This method is called when a horizontal line is moved in the heatmap or when a new pattern is added."""
        # Get the selected frame from the heatmap
        y = self.azint_data.get_I(index=pos)
        self.pattern.set_data(y=y, index=index)
        self.pattern.set_pattern_name(name=f"frame {pos}", index=index)

    def update_map_cursor(self, pos):
        """Update the map cursors in the correlation and diffraction maps."""
        # update the diffraction map cursor, if visible
        if self.diffraction_map_dock.isVisible() and self.diffraction_map.map_shape is not None:
            if self.azint_data.map_indices is not None:
                pos = self.azint_data.map_indices[pos]
            x,y = np.unravel_index(pos,self.diffraction_map.map_shape)    
            self.diffraction_map.move_cursor(x,y)

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
            # default_dir = os.path.expanduser("~")
            default_dir = _get_default_path()
        file_path, ok = QFileDialog.getOpenFileName(self, "Select Crystallographic Information File", default_dir, "CIF Files (*.cif);;All Files (*)")
        if not ok or not file_path:
            return
        # add the file to the file tree
        self.cif_tree.add_file(file_path)

    def add_reference(self, cif_file, Qmax=None):
        """Add a reference pattern from a CIF file to the pattern plot."""
        if self.E is None:
            self.E = self.get_user_input_energy()
            if self.E is None:
                QMessageBox.critical(self, "Error", "Energy not set. Cannot add reference pattern.")
                return
        if Qmax is None:
            Qmax = self.getQmax()
        self.ref = Reference(cif_file,E=self.E, Qmax=Qmax)
        color = self.cif_tree.get_next_color()
        self.plot_reference(color=color)
        tooltip = f"{self.ref.get_spacegroup_info()}\n{self.ref.get_cell_parameter_info()}"
        self.cif_tree.set_latest_item_tooltip(tooltip)
        
    def get_reference_reflections(self, Qmax=None, dmin=None):
        """
        Get the reference reflections from the current reference pattern,
        converted to the current x-axis units.
        """
        if Qmax is None:
            Qmax = self.getQmax()
        hkl, d, I = self.ref.get_reflections(Qmax=Qmax, dmin=dmin)
        if len(hkl) == 0:
            QMessageBox.warning(self, "No Reflections", "No reflections found in the reference pattern.")
            return
        if self.is_Q:
            # Convert d to Q
            x = d_to_q(d)
        else:
            # Convert d to 2theta
            x = d_to_tth(d, self.E)
        return hkl, x, I

    def plot_reference(self, Qmax=None, dmin=None, color=None):
        """Plot the reference pattern in the pattern plot."""
        hkl, x, I = self.get_reference_reflections(Qmax=Qmax, dmin=dmin)
        self.pattern.add_reference(hkl, x, I,color=color)

    def reload_reference(self,index, Qmax=None):
        """Reload the reference pattern at the given index from the cif tree."""
        cif_file = self.cif_tree.files[index]
        # check that the cif file still exists
        if not os.path.exists(cif_file):
            QMessageBox.critical(self, "Error", f"CIF file not found: {cif_file}")
            return
        item = self.cif_tree.file_tree.topLevelItem(index)
        if Qmax is None:
            Qmax = self.getQmax()
        self.ref = Reference(cif_file,E=self.E, Qmax=Qmax)
        hkl, x, I = self.get_reference_reflections(Qmax=Qmax)
        self.pattern.update_reference(index, hkl, x, I)
        # update the tooltip
        tooltip = f"{self.ref.get_spacegroup_info()}\n{self.ref.get_cell_parameter_info()}"
        item.setToolTip(0, tooltip)
        self.statusBar().showMessage(f"Reloaded reference from {cif_file}")

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
        self.statusBar().showMessage(f"Rescaled {name}")

    def get_user_input_energy(self):
        """Prompt the user to input the energy if not already set."""
        E = self.azint_data.user_E_dialog()
        if E is not None and self.azint_data.fnames[0] in self.aux_data:
            self.aux_data[self.azint_data.fnames[0]].set_energy(E)
        return E

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

                fname = os.path.abspath(aname)
                fname = fname.replace("\\", "/")  # use forward slashes for consistency
                fname = fname.replace("_pilatus_integrated.h5", ".h5")  # remove _pilatus_integrated if present (DanMAX default)
                
                # check if the corresponding raw file exists
                if os.path.exists(fname.replace("/process/azint", "/raw")):
                    default_dir = fname.replace("/process/azint", "/raw")
                else:
                    # check if the raw folder exists
                    adir = os.path.dirname(fname)
                    if os.path.exists(adir.replace("/process/azint", "/raw")):
                        default_dir = adir.replace("/process/azint", "/raw")
                    elif os.path.exists(adir):
                        default_dir = adir
                    else:
                        default_dir = os.path.expanduser("~")
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
        target_name, target_shape = self.file_tree.get_aux_target_name()
        if not target_name in self.aux_data.keys():
            self.aux_data[target_name] = AuxData(self)
        with h5.File(self.h5dialog.get_file_path(), 'r') as f:
            for [alias,file_path,shape] in self.h5dialog.get_selected_items():
                data = f[file_path][:]
                if self.azint_data.reduction_factor > 1:
                    data = average_blocks(data, self.azint_data.reduction_factor)
                    shape = f"{data.shape[0]}*"
                self.file_tree.add_auxiliary_item(alias,shape)
                self.aux_data[target_name].add_data(alias, data)
        
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
                data = average_blocks(data, self.azint_data.reduction_factor)
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
        if self.azint_data.I is None:
            return
        if self.E is None:
            self.E = self.get_user_input_energy()
            if self.E is None:
                QMessageBox.critical(self, "Error", "Energy not set. Cannot toggle between q and 2theta.")
                return
        self.is_Q = not self.is_Q
        self.toggle_q_action.setChecked(self.is_Q)
        if self.is_Q:
            self.heatmap.set_xlabel("Q (1/A)")
            self.pattern.set_xlabel("Q (1/A)")
            x = self.azint_data.get_q()
            self.heatmap.set_data(x, self.azint_data.get_I().T)
            self.pattern.x = x
            self.pattern.avg_pattern_item.setData(x=x, y=self.azint_data.get_average_I())
            for index in range(len(self.pattern.pattern_items)):
                _x, y = self.pattern.get_data(index)
                self.pattern.set_data(x=x, y=y, index=index)
            for ref_item in self.pattern.reference_items:
                _x, _y = ref_item.getData()
                _x = tth_to_q(_x, self.E)
                ref_item.setData(x=_x, y=_y)
            for i, locked_pattern in enumerate(self.locked_patterns):
                is_Q, E = locked_pattern
                if not is_Q:
                    self.pattern.locked_pattern_tth_to_Q(i, E)
                    locked_pattern[0] = True  # update the is_Q status

        else:
            self.heatmap.set_xlabel("2theta (deg)")
            self.pattern.set_xlabel("2theta (deg)")
            x = self.azint_data.get_tth()
            self.heatmap.set_data(x, self.azint_data.get_I().T)
            self.pattern.x = x
            self.pattern.avg_pattern_item.setData(x=x, y=self.azint_data.get_average_I())
            for index in range(len(self.pattern.pattern_items)):
                _x, y = self.pattern.get_data(index)
                self.pattern.set_data(x=x, y=y, index=index)
            for ref_item in self.pattern.reference_items:
                _x, _y = ref_item.getData()
                _x = q_to_tth(_x, self.E)
                ref_item.setData(x=_x, y=_y)
            for i, locked_pattern in enumerate(self.locked_patterns):
                is_Q, E = locked_pattern
                if is_Q:
                    self.pattern.locked_pattern_Q_to_tth(i, E)
                    locked_pattern[0] = False  # update the is_Q status
        # get the updated x-range from the heatmap
        x_range = self.heatmap.get_xrange()
        self.pattern.set_xrange(x_range)

    def set_active_pattern_as_background(self):
        """Set the currently active pattern as the background to be subtracted from all patterns."""
        if self.azint_data.I is None:
            return
        index = self.heatmap.get_active_h_line_pos()
        y_bgr = self.azint_data.get_I(index,bgr_subtracted=False,I0_normalized=False)
        # if the background is the same as the current background, set to None
        if np.all(y_bgr == self.azint_data.y_bgr):
            y_bgr = None
        self.azint_data.set_y_bgr(y_bgr)
        
        # update heatmap
        I = self.azint_data.get_I()
        x = self.heatmap.x
        self.heatmap.set_data(x, I.T)
        # update patterns and average pattern
        self.update_all_patterns()
        y_avg = self.azint_data.get_average_I()
        self.pattern.set_avg_data(y_avg)
        # update diffraction map if visible
        if self.diffraction_map_dock.isVisible():
            self.update_diffraction_map(True)

    def lock_active_pattern(self):
        """Lock the currently active pattern in the pattern plot."""
        if self.azint_data.I is None:
            return
        index = self.heatmap.get_active_h_line_pos()
        x = self.azint_data.get_tth() if not self.is_Q else self.azint_data.get_q()
        y = self.azint_data.get_I(index)
        # U+1F512 padlock emoji
        name = f"\U0001F512 {index}"
        if self.E is None:
            self.E = self.get_user_input_energy()
            if self.E is None:
                QMessageBox.critical(self, "Error", "Energy not set. Cannot lock pattern.")
                return
        self.locked_patterns.append([self.is_Q, self.E]) 
        self.pattern.add_locked_pattern(x,y,name)

    def remove_locked_pattern(self):
        """Remove the last locked pattern from the pattern plot."""
        if len(self.locked_patterns) == 0:
            return
        self.locked_patterns.pop(-1)
        self.pattern.remove_locked_pattern()

    def handle_lock_pattern_request(self, flag):
        """Handle the lock pattern request from the pattern plot."""
        if flag:
            self.lock_active_pattern()
        else:
            self.remove_locked_pattern()

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
            header = ("plaid - plaid looks at integrated data\n"
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

    def update_correlation_map(self, is_checked):
        """Update the correlation map when the correlation map checkbox is toggled."""
        # resize the correlation map dock
        self.correlation_map_dock.resize(self.width()//2, self.height()//2)
        # move the correlation map dock to the bottom right corner of the main window
        self.correlation_map_dock.move(self.geometry().bottomRight() - self.correlation_map_dock.rect().bottomRight())
        if is_checked and self.azint_data.I is not None:
            # check if the correlation map is already calculated for the current data
            if not self.azint_data.fnames == self.correlation_map.fnames:
                self.correlation_map.set_correlation_data(self.azint_data.get_I())
                self.correlation_map.fnames = self.azint_data.fnames

    def correlation_map_double_clicked(self, pos):
        """Handle double click events on the correlation map."""
        if self.correlation_map.fnames:
            # Get the index of the clicked position
            x, y = pos

            # Ensure that at least two horizontal lines exist in the heatmap
            if len(self.heatmap.h_lines) < 2:
                for i in range(2 - len(self.heatmap.h_lines)):
                    self.add_pattern((0,i))

            # move the last two horizontal and vertical lines to the selected positions
            for i in range(2):
                index = len(self.heatmap.h_lines) - 2 + i
                self.update_pattern(index, pos[i])
                self.heatmap.set_h_line_pos(index, pos[i])
                self.auxiliary_plot.set_v_line_pos(index, pos[i])

    def diffraction_map_double_clicked(self, pos):
        """Handle double click events on the diffraction map."""
        if self.diffraction_map.fnames:
            shape = self.diffraction_map.map_shape
            # Get the index of the clicked position
            # convert the (x,y) position to a linear index
            n = np.ravel_multi_index(pos, shape)
            
            # check if the azint_data has map_indices defined
            # and convert the linear index accordingly
            if self.azint_data.map_indices is not None:
                n = self.azint_data.map_indices.index(n)

            # Ensure that at least one horizontal line exists in the heatmap
            if len(self.heatmap.h_lines) < 1:
                self.add_pattern((0,0))

            # move the last horizontal and vertical lines to the selected positions
            index = len(self.heatmap.h_lines) - 1
            self.update_pattern(index, n)
            self.heatmap.set_h_line_pos(index, n)
            self.auxiliary_plot.set_v_line_pos(index, n)

    def update_diffraction_map(self, is_checked):
        """Update the diffraction map when the diffraction map checkbox is toggled."""
        # resize the diffraction map dock
        self.diffraction_map_dock.resize(self.width()//2, self.height()//2)
        # move the diffraction map dock to the bottom right corner of the main window
        self.diffraction_map_dock.move(self.geometry().bottomRight() - self.diffraction_map_dock.rect().bottomRight())
        # toggle the linear region box in the pattern plot
        self.pattern.show_linear_region_box(is_checked)
        if not is_checked or self.azint_data.I is None or self.azint_data.shape[0] <= 1:
            return
        
        # use the fnames attribute to check if the diffraction map
        # is already initialized for the current azint data
        if self.diffraction_map.fnames != self.azint_data.fnames:
            if self.azint_data.map_shape is None:
                # if no map shape is defined in the loaded data,
                # get the viable map shapes
                divisors = get_divisors(self.azint_data.shape[0])[::-1]
                self.diffraction_map.set_map_shape_options(divisors)
            else:
                # self.diffraction_map.set_map_shape_options([self.azint_data.map_shape[0],])
                self.diffraction_map.set_map_shape_options([*self.azint_data.map_shape],current_index=0)
            self.diffraction_map.fnames = self.azint_data.fnames

        roi = self.pattern.get_linear_region_roi()
        self.set_diffraction_map(roi)
  
    def set_diffraction_map(self,roi):
        """
        Set the diffraction map data according to the provided roi.
        Called when the linear region in the pattern plot is changed and 
        whenever the diffraction map is updated.
        """
        if self.diffraction_map_dock.isVisible() and self.azint_data.I is not None and self.azint_data.shape[0] > 1:
            if roi is None or np.sum(roi) == 0:
                z = np.zeros(self.azint_data.shape[0])
            else:
                I = self.azint_data.get_I()[:, roi]
                if self.pattern.linear_region_ignore_negative:
                    I[I<0] = 0
                elif self.pattern.linear_region_linear_background:
                    # perform a simple linear background subtraction
                    # using the first and last points in the ROI
                    bgr = np.linspace(I[:,0], I[:,-1], I.shape[1]).T
                    I = I - bgr

                if self.azint_data.map_indices is None:
                    z = np.mean(I,axis=1)
                    # z = np.mean(self.azint_data.get_I()[:, roi],axis=1)
                else:
                    z = np.full((np.prod(self.azint_data.map_shape),), np.nan)
                    z[self.azint_data.map_indices] = np.mean(I,axis=1)
                    # z[self.azint_data.map_indices] = np.mean(self.azint_data.get_I()[:, roi],axis=1)
            self.diffraction_map.set_diffraction_data(z)

    def apply_reduction_factor(self,files):
        """
        Apply a data reduction factor to the azimuthal integration data.
        Request a reduction factor from the user and apply it to the data.
        Update relevant plots and file tree items.
        Called when the user requests data reduction from the file tree.
        """
        
        # request a reduction factor from the user
        reduction_factor, ok = QInputDialog.getInt(self, 
                                                   "Data Reduction", 
                                                   "Enter reduction factor:\n(Reload to revert)",
                                                    value=2,
                                                    min=1,
                                                    max=self.azint_data.shape[0],
                                                    )
        if not ok:
            return
        
        if self.azint_data.fnames is None or not all(file in self.azint_data.fnames for file in files):
            self.open_file(files)
            if self.azint_data.fnames is None or not all(file in self.azint_data.fnames for file in files):
                QMessageBox.critical(self, "Error", f"Failed to load azimuthal integration data from {files}.")
                return
        
        # apply the reduction factor to the azint data
        self.azint_data.reduce_data(reduction_factor=reduction_factor)
        # update the file tree item shape
        for file in (files):
            shape = self.azint_data.shape
            self.file_tree.add_file(file,shape=shape.__str__().replace(',','*,'))
  
        # update heatmap
        I = self.azint_data.get_I()
        x = self.heatmap.x
        self.heatmap.set_data(x, I.T)
        # update patterns and average pattern
        self.update_all_patterns()
        y_avg = self.azint_data.get_average_I()
        self.pattern.set_avg_data(y_avg)
        # flag the correlation and diffraction maps for update
        self.correlation_map.fnames = None  # force update
        self.diffraction_map.fnames = None  # force update
        # update diffraction map if visible
        if self.diffraction_map_dock.isVisible():
            self.update_diffraction_map(True)
        if self.correlation_map_dock.isVisible():
            self.update_correlation_map(True)
        # update the file tree item status tip to indicate the new reduction factor
        for file in files:
            item = self.file_tree.file_tree.topLevelItem(self.file_tree.files.index(file))
            self.file_tree.set_target_item_status_tip(self.azint_data.get_info_string(), item)
        
        group_path = ";".join([file for file in files])
        # update auxiliary data plot
        if group_path in self.aux_data:
            self.add_auxiliary_plot(group_path)

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
        elif event.key() == QtCore.Qt.Key.Key_C:
            # Show/hide the correlation map
            self.show_correlation_map()
        elif event.key() == QtCore.Qt.Key.Key_M:
            # Show/hide the diffraction map
            self.show_diffraction_map()
        elif event.key() == QtCore.Qt.Key.Key_Q:
            # Toggle between q and 2theta
            self.toggle_q()
        elif event.key() == QtCore.Qt.Key.Key_B:
            # Set the active pattern as background
            self.set_active_pattern_as_background()
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
            pass
    
    def show_correlation_map(self):
        self.correlation_map_dock.setVisible(not self.correlation_map_dock.isVisible())

    def show_diffraction_map(self):
        self.diffraction_map_dock.setVisible(not self.diffraction_map_dock.isVisible())

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
        dock_widgets = [dock for dock in dock_widgets if dock.windowTitle() in ['File Tree', 'CIF Tree', 'Auxiliary Plot']]
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

    def _save_dark_mode_setting(self):
        """Save the dark mode setting."""
        settings = QtCore.QSettings("plaid", "plaid")
        settings.beginGroup("Appearance")
        settings.setValue("dark_mode", self.is_dark_mode)
        settings.endGroup()

    def _load_dark_mode_setting(self):
        """Load the dark mode setting."""
        # get the system default dark mode setting
        app = QApplication.instance()
        system_default = app.styleHints().colorScheme() == QtCore.Qt.ColorScheme.Dark
        settings = QtCore.QSettings("plaid", "plaid")
        settings.beginGroup("Appearance")
        dark_mode = settings.value("dark_mode", system_default, type=bool)
        settings.endGroup()
        return dark_mode

    def show_help_dialog(self):
        """Show the help dialog."""
        help_text = (
            "<h2>Help</h2>"
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
            "<li><b>C</b>: Show/hide the correlation map.</li>"
            "<li><b>M</b>: Show/hide the diffraction map.</li>"
            "<li><b>B</b>: Subtract the active pattern as background.</li>"
            "</ul>"
        )

        # Show the help dialog with the specified text
        QMessageBox.about(self, "Help", help_text)
    
    def show_about_dialog(self):
        """Show the about dialog."""
        about_text = (
            "<h2>plaid - plaid looks at integrated data</h2>"
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

    def _check_if_first_run(self):
        """Check if this is the first run of the application."""
        settings = QtCore.QSettings("plaid", "plaid")
        first_run = settings.value("first_run", True, type=bool)
        if first_run:
            def show_welcome_message():
                # Show a welcome message and ask if the user wish to create a desktop shortcut
                welcome_text = (
                    "<h2>Welcome to plaid!</h2>"
                    "<p>Thank you for using plaid - plaid looks at integrated data.</p>"
                    "<p>You can find help to some of the basic functionalities in the 'Help' menu.</p>"
                )
                if os.name == 'nt':  # Only ask for shortcut creation on Windows
                    welcome_text += "<p>Do you wish to create a desktop shortcut?</p>"
                    reply = QMessageBox.question(self, "Welcome", welcome_text)
                    if reply == QMessageBox.StandardButton.Yes:
                        self.create_shortcut()
                else:
                    QMessageBox.information(self, "Welcome", welcome_text)
            # delay the welcome message by 1 second to avoid blocking startup
            QtCore.QTimer.singleShot(1000, show_welcome_message)
            # Set first_run to False for future runs
            settings.setValue("first_run", False)

    def create_ico_from_resource(self, target_path=None):
        """
        Save the application icon from Qt resources as an .ico file.
        If target_path is None, saves to the directory containing plaid.py and resources.py.
        Returns the path to the saved .ico file.
        """
        if target_path is None:
            # Save to the same directory as this file (plaid.py)
            base_dir = os.path.dirname(os.path.abspath(__file__))
            target_path = os.path.join(base_dir, 'plaid.ico')
        icon = QIcon(':/icons/plaid.png')
        pixmap = icon.pixmap(256, 256)
        pixmap.save(target_path, 'ICO')
        return target_path

    def create_shortcut(self):
        """
        Create a desktop shortcut to launch the application.
        WINDOWS ONLY
        """
        if os.name != 'nt':
            QMessageBox.warning(self, "Unsupported OS", "Shortcut creation is only supported on Windows.")
            return
        # Find the user's desktop path
        shortcut_path = _get_desktop_path()
        if not os.path.exists(shortcut_path):
            # if the desktop path does not exist, prompt the user
            # for a different location
            shortcut_path = ""
            shortcut_path = QFileDialog.getExistingDirectory(self, "Select Directory to Create Shortcut", os.path.expanduser("~"))
            if not shortcut_path:
                return
            shortcut_path = os.path.abspath(shortcut_path)
        shortcut_path = os.path.join(shortcut_path, 'Plaid.lnk')

        # Find the current Python interpreter
        python_exe = sys.executable

        # Find the absolute path to plaid.py
        plaid_py = os.path.abspath(__file__)

        # Find the .ico file (use your create_ico_from_resource method)
        ico_path = self.create_ico_from_resource()

        # Set working directory to user profile
        working_dir = os.environ['USERPROFILE']

        # Compose PowerShell command to create the shortcut
        powershell_cmd = (
            f"$s=(New-Object -COM WScript.Shell).CreateShortcut('{shortcut_path}');"
            f"$s.TargetPath='{python_exe}';"
            f"$s.Arguments='\"{plaid_py}\"';"
            f"$s.IconLocation='{ico_path}';"
            f"$s.WorkingDirectory='{working_dir}';"
            f"$s.WindowStyle=7;"  # 7 = Minimized
            "$s.Save()"
        )

        # Run the command
        os.system(f'powershell -NoProfile -Command "{powershell_cmd}"')

        if os.path.exists(shortcut_path):
            QMessageBox.information(self, "Shortcut Created", f"Shortcut created:\n{shortcut_path}")
        else:
            QMessageBox.critical(self, "Error", "Failed to create shortcut.")

    def toggle_dark_mode(self, is_checked):
        """Toggle dark mode for the application."""
        # get the application instance
        app = QApplication.instance()
        if is_checked:
            app.styleHints().setColorScheme(QtCore.Qt.ColorScheme.Dark)
            self.is_dark_mode = True
            _foreground_darker = 120
            _background_darker = 110
        else:
            app.styleHints().setColorScheme(QtCore.Qt.ColorScheme.Light)
            self.is_dark_mode = False
            _foreground_darker = 180
            _background_darker = 103

        QtCore.QCoreApplication.processEvents()
        foreground_color = app.palette().text().color().darker(_foreground_darker).name()
        background_color = app.palette().window().color().darker(_background_darker).name()

        pg.setConfigOption('foreground', foreground_color)
        pg.setConfigOption('background', background_color)

        self.heatmap.updateBackground()
        self.heatmap.updateForeground()
        self.pattern.updateBackground()
        self.pattern.updateForeground()
        self.auxiliary_plot.updateBackground()
        self.auxiliary_plot.updateForeground()
        self.correlation_map.updateBackground()
        self.correlation_map.updateForeground()
        self.diffraction_map.updateBackground()
        self.diffraction_map.updateForeground()

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
        self._save_dark_mode_setting()
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

    # Create and show the splash screen
    splash_pix = QPixmap(":/icons/plaid.png")  # Use your resource or a file path
    splash = QSplashScreen(splash_pix)
    splash.show()

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
    splash.finish(window)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()