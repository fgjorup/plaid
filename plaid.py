# -*- coding: utf-8 -*-
"""
plaid - Plot Azimuthally Integrated Data
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides the main application window for plotting azimuthally integrated data,
including loading files, displaying heatmaps and patterns, and managing auxiliary data.
"""
import sys
import os
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QDockWidget, QSizePolicy, QFileDialog, QMessageBox
from PyQt6.QtGui import QAction, QIcon
from PyQt6 import QtCore
import pyqtgraph as pg
import h5py as h5
import resources.resources
from trees import FileTreeWidget, CIFTreeWidget
from dialogs import H5Dialog
from reference import Reference
from plot_widgets import HeatmapWidget, PatternWidget, AuxiliaryPlotWidget
from misc import q_to_tth, tth_to_q
from data_containers import AzintData, AuxData


# TODO/IDEAS

# - Update patterns when a new file is loaded
# - Add a button to save the average pattern
# - Add a button to save the selected pattern(s)
# - Expand the Help menu 
# - Make a more robust file loading mechanism that can handle different file formats and 
#   structures, perhaps as a "data class"

# - replace print warnings/messages with QMessageBox dialogs

# - properly remove data from all plots when itemRemoved from the file tree

# - handle auxiliary data drag drop 

# - save additional settings like default path(s), dock widget positions, etc.

# - optimize memory usage and performance for large datasets

# - add more tooltips


colors = [
        '#AAAA00',  # Yellow
        '#AA00AA',  # Magenta
        '#00AAAA',  # Cyan
        '#AA0000',  # Red
        '#00AA00',  # Green
        "#0066FF",  # Blue
        '#AAAAAA',  # Light Gray
        ]

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
    # Remove duplicates and empty entries
    recent_files = list(set(recent_files + existing_files))
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
    recent_refs = list(set(recent_refs + existing_refs))
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("plaid - plot azimuthally integrated data")
        self.statusBar().showMessage("")
        # Set the window icon
        self.setWindowIcon(QIcon(":/icons/plaid.png"))
    
        self.E = None  # Energy in keV
        self.is_Q = False
        self.y_avg = None

        self.azint_data = AzintData()
        self.aux_data = {}

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

        


        self.heatmap = HeatmapWidget()

        # Create the PatternWidget
        self.pattern = PatternWidget()

        # Add the widgets to the main layout
        plot_layout.addWidget(self.heatmap,1)
        plot_layout.addWidget(self.pattern,1, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)# | QtCore.Qt.AlignmentFlag.AlignTop, )

        # Create the file tree widget
        self.file_tree = FileTreeWidget()
        # create a dock widget for the file tree
        file_tree_dock = QDockWidget("File Tree", self)
        file_tree_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        file_tree_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        file_tree_dock.setWidget(self.file_tree)

        # Create the CIF tree widget
        self.cif_tree = CIFTreeWidget(self)
        # create a dock widget for the CIF tree
        cif_tree_dock = QDockWidget("CIF Tree", self)
        cif_tree_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        cif_tree_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        cif_tree_dock.setWidget(self.cif_tree)
  
        self.auxiliary_plot = AuxiliaryPlotWidget()
        # create a dock widget for the auxiliary plot
        auxiliary_plot_dock = QDockWidget("Auxiliary Plot", self)
        auxiliary_plot_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        auxiliary_plot_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        auxiliary_plot_dock.setWidget(self.auxiliary_plot)
        
        # get the current dock widget settings (if any)
        left, right = self._load_dock_settings()
        # if settings for all three dock widgets are available
        if len(left) + len(right) == 3:
            dock_widgets = {file_tree_dock.windowTitle(): file_tree_dock,
                            cif_tree_dock.windowTitle(): cif_tree_dock,
                            auxiliary_plot_dock.windowTitle(): auxiliary_plot_dock}
            for [key,is_visible] in left:
                dock = dock_widgets[key]
                self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, dock)
                dock.setVisible(is_visible)
            for [key,is_visible] in right:
                dock = dock_widgets[key]
                self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
                dock.setVisible(is_visible)

        else:
            self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, file_tree_dock)
            self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, cif_tree_dock)
            self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, auxiliary_plot_dock)

        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks)
 
        self.file_tree.sigItemDoubleClicked.connect(self.load_file)
        self.file_tree.sigItemRemoved.connect(self.remove_file)
        self.file_tree.sigI0DataRequested.connect(self.load_I0_data)
        self.file_tree.sigAuxiliaryDataRequested.connect(self.load_auxiliary_data)

        self.cif_tree.sigItemAdded.connect(self.add_reference)
        self.cif_tree.sigItemChecked.connect(self.toggle_reference)
        self.cif_tree.sigItemDoubleClicked.connect(self.rescale_reference)

        self.heatmap.sigHLineMoved.connect(self.hline_moved)
        self.heatmap.sigXRangeChanged.connect(self.pattern.set_xrange)
        self.heatmap.sigImageDoubleClicked.connect(self.add_pattern)
        self.heatmap.sigImageHovered.connect(self._update_status_bar)
        #self.heatmap.sigHLineAdded.connect(self.add_pattern)
        self.heatmap.sigHLineRemoved.connect(self.remove_pattern)

        self.pattern.sigXRangeChanged.connect(self.heatmap.set_xrange)
        self.pattern.sigPatternHovered.connect(self.update_status_bar)

        self.auxiliary_plot.sigVLineMoved.connect(self.vline_moved)
        self.auxiliary_plot.sigAuxHovered.connect(self.update_status_bar_aux)

        self.heatmap.addHLine()
        self.auxiliary_plot.addVLine()

        # Create a menu bar
        menu_bar = self.menuBar()
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
                action.triggered.connect(lambda checked, f=file: self.file_tree.add_file(f))
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
        recent_references_menu = file_menu.addMenu("Load Re&cent")
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




        # create a view menu
        view_menu = menu_bar.addMenu("&View")
        # Add an action to toggle the file tree visibility
        toggle_file_tree_action = file_tree_dock.toggleViewAction()
        toggle_file_tree_action.setText("Show &File Tree")
        view_menu.addAction(toggle_file_tree_action)
        # Add an action to toggle the CIF tree visibility
        toggle_cif_tree_action = cif_tree_dock.toggleViewAction()
        toggle_cif_tree_action.setText("Show &CIF Tree")
        view_menu.addAction(toggle_cif_tree_action)
        # Add an action to toggle the auxiliary plot visibility
        toggle_auxiliary_plot_action = auxiliary_plot_dock.toggleViewAction()
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

        # create a help menu
        help_menu = menu_bar.addMenu("&Help")
        # Add an action to show the help dialog
        help_action = QAction("&Help", self)
        help_action.setToolTip("Show help dialog")
        help_action.triggered.connect(self.show_help_dialog)
        help_menu.addAction(help_action)
        # Add an action to show the about dialog
        about_action = QAction("&About", self)
        about_action.setToolTip("Show about dialog")
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)


  
        self.centralWidget().resizeEvent = self.resizeEvent



        # TEST
        #fname = r"C:\Users\au480461\Postdoc\Scripts\test_files\raw\pxrd_cryo\scan-0100.h5"
        #aname = fname.replace("\\raw", "\\process\\azint").replace(".h5", "_pilatus_integrated.h5")
        #self.file_tree.add_file(aname)
        #self.load_file(aname)
        #self.load_auxiliary_data(fname)
        #h5dialog = H5Dialog(self, fname)
        #h5dialog.open()
        # h5dialog.finished.connect(lambda result: print(f"H5Dialog finished with result: {result}"))
        #h5dialog.finished.connect(lambda result: print(h5dialog.selected_items) if result == QDialog.DialogCode.Accepted else print("H5Dialog cancelled"))


        self.resizeDocks([file_tree_dock, cif_tree_dock, auxiliary_plot_dock], [200, 200, 200], QtCore.Qt.Orientation.Horizontal)


    def add_pattern(self, pos):
        """Add a horizontal line to the heatmap and an accompanying pattern."""
        I = self.azint_data.get_I()
        index = int(np.clip(pos[1], 0, I.shape[0]-1))
        self.heatmap.addHLine(pos=index+0.5)
        self.pattern.add_pattern()
        self.pattern.set_data(y=I[index], index=len(self.pattern.pattern_items)-1)
        self.pattern.set_pattern_name(name=f"frame {index}", index=len(self.pattern.pattern_items)-1)

        # add a vertical line to the auxiliary plot
        self.auxiliary_plot.addVLine(pos=index)


    def remove_pattern(self, index):
        """Remove a pattern."""
        self.pattern.remove_pattern(index)
        self.auxiliary_plot.remove_v_line(index)

    def remove_file(self, file):
        """Handle the removal of a file from the file tree."""
        if self.azint_data.fnames is None or file not in self.azint_data.fnames:
            return
        self.azint_data = AzintData(self)
        self.heatmap.clear()
        self.pattern.clear()
        self.auxiliary_plot.clear()


    def resizeEvent(self, event):
        """Handle the resize event to update the pattern width."""
        super().resizeEvent(event)
        self.update_pattern_geometry()

    def update_pattern_geometry(self):
        """Update the geometry of the pattern widget to match the heatmap."""
        self.pattern.plot_widget.setFixedWidth(self.heatmap.plot_widget.width())

    def _update_status_bar(self, x_idx, y_idx):
        if self.azint_data.x is None:
            return
        if self.is_Q:
            x_value = self.azint_data.get_q()[x_idx]
        else:
            x_value = self.azint_data.get_tth()[x_idx]
        y_value = self.azint_data.I[y_idx, x_idx] if self.azint_data.I is not None else 0
        self.update_status_bar(x_value, y_value)


    def update_status_bar(self, x_value, y_value):
        """Update the status bar with the current position."""
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

    def update_status_bar_aux(self, x_value, y_value):
        """Update the status bar with the auxiliary plot position."""
        # determine which string formatting to use based on the values
        status_text = f"X: {x_value:7.1f}, "   
        if np.abs(y_value) < 1e-3 or np.abs(y_value) >= 1e4:
            # use scientific notation for very small or very large values
            status_text += f"Y: {y_value:.3e}" 
        else:
            # use normal float formatting for other values
            status_text += f"Y: {y_value:7.3f}"
        self.statusBar().showMessage(status_text)

    def open_file(self):
        """
        Open a file dialog to select an azimuthal integration file
        and add it to the file tree.
        """
        # prompt the user to select a file
        if self.file_tree.files and self.file_tree.files[-1] is not None:
            default_dir = os.path.dirname(self.file_tree.files[-1])
        else:
            default_dir = os.path.expanduser("~")
        file_path, ok = QFileDialog.getOpenFileName(self, "Select Azimuthal Integration File", default_dir, "HDF5 Files (*.h5);;All Files (*)")
        if not ok or not file_path:
            return
        # add the file to the file tree
        self.file_tree.add_file(file_path)
        

    def load_file(self, file_path, item=None):
        """Load the selected file and update the heatmap and pattern."""

        self.azint_data = AzintData(self,[file_path])
        if not self.azint_data.load():
            QMessageBox.critical(self, "Error", f"Failed to load file: {file_path}")
            return
        x = self.azint_data.get_tth() if not self.azint_data.is_q else self.azint_data.get_q()
        I = self.azint_data.get_I()
        y_avg = self.azint_data.y_avg
        is_q = self.azint_data.is_q
        self.is_Q = is_q
        self.toggle_q_action.setChecked(is_q)
        if self.azint_data.E is not None:
            self.E = self.azint_data.E
        
        # clear the auxiliary plot and check for I0 and auxiliary data
        self.auxiliary_plot.clear_plot()  # Clear the previous plot
        if item is not None:
            # check if the item has I0 data
            if item.text(0) in self.aux_data:
                I0 = self.aux_data[item.text(0)].get_data('I0')
                if I0 is not None:
                    self.azint_data.set_I0(I0)
                if len(self.aux_data[item.text(0)].keys()) > 1:
                    # if there are more keys, plot the auxiliary data
                    self.add_auxiliary_plot(item.text(0))


        # Update the heatmap with the new data
        self.heatmap.set_data(x, I.T)
        # self.heatmap.set_data(x_edge, y_edge, I)
        self.heatmap.set_xlabel("2theta (deg)" if not is_q else "q (1/A)")


        # Update the pattern with the first frame
        self.pattern.set_data(x, I[0])
        self.pattern.set_avg_data(y_avg)
        self.pattern.set_xlabel("2theta (deg)" if not is_q else "q (1/A)")
        self.pattern.set_xrange((x[0], x[-1]))

    def hline_moved(self, index, pos):
        """Handle the horizontal line movement in the heatmap."""
        self.update_pattern(index, pos)
        self.auxiliary_plot.set_v_line_pos(index, pos)

    def vline_moved(self, index, pos):
        """Handle the vertical line movement in the auxiliary plot."""
        self.update_pattern(index, pos)
        self.heatmap.set_h_line_pos(index, pos)

    def update_pattern(self, index, pos):
        # Get the selected frame from the heatmap
        I = self.azint_data.get_I()
        self.pattern.set_data(y=I[pos], index=index)
        self.pattern.set_pattern_name(name=f"frame {pos}", index=index)

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
        """Add a reference pattern from a CIF file."""
        if self.E is None:
            self.E = self.azint_data.user_E_dialog()
            if self.E is None:
                QMessageBox.critical(self, "Error", "Energy not set. Cannot add reference pattern.")
                return
        if Qmax is None:
            Qmax = self.getQmax()
        self.ref = Reference(cif_file,E=self.E, Qmax=Qmax)
        self.plot_reference()

    def plot_reference(self, Qmax=None, dmin=None):
        """Plot the reference pattern."""
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
        """Toggle the visibility of the reference pattern."""
        self.pattern.toggle_reference(index, is_checked)

    def rescale_reference(self,index,name):
        """Rescale the intensity of the indexed reference to the current y-max"""
        self.pattern.rescale_reference(index)

    def load_I0_data(self, fname=None):
        """Load auxillary data as I0"""
        self.load_auxiliary_data(is_I0=True)

    def load_auxiliary_data(self, fname=None, is_I0=False):
        """Handle the auxiliary data file name and open the H5Dialog."""
        if fname is None:
            # prompt the user to select a file
            if self.file_tree.files[-1] is not None:
                default_dir = os.path.dirname(self.file_tree.files[-1])
            else:
                default_dir = os.path.expanduser("~")
            fname, ok = QFileDialog.getOpenFileName(self, "Select Auxiliary Data File", default_dir, "HDF5 Files (*.h5);;All Files (*)")
            if not ok or not fname:
                return
        
        self.h5dialog = H5Dialog(self, fname)
        self.h5dialog.open()
        if is_I0:
            self.h5dialog.finished.connect(self.add_I0_data)
        else:
            self.h5dialog.finished.connect(self.add_auxiliary_data)

    def add_I0_data(self,is_ok):
        """Add I0 data to the azint data instance."""
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
        self.aux_data[target_name].set_I0(I0)


    def add_auxiliary_data(self,is_ok):
        """Add auxiliary data to the azint data instance."""
        if not is_ok:
            return
        aux_data = {}
        target_name, target_shape = self.file_tree.get_aux_target_name()
        if not target_name in self.aux_data.keys():
            self.aux_data[target_name] = AuxData(self)
        with h5.File(self.h5dialog.file_path, 'r') as f:
            for [alias,file_path,shape] in self.h5dialog.selected_items:
                aux_data[alias] =  f[file_path][:]
                self.file_tree.add_auxiliary_item(alias,shape)
                self.aux_data[target_name].add_data(alias, f[file_path][:])
        
        #self.azint_data.set_auxiliary_data(aux_data)
        # Update the auxiliary plot with the new data
        self.add_auxiliary_plot(target_name)

    # MARKED FOR DEPRECATION
    def _add_auxiliary_plot(self):
        """Add an auxiliary plot"""
        if not self.azint_data.aux_data:
            print("No auxiliary data available.")
            return
        self.auxiliary_plot.clear_plot()  # Clear the previous plot
        for alias, data in self.azint_data.aux_data.items():
            if data.ndim == 1:
                # If the data is 1D, plot it directly
                self.auxiliary_plot.set_data(data, label=alias)
    
    def add_auxiliary_plot(self, selected_item):
        """Add an auxiliary plot"""
        if not selected_item in self.aux_data:
            QMessageBox.warning(self, "No Auxiliary Data", f"No auxiliary data available for {selected_item}.")
            return
        self.auxiliary_plot.clear_plot()  # Clear the previous plot
        for alias, data in self.aux_data[selected_item].get_dict().items():
            if alias == 'I0':
                # Skip I0 data for the auxiliary plot
                continue
            if data is not None and data.ndim == 1:
                # If the data is 1D, plot it directly
                self.auxiliary_plot.set_data(data, label=alias)
            



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
            self.pattern.avg_pattern_item.setData(x=x, y=self.azint_data.y_avg)
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
            self.pattern.avg_pattern_item.setData(x=x, y=self.azint_data.y_avg)
            for pattern_item in self.pattern.pattern_items:
                _x, y = pattern_item.getData()
                pattern_item.setData(x=x, y=y)
            for ref_item in self.pattern.reference_items:
                _x, _y = ref_item.getData()
                _x = q_to_tth(_x, self.E)
                ref_item.setData(x=_x, y=_y)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            if all(url.toLocalFile().endswith('.cif') for url in event.mimeData().urls()):
                self.cif_tree.dragEnterEvent(event)
            elif all(url.toLocalFile().endswith('.h5') for url in event.mimeData().urls()):
                self.file_tree.dragEnterEvent(event)
    
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            if all(url.toLocalFile().endswith('.cif') for url in event.mimeData().urls()):
                self.cif_tree.dropEvent(event)
            elif all(url.toLocalFile().endswith('.h5') for url in event.mimeData().urls()):
                self.file_tree.dropEvent(event)

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
            "<li>Double-click on the heatmap to add a moveable selection line.</li>"
            "<li>Right-click on the moveale line to remove it.</li>"
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
            "<p>Version 0.1</p>"
            "<p>This application allows you to visualize azimuthally integrated data "
            "from HDF5 files and compare them with reference patterns from CIF files.</p>"
            "<p>Developed by: <a href='mailto:fgjorup@chem.au.dk'>F.H. Gjørup</a><br>"
            "Department of Chemistry, Aarhus University & <br>"
            "MAX IV Laboratory, Lund University</p>"
            "<p>License: GPL-3.0</p>"
            "<p>For more information, visit the <a href='https://github.com/fgjorup/plaid'>GitHub repository</a>.</p>"
        )
        # Show the about dialog with the specified text
        QMessageBox.about(self, "About", about_text)

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
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # get the application palette colors
    foreground_color = app.palette().text().color().darker(150).name()
    background_color = app.palette().window().color().darker(110).name()

    pg.setConfigOptions(antialias=True,
                        foreground=foreground_color,
                        background=background_color,
                        )
    window = MainWindow()
    window.show()

    sys.exit(app.exec())