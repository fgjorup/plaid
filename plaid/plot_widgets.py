# -*- coding: utf-8 -*-
"""
plaid - Plot Azimuthally Integrated Data
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides classes for plotting heatmaps and patterns using PyQtGraph.
"""

from operator import index
import numpy as np
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QToolBar
from PyQt6 import QtCore
from PyQt6.QtGui import QColor
import pyqtgraph as pg

colors = [
        '#AAAA00',  # Yellow
        '#AA00AA',  # Magenta
        '#00AAAA',  # Cyan
        '#AA0000',  # Red
        '#00AA00',  # Green
        "#0066FF",  # Blue
        '#AAAAAA',  # Light Gray
        ]

class HeatmapWidget(QWidget):
    """
    A widget to display a heatmap of 2d data with moveable
    horizontal lines for selecting frames.
    It uses pyqtgraph for plotting and provides signals for interaction.
    Signals:
    - sigHLineMoved: Emitted when a horizontal line is moved, providing the index and new position.
    - sigXRangeChanged: Emitted when the x-axis range is changed, providing the new range.
    - sigHLineRemoved: Emitted when a horizontal line is removed, providing the index of the removed line.
    - sigImageDoubleClicked: Emitted when the image is double-clicked, providing the position (x, y).
    - sigImageHovered: Emitted when the image is hovered, providing the x and y indices of the hovered position.
    """
    sigHLineMoved = QtCore.pyqtSignal(int,int)
    sigXRangeChanged = QtCore.pyqtSignal(object)
    #sigHLineAdded = QtCore.pyqtSignal(int)
    sigHLineRemoved = QtCore.pyqtSignal(int)
    sigImageDoubleClicked = QtCore.pyqtSignal(object)
    sigImageHovered = QtCore.pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize variables
        self.x = None
        self.n = None
        self.h_lines = []
        self.active_line = None
        self.use_log_scale = False  # Flag to use logarithmic scale for the heatmap
        self.color_cycle = colors
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
        pen = pg.mkPen(color=self.color_cycle[len(self.h_lines) % len(self.color_cycle)], width=1)
        hoverpen = pg.mkPen(color=self.color_cycle[len(self.h_lines) % len(self.color_cycle)], width=3)
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
        self.active_line = h_line

    def removeHLine(self, index=-1):
        """Remove a horizontal line from the plot."""
        h_line = self.h_lines.pop(index)
        self.plot_widget.removeItem(h_line)
        # emit the signal for the removed horizontal line
        self.sigHLineRemoved.emit(index)
        self.active_line = self.h_lines[-1] if self.h_lines else None  # Set the active line to the last one if available

    def set_data(self, x,z,y=None):
        """Set the data for the heatmap."""
        self.n = z.shape[1]
        self.x = x
        if self.use_log_scale:
            z = np.log10(z,out=np.zeros_like(z), where=(z>0))  # Apply log scale to the data
        self.image_item.setImage(z)
        self._set_xticks(x)

        # update the limits of the plot
        self.plot_widget.setLimits(xMin=-len(x)*.1, xMax=len(x)*1.1, yMin=-self.n*0.02, yMax=self.n*1.02)

        # update the horizontal lines bounds
        for h_line in self.h_lines:
            # disconnect the signal to avoid recursion
            h_line.sigPositionChanged.disconnect(self.h_line_moved)
            h_line.setBounds([-1, self.n])
            # reconnect the signal
            h_line.sigPositionChanged.connect(self.h_line_moved)

    def _set_xticks(self,view=None,vrange=(None,None)):
        """Set the x-axis ticks. Called when the x-axis range is changed."""
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

    def get_h_line_pos(self, index):
        """Get the position of a horizontal line."""
        if index < 0 or index >= len(self.h_lines) or self.n is None:
            return None
        # get the position of the horizontal line
        pos = self.h_lines[index].y()
        # return the position as an integer index
        return int(np.clip(pos, 0, self.n-1))
    
    def get_h_line_positions(self):
        """Get the positions of all horizontal lines."""
        if self.n is None:
            return []
        # return the positions of all horizontal lines as a list of indices
        return [self.get_h_line_pos(i) for i in range(len(self.h_lines))]

    def move_active_h_line(self, delta):
        """Move the active horizontal line by a delta value."""
        if not self.h_lines:
            return
        # get the index of the currently active horizontal line
        current_index = self.h_lines.index(self.active_line) if self.active_line in self.h_lines else 0
        pos = self.get_h_line_pos(current_index)
        if pos is None:
            return
        # move the horizontal line by the delta value
        new_pos = pos + delta
        new_pos = int(np.clip(new_pos, 0, self.n-1))
        self.set_h_line_pos(current_index, new_pos)
        # emit the signal with the new position
        self.sigHLineMoved.emit(current_index, new_pos)

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
        self.active_line = self.h_lines[index]  # Set the active line to the one being moved

    def h_line_clicked(self, line, event):
        """Handle the horizontal line click event."""
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            event.accept()  # Accept the event to prevent further processing
            index = self.h_lines.index(line)
            self.removeHLine(index)
        elif event.button() == QtCore.Qt.MouseButton.LeftButton:
            # set the active line to the clicked line
            self.active_line = line

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
            self.sigImageHovered.emit((x_idx, y_idx))

        else:
            # emit None to indicate the mouse is no longer hovering
            self.sigImageHovered.emit(None)
    
    def set_color_cycle(self,color_cycle):
        """Set the color cycle for the plot items."""
        self.color_cycle = color_cycle
        self._update_line_colors()

    def _update_line_colors(self):
        """Update the colors of the line items based on the color cycle."""
        for i, line in enumerate(self.h_lines):
            color = QColor(self.color_cycle[i % len(self.color_cycle)])
            # get the current pen
            pen = line.pen
            pen.setColor(color)
            line.setPen(pen)

    def clear(self):
        """Clear the heatmap data and horizontal lines."""
        self.image_item.clear()
        self.x = None
        self.n = None
        for h_line in self.h_lines:
            self.plot_widget.removeItem(h_line)
        self.h_lines = []
        self.addHLine()


class PatternWidget(QWidget):
    """
    A widget to display patterns and vertical lines for reference patterns.
    It uses pyqtgraph for plotting and provides signals for interaction.
    Signals:
    - sigXRangeChanged: Emitted when the x-axis range is changed, providing the new range.
    - sigPatternHovered: Emitted when the mouse hovers over a pattern, providing the x and y coordinates.
    """
    sigXRangeChanged = QtCore.pyqtSignal(object)
    sigPatternHovered = QtCore.pyqtSignal(object)
    def __init__(self, parent=None):
        super().__init__(parent)

        self.x = None
        self.y = None
        self.pattern_items = []
        self.reference_items = []
        self.reference_hkl = {}

        self.color_cycle = colors  # Default color cycle for patterns

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

        # Create a plot item for the pattern
        self.add_pattern()

        # Add a text item to the plot for displaying hkl
        self.hkl_text_item = pg.TextItem(text='', anchor=(0.5, 0), color='w')
        self.plot_widget.getPlotItem().addItem(self.hkl_text_item)
        self.hkl_text_item.setVisible(False)  # Hide the text item by default

        self.plot_widget.sigXRangeChanged.connect(self.xrange_changed)

        self.plot_widget.getPlotItem().vb.hoverEvent = self.hover_event

        self.set_xlabel("radial axis")
        self.set_ylabel("intensity")

        # add a toolbar to the widget
        # Possible actions?
        # - export average pattern
        # - export current pattern(s)
        # - export all patterns
        # - fix current pattern(s)
        # - subtract current pattern(s)
        
        # self.toolbar = QToolBar(self)
        # self.toolbar.setOrientation(QtCore.Qt.Orientation.Vertical)
        # # Add actions to the toolbar
        # action = self.toolbar.addAction("Add Pattern")
        # layout.addWidget(self.toolbar)


    def add_pattern(self):
        """Add a new pattern item to the plot."""
        color = self.color_cycle[len(self.pattern_items) % len(self.color_cycle)]
        pen = pg.mkPen(color=color, width=1)
        brush = pg.mkBrush(color=color)
        pattern = pg.PlotDataItem(pen=pen, symbol='o',symbolSize=2, symbolPen=pen, symbolBrush=brush, name='frame')
        self.plot_widget.getPlotItem().addItem(pattern)
        self.pattern_items.append(pattern)

    def remove_pattern(self, index=-1):
        """Remove a pattern item from the plot."""
        pattern = self.pattern_items.pop(index)
        self.plot_widget.getPlotItem().removeItem(pattern)

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
        color = self.color_cycle[::-1][len(self.reference_items) % len(self.color_cycle)]
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

    def rescale_reference(self,index):
        """Rescale the intensity of the indexed reference to the current y-max"""
        reference_item = self.reference_items[index]
        x, I = reference_item.getData()
        I /= I.max()  # Normalize the intensity to the maximum value
        if self.y is None or len(self.y) == 0:
            scale = 100
        else:
            scale = self.y.max()
        reference_item.setData(x, I*scale)  # Rescale the reference pattern
        
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
            self.sigPatternHovered.emit((x, y))
        else:
            # emit None to indicate the mouse is no longer hovering
            self.sigPatternHovered.emit(None)  # Emit None to indicate no hover

    def set_color_cycle(self,color_cycle):
        """Set the color cycle for the plot items."""
        self.color_cycle = color_cycle
        self._update_pattern_colors()
        self._update_reference_colors()

    def _update_pattern_colors(self):
        """Update the colors of the pattern items based on the color cycle."""
        for i, pattern in enumerate(self.pattern_items):
            color = QColor(self.color_cycle[i % len(self.color_cycle)])
            # get the current pen
            pen = pattern.opts['pen']
            pen.setColor(color)
            pattern.setPen(pen)
            pattern.setSymbolPen(color)
            pattern.setSymbolBrush(color)


    def _update_reference_colors(self):
        """Update the colors of the reference items based on the color cycle (reverse order)."""
        for i, reference_item in enumerate(self.reference_items):
            color = QColor(self.color_cycle[::-1][i % len(self.color_cycle)])
            reference_item.setPen(color)

    def clear(self):
        """Clear the pattern data"""
        for i in range(len(self.pattern_items)):
            pattern = self.pattern_items.pop(0)
            self.plot_widget.getPlotItem().removeItem(pattern)
        self.add_pattern()  # Add a new pattern item to keep the list non-empty
       
class AuxiliaryPlotWidget(QWidget):
    """
    A widget to display auxiliary plots.
    It uses pyqtgraph for plotting and provides signals for interaction.
    Signals:
    - sigVLineMoved: Emitted when a vertical line is moved, providing the index and new position.
    - sigAuxHovered: Emitted when the mouse hovers over a vertical line, providing the x and y coordinates.
    """
    sigVLineMoved = QtCore.pyqtSignal(int, int)  # Signal emitted when a vertical line is moved
    sigAuxHovered = QtCore.pyqtSignal(object)  # Signal emitted when the mouse hovers over a vertical line
    def __init__(self, parent=None):
        super().__init__(parent)
        self.v_lines = []
        self.n = None  # Number of data points in the x-axis
        self.color_cycle = colors
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
            color = self.color_cycle[len(self.plot_item.items) % len(self.color_cycle)]
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
        pen = pg.mkPen(color=self.color_cycle[len(self.v_lines) % len(self.color_cycle)], width=1)
        hoverpen = pg.mkPen(color=self.color_cycle[len(self.v_lines) % len(self.color_cycle)], width=3)
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
            self.sigAuxHovered.emit((x, y))
        else:
            # emit None to indicate the mouse is no longer hovering
            self.sigAuxHovered.emit(None)
    
    def set_color_cycle(self,color_cycle):
        """Set the color cycle for the plot items."""
        self.color_cycle = color_cycle
        self._update_line_colors()

    def _update_line_colors(self):
        """Update the colors of the line items based on the color cycle."""
        for i, line in enumerate(self.v_lines):
            color = QColor(self.color_cycle[i % len(self.color_cycle)])
            # get the current pen
            pen = line.pen
            pen.setColor(color)
            line.setPen(pen)

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
        #self.addVLine()


if __name__ == "__main__":
    pass