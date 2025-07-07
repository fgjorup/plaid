# -*- coding: utf-8 -*-
"""
plaid - Plot Azimuthally Integrated Data
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides dialogs classes to select and manage HDF5 files and their content.

"""
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QDialog, QPushButton
from PyQt6 import QtCore
import pyqtgraph as pg
import h5py as h5

class H5Dialog(QDialog):
    """A dialog to select the content of an HDF5 file."""
    def __init__(self, parent=None, file_path=None):
        super().__init__(parent)
        self.selected_items = None
        self.file_path = file_path
        self.setWindowTitle("Select HDF5 Content")
        self.setLayout(QVBoxLayout())
        
        # add a file tree to the dialog
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(['Content', 'Shape'])
        self.file_tree.setSortingEnabled(False)
        self.layout().addWidget(self.file_tree)
        self.file_tree.itemDoubleClicked.connect(self.item_double_clicked)
        self._populate_tree(file_path)
        self.file_tree.header().setSectionResizeMode(1,self.file_tree.header().ResizeMode.Fixed)
        self.file_tree.header().setStretchLastSection(False)

        # handle resizing events, such that the first section expands during resizing
        # and the last section is only resized when the user resizes the section
        self.file_tree.header().geometriesChanged.connect(self._resize_first_section)
        self.file_tree.header().sectionResized.connect(self._resize_last_section)

        # add a selected tree to the dialog
        self.selected_tree = QTreeWidget()
        self.selected_tree.setHeaderLabels(['Alias', 'Path', 'Shape'])
        self.selected_tree.setSortingEnabled(False)
        self.layout().addWidget(self.selected_tree)
        self.selected_tree.itemDoubleClicked.connect(self.edit_alias)

        # add a horizontal layout for the accept/cancel buttons
        button_layout = QHBoxLayout()
        self.layout().addLayout(button_layout)
        button_layout.addStretch(1)  # Add stretchable space to the left of the buttons

        # add a button to accept the dialog and emit the selected items
        # for loading the selected datasets
        self.accept_button = QPushButton("Accept")
        self.accept_button.setEnabled(False)  # Initially disabled until items are selected
        self.accept_button.clicked.connect(self.selection_finished)
        button_layout.addWidget(self.accept_button)

        # add a button to cancel the dialog
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.keyPressEvent = self.keyPressEventHandler



    def item_double_clicked(self, item, column):
        """Handle item double click event."""
        # if the item is a 1D dataset, add it to the selected tree
        if item.childCount() == 0 and item.text(1) != "" and len(item.text(1).split('×')) == 1:
            alias, shape = item.text(0) , item.text(1)
            if alias == "data" or alias == "value":
                alias = item.parent().text(0)  # Use the parent name as alias if it's a data or value item
            # get the full path of the item
            full_path = self._get_path(item)
            # check if the item is already in the selected tree
            for i in range(self.selected_tree.topLevelItemCount()):
                selected_item = self.selected_tree.topLevelItem(i)
                if selected_item.text(1) == full_path:
                    # If the item is already in the selected tree, skip adding it
                    return
            # Create a new tree item for the selected item
            selected_item = QTreeWidgetItem([alias, full_path, shape])
            self.selected_tree.addTopLevelItem(selected_item)
            # Enable the accept button if there are items in the selected tree
            if self.selected_tree.topLevelItemCount() > 0:
                self.accept_button.setEnabled(True)

    def edit_alias(self, item,column):
        """Edit the alias of the selected item."""
        #if column != 0:  # Only allow editing the alias column
        #    return
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)  # Make the item editable
        self.selected_tree.editItem(item, 0)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)  # Make the item non-editable again

            
        
        #print(f"Item double clicked: {item.text(0)}")
        #index = self.file_tree.indexOfTopLevelItem(item)
        #if index == -1:
        #    return
        # Emit the signal with the selected item
        # self.accept()
        # self.selected_item = item.text(0)
        # self.selected_shape = item.text(1)
        # self.close()

    def keyPressEventHandler(self, event):
        """Handle key press events."""
        if event.key() == QtCore.Qt.Key.Key_Return:
            if self.selected_tree.topLevelItemCount() > 0:
                """Handle the return key press event."""
                # Emit the signal with the selected items
                self.selection_finished()
        elif event.key() == QtCore.Qt.Key.Key_Escape:
            """Handle the escape key press event."""
            # Close the dialog without accepting
            self.reject()
        elif event.key() == QtCore.Qt.Key.Key_Delete:
            """Handle the delete key press event."""
            # check if the selected tree is focused
            if self.selected_tree.hasFocus():
                selected_items = self.selected_tree.selectedItems()
                if selected_items:
                    for item in selected_items:
                        index = self.selected_tree.indexOfTopLevelItem(item)
                        if index != -1:
                            self.selected_tree.takeTopLevelItem(index)
                    # Disable the accept button if there are no items in the selected tree
                    if self.selected_tree.topLevelItemCount() == 0:
                        self.accept_button.setEnabled(False)

    def selection_finished(self):
        """Handle the selection finished event."""
        # Emit the signal with the selected items
        selected_items = []
        for i in range(self.selected_tree.topLevelItemCount()):
            item = self.selected_tree.topLevelItem(i)
            selected_items.append((item.text(0), item.text(1), item.text(2)))
        if selected_items:
            self.selected_items = selected_items
        else:
            self.selected_items = None
        self.accept()

    def _populate_tree(self, file_path):
        """Populate the tree with the content of the HDF5 file."""
        with h5.File(file_path, 'r') as f:
            for key in f.keys():
                shape = f[key].shape if hasattr(f[key], 'shape') and len(f[key].shape) else ""
                item = QTreeWidgetItem([key, self._shape_to_str(shape)])
                self.file_tree.addTopLevelItem(item)
                has_child_with_shape = self._populate_item(item, f[key])
                #if not has_child_with_shape:
                    # If no child has a shape, set the item to a lighter color
                    # item.setForeground(0, pg.mkColor("#AAAAAA"))

    def _populate_item(self, parent_item, group):
        """Recursively populate the tree with the content of a group."""
        has_child_with_shape = False
        for key in group.keys():
            try:
                shape = group[key].shape if hasattr(group[key], 'shape') and len(group[key].shape) else ""
                item = QTreeWidgetItem([key, self._shape_to_str(shape)])
                parent_item.addChild(item)
                if isinstance(group[key], h5.Group):
                    _has_child_with_shape = self._populate_item(item, group[key])
                    has_child_with_shape = has_child_with_shape or _has_child_with_shape
                elif isinstance(group[key], h5.Dataset):
                    if shape:
                        has_child_with_shape = True
                    else:
                        item.setForeground(0, pg.mkColor("#AAAAAA"))
                if not has_child_with_shape:
                    # If no child has a shape, set the item to a lighter color
                    item.setForeground(0, pg.mkColor("#AAAAAA"))
            except KeyError:
                item = QTreeWidgetItem([key, str("")])
                parent_item.addChild(item)
                item.setForeground(0, pg.mkColor("#AA0000"))  # Set to red if key is not found
        if not has_child_with_shape:
            # If no child has a shape, set the parent item to a lighter color
            parent_item.setForeground(0, pg.mkColor("#AAAAAA"))
        return has_child_with_shape

    def _get_path(self, item):
        """Get the full path of the item."""
        path = item.text(0)
        parent = item.parent()
        while parent is not None:
            path = parent.text(0) + '/' + path
            parent = parent.parent()
        return path

    def _resize_first_section(self):
        """Resize the first section of the tree header to span the available width."""
        new_size = self.file_tree.size().width()-self.file_tree.header().sectionSize(1) -3
        self.file_tree.header().resizeSection(0, new_size)  # 

    def _resize_last_section(self, logicalIndex, oldSize, newSize):
        """Resize the last section of the tree header."""
        new_size = self.file_tree.size().width()-(newSize+3)
        if new_size != self.file_tree.header().sectionSize(1):
            # disconnect the signal to avoid recursion
            self.file_tree.header().sectionResized.disconnect(self._resize_last_section)
            self.file_tree.header().resizeSection(1, new_size)
            # reconnect the signal
            self.file_tree.header().sectionResized.connect(self._resize_last_section)
    
    def _shape_to_str(self, shape):
        """Convert a shape tuple to a string."""
        if isinstance(shape, tuple):
            return ' × '.join([str(s) for s in shape])
        return str(shape)
    

if __name__ == "__main__":
    pass