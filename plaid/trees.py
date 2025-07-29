# -*- coding: utf-8 -*-
"""
plaid - Plot Azimuthally Integrated Data
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides classes to create tree widgets for managing files and CIFs.

"""
import os
from PyQt6.QtWidgets import  QVBoxLayout, QWidget, QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox
from PyQt6 import QtCore
from PyQt6.QtGui import QFont
import pyqtgraph as pg
from plaid.reference import validate_cif

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
    sigGroupDoubleClicked = QtCore.pyqtSignal(list,list)
    sigItemRemoved = QtCore.pyqtSignal(str)
    sigI0DataRequested = QtCore.pyqtSignal()
    sigAuxiliaryDataRequested = QtCore.pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = []  # List to store file paths
        self.aux_target_index = None  # Index of the item for which auxiliary data is requested
        self.item_group = []  # List to store selected items for grouping
        # Create a layout
        layout = QVBoxLayout(self)
        # Create a file tree view
        #self.file_tree = pg.TreeWidget()
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(['File name', 'Shape'])
        self.file_tree.setSortingEnabled(False)
        self.file_tree.setColumnWidth(0, 150)
        self.file_tree.setColumnWidth(1, 75)
        self.file_tree.itemDoubleClicked.connect(self.itemDoubleClicked)
        self.file_tree.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.customMenuEvent)
        self.file_tree.setSelectionMode(QTreeWidget().SelectionMode.ExtendedSelection)
        layout.addWidget(self.file_tree)

        #self.setAcceptDrops(True)

    def add_file(self, file_path,shape):
        """Add a file to the tree widget."""
        file_path = os.path.abspath(file_path)

        # check if the file is already in self.files
        if file_path in self.files:
            # If the file is already in the list, update its shape
            index = self.files.index(file_path)
            item = self.file_tree.topLevelItem(index)
            if item is not None:
                item.setText(1, shape.__str__())
            return
        # add the file to the list
        self.files.append(file_path)
        # get the file name
        file_name = os.path.basename(file_path).replace('_pilatus_integrated.h5', '')
        
        # Create a new tree item for the file
        item = QTreeWidgetItem([file_name, shape.__str__()])
        item.setToolTip(0, file_path)  # Set the tooltip to the full file path
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
        """Get the target item name and shape for auxiliary data."""
        if self.aux_target_index is None or self.aux_target_index >= len(self.files):
            return None
        # get the target item
        item = self.file_tree.topLevelItem(self.aux_target_index)
        if item is None:
            return None
        # target_name = item.text(0)
        target_name = item.toolTip(0)  # Get the full file path as the target name
        target_shape = item.text(1).replace('(', '').replace(')', '').replace(' ', '').split(',')
        target_shape = tuple(int(dim) for dim in target_shape if dim.isdigit())
        return target_name,target_shape  # Return the file name of the target item

    def get_aux_target_item(self):
        """Get the target item for auxiliary data."""
        if self.aux_target_index is None or self.aux_target_index >= len(self.files):
            return None
        # get the target item
        item = self.file_tree.topLevelItem(self.aux_target_index)
        if item is None:
            return None
        return item

    def dragEnterEvent(self, event):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    # def dropEvent(self, event):
    #     """Handle drop event."""
    #     if event.mimeData().hasUrls():
    #         for url in event.mimeData().urls():
    #             file_path = url.toLocalFile()
    #             if file_path.endswith('.h5'):
    #                 self.add_file(file_path)
    #         event.acceptProposedAction()

    def itemDoubleClicked(self, item, column):
        """Handle item double click event."""
        index = self.file_tree.indexOfTopLevelItem(item)
        if index == -1:
            return
        # set the expanded state to avoid the default behavior of expanding/collapsing
        # the item when double-clicked
        item.setExpanded(not item.isExpanded())
        # check if the item is in the group
        if item in self.item_group:
            indices = [self.file_tree.indexOfTopLevelItem(i) for i in self.item_group]
            # emit a signal with the list of files in the group
            self.sigGroupDoubleClicked.emit([self.files[i] for i in indices],self.item_group)
        else:
            self.sigItemDoubleClicked.emit(self.files[index],item)

    def remove_item(self, item):
        """Remove the item from the tree."""
        index = self.file_tree.indexOfTopLevelItem(item)
        if index == -1:
            return
        # check if the item is in the group
        if item in self.item_group:
            # if the item is in the group, ungroup it
            self.ungroup_selected_items()
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

    def group_selected_items(self):
        """Group the selected items together."""
        self.item_group = self.file_tree.selectedItems()
        # set the font of the selected items to bold
        for item in self.item_group:
            item.setFont(0, QFont("Arial", weight=QFont.Weight.Bold))
        # emit the sigGroupDoubleClicked signal with the list of files in the group
        self.itemDoubleClicked(self.item_group[0], 0)  # Use the first item as the representative

    def ungroup_selected_items(self):
        """Ungroup the selected items."""
        # set the font of the selected items to normal
        for item in self.item_group:
            item.setFont(0, QFont("Arial", weight=QFont.Weight.Normal))
        # clear the item group
        self.item_group = []

    def customMenuEvent(self, pos):
        """Handle the custom context menu event."""
        # determine the item at the position
        item = self.file_tree.itemAt(pos)
        if item is None:    
            return
        # check if the item is a top-level item
        if item.parent() is not None:
            return
        
        # check if several items are selected
        selected_items = self.file_tree.selectedItems()
        if len(selected_items) > 1:
            # create a context menu for the group of items
            menu = self._mkGroupMenu(selected_items)
        else:
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
            if item in self.item_group:
                # if the item is in the group, add an action to ungroup it
                ungroup_action = menu.addAction("Ungroup")
                ungroup_action.setToolTip("Ungroup the selected items")
                ungroup_action.triggered.connect(self.ungroup_selected_items)
        # elif level == 'child':
        #     menu = QMenu(self)
        #     # add an action to request normalization the data
        #     norm_action = menu.addAction("Normalize")
        #     norm_action.triggered.connect(lambda: self.request_auxiliary_normalization(item))
        #     # add an action to remove the auxiliary item
        #     remove_action = menu.addAction("Remove Auxiliary Data")
        #     remove_action.triggered.connect(lambda: item.parent().removeChild(item))
        return menu

    def _mkGroupMenu(self,selected_items):
        """Create a context menu for a group of selected items."""
        menu = QMenu(self)
        # add an action to group the selected items
        group_action = menu.addAction("Group")
        group_action.setToolTip("Group the selected files together")
        group_action.triggered.connect(self.group_selected_items)
        # add an action to ungroup the selected items if any are grouped
        if any(item in self.item_group for item in selected_items):
            ungroup_action = menu.addAction("Ungroup")
            ungroup_action.setToolTip("Ungroup the selected items")
            ungroup_action.triggered.connect(self.ungroup_selected_items)
        return menu

class CIFTreeWidget(QWidget):
    sigItemAdded = QtCore.pyqtSignal(str)
    sigItemChecked = QtCore.pyqtSignal(int, bool)
    sigItemDoubleClicked = QtCore.pyqtSignal(int, str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.files = []  # List to store CIF file paths
        # Create a layout
        layout = QVBoxLayout(self)
        # Create a file tree view
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(['CIF file name'])
        self.file_tree.setSortingEnabled(False)
        self.file_tree.itemChanged.connect(self.itemChecked)
        self.file_tree.itemDoubleClicked.connect(self.itemDoubleClicked)
        layout.addWidget(self.file_tree)

        self.setAcceptDrops(True)

    def add_file(self, file_path):
        """Add a CIF file to the tree widget."""
        file_path = os.path.abspath(file_path)
        if not file_path.endswith('.cif'):
            return
        file_name = os.path.basename(file_path)
        # check if the file is already in the tree
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item.text(0) == file_name:
                # If the file is already in the tree
                return
        # Validate the CIF file
        if not validate_cif(file_path):
            QMessageBox.critical(self.parent, "Invalid CIF", f"The file {file_name} is not recognized as a valid CIF file.")
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

    def itemDoubleClicked(self, item, column):
        """Handle item double click event."""
        index = self.file_tree.indexOfTopLevelItem(item)
        if index == -1:
            return
        self.sigItemDoubleClicked.emit(index,item.text(0))



if __name__ == "__main__":
    pass