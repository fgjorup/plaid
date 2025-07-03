import sys
import os
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QTreeWidget, QTreeWidgetItem, QDockWidget, QInputDialog, QDialog, QPushButton, QSizePolicy, QFileDialog, QMenu, QMessageBox
from PyQt6.QtGui import QAction, QIcon
from PyQt6 import QtCore
import pyqtgraph as pg
import h5py as h5
import Dans_Diffraction as dans
import resources.resources

# TODO/IDEAS

# - Update patterns when a new file is loaded
# - Add a button to save the average pattern
# - Add a button to save the selected pattern(s)
# - Add a button to convert between 2theta and q
# - Add Open file(s) button to load files from the file system
# - Add a Load CIF button to load CIF files from the file system
# - Add an option for loading and plotting meta
# - Add a View menu with options to toggle the visibility of the file tree and CIF tree
# - Add a Help menu with options to show the documentation and the about dialog
# - Make a more robust file loading mechanism that can handle different file formats and 
#   structures, perhaps as a "data class"

# - properly remove data from all plots when itemRemoved from the file tree

# - add auxilary tree item in the file tree
# - add a button/function to load aux data, including a way to relate the diffraction data
#   to the aux data. Perhaps as a context menu on the file tree items
# - handle auxiliary data drag drop
# - add "add I0" to filetree context 

# - find a way to avoid overwriting aux data and I0 data when loading new files
#   perhaps with a seperate class for the aux data and I0 data, rather than
#   the azint class

def load_xrd1d(fname):
    """Load XRD 1D data from an HDF5 file."""
    is_q = False
    with h5.File(fname, 'r') as f:
        if 'entry/data1d' in f:
            gr = f['entry/data1d']
        elif 'I' in f:
            gr = f

        if '2th' in gr:
            x = gr['2th'][:]
        elif 'q' in gr:
            x = gr['q'][:]
            is_q = True
        I = gr['I'][:]
    return x, I, is_q

colors = [
        '#AAAA00',  # Yellow
        '#AA00AA',  # Magenta
        '#00AAAA',  # Cyan
        '#AA0000',  # Red
        '#00AA00',  # Green
        "#0066FF",  # Blue
        '#AAAAAA',  # Light Gray
        ]



def validate_cif(cif_file):
    """Validate the CIF file."""
    return dans.functions_crystallography.cif_check(dans.functions_crystallography.readcif(cif_file))

def q_to_tth(q, E):
    """Convert q to 2theta."""
    # Convert 2theta to radians
    wavelength = 12.398 / E
    tth = 2 * np.degrees(np.arcsin(q * wavelength / (4 * np.pi)))
    return tth

def tth_to_q(tth, E):
    """Convert 2theta to q."""
    # Convert 2theta to radians
    wavelength = 12.398 / E
    q = (4 * np.pi / wavelength) * np.sin(np.radians(tth) / 2)
    return q

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
    
class PColorMeshWidget(QWidget):
    # NOT USEFULL, TOO SLOW
    def __init__(self, x, y, z, parent=None):
        super().__init__(parent)

        # Create a layout
        layout = QHBoxLayout(self)

        # Create a pyqtgraph PlotWidget
        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget)

        # Create a pColorMesh plot
        # self.plot = pg.ImageItem()
        self.plot = pg.PColorMeshItem()
        self.plot_widget.addItem(self.plot)

        # create a hidden image item for the histogram
        # as a workaround for the histogram widget
        self.hidden_image = pg.ImageItem()
        self.hidden_image.setColorMap(self.plot.cmap)


        # create a histogram widget
        self.histogram = pg.HistogramLUTWidget(image=self.hidden_image)
        self.histogram.item.lut
        # self.histogram.setImageItem(self.hidden_image)
        self.histogram.item.sigLookupTableChanged.connect(self.updateColormap)
        self.histogram.item.sigLevelsChanged.connect(self.updateLevels)
        self.histogram.item.gradient.loadPreset(self.plot.cmap.name)
        layout.addWidget(self.histogram)


        # Set the data
        self.set_data(x, y, z)

    def set_data(self, x, y, z):
        # Ensure the data is valid
        if len(x)-1 != z.shape[1] or len(y)-1 != z.shape[0]:
            raise ValueError("Dimensions of x, y, and z do not match.")
        
        if x.ndim == 1 or y.ndim == 1:
            x, y = np.meshgrid(x, y)

        # Set the image data

        self.plot.setData(x, y, z)
        self.hidden_image.setImage(z.T)


        # Set axis scales
        self.plot_widget.setLimits(xMin=np.min(x), xMax=np.max(x), yMin=np.min(y), yMax=np.max(y))
        self.plot_widget.getViewBox().setAspectLocked(False)
        self.plot_widget.getViewBox().setRange(xRange=(np.min(x), np.max(x)), yRange=(np.min(y), np.max(y)))

        #self.histogram.setImageItem(self.plot)

    def updateColormap(self,lut):
        """Update the colormap of the pcolormesh"""
        cmap = pg.ColorMap(None,lut.getLookupTable(n=256))
        self.plot.setColorMap(cmap)

    def updateLevels(self, lut):
        """Update the levels for the histogram."""
        self.plot.setLevels(lut.getLevels())


class HeatmapWidget(QWidget):
    sigHLineMoved = QtCore.pyqtSignal(int,int)
    sigXRangeChanged = QtCore.pyqtSignal(object)
    #sigHLineAdded = QtCore.pyqtSignal(int)
    sigHLineRemoved = QtCore.pyqtSignal(int)
    sigImageDoubleClicked = QtCore.pyqtSignal(object)
    sigImageHovered = QtCore.pyqtSignal(int,int)

    def __init__(self, parent=None):
        super().__init__(parent)


        # Initialize variables
        self.x = None
        self.n = None
        self.h_lines = []
        self.use_log_scale = False  # Flag to use logarithmic scale for the heatmap
        # Create a layout
        layout = QHBoxLayout(self)

        # Create a pyqtgraph PlotWidget
        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget,1)

        # Create a image item for the heatmap
        self.image_item = pg.ImageItem()
        self.plot_widget.addItem(self.image_item)
        self.plot_widget.setLimits(minXRange=3)

        self.image_item.hoverEvent = self.hover_event

        self.x_axis = self.plot_widget.getPlotItem().getAxis('bottom')
        self.y_axis = self.plot_widget.getPlotItem().getAxis('left')

        self.set_xlabel("radial axis")
        self.set_ylabel("frame number #")

        # update the ticks whenenver the x-axis is changed
        self.plot_widget.getPlotItem().sigXRangeChanged.connect(self._set_xticks)

        # Create a histogram widget
        self.histogram = pg.HistogramLUTWidget()
        self.histogram.setImageItem(self.image_item)
        self.histogram.item.gradient.loadPreset('viridis')
        layout.addWidget(self.histogram,0)

        # Add a horizontal line to the plot

        # self.h_line = pg.InfiniteLine(angle=0, movable=True)
        # self.h_line.sigPositionChanged.connect(self.h_line_moved)
        # self.plot_widget.addItem(self.h_line)
        

        self.plot_widget.getPlotItem().mouseDoubleClickEvent = self.image_double_clicked
    def image_double_clicked(self, event):
        """Handle the double click event on the image item."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.n is not None:
            pos = self.plot_widget.getPlotItem().vb.mapSceneToView(event.pos())
            x = pos.x()
            y = pos.y()
            self.sigImageDoubleClicked.emit((x, y))


    def addHLine(self, pos=0):
        """Add a horizontal line to the plot."""
        pen = pg.mkPen(color=colors[len(self.h_lines) % len(colors)], width=1)
        hoverpen = pg.mkPen(color=colors[len(self.h_lines) % len(colors)], width=3)
        h_line = pg.InfiniteLine(angle=0, movable=True, pen=pen,hoverPen=hoverpen)
        h_line.setPos(pos+.5)
        h_line.sigPositionChanged.connect(self.h_line_moved)
        h_line.sigClicked.connect(self.h_line_clicked)
        self.plot_widget.addItem(h_line)
        self.h_lines.append(h_line)

        # set the bounds of the horizontal line
        h_line.setBounds([-1, self.n])
        # emit the signal for the new horizontal line
        #self.sigHLineAdded.emit(len(self.h_lines) - 1)

    def removeHLine(self, index=-1):
        """Remove a horizontal line from the plot."""
        h_line = self.h_lines.pop(index)
        self.plot_widget.removeItem(h_line)
        # emit the signal for the removed horizontal line
        self.sigHLineRemoved.emit(index)

    def set_data(self, x,z,y=None):
        """Set the data for the heatmap."""
        self.n = z.shape[1]
        self.x = x
        if self.use_log_scale:
            z = np.log10(z,out=np.zeros_like(z), where=(z>0))  # Apply log scale to the data
        self.image_item.setImage(z)
        self._set_xticks(x)

        # update the limits of the plot
        # self.plot_widget.setLimits(xMin=-len(x)*0.05, xMax=len(x)*1.05, yMin=-len(y)*0.05, yMax=len(y)*1.05)

        self.plot_widget.setLimits(xMin=-len(x)*.1, xMax=len(x)*1.1, yMin=-self.n*0.02, yMax=self.n*1.02)
        # self.plot_widget.setLimits(xMin=-len(x)*.025, xMax=len(x)+2, yMin=-2, yMax=self.n+2)

        # update the horizontal lines bounds
        for h_line in self.h_lines:
            h_line.setBounds([-1, self.n])

    def _set_xticks(self,view=None,vrange=(None,None)):
        """Set the x-axis ticks."""
        if self.x is None:
            return
        x = self.x
        vrange = [int(np.clip(v, 1, len(x)-1)) if v is not None else v for v in vrange]

        s_ = np.s_[vrange[0]-1:vrange[1]+1] if vrange[0] is not None and vrange[1] is not None else slice(None)
        x_min = np.min(x[s_])
        x_max = np.max(x[s_])
        step = (x_max - x_min)/10
        if step>5:
            step = np.round(step*.2, 0)/.2
        elif step > 1:
            step = np.round(step*.5, 0)/.5
        elif step > 0.5:
            step = np.round(step*2, 0)/2
        elif step > 0.1:
            step = np.round(step*5, 0)/5
        elif step > 0.05:
            step = np.round(step*20, 0)/20
        elif step > 0.01:
            step = np.round(step*50, 0)/50

        step = max(step,np.round(np.mean(np.diff(x)),4))
       
        x_ = np.arange(0, x_max+step, step)
        x_ = x_[x_ >= x_min-step]
        x_ = x_[x_ <= x_max+step]
        if step >= 1:
            self.x_axis.setTicks([[(np.argmin(np.abs(x - xi))+0.5, f"{xi:.0f}") for xi in x_]])
        elif step >= 0.1:
            self.x_axis.setTicks([[(np.argmin(np.abs(x - xi))+0.5, f"{xi:.1f}") for xi in x_]])
        elif step >= 0.01:
            self.x_axis.setTicks([[(np.argmin(np.abs(x - xi))+0.5, f"{xi:.2f}") for xi in x_]])
        else:
            self.x_axis.setTicks([[(np.argmin(np.abs(x - xi))+0.5, f"{xi:.3f}") for xi in x_]])

        # emit the signal for x range change in the axis units (2theta or q)
        self.sigXRangeChanged.emit((x_min, x_max))

    def set_xlabel(self, label):
        """Set the x-axis label."""
        self.x_axis.setLabel(label)

    def set_ylabel(self, label):
        """Set the y-axis label."""
        self.y_axis.setLabel(label)

    def set_xrange(self, x_range):
        """Set the x-axis range."""
        if self.x is None:
            return
        x_min, x_max = x_range
        # convert the x_range to indices
        x_min_idx = np.argmin(np.abs(self.x - x_min))
        x_max_idx = np.argmin(np.abs(self.x - x_max))
        # disconnect the signal to avoid recursion
        self.plot_widget.sigXRangeChanged.disconnect(self._set_xticks)
        # set the x-axis range
        self.plot_widget.setXRange(x_min_idx, x_max_idx, padding=0)
        # reconnect the signal
        self.plot_widget.sigXRangeChanged.connect(self._set_xticks)

    def set_h_line_pos(self, index, pos):
        """Set the position of a horizontal line."""
        if index < 0 or index >= len(self.h_lines) or self.n is None:
            return
        # disconnect the signal to avoid recursion
        self.h_lines[index].sigPositionChanged.disconnect(self.h_line_moved)
        # set the position of the horizontal line
        self.h_lines[index].setPos(pos+.5)
        # reconnect the signal
        self.h_lines[index].sigPositionChanged.connect(self.h_line_moved)

    def h_line_moved(self, line):
        """Handle the horizontal line movement."""
        if self.x is None or self.n is None:
            return
        pos = int(np.clip(line.value(), 0, self.n-1))
        # set the position of the horizontal line
        line.setPos(pos+.5)
        # get the index of the horizontal line
        index = self.h_lines.index(line)
        # emit the signal with the position
        self.sigHLineMoved.emit(index, pos)

    def h_line_clicked(self, line, event):
        """Handle the horizontal line click event."""
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            event.accept()  # Accept the event to prevent further processing
            index = self.h_lines.index(line)
            self.removeHLine(index)

    def hover_event(self, event):
        """Handle the hover event on the image item."""
        if not event.isExit():
            # If the mouse is not exiting, print the position
            # This is useful for debugging or displaying information
            # about the hovered position
            pos = event.pos()
            x_idx = int(np.clip(pos.x(), 0, self.x.size-1))  # Ensure x is within bounds
            y_idx = int(np.clip(pos.y(), 0, self.n-1))  # Ensure y is within bounds
            # Emit the signal with the x and y indices
            self.sigImageHovered.emit(x_idx, y_idx)

        else:
            # If the mouse is exiting, you can clear any hover-related information
            #print("Mouse exited the image item.")
            # Optionally, you can hide any hover-related UI elements here
            # For example, if you had a tooltip or a label showing the position,
            # you could hide it here.
            pass

    def clear(self):
        """Clear the heatmap data and horizontal lines."""
        self.image_item.clear()
        self.x = None
        self.n = None
        for h_line in self.h_lines:
            self.plot_widget.removeItem(h_line)
        self.h_lines = []
        self.addHLine()
        
        # self.plot_widget.clear()


class PatternWidget(QWidget):
    sigXRangeChanged = QtCore.pyqtSignal(object)
    sigPatternHovered = QtCore.pyqtSignal(float, float)
    def __init__(self, parent=None):
        super().__init__(parent)

        self.x = None
        self.y = None
        self.pattern_items = []
        self.reference_items = []
        self.reference_hkl = {}

        # Create a layout
        layout = QHBoxLayout(self)

        # Create a pyqtgraph PlotWidget
        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget,1)

        # create a plot item for the average pattern
        self.avg_pattern_item = pg.PlotDataItem(pen='#AAAAAA', name='Average Pattern')
        self.plot_widget.getPlotItem().addItem(self.avg_pattern_item)

        # Add a legend to the plot
        self.legend = self.plot_widget.getPlotItem().addLegend()
        self.legend.addItem(self.avg_pattern_item, 'Average Pattern')
        self.legend.items[0][0].item.setVisible(False)  # Hide the average pattern by default
        # self.legend.addItem(self.pattern_item, 'Pattern')

        # Create a plot item for the pattern
        self.add_pattern()
        #self.pattern_item = pg.PlotDataItem(pen='w', name='Pattern')
        #self.plot_widget.getPlotItem().addItem(self.pattern_item)

        # Add a text item to the plot for displaying hkl
        self.hkl_text_item = pg.TextItem(text='', anchor=(0.5, 0), color='w')
        self.plot_widget.getPlotItem().addItem(self.hkl_text_item)
        self.hkl_text_item.setVisible(False)  # Hide the text item by default

        self.plot_widget.sigXRangeChanged.connect(self.xrange_changed)

        # self.plot_widget.getPlotItem().hoverEvent = self.hover_event
        self.plot_widget.getPlotItem().vb.hoverEvent = self.hover_event

        self.set_xlabel("radial axis")
        self.set_ylabel("intensity")

    def add_pattern(self):
        """Add a new pattern item to the plot."""
        color = colors[len(self.pattern_items) % len(colors)]
        pen = pg.mkPen(color=color, width=1)
        pattern = pg.PlotDataItem(pen=pen, symbol='o',symbolSize=2, symbolPen=pen, symbolBrush=color, name='frame')
        self.plot_widget.getPlotItem().addItem(pattern)
        #self.legend.addItem(pattern, 'Pattern')
        self.pattern_items.append(pattern)

    def remove_pattern(self, index=-1):
        """Remove a pattern item from the plot."""
        pattern = self.pattern_items.pop(index)
        self.plot_widget.getPlotItem().removeItem(pattern)
        #self.legend.removeItem(pattern.name())

    
    def set_data(self, x=None, y=None,index=-1):
        """Set the data for the pattern."""
        if x is None:
            x = self.x
            #x = self.pattern_items[index].getData()[0]  # Get the x data from the pattern item
        if y is None:
            y = self.y
        if x is None or y is None:
            return
        self.pattern_items[index].setData(x, y)
        # update the limits of the plot
        #y_pad = (np.max(y) - np.min(y))*.1
        # self.plot_widget.setLimits(xMin=0, xMax=np.ceil(np.max(x)/10)*10) #, yMin=np.min(y)-y_pad, yMax=np.max(y)+y_pad)
        x_pad = (np.max(x) - np.min(x))*.1
        self.plot_widget.setLimits(xMin=np.min(x)-x_pad, xMax=np.max(x)+x_pad)
        self.x = x
        self.y = y

    def set_pattern_name(self, name=None, index=-1):
        """Set the name of the pattern item."""
        if name is None:
            name = f"frame {index}"
        self.legend.items[index+1][1].setText(name)  # update the legend item text
    
    def add_reference(self, hkl, x, I):
        """Add a reference pattern to the plot."""
        color = colors[::-1][len(self.reference_items) % len(colors)]
        reference_item = pg.PlotDataItem(pen=color,connect='pairs')
        reference_item.setCurveClickable(True)
        reference_item.setZValue(-1)  # Set a lower z-value to draw below the patterns
        reference_item.sigClicked.connect(self.reference_clicked)  # Connect the click signal to a function
        self.plot_widget.getPlotItem().addItem(reference_item)
        self.reference_items.append(reference_item)
        self.reference_hkl[reference_item] = (x,hkl)  # Store the hkl indices for the reference item
        # tth = np.degrees(np.arcsin(lambd/(2*d)))*2
        x = np.repeat(x,2)
        I = np.repeat(I,2)
        I[::2] = 0  # Set the intensity to 0 for the first point of each pair
        if self.y is None:
            scale = 100
        else:
            scale = self.y.max() 
        reference_item.setData(x, I*scale)  # Initialize with test data

    def toggle_reference(self, index, is_checked):
        """Toggle the visibility of a reference pattern."""
        reference_item = self.reference_items[index]
        reference_item.setVisible(is_checked)
        self.hkl_text_item.setVisible(False)  # Hide the text item when toggling reference visibility


    def reference_clicked(self, item, event):
        """Handle the click event on a reference pattern."""
        x_hkls, hkls = self.reference_hkl.get(item, None)
        x,y = event.pos()
        idx = np.argmin(np.abs(x_hkls - x))

        if self.hkl_text_item.isVisible() and self.hkl_text_item.pos()[0] == x_hkls[idx]:
            # If the text item is already showing the same hkl, hide it
            self.hkl_text_item.setVisible(False)
            return
        hkl = ' '.join(hkls[idx].astype(str))  # Convert hkl indices to string
        # get the color of the clicked item
        color = item.opts['pen']
        # Show the hkl indices in the text item
        self.hkl_text_item.setColor(color)
        self.hkl_text_item.setText(f"({hkl})")
        self.hkl_text_item.setPos(x_hkls[idx], 0)
        self.hkl_text_item.setVisible(True)  # Show the text item


    
    # def _set_data(self, x=None, y=None):
    #     """Set the data for the pattern."""
    #     if x is None:
    #         x = self.x
    #     if y is None:
    #         y = self.y
    #     if x is None or y is None:
    #         return
    #     self.pattern_item.setData(x, y)

    #     # update the limits of the plot
    #     y_pad = (np.max(y) - np.min(y))*.1
    #     self.plot_widget.setLimits(xMin=0, xMax=np.ceil(np.max(x)/10)*10, yMin=np.min(y)-y_pad, yMax=np.max(y)+y_pad)
    #     self.x = x
    #     self.y = y

    def set_avg_data(self, y_avg):
        """Set the average data for the pattern."""
        if y_avg is None:
            return
        self.avg_pattern_item.setData(self.x, y_avg)
        self.y_avg = y_avg

    def set_xlabel(self, label):
        """Set the x-axis label."""
        self.plot_widget.getPlotItem().getAxis('bottom').setLabel(label)
    
    def set_ylabel(self, label):
        """Set the y-axis label."""
        self.plot_widget.getPlotItem().getAxis('left').setLabel(label)

    def set_xrange(self, x_range):
        """Set the x-axis range."""
        if self.x is None:
            return
        # disconnect the signal to avoid recursion
        self.plot_widget.sigXRangeChanged.disconnect(self.xrange_changed)
        x_min, x_max = x_range
        self.plot_widget.setXRange(x_min, x_max, padding=0)
        # reconnect the signal
        self.plot_widget.sigXRangeChanged.connect(self.xrange_changed)
        #self.plot_widget.getPlotItem().getAxis('bottom').setRange(x_min, x_max)
    
    def xrange_changed(self,vb, x_range):
        """Handle the x-axis range change."""
        self.sigXRangeChanged.emit(x_range)

    def hover_event(self, event):
        """Handle the hover event on the plot item."""
        if not event.isExit():
            # If the mouse is not exiting, print the position
            # This is useful for debugging or displaying information
            # about the hovered position
            pos = event.pos()
            # Convert the position to the plot item's coordinates
            pos = self.plot_widget.getPlotItem().vb.mapToView(pos)
            x = pos.x()
            y = pos.y()
            # Emit the signal with the x and y coordinates
            self.sigPatternHovered.emit(x, y)

            # print(f"Hovered at x: {x}, y: {y}")
        else:
            # If the mouse is exiting, you can clear any hover-related information
            #print("Mouse exited the plot item.")
            pass
    
    def clear(self):
        """Clear the pattern data"""
        for i in range(len(self.pattern_items)):
            pattern = self.pattern_items.pop(0)
            self.plot_widget.getPlotItem().removeItem(pattern)
        self.add_pattern()  # Add a new pattern item to keep the list non-empty


       
class AuxiliaryPlotWidget(QWidget):
    """A widget to display auxiliary plots."""
    sigVLineMoved = QtCore.pyqtSignal(int, int)  # Signal emitted when a vertical line is moved
    sigAuxHovered = QtCore.pyqtSignal(float, float)  # Signal emitted when the mouse hovers over a vertical line
    def __init__(self, parent=None):
        super().__init__(parent)
        self.v_lines = []
        self.n = None  # Number of data points in the x-axis
        # Create a layout
        layout = QVBoxLayout(self)

        # Create a pyqtgraph PlotWidget
        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget)

        # Set the plot item
        self.plot_item = self.plot_widget.getPlotItem()
        # add a legend to the plot item
        self.plot_item.addLegend()

        # Set the x-axis label
        self.plot_item.getAxis('bottom').setLabel("Frame number #")

        self.plot_widget.getPlotItem().vb.hoverEvent = self.hover_event



    def set_data(self, y, label=None,color=None):
        """Set the data for the auxiliary plot."""
        if y is None:
            return
        if color is None:
            color = colors[len(self.plot_item.items) % len(colors)]
        x = np.arange(len(y))
        self.plot_item.plot(x, y, pen=color, name=label if label else 'Auxiliary Plot')
        self.n = len(y)

        # make sure the vlines are re-added if the plot has been cleared
        for v_line in self.v_lines:
            if v_line in self.plot_item.items:
                continue
            self.plot_item.addItem(v_line)


    def addVLine(self, pos=0):
        """Add a horizontal line to the plot."""
        pen = pg.mkPen(color=colors[len(self.v_lines) % len(colors)], width=1)
        hoverpen = pg.mkPen(color=colors[len(self.v_lines) % len(colors)], width=3)
        v_line = pg.InfiniteLine(angle=90, movable=True, pen=pen,hoverPen=hoverpen)
        v_line.setPos(pos)
        v_line.sigPositionChanged.connect(self.v_line_moved)
        #v_line.sigClicked.connect(self.v_line_clicked)
        self.plot_widget.addItem(v_line)
        self.v_lines.append(v_line)

        # set the bounds of the vertical line
        v_line.setBounds([-1, self.n])

    def remove_v_line(self, index=-1):
        """Remove a vertical line from the plot."""
        if index < 0 or index >= len(self.v_lines):
            return
        v_line = self.v_lines.pop(index)
        self.plot_item.removeItem(v_line)


    def v_line_moved(self, line):
        """Handle the horizontal line movement."""
        if self.n is None:
            return
        pos = int(np.clip(line.value(), 0, self.n-1))
        # set the position of the vertical line
        line.setPos(pos)
        # get the index of the vertical line
        index = self.v_lines.index(line)
        # emit the signal with the position
        self.sigVLineMoved.emit(index, pos)

    def set_v_line_pos(self, index, pos):
        """Set the position of a vertical line."""
        if index < 0 or index >= len(self.v_lines) or  self.n is None:
            return
        v_line = self.v_lines[index]
        pos = int(np.clip(pos, 0, self.n-1))
        # disconnect the signal to avoid recursion
        v_line.sigPositionChanged.disconnect(self.v_line_moved)
        v_line.setPos(pos)
        # reconnect the signal
        v_line.sigPositionChanged.connect(self.v_line_moved)

    def hover_event(self, event):
        """Handle the hover event on the plot item."""
        if not event.isExit():
            # If the mouse is not exiting, print the position
            # This is useful for debugging or displaying information
            # about the hovered position
            pos = event.pos()
            # Convert the position to the plot item's coordinates
            pos = self.plot_widget.getPlotItem().vb.mapToView(pos)
            x = pos.x()
            y = pos.y()
            # Emit the signal with the x and y coordinates
            self.sigAuxHovered.emit(x, y)

            # print(f"Hovered at x: {x}, y: {y}")
        else:
            # If the mouse is exiting, you can clear any hover-related information
            #print("Mouse exited the plot item.")
            pass


    def clear_plot(self):
        """Clear the auxiliary plot."""
        self.plot_item.clear()

    def clear(self):
        """Clear the auxiliary plot and vertical lines."""
        self.clear_plot()
        self.n = None
        for v_line in self.v_lines:
            self.plot_item.removeItem(v_line)
        self.v_lines = []
        self.addVLine()


# class FileTreeWidget(QWidget):
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
                if 'entry/data1d' in f:
                    dset = f['entry/data1d']
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

class Reference():
    """A class to hold reference data."""
    def __init__(self, cif_file,E=35.0,Qmax=6.28):
        self.cif_file = cif_file
        self.E = E  # Energy in keV
        self.Qmax = Qmax  # Maximum Q value in 1/A
        max_twotheta = np.degrees(2 * np.arcsin((Qmax*(12.398/E))/(4*np.pi)))  # Calculate max 2theta from Qmax and energy
        xtl = dans.Crystal(cif_file)
        xtl.Scatter.setup_scatter(max_twotheta=max_twotheta,energy_kev=E,
                                 scattering_type='xray',output=False)

        d, I, reflections = xtl.Scatter.powder(scattering_type='xray',
                                       units='dspace', 
                                       powder_average=True, 
                                       min_overlap=0.02, 
                                       energy_kev=E,)

        self.hkl = reflections[::-1, :3].astype(int)  # Get the hkl indices
        self.d = reflections[::-1, 3]  # Get the d-spacings
        I = reflections[::-1, 4]  # Get the intensities
        self.I = I / np.max(I)  # Normalize the intensities

    def get_reflections(self, Qmax=None, dmin=None):
        """Get the reflections within the specified Qmax or dmin."""
        if Qmax is None and dmin is None:
            Qmax = self.Qmax
        if dmin is None:
            dmin = 2*np.pi/Qmax
        mask = self.d >= dmin
        return self.hkl[mask], self.d[mask], self.I[mask]


class AzintData():
    """A class to hold azimuthal integration data."""

    def __init__(self, fnames=None):
        if isinstance(fnames, str):
            fnames = [fnames]
        self.fnames = fnames
        self.x = None
        self.I = None
        self.y_avg = None
        self.is_q = False
        self.E = None
        self.I0 = None
        #self.aux_data = {} # {alias: np.array}

    def load(self):
        """
        Determine the file type and load the data with the appropriate function.
        The load function should take a file name as input and return the x, I, is_q, and E values.
        If the energy is not available in the file, the load function should return None for E.
        """

        if not all(fname.endswith('.h5') for fname in self.fnames):
            print("File(s) are not HDF5 files.")
            return False
        
        # check the first file to determine the type
        # assume the first file is representative of the others
        with h5.File(self.fnames[0], 'r') as f:
            if 'entry/data1d' in f:
                load_func = self._load_azint_old
            elif 'entry/data' in f:
                load_func = self._load_azint
            elif 'I' in f:
                load_func = self._load_DM_old
            # here one could add an option for a custom load function
            # elif not CUSTOM_LOAD_FUNC is None:
            #     load_func = CUSTOM_LOAD_FUNC
            else:
                print("File type not recognized. Please provide a valid azimuthal integration file.")
                return False

        I = np.array([[],[]])
        for fname in self.fnames:
            x, I_, is_q, E = load_func(fname)
            I = np.append(I, I_, axis=0) if I.size else I_
        #I = np.array(I)
        self.x = x
        self.I = I
        self.is_q = is_q
        self.E = E
        self.y_avg = I.mean(axis=0)
        
        return True

    def user_E_dialog(self):
        """Prompt the user for the energy value if not available in the file."""
        if self.E is None:
            E, ok = QInputDialog.getDouble(None, "Energy Input", "Enter the energy in keV:", value=35.0, min=1.0, max=200.0)
            if ok:
                self.E = E
                return E
        else:
            return self.E
    
    def get_tth(self):
        """Calculate the 2theta values from the energy and radial axis."""
        if not self.is_q:
            # If the data is already in 2theta, return it directly
            return self.x
        if self.E is None:
            self.user_E_dialog()
        if self.E is None:
            print("Energy not set. Cannot calculate 2theta.")
            return None
        tth = q_to_tth(self.x, self.E)
        return tth
    
    def get_q(self):
        """Calculate the q values from the energy and radial axis."""
        if self.is_q:
            return self.x
        if self.E is None:
            self.user_E_dialog()
        if self.E is None:
            print("Energy not set. Cannot calculate q.")
            return None
        q = tth_to_q(self.x, self.E)
        return q
        
    def get_I(self, I0_normalized=True):
        """Get the intensity data. By default, it returns the normalized intensity
                data by dividing by I0 if I0 is set."""
        if self.I is None:
            print("No intensity data loaded.")
            return None
        I = self.I.copy()  # Make a copy of the intensity data
        if self.I0 is not None and I0_normalized:
            if self.I0.shape[0] != I.shape[0]:
                print(f"I0 data shape {self.I0.shape} must match the number of frames {I.shape} in the azimuthal integration data.")
                return None
            # Normalize the intensity data by I0
            I = I / self.I0[:, np.newaxis]
        return I
    
    def set_I0(self, I0):
        """Set the I0 data."""
        if isinstance(I0, np.ndarray):
            self.I0 = I0
        elif isinstance(I0, (list, tuple)):
            self.I0 = np.array(I0)
        else:
            print("I0 data must be a numpy array or a list/tuple.")
            return
        
        # check if the I0 data are close to unity
        # otherwise, normalize it and print a warning
        if self.I0.min() <= 0 or self.I0.max() < 0.5 or self.I0.max() > 2:
            print("Warning: I0 data should be close to unity and >0. Normalizing it.")
            print(f"I0 [{self.I0.min():.2e}, {self.I0.max():.2e}] normalized to [{self.I0.min()/self.I0.max():.2f}, 1.00]")
            self.I0 = self.I0 / np.max(self.I0)
            self.I0[self.I0<=0] = 1  # Set any zero values to 1 to avoid division by zero

        # TEST REMBER TO DELETE THIS
        print("DEBUG! - Delete after test")
        if self.I0.shape[0] == 1066:
            self.I0 = np.append(self.I0, 1)

        if self.I is None:
            # Don't normalize (yet)
            return
        if self.I.shape[0]  != self.I0.shape[0]:
            print(f"I0 data shape {self.I0.shape} must match the number of frames {self.I.shape} in the azimuthal integration data.")
            return

        #self.I = self.I / self.I0[:, np.newaxis]  # Normalize the intensity data by I0
 


    # def set_auxiliary_data(self, aux_data):
    #     """Set auxiliary data"""
    #     if isinstance(aux_data, dict):
    #         self.aux_data = aux_data
    #     elif isinstance(aux_data, (list, tuple)):
    #         for alias, data in aux_data:
    #             self.aux_data[alias] = data
    #     else:
    #         raise ValueError("Auxiliary data must be a dictionary or a list of tuples.")

    def _load_azint(self, fname):
        """Load azimuthal integration data from a nxazint HDF5 file."""
        with h5.File(fname, 'r') as f:
            data_group = f['entry/data']
            x = data_group['radial_axis'][:]
            I = data_group['I'][:]
            is_q = 'q' in data_group['radial_axis'].attrs['long_name'].lower()

            if 'entry/instrument/monochromator/energy' in f:
                E = f['entry/instrument/monochromator/energy'][()]
            elif 'entry/instrument/monochromator/wavelength' in f:
                wavelength = f['entry/instrument/monochromator/wavelength'][()]
                E = 12.398 / wavelength  # Convert wavelength to energy in keV
            else:
                E = None
        return x, I, is_q

    def _load_azint_old(self, fname):
        """Load azimuthal integration data from an old (DanMAX) nxazint HDF5 file."""
        with h5.File(fname, 'r') as f:
            data_group = f['entry/data1d']
            if '2th' in data_group:
                x = data_group['2th'][:]
                is_q = False
            elif 'q' in data_group:
                x = data_group['q'][:]
                is_q = True
            I = data_group['I'][:]
        return x, I, is_q, None

    def _load_DM_old(self, fname):
        """Load azimuthal integration data from an old DanMAX HDF5 file."""
        with h5.File(fname, 'r') as f:
            if '2th' in f:
                x = f['2th'][:]
                is_q = False
            elif 'q' in f:
                x = f['q'][:]
                is_q = True
            I = f['I'][:]
        return x, I, is_q, None
    

class AuxData:
    def __init__(self):
        self.I0 = None

    def set_I0(self, I0):
        """Set I0"""
        if isinstance(I0, (tuple, list)):
            I0 = np.array(I0)

        # check if the I0 data are close to unity
        # otherwise, normalize it and print a warning
        if I0.min() <= 0 or I0.max() < 0.5 or I0.max() > 2:
            print("Warning: I0 data should be close to unity and >0. Normalizing it.")
            print(f"I0 [{I0.min():.2e}, {I0.max():.2e}] normalized to [{I0.min()/I0.max():.2f}, 1.00]")
            I0 = I0 / np.max(I0)
            I0[I0<=0] = 1  # Set any zero values to 1 to avoid division by zero
        self.I0 = I0

    def add_data(self, key, data):
        """Add data to the AuxData instance."""
        if isinstance(data, (list, tuple)):
            data = np.array(data)
        setattr(self, key, data)

    def get_data(self, key):
        """Get data from the AuxData instance."""
        if isinstance(key, (list, tuple)):
            return [self.get_data(k) for k in key]
        if not hasattr(self, key):
            print(f"Key '{key}' not found in AuxData.")
            return None
        return getattr(self, key, None)
    
    def get_dict(self):
        """Get a dictionary representation of the AuxData instance."""
        return {key: value for key, value in self.__dict__.items() if not key.startswith('_')}
    
    def keys(self):
        """Get the keys of the AuxData instance."""
        return [key for key in self.__dict__.keys() if not key.startswith('_')]
    
    def clear(self):
        """Clear all data in the AuxData instance."""
        self.__dict__.clear()
        self.I0 = None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Plot Azimuthally Integrated Data")
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
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, file_tree_dock)

        # Create the CIF tree widget
        self.cif_tree = CIFTreeWidget()
        # create a dock widget for the CIF tree
        cif_tree_dock = QDockWidget("CIF Tree", self)
        cif_tree_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        cif_tree_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        cif_tree_dock.setWidget(self.cif_tree)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, cif_tree_dock)
  
        self.auxiliary_plot = AuxiliaryPlotWidget()
        # create a dock widget for the auxiliary plot
        auxiliary_plot_dock = QDockWidget("Auxiliary Plot", self)
        auxiliary_plot_dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea | QtCore.Qt.DockWidgetArea.RightDockWidgetArea)
        auxiliary_plot_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        auxiliary_plot_dock.setWidget(self.auxiliary_plot)
        
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, auxiliary_plot_dock)

        self.setDockOptions(QMainWindow.DockOption.AnimatedDocks)
 
        self.file_tree.sigItemDoubleClicked.connect(self.load_file)
        self.file_tree.sigItemRemoved.connect(self.remove_file)
        self.file_tree.sigI0DataRequested.connect(self.load_I0_data)
        self.file_tree.sigAuxiliaryDataRequested.connect(self.load_auxiliary_data)

        self.cif_tree.sigItemAdded.connect(self.add_reference)
        self.cif_tree.sigItemChecked.connect(self.toggle_reference)

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
        fname = r"C:\Users\au480461\Postdoc\Scripts\test_files\raw\pxrd_cryo\scan-0100.h5"
        aname = fname.replace("\\raw", "\\process\\azint").replace(".h5", "_pilatus_integrated.h5")
        self.file_tree.add_file(aname)
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
        self.azint_data = AzintData()
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

        self.azint_data = AzintData([file_path])
        if not self.azint_data.load():
            print(f"Failed to load file: {file_path}")
            return
        x = self.azint_data.get_tth() if not self.azint_data.is_q else self.azint_data.get_q()
        I = self.azint_data.get_I()
        y_avg = self.azint_data.y_avg
        is_q = self.azint_data.is_q
        self.is_Q = is_q
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


    def add_reference(self, cif_file, Qmax=None):
        """Add a reference pattern from a CIF file."""
        if self.E is None:
            self.E = self.azint_data.user_E_dialog()
            if self.E is None:
                print("Energy not set. Cannot add reference pattern.")
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
            print("No reflections found in the reference pattern.")
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
        
        target_item = self.file_tree.get_aux_target_name()
        if not target_item in self.aux_data.keys():
            self.aux_data[target_item] = AuxData()
        self.aux_data[target_item].set_I0(I0)
        #self.azint_data.set_I0(I0)

    def add_auxiliary_data(self,is_ok):
        """Add auxiliary data to the azint data instance."""
        if not is_ok:
            return
        aux_data = {}
        target_item = self.file_tree.get_aux_target_name()
        if not target_item in self.aux_data.keys():
            self.aux_data[target_item] = AuxData()
        with h5.File(self.h5dialog.file_path, 'r') as f:
            for [alias,file_path,shape] in self.h5dialog.selected_items:
                aux_data[alias] =  f[file_path][:]
                self.file_tree.add_auxiliary_item(alias,shape)
                self.aux_data[target_item].add_data(alias, f[file_path][:])
        
        #self.azint_data.set_auxiliary_data(aux_data)
        # Update the auxiliary plot with the new data
        self.add_auxiliary_plot(target_item)

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
            print("No auxiliary data available.")
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
            if self.E is None:
                self.E = self.azint_data.user_E_dialog()
                if self.E is None:
                    print("Energy not set. Cannot toggle between q and 2theta.")
                    return
            self.is_Q = not self.is_Q
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

    def show_help_dialog(self):
        """Show the help dialog."""
        help_text = (
            "<h2>Help - Plot Azimuthally Integrated Data</h2>"
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
            "<h2>plaid - Plot Azimuthally Integrated Data</h2>"
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