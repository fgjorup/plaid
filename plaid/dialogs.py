# -*- coding: utf-8 -*-
"""
plaid - Plot Azimuthally Integrated Data
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides dialogs classes to select and manage HDF5 files and their content.

"""
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QDialog,
                             QPushButton, QLineEdit, QCheckBox, QRadioButton, QButtonGroup, 
                             QSpinBox, QLabel, QGroupBox)
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6 import QtCore
import pyqtgraph as pg
import h5py as h5

class H5Dialog(QDialog):
    """
    A custom dialog to select the content of an HDF5 file, using a tree view
    for browsing the file structure and a second tree for selected items.
    The dialog allows users to double-click items to select them, edit aliases,
    and remove them from the selection.  

    Use H5Dialog(file_path) to create an instance of the dialog.
    The dialog will populate the file tree with the content of the HDF5 file.  
    
    Use open() to display the dialog as a modal dialog. The selected items are 
    stored in self.selected_items as a list of tuples (alias, path, shape) when 
    the dialog is accepted. If the dialog is rejected, self.selected_items will 
    be None.  

    Use the `finished` signal to connect to a slot that handles the 
    selected items and call `get_selected_items()` to retrieve a list of tuples
    (alias, path, shape) for the selected items, where alias is the user-editable
    name for the item, path is the full path to the item in the HDF5 file, and 
    shape is the shape of the item as a string.
    If no items are selected, `get_selected_items()` will return None.

    The dialog supports different modes:
    - 'any': Allows selection of any dataset, including 1D, 2D, and higher-dimensional datasets.
    - '1d': Only allows selection of 1D datasets.
    - '2d': Only allows selection of 2D datasets.
    - '1d_2d_pair': Allows selection of one 1D dataset and one 2D dataset.
    The mode can be set using the `open_1d()`, `open_2d()`, `open_1d_2d_pair()`, or `open()` methods.

    """
    def __init__(self, parent=None, file_path=None, mode='any'):
        super().__init__(parent)
        self.selected_items = None
        self.file_path = file_path
        self.mode = mode
        self.setWindowTitle("Select HDF5 Content")
        self.setLayout(QVBoxLayout())
        
        # add a file tree to the dialog
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(['Content', 'Shape'])
        self.file_tree.setSortingEnabled(False)
        self.layout().addWidget(self.file_tree,2)
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
        self.layout().addWidget(self.selected_tree, 1)
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

        self.resize(350, 500)  # Set a default size for the dialog

    def item_double_clicked(self, item, column):
        """
        Handle item double click event.
        Adds datasets to the selected tree if they match the selection mode.
        Prevents duplicates.
        Modes:
        - 'any': Allows any dataset.
        - '1d': Only allows 1D datasets.
        - '2d': Only allows 2D datasets.
        - '1d_2d_pair': Allows one 1D dataset and one 2D dataset.
        """
        # determine if the item is a dataset or a group
        if item.childCount() == 0 and item.text(1) != "":
            if self.mode == '1d' and not self._get_item_dim(item) == 1:
                # If only 1D datasets are allowed, skip items with more than one dimension
                return
            elif self.mode == '2d' and not self._get_item_dim(item) == 2:
                # If only 2D datasets are allowed, skip items with more than two dimensions
                return
            elif self.mode == '1d_2d_pair':
                if not self._get_item_dim(item) == 1 and not self._get_item_dim(item) == 2:
                    # If only 1D and 2D datasets are allowed, skip items with more than two dimensions
                    return
                # If 1D_2D pair mode is active, make sure there is only one 1D dataset and one 2D dataset
                # by removing any existing items with the same dimension as the clicked item
                for i in range(self.selected_tree.topLevelItemCount()):
                    selected_item = self.selected_tree.topLevelItem(i)
                    if self._get_item_dim(selected_item) == self._get_item_dim(item):
                        self.selected_tree.takeTopLevelItem(i)
                        break
            elif self.mode == 'any':
                # If any dataset is allowed, proceed
                pass
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
            if self.mode == '1d_2d_pair':
                self.accept_button.setToolTip("Select one 1D dataset and one 2D dataset")
                if self.selected_tree.topLevelItemCount() == 2:
                    # If in 1D_2D pair mode, enable the accept button only if there are exactly two items
                    self.accept_button.setEnabled(True)
            elif self.selected_tree.topLevelItemCount() > 0 and self.mode != '1d_2d_pair':
                self.accept_button.setEnabled(True)

    def edit_alias(self, item,column):
        """
        Edit the alias of the selected item.  
        Called when an item in the selected tree is double-clicked.
        The alias is the first column of the selected tree.
        The item is made editable, and the user can change the alias."""
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)  # Make the item editable
        self.selected_tree.editItem(item, 0)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)  # Make the item non-editable again

    def get_file_path(self):
        """Get the file path of the HDF5 file."""
        return self.file_path

    def get_selected_items(self):
        """
        Get the selected items from the dialog.
        Return a list of tuples (alias, path, shape) for the selected items
        or None if no items are selected.
        If the dialog is accepted, the selected items are stored in self.selected_items.
        """
        return self.selected_items

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
        """
        Handle the selection finished event.  
        Populate the selected_items attribute with the selected items
        (alias, path, shape) from the selected tree.
        This method is called when the accept button is clicked.
        emits the `finished` signal (inherited from QDialog).
        """
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
        """
        Populate the tree with the content of the HDF5 file as a tree structure
        with two columns: the item name and its shape.
        """
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
        """
        Recursively populate the tree with the content of a group.
        Each item is represented by a QTreeWidgetItem with two columns:
        the item name and its shape.
        If the item has no shape and no children with a shape, it is set to a lighter color.
        If the item throws a KeyError (e.g. dead links), it is set to a red color.
        Returns True if any child has a shape, otherwise False.
        """
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
    
    def _get_item_dim(self, item):
        """Get the dimension of the item."""
        if item.childCount() == 0:
            # If the item is a dataset, return its shape
            shape = item.text(item.columnCount() - 1)
            if shape:
                return len(shape.split('×'))
            else:
                return 0

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
    
    def open(self):
        """Open the dialog as a modal dialog."""
        self.mode = 'any'
        self.setWindowTitle("Select HDF5 Content")
        super().open()

    def open_1d(self):
        """Open the dialog as a modal dialog only permitting 1D datasets."""
        self.mode = '1d'
        # set the window title to indicate that only 1D datasets are allowed
        self.setWindowTitle("Select 1D HDF5 Content")
        super().open()
    
    def open_2d(self):
        """Open the dialog as a modal dialog only permitting 2D datasets."""
        self.mode = '2d'
        # set the window title to indicate that only 2D datasets are allowed
        self.setWindowTitle("Select 2D HDF5 Content")
        super().open()

    def exec_1d_2d_pair(self):
        """Open the dialog as a modal dialog specifically for one 1d dataset and one 2d dataset."""
        self.mode = '1d_2d_pair'
        # set the window title to indicate that only 1D datasets are allowed
        self.setWindowTitle("Select 1D and 2D HDF5 Content")
        return super().exec() == 1 

    # make a regular expression for valid file extensions


class ExportSettingsDialog(QDialog):
    """A dialog to set export settings for exporting patterns from plaid."""
    sigSaveAsDefault = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Settings")
        self.setLayout(QVBoxLayout())

        # Add a restore default button in the upper right corner
        self.restore_default_button = QPushButton("Restore Default")
        self.restore_default_button.setToolTip("Restore the default settings")
        self.restore_default_button.clicked.connect(self.restore_default)
        self.layout().addWidget(self.restore_default_button, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        self._filename()  # Add file name settings
        self._fileformat()  # Add file format settings
        self._dataformat()  # Add data format settings
        
        # get the default settings in case it is necessary to revert
        self._default_settings = self.get_settings()
        # get the current settings in case the user rejects the dialog
        self._previous_settings = self.get_settings()

        layout = QHBoxLayout()
        self.layout().addLayout(layout)

        # add a save as default button
        self.save_button = QPushButton("Save as Default")
        self.save_button.setToolTip("Save the current settings")
        self.save_button.clicked.connect(self.save_as_default)
        layout.addWidget(self.save_button)
        layout.addStretch(1)  # Add stretchable space to the right of the button

        # Add a button to accept the settings
        self.accept_button = QPushButton("Accept")
        self.accept_button.clicked.connect(self.accept)
        # Set the accept button as the default button (activated by pressing Enter)
        self.accept_button.setDefault(True)
        layout.addWidget(self.accept_button)

        # Add a button to cancel the dialog
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)

    def _filename(self):
        """Add a group box for file name settings."""
        # Add a group box for file name settings
        group = QGroupBox("File Name Settings")
        self.layout().addWidget(group)
        group_layout = QVBoxLayout()
        group.setLayout(group_layout)
        
        # extension validator for 1-3 lowercase letters
        validator = QRegularExpressionValidator(QtCore.QRegularExpression(r"^[a-z]{1,3}$"))
        
        # Add a line edit for the file extension
        label = QLabel("File Extension:")
        self.extension_edit = QLineEdit()
        self.extension_edit.setText("xy")
        self.extension_edit.setValidator(validator)
        self.extension_edit.setToolTip(("File extension (1-3 lowercase letters)\n"
                                        "e.g. 'xy', 'dat', 'txt'.\n"
                                        "NB: Does not affect the content of the file,\n"
                                        "only the file name."))
        self.extension_edit.setMaximumWidth(50)  # Set a maximum width for the line edit
        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.extension_edit)
        layout.addStretch(1)  # Add stretchable space to the right of the line edit
        group_layout.addLayout(layout)

        # Add a spinbox for leading zeros
        label = QLabel("Leading Zeros:")
        self.leading_zeros_spinbox = QSpinBox()
        self.leading_zeros_spinbox.setRange(0, 9)
        self.leading_zeros_spinbox.setValue(4) # Default to 4 leading zeros
        self.leading_zeros_spinbox.setToolTip("Number of leading zeros for the exported file names")
        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.leading_zeros_spinbox)
        layout.addStretch(1)  # Add stretchable space to the right of the line edit
        group_layout.addLayout(layout)


    def _fileformat(self):
        """Add a group box for file format settings."""
        # Add a group box for file format settings
        group = QGroupBox("File Format Settings")
        self.layout().addWidget(group)
        group_layout = QVBoxLayout()
        group.setLayout(group_layout)

        # Add a checkbox for header inclusion
        self.header_checkbox = QCheckBox("Include Header")
        self.header_checkbox.setChecked(True)  # Default to including header
        self.header_checkbox.setToolTip("Include header in the exported file")
        group_layout.addWidget(self.header_checkbox)

        # Add a checkbox for scientific string formatting
        self.scientific_checkbox = QCheckBox("Scientific notation")
        self.scientific_checkbox.setChecked(False)  # Default to not using scientific notation
        self.scientific_checkbox.setToolTip("Use scientific notation for numbers")
        group_layout.addWidget(self.scientific_checkbox)

        # Add radio buttons for delimiter selection
        self.delimiter_radio_group = QButtonGroup()
        self.space_radio = QRadioButton("Space")
        self.space_radio.setChecked(True)  # Default to space delimiter
        self.space_radio.setToolTip("Use space as delimiter")
        self.tab_radio = QRadioButton("Tab")
        self.tab_radio.setToolTip("Use tab as delimiter")
        self.delimiter_radio_group.addButton(self.space_radio)
        self.delimiter_radio_group.addButton(self.tab_radio)
        group_layout.addWidget(self.space_radio)
        group_layout.addWidget(self.tab_radio)

    def _dataformat(self):
        """Add a group box for data format settings."""
        # Add a group box for data format settings
        group = QGroupBox("Data Format Settings")
        self.layout().addWidget(group)
        group_layout = QVBoxLayout()
        group.setLayout(group_layout)



        # Add a checkbox for I0 normalization
        self.I0_checkbox = QCheckBox("I0 Normalized")
        self.I0_checkbox.setToolTip("Normalize by I0 (if available)")
        group_layout.addWidget(self.I0_checkbox)

        # Add radio buttons for Q/2theta selection
        self.tth_Q_radio_group = QButtonGroup()
        self.native_radio = QRadioButton("Native")
        self.native_radio.setToolTip("Export data in the format native to the original file (2θ or Q)")
        self.native_radio.setChecked(True) # Default to native format
        self.tth_radio = QRadioButton("2θ")
        # self.tth_radio.setChecked(True)  # Default to 2theta
        self.tth_radio.setToolTip("Export data in 2θ")
        self.Q_radio = QRadioButton("Q")
        self.Q_radio.setToolTip("Export data in Q")
        self.tth_Q_radio_group.addButton(self.native_radio)
        self.tth_Q_radio_group.addButton(self.tth_radio)
        self.tth_Q_radio_group.addButton(self.Q_radio)
        group_layout.addWidget(self.native_radio)
        group_layout.addWidget(self.tth_radio)
        group_layout.addWidget(self.Q_radio)

    def get_settings(self):
        """
        Get the current settings as a dictionary.
        
        extension_edit: str  
        leading_zeros_spinbox: int  
        header_checkbox: bool  
        scientific_checkbox: bool  
        space_radio: bool  
        tab_radio: bool  
        I0_checkbox: bool  
        native_radio: bool  
        tth_radio: bool  
        Q_radio: bool  
        """
        settings = {}
        for attr in self.__dict__:
            widget = getattr(self, attr)
            if isinstance(widget, QLineEdit):
                settings[attr] = widget.text()
            elif isinstance(widget, QSpinBox):
                settings[attr] = widget.value()
            elif isinstance(widget, QCheckBox):
                settings[attr] = widget.isChecked()
            elif isinstance(widget, QRadioButton):
                settings[attr] = widget.isChecked()
        return settings
    
    def set_settings(self, settings):
        """Set the settings from a dictionary."""
        for key, value in settings.items():
            if hasattr(self, key):
                widget = getattr(self, key)
                if isinstance(widget, QLineEdit):
                    widget.setText(value)
                elif isinstance(widget, QSpinBox):
                    widget.setValue(value)
                elif isinstance(widget, (QCheckBox, QRadioButton)):
                    if isinstance(value, str):
                        # If the value is a string, convert it to boolean
                        value = value.lower() in ['true', '1', 'yes']
                    widget.setChecked(value)
        self._previous_settings = self.get_settings()
            
    def print_settings(self):
        """Print the current settings."""
        settings = self.get_settings()
        for key, value in settings.items():
            print(f"{key}: {value}")

    def save_as_default(self):
        """Emit a signal to save the current settings as default."""
        settings = self.get_settings()
        self.sigSaveAsDefault.emit(settings)
        self.accept()

    def restore_default(self):
        """Restore the default settings."""
        self.set_settings(self._default_settings)

    def accept(self):
        """Override the accept method to keep the changes."""
        self._previous_settings = self.get_settings()
        super().accept()

    def reject(self):
        """Override the reject method to discard the changes."""
        self.set_settings(self._previous_settings)
        super().reject()


if __name__ == "__main__":
    pass
