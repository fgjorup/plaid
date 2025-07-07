# -*- coding: utf-8 -*-
"""
plaid - Plot Azimuthally Integrated Data
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides classes to create tree widgets for managing files and CIFs.

"""
import os
from PyQt6.QtWidgets import  QVBoxLayout, QWidget, QTreeWidget, QTreeWidgetItem, QMenu
from PyQt6 import QtCore
import pyqtgraph as pg
import h5py as h5
from nexus import get_nx_default, get_nx_signal
from reference import validate_cif

colors = [
        '#AAAA00',  # Yellow
        '#AA00AA',  # Magenta
        '#00AAAA',  # Cyan
        '#AA0000',  # Red
        '#00AA00',  # Green
        "#0066FF",  # Blue
        '#AAAAAA',  # Light Gray
        ]

class FileTreeWidget(QWidget):
    sigItemDoubleClicked = QtCore.pyqtSignal(str,object)
    sigItemRemoved = QtCore.pyqtSignal(str)
    sigI0DataRequested = QtCore.pyqtSignal()
    sigAuxiliaryDataRequested = QtCore.pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = []  # List to store file paths
        self.aux_target_index = None  # Index of the item for which auxiliary data is requested
        # Create a layout
        layout = QVBoxLayout(self)
        # Create a file tree view
        #self.file_tree = pg.TreeWidget()
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(['File name', 'Shape'])
        self.file_tree.setSortingEnabled(False)
        self.file_tree.itemDoubleClicked.connect(self.itemDoubleClicked)
        self.file_tree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.customMenuEvent)

        layout.addWidget(self.file_tree)

        self.setAcceptDrops(True)

    def add_file(self, file_path):
        """Add a file to the tree widget."""
        
        ###
        # the following should probably be moved to the main application
        
        if not file_path.endswith('.h5'):
            return
        # try to read the file to get its shape
        try:
            with h5.File(file_path, 'r') as f:
                default = get_nx_default(f)
                signal = get_nx_signal(default)
                if not signal is None:
                    shape = signal.shape
                elif 'entry' in f and 'default' in f['entry'].attrs:
                    dset = f['entry'][f['entry'].attrs['default']]
                    if 'signal' in dset.attrs:
                        shape = dset[dset.attrs['signal']].shape
                    elif 'I' in dset:
                        shape = dset['I'].shape
                elif 'entry/data1d' in f:
                    dset = f['entry/data1d']
                    shape = dset['I'].shape
                elif 'entry/data' in f:
                    dset = f['entry/data']
                    shape = dset['I'].shape
                elif 'I' in f:
                    dset = f['I']
                    shape = dset.shape
                else:
                    print(f.keys())
                    return
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return
        
        ### end
        

        self.files.append(file_path)
        file_name = os.path.basename(file_path).replace('_pilatus_integrated.h5', '')
        # check if the file is already in the tree
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item.text(0) == file_name:
                # If the file is already in the tree, update its shape
                item.setText(1, shape.__str__())
                return
        # Create a new tree item for the file
        item = pg.TreeWidgetItem([file_name,shape.__str__()])
        self.file_tree.addTopLevelItem(item)
        # Optionally, you can expand the item
        item.setExpanded(True)

    def add_auxiliary_item(self, alias,shape):
        """Add an auxiliary child item to the target toplevel item"""
        if self.aux_target_index is None or self.aux_target_index >= len(self.files):
            return
        # get the target item
        item = self.file_tree.topLevelItem(self.aux_target_index)
        if item is None:
            return
        # check if the auxiliary item already exists
        for i in range(item.childCount()):
            aux_item = item.child(i)
            if aux_item.text(0) == alias:
                # If the auxiliary item already exists, update its shape
                aux_item.setText(1, shape.__str__())
                return
        # create a new item for the auxiliary data
        aux_item = pg.TreeWidgetItem([alias, shape.__str__()])
        item.addChild(aux_item)

    def get_aux_target_name(self):
        """Get the target item name for auxiliary data."""
        if self.aux_target_index is None or self.aux_target_index >= len(self.files):
            return None
        # get the target item
        item = self.file_tree.topLevelItem(self.aux_target_index)
        if item is None:
            return None
        return item.text(0)  # Return the file name of the target item

        

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """Handle drop event."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.endswith('.h5'):
                    self.add_file(file_path)
            event.acceptProposedAction()

    def itemDoubleClicked(self, item, column):
        """Handle item double click event."""
        index = self.file_tree.indexOfTopLevelItem(item)
        if index == -1:
            return
        self.sigItemDoubleClicked.emit(self.files[index],item)

    def remove_item(self, item):
        """Remove the item from the tree."""
        index = self.file_tree.indexOfTopLevelItem(item)
        if index == -1:
            return
        # remove the file from the list
        file = self.files.pop(index)

        # remove the item from the tree
        self.file_tree.takeTopLevelItem(index)
        # emit a signal if needed
        self.sigItemRemoved.emit(file)

    def request_I0_data(self, item):
        """Request I0 data for the selected item."""
        index = self.file_tree.indexOfTopLevelItem(item)
        if index == -1:
            return
        self.aux_target_index = index
        # clear any I0 data for the target item
        for i in range(item.childCount()):
            if item.child(i).text(0).startswith('I₀'):
                # remove the I0 data item
                item.removeChild(item.child(i))
                break
        # Emit a signal to request I0 data for item
        self.sigI0DataRequested.emit()

    def request_auxiliary_data(self, item):
        """Request auxiliary data for the selected item."""
        index = self.file_tree.indexOfTopLevelItem(item)
        if index == -1:
            return
        self.aux_target_index = index
        ## clear the auxiliary data for the target item
        #for i in range(item.childCount()):
        #    item.removeChild(item.child(0))
        # Emit a signal to request auxiliary data for item
        self.sigAuxiliaryDataRequested.emit()

    def customMenuEvent(self, pos):
        """Handle the custom context menu event."""
        # determine the item at the position
        item = self.file_tree.itemAt(pos)
        if item is None:    
            return
        # check if the item is a top-level item
        if item.parent() is not None:
            return
        # # create a context menu
        # menu = QMenu(self)
        # # add an action to remove the item
        # remove_action = menu.addAction("Remove")
        # remove_action.triggered.connect(lambda: self.remove_item(item))
        # # add an action to add auxiliary data
        # add_aux_action = menu.addAction("Add Auxiliary Data")
        # add_aux_action.triggered.connect(lambda: self.request_auxiliary_data(item))
        # create a context menu for the item
        menu = self._mkMenu('toplevel',item)
        menu.exec(self.file_tree.viewport().mapToGlobal(pos))
        menu.deleteLater()  # Clean up the menu after use

    def _mkMenu(self,level, item):
        """Create a context menu for the item."""
        if level == 'toplevel':
            menu = QMenu(self)
            # add an action to add "I0" data U+2080 Subscript Zero Unicode Character.
            add_aux_action = menu.addAction("Add I₀ Data")
            add_aux_action.setToolTip("Add I₀ data for normalization")
            add_aux_action.triggered.connect(lambda: self.request_I0_data(item))
            # add an action to add auxiliary data
            add_aux_action = menu.addAction("Add Auxiliary Data")
            add_aux_action.setToolTip("Add auxiliary 1D data from an h5 file")
            add_aux_action.triggered.connect(lambda: self.request_auxiliary_data(item))
            # add an action to remove the item
            remove_action = menu.addAction("Remove")
            remove_action.setToolTip("Remove the selected item from the tree")
            remove_action.triggered.connect(lambda: self.remove_item(item))
        # elif level == 'child':
        #     menu = QMenu(self)
        #     # add an action to request normalization the data
        #     norm_action = menu.addAction("Normalize")
        #     norm_action.triggered.connect(lambda: self.request_auxiliary_normalization(item))
        #     # add an action to remove the auxiliary item
        #     remove_action = menu.addAction("Remove Auxiliary Data")
        #     remove_action.triggered.connect(lambda: item.parent().removeChild(item))
        return menu


class CIFTreeWidget(QWidget):
    sigItemAdded = QtCore.pyqtSignal(str)
    sigItemChecked = QtCore.pyqtSignal(int, bool)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = []  # List to store CIF file paths
        # Create a layout
        layout = QVBoxLayout(self)
        # Create a file tree view
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(['CIF file name'])
        self.file_tree.setSortingEnabled(False)
        self.file_tree.itemChanged.connect(self.itemChecked)
        layout.addWidget(self.file_tree)

        self.setAcceptDrops(True)

    def add_file(self, file_path):
        """Add a CIF file to the tree widget."""
        if not file_path.endswith('.cif'):
            return
        file_name = os.path.basename(file_path)
        # check if the file is already in the tree
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item.text(0) == file_name:
                # If the file is already in the tree, emit the signal and return
                return
        # Validate the CIF file
        if not validate_cif(file_path):
            print(f"Invalid CIF file: {file_path}")
            return
        self.files.append(file_path)
        item = QTreeWidgetItem([file_name])
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0,QtCore.Qt.CheckState.Checked)
        # set the item color
        item.setForeground(0, pg.mkColor(colors[::-1][len(self.files)-1 % len(colors)]))
        self.file_tree.addTopLevelItem(item)
        self.sigItemAdded.emit(file_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.endswith('.cif'):
                    self.add_file(file_path)
            event.acceptProposedAction()
    
    def itemChecked(self, item, column):
        """Handle item checked event."""
        index = self.file_tree.indexOfTopLevelItem(item)
        if index == -1:
            return
        checked = item.checkState(column) == QtCore.Qt.CheckState.Checked
        self.sigItemChecked.emit(index, checked)



if __name__ == "__main__":
    pass