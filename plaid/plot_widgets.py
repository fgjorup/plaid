# -*- coding: utf-8 -*-
"""
plaid - plaid looks at integrated data
F.H. Gjørup 2025-2026
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides classes for plotting heatmaps and patterns using PyQtGraph.
"""

import numpy as np
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QWidget, QToolBar, QLabel, QComboBox,
                            QDoubleSpinBox, QCheckBox, QGraphicsColorizeEffect, QMenu)
from PyQt6 import QtCore
from PyQt6.QtGui import QColor, QTransform, QPixmap, QIcon, QFont, QCursor, QAction
import pyqtgraph as pg
from plaid.misc import q_to_tth, tth_to_q
import plaid.resources

colors = ["#C41E3A", # Crimson Red
          "#FF8C00", # Dark Orange
          "#228B22", # Forest Green
          "#4169E1", # Royal Blue
          "#8B008B", # Dark Magenta
          "#2F4F4F", # Dark Slate Gray
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
        self.ticks_lut = None
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

        # create a ticks lookup table to relate x values in scattering units to pixel indices
        _x = np.arange(0, x[0], np.mean(np.diff(x[:10])))
        x_ = np.arange(x[-1], np.ceil(x[-1]/10)*10+np.mean(np.diff(x[-10:])), np.mean(np.diff(x[-10:])))
        self.ticks_lut = np.array([np.append(np.append(_x,x),x_)[::10],
                              np.arange(-_x.shape[0], x.shape[0]+x_.shape[0], 10)])
        

        # get the current view range
        vrange = self.plot_widget.getViewBox().viewRange()[0]
        self._set_xticks(vrange=vrange)

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

        # get the tick positions in pixel indices using the lookup table
        tick_pos = np.interp(x_, self.ticks_lut[0], self.ticks_lut[1])
        # determine number of decimals based on step size
        decimals = int(np.ceil(-np.log10(step)))
        # set the ticks with tick positions and formatted labels
        self.x_axis.setTicks([[(idx+0.5, f"{x_[i]:.{decimals}f}") for i, idx in enumerate(tick_pos)]])

        # if step >= 1:
        #     self.x_axis.setTicks([[(np.argmin(np.abs(x - xi))+0.5, f"{xi:.0f}") for xi in x_]])
        # elif step >= 0.1:
        #     self.x_axis.setTicks([[(np.argmin(np.abs(x - xi))+0.5, f"{xi:.1f}") for xi in x_]])
        # elif step >= 0.01:
        #     self.x_axis.setTicks([[(np.argmin(np.abs(x - xi))+0.5, f"{xi:.2f}") for xi in x_]])
        # else:
        #     self.x_axis.setTicks([[(np.argmin(np.abs(x - xi))+0.5, f"{xi:.3f}") for xi in x_]])

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

    def get_xrange(self):
        """Get the x-axis range."""
        if self.x is None:
            return None
        view_range = self.plot_widget.getViewBox().viewRange()[0]
        x_min_idx = int(np.clip(view_range[0], 0, len(self.x)-1))
        x_max_idx = int(np.clip(view_range[1], 0, len(self.x)-1))
        return (self.x[x_min_idx], self.x[x_max_idx])

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
    
    def get_active_h_line_index(self):
        """Get the index of the currently active horizontal line."""
        current_index = self.h_lines.index(self.active_line) if self.active_line in self.h_lines else 0
        return current_index
    
    def get_active_h_line_pos(self):
        """Get the index of the currently active horizontal line."""
        current_index = self.get_active_h_line_index()
        return self.get_h_line_pos(current_index)

    def move_active_h_line(self, delta):
        """Move the active horizontal line by a delta value."""
        if not self.h_lines:
            return
        # get the index of the currently active horizontal line
        #current_index = self.h_lines.index(self.active_line) if self.active_line in self.h_lines else 0
        current_index = self.get_active_h_line_index()
        #pos = self.get_h_line_pos(current_index)
        pos = self.get_active_h_line_pos()
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

    def updateBackground(self):
        """
        Update the background color of the plot widget to the current default
        from pyqtgraph configOptions.
        """
        self.plot_widget.setBackground('default')
        self.histogram.setBackground('default')

    def updateForeground(self):
        """
        Update the foreground color of the plot widget to the current default
        from pyqtgraph configOptions.
        """
        self.x_axis.setPen()
        self.x_axis.setTextPen()
        self.x_axis.setTickPen()
        self.y_axis.setPen()
        self.y_axis.setTextPen()
        self.y_axis.setTickPen()

        self.histogram.item.axis.setPen()
        self.histogram.item.axis.setTextPen()
        self.histogram.item.axis.setTickPen()

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
    sigLinearRegionChangedFinished = QtCore.pyqtSignal(object)
    sigRequestQToggle = QtCore.pyqtSignal()
    sigRequestLockPattern = QtCore.pyqtSignal(object)
    sigRequestSubtractPattern = QtCore.pyqtSignal()
    sigRequestCorrelationMap = QtCore.pyqtSignal()
    sigRequestDiffractionMap = QtCore.pyqtSignal()
    sigRequestExportAvg = QtCore.pyqtSignal()
    sigRequestExportCurrent = QtCore.pyqtSignal()
    sigRequestExportAll = QtCore.pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)

        self.x = None
        self.y = None
        self.pattern_items = []
        self.locked_pattern_items = []
        self.reference_items = []
        self.reference_hkl = {}

        self.linear_region_ignore_negative = False
        self.linear_region_linear_background = False

        self.color_cycle = colors  # Default color cycle for patterns

        # Create a layout
        layout = QHBoxLayout(self)

        # Create a pyqtgraph PlotWidget
        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget,1)

        # add a moveable LinearRegionItem for selecting x-range
        self.lr = pg.LinearRegionItem(values=[-2, -1], 
                                      orientation="vertical",
                                      brush="#AAAA0050",
                                      hoverBrush="#AAAA0080",
                                      pen="#0000AAAA",
                                      )
        
        self.plot_widget.addItem(self.lr, ignoreBounds=True)
        self.lr.setVisible(False)  # Hide the LinearRegionItem by default

        self.fill_plots = [pg.PlotDataItem(pen="#FFFFFF00"), pg.PlotDataItem(pen="#FFFFFF00")]
        for fill_plot in self.fill_plots:
            self.plot_widget.addItem(fill_plot)
            fill_plot.setVisible(True)  # Hide the fill plots by default

        self.fill_area = pg.FillBetweenItem(self.fill_plots[0], self.fill_plots[1], brush='#AAAA0080')
        self.plot_widget.addItem(self.fill_area)
        self.fill_area.setVisible(False)  # Hide the FillBetweenItem by default

        # add a button item to the plot
        pxmap = QPixmap(":/icons/roi_default.png")
        self.button_default = pg.ButtonItem(pixmap=pxmap, width=15)
        self.button_default.setToolTip("Include full linear region")
        # self.button_default.setScale(1.5)
        self.button_default.clicked.connect(self.toggle_linear_region_options)
        # add the button to the scene of the plot widget
        # to ensure that is doesn't change size or scale with the data
        self.plot_widget.scene().addItem(self.button_default)
        self.button_default.setVisible(False)  # Hide the button by default
        
        # add a button item to the plot
        pxmap = QPixmap(":/icons/roi_ign_neg.png")
        self.button_ign_neg = pg.ButtonItem(pixmap=pxmap, width=15)
        self.button_ign_neg.setToolTip("Ignore negative values in linear region")
        self.button_ign_neg.setGraphicsEffect(QGraphicsColorizeEffect(color=QColor("#AAAAAA"),strength=.3))
        self.button_ign_neg.clicked.connect(self.toggle_linear_region_options)
        # add the button to the scene of the plot widget
        # to ensure that is doesn't change size or scale with the data
        self.plot_widget.scene().addItem(self.button_ign_neg)
        self.button_ign_neg.setVisible(False)  # Hide the button by default

        # add a button item to the plot
        pxmap = QPixmap(":/icons/roi_linear.png")
        self.button_linear_bgr = pg.ButtonItem(pixmap=pxmap, width=15)
        self.button_linear_bgr.setToolTip("Use linear background in linear region")
        self.button_linear_bgr.setGraphicsEffect(QGraphicsColorizeEffect(color=QColor("#AAAAAA"),strength=.3))
        self.button_linear_bgr.clicked.connect(self.toggle_linear_region_options)
        # add the button to the scene of the plot widget
        # to ensure that is doesn't change size or scale with the data
        self.plot_widget.scene().addItem(self.button_linear_bgr)
        self.button_linear_bgr.setVisible(False)  # Hide the button by default


        self.lr.sigRegionChangeFinished.connect(lambda: self.sigLinearRegionChangedFinished.emit(self.get_linear_region_roi()))
        # update the fill area when the linear region is moved
        self.lr.sigRegionChanged.connect(self.update_fill_area)
        self.lr.sigRegionChanged.connect(self.move_linear_region_button)

        self.plot_widget.getPlotItem().vb.sigRangeChanged.connect(self.move_linear_region_button)

  

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
        # initialize the plot limits
        self.plot_widget.setLimits(xMin=-1, xMax=181)

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
        #    > lock current active pattern
        #    > unlock/remove current active pattern
        # - subtract current pattern(s)
        
        self.toolbar = QToolBar(self)
        self.toolbar.setOrientation(QtCore.Qt.Orientation.Vertical)
        background_color = self.plot_widget.backgroundBrush().color().name()
        self.toolbar.setStyleSheet(f"background: {background_color}; ")
        self.toolbar.setIconSize(QtCore.QSize(20,20))
        layout.addWidget(self.toolbar)

        # Add actions to the toolbar 
        action = self.toolbar.addAction(f"2\u03B8\nQ") # unicode theta : \U000003B8
        font = QFont()
        font.setBold(True)
        action.setFont(font)
        action.setToolTip("Switch between 2theta and Q")
        action.triggered.connect(lambda: self.sigRequestQToggle.emit())

        self.toolbar.addSeparator()

        icon = QIcon(":/icons/lock.png")
        action = self.toolbar.addAction(icon,None)   #f"\U0001F512") # padlock icon
        action.setToolTip("Lock current active pattern")
        action.triggered.connect(lambda: self.sigRequestLockPattern.emit(True))

        icon = QIcon(":/icons/unlock.png")
        action = self.toolbar.addAction(icon,None)   #f"\U0001F513") # padlock icon
        action.setToolTip("Unlock latest locked pattern")
        action.triggered.connect(lambda: self.sigRequestLockPattern.emit(False))

        self.toolbar.addSeparator()

        icon = QIcon(":/icons/subtract.png")
        action = self.toolbar.addAction(icon,None) 
        action.setToolTip("Subtract current pattern")
        action.triggered.connect(lambda: self.sigRequestSubtractPattern.emit())

        self.toolbar.addSeparator()

        icon = QIcon(":/icons/correlation.png")
        action = self.toolbar.addAction(icon,None)
        action.setToolTip("Show correlation map")
        action.triggered.connect(lambda: self.sigRequestCorrelationMap.emit())
        
        icon = QIcon(":/icons/map.png")
        action = self.toolbar.addAction(icon,None)
        action.setToolTip("Show diffraction map")
        action.triggered.connect(lambda: self.sigRequestDiffractionMap.emit())

        self.toolbar.addSeparator()

        icon = QIcon(":/icons/save_pattern.png")
        action = self.toolbar.addAction(icon,None)
        action.setToolTip("Export...")

        menu = QMenu()
        menu.setToolTipsVisible(False)
        menu.addAction("Export average pattern", lambda: self.sigRequestExportAvg.emit())
        menu.addAction("Export current pattern(s)", lambda: self.sigRequestExportCurrent.emit())
        menu.addAction("Export all patterns", lambda: self.sigRequestExportAll.emit())

        #self.toolbar.addAction(menu.menuAction())
        action.setMenu(menu)
        action.triggered.connect(lambda: menu.exec(QCursor.pos()))


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

    def get_data(self, index=-1):
        """Get the data for the pattern."""
        return self.pattern_items[index].getData()

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
        self.update_fill_area()

    def set_pattern_name(self, name=None, index=-1):
        """Set the name of the pattern item."""
        if name is None:
            name = f"frame {index}"
        offset = 1+len(self.locked_pattern_items)
        self.legend.items[index+offset][1].setText(name)  # update the legend item text
    
    def add_locked_pattern(self,x,y,name):
        """Add a new locked pattern item to the plot."""
        color = self.color_cycle[len(self.locked_pattern_items) % len(self.color_cycle)]
        pen = pg.mkPen(color=color, width=1, style=QtCore.Qt.PenStyle.DashLine)
        brush = pg.mkBrush(color=color)
        pattern = pg.PlotDataItem(x=x,
                                  y=y,
                                  pen=pen,
                                  symbol='o',
                                  symbolSize=2, 
                                  symbolPen=pen, 
                                  symbolBrush=brush,
                                  name=name,
                                )
        pattern.setZValue(-1)
        self.plot_widget.getPlotItem().addItem(pattern)
        
        # clunky workaround to "insert" the legend item. Remove all and re-add
        self.legend.removeItem(pattern)
        for item in self.pattern_items:
            self.legend.removeItem(item)
        self.legend.addItem(pattern,name)
        for item in self.pattern_items:
            self.legend.addItem(item,item.name())
        self.locked_pattern_items.append(pattern)

    def locked_pattern_Q_to_tth(self,index,E):
        """Convert the locked patterns from Q to 2theta using the given energy E (in keV)."""
        pattern = self.locked_pattern_items[index]
        q, y = pattern.getData()
        tth = q_to_tth(q, E)
        pattern.setData(tth, y)
    
    def locked_pattern_tth_to_Q(self,index,E):
        """Convert the locked patterns from 2theta to Q using the given energy E (in keV)."""
        pattern = self.locked_pattern_items[index]
        tth, y = pattern.getData()
        q = tth_to_q(tth, E)
        pattern.setData(q, y)

    def remove_locked_pattern(self):
        """Remove the last locked pattern item from the plot."""
        if not self.locked_pattern_items:
            return
        pattern = self.locked_pattern_items.pop(-1)
        self.plot_widget.getPlotItem().removeItem(pattern)
        self.legend.removeItem(pattern)

    def add_reference(self, hkl, x, I,color=None):
        """Add a reference pattern to the plot."""
        if color is None:
            color = self.color_cycle[::-1][len(self.reference_items) % len(self.color_cycle)]
        pen = pg.mkPen(color=color) 
        reference_item = pg.PlotDataItem(pen=pen, connect='pairs')
        reference_item.setCurveClickable(True)
        reference_item.setZValue(-1)  # Set a lower z-value to draw below the patterns
        reference_item.sigClicked.connect(self.reference_clicked)  # Connect the click signal to a function
        self.plot_widget.getPlotItem().addItem(reference_item)
        self.reference_items.append(reference_item)
        self.reference_hkl[reference_item] = (x,hkl)  # Store the hkl indices for the reference item
        self._set_reference_data(reference_item, x, I)

    def update_reference(self, index, hkl, x, I):
        """Update a reference pattern in the plot."""
        reference_item = self.reference_items[index]
        self.reference_hkl[reference_item] = (x,hkl)  # Update the hkl indices for the reference item
        self._set_reference_data(reference_item, x, I)

    def _set_reference_data(self, item, x, I):
        """Set the data for a reference pattern item."""
        x = np.repeat(x,2)
        I = np.repeat(I,2)
        I[::2] = 0  # Set the intensity to 0 for the first point of each pair
        if self.y is None:
            scale = 100
        else:
            scale = self.y.max() if self.y.max()>0 else 1.
        item.setData(x, I*scale)  # Update with new data

    def remove_reference(self, index=-1):
        """Remove a reference pattern from the plot."""
        reference_item = self.reference_items.pop(index)
        self.plot_widget.getPlotItem().removeItem(reference_item)
        del self.reference_hkl[reference_item]

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
        color = item.opts['pen'].color()
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

    def show_linear_region_box(self, show=True):
        """Show or hide the linear region box."""
        # make sure the linear region box is within the x data range
        if self.x is not None and len(self.x) > 1:
            x_min, x_max = self.lr.getRegion()

            if x_min < self.x[0] and x_max < self.x[0] or x_min > self.x[-1] and x_max > self.x[-1]:
                # if the linear region box is completely outside the x data range, reset the range
                # to around the center of the x data range
                center = (self.x[0] + self.x[-1]) / 2
                width = (self.x[-1] - self.x[0]) / 10
                self.lr.setRegion([center - width / 2, center + width / 2])
            else:
                # otherwise, clip the linear region box to be within the x data range
                self.lr.setRegion([np.clip(x_min,self.x[0],self.x[-10]),
                                   np.clip(x_max,self.x[10],self.x[-1])])
        self.lr.setVisible(show)
        self.fill_area.setVisible(show)
        self.button_default.setVisible(show)
        self.button_ign_neg.setVisible(show)
        self.button_linear_bgr.setVisible(show)
        self.update_fill_area()

    def get_linear_region_roi(self):
        """Get the current roi boolean mask of the linear region box."""
        if not self.lr.isVisible() or self.x is None:
            return None
        x_min, x_max = self.lr.getRegion()
        # convert the x_range to indices
        roi = (self.x >= x_min) & (self.x <= x_max)
        return roi
    
    def update_fill_area(self):
        """Update the fill area between the linear region box."""
        roi = self.get_linear_region_roi()
        if roi is None or np.sum(roi) == 0:
            return
        y = self.y[roi]
        y0 = np.zeros_like(y)
        if self.linear_region_ignore_negative:
            y = np.clip(y, 0, None)
        if self.linear_region_linear_background:
            # make a simple linear background using the first 
            # and last points in the ROI
            y0 = np.linspace(y[0], y[-1], len(y))

        self.fill_plots[0].setData(self.x[roi], y0)
        self.fill_plots[1].setData(self.x[roi], y)
        self.fill_area.setCurves(self.fill_plots[0], self.fill_plots[1])
        
    def move_linear_region_button(self):
        """Move the linear region button to the top-right corner of the linear region."""
        # get the position in data coordinates
        x_min, x_max = self.lr.getRegion()
        y_max = self.plot_widget.getPlotItem().viewRange()[1][1]
        pos = QtCore.QPointF(x_max, y_max)
        # map the position to the scene coordinates
        pos = self.plot_widget.getPlotItem().vb.mapViewToScene(pos)
        # move the button to the position with some offset
        self.button_default.setPos(pos)
        pos = pos + QtCore.QPointF(0, self.button_default._width+2)
        self.button_ign_neg.setPos(pos)
        pos = pos + QtCore.QPointF(0, self.button_default._width+2)
        self.button_linear_bgr.setPos(pos)
 
    def toggle_linear_region_options(self,button):
        """Toggle the linear region options based on the button clicked."""
        if button == self.button_default:
            self.linear_region_ignore_negative = False
            self.linear_region_linear_background = False
            self.button_default.setGraphicsEffect(None)
            self.button_ign_neg.setGraphicsEffect(QGraphicsColorizeEffect(color=QColor("#AAAAAA"),strength=.3))
            self.button_linear_bgr.setGraphicsEffect(QGraphicsColorizeEffect(color=QColor("#AAAAAA"),strength=.3))
            # self.button_default.setGraphicsEffect(QGraphicsDropShadowEffect(color=QColor("#AA0000")))#blurRadius=2, xOffset=0, yOffset=0))
        
        elif button == self.button_ign_neg:
            self.linear_region_ignore_negative = True
            self.linear_region_linear_background = False
            self.button_default.setGraphicsEffect(QGraphicsColorizeEffect(color=QColor("#AAAAAA"),strength=.3))
            self.button_ign_neg.setGraphicsEffect(None)
            self.button_linear_bgr.setGraphicsEffect(QGraphicsColorizeEffect(color=QColor("#AAAAAA"),strength=.3))

        elif button == self.button_linear_bgr:
            self.linear_region_ignore_negative = False
            self.linear_region_linear_background = True
            self.button_default.setGraphicsEffect(QGraphicsColorizeEffect(color=QColor("#AAAAAA"),strength=.3))
            self.button_ign_neg.setGraphicsEffect(QGraphicsColorizeEffect(color=QColor("#AAAAAA"),strength=.3))
            self.button_linear_bgr.setGraphicsEffect(None)

        self.update_fill_area()
        self.sigLinearRegionChangedFinished.emit(self.get_linear_region_roi())

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

    def updateBackground(self):
        """
        Update the background color of the plot widget to the current default
        from pyqtgraph configOptions.
        """
        self.plot_widget.setBackground('default')
        background_color = self.plot_widget.backgroundBrush().color().name()
        self.toolbar.setStyleSheet(f"background: {background_color}; ")

    def updateForeground(self):
        """
        Update the foreground color of the plot widget to the current default
        from pyqtgraph configOptions.
        """
        x_axis = self.plot_widget.getPlotItem().getAxis('bottom')
        y_axis = self.plot_widget.getPlotItem().getAxis('left')

        x_axis.setPen()
        x_axis.setTextPen()
        x_axis.setTickPen()
        y_axis.setPen()
        y_axis.setTextPen()
        y_axis.setTickPen()

        self.legend.setLabelTextColor(x_axis.textPen().color())
        # workaround to set the legend text color
        for _, item in self.legend.items:
            text = item.text
            item.setText(text, color=x_axis.textPen().color())
        
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
        self.plot_data_items = []
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
        plot_data_item = self.plot_item.plot(x, y, pen=color, name=label if label else 'Auxiliary Plot')
        self.plot_data_items.append(plot_data_item)
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
        self._update_plot_colors()

    def _update_line_colors(self):
        """Update the colors of the line items based on the color cycle."""
        for i, line in enumerate(self.v_lines):
            color = QColor(self.color_cycle[i % len(self.color_cycle)])
            # get the current pen
            pen = line.pen
            pen.setColor(color)
            line.setPen(pen)

    def _update_plot_colors(self):
        """Update the colors of the plot items based on the color cycle."""
        for i, pdi in enumerate(self.plot_data_items):
            color = QColor(self.color_cycle[i % len(self.color_cycle)])
            pdi.setPen(color)

    def updateBackground(self):
        """
        Update the background color of the plot widget to the current default
        from pyqtgraph configOptions.
        """
        self.plot_widget.setBackground('default')

    def updateForeground(self):
        """
        Update the foreground color of the plot widget to the current default
        from pyqtgraph configOptions.
        """
        x_axis = self.plot_widget.getPlotItem().getAxis('bottom')
        y_axis = self.plot_widget.getPlotItem().getAxis('left')
        x_axis.setPen()
        x_axis.setTextPen()
        x_axis.setTickPen()
        y_axis.setPen()
        y_axis.setTextPen()
        y_axis.setTickPen()

        legend = self.plot_item.legend
        for _, item in legend.items:
            text = item.text
            item.setText(text, color=x_axis.textPen().color())


    def clear_plot(self):
        """Clear the auxiliary plot."""
        self.plot_item.clear()
        self.plot_data_items = []

    def clear(self):
        """Clear the auxiliary plot and vertical lines."""
        self.clear_plot()
        self.n = None
        for v_line in self.v_lines:
            self.plot_item.removeItem(v_line)
        self.v_lines = []
        #self.addVLine()

class BasicMapWidget(QWidget):
    """
    A widget to display a basic map.
    """
    sigImageDoubleClicked = QtCore.pyqtSignal(object)  # Signal emitted when the image is double-clicked
    def __init__(self, parent=None):
        super().__init__(parent)
        self.fnames = []  # used to keep track of which dataset is used
        self.transpose = False

        # Create a layout
        vlayout = QVBoxLayout(self)

        self.toolbar = QToolBar(self)
        self.toolbar.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.toolbar.setFloatable(False)
        self.toolbar.setMovable(False)
        self.toolbar.setHidden(True)
        vlayout.addWidget(self.toolbar)

        self.layout = QHBoxLayout()
        vlayout.addLayout(self.layout)

        # Create a pyqtgraph PlotWidget
        self.plot_widget = pg.PlotWidget()
        self.layout.addWidget(self.plot_widget,1)

        # Create a image item for the heatmap
        self.image_item = pg.ImageItem()
        self.plot_widget.addItem(self.image_item)
        self.plot_widget.setLimits(minXRange=3)

        # create a cursor plus symbol at the center of the image
        self.cursor = pg.ScatterPlotItem(size=1.0, 
                                         pen=pg.mkPen((255, 255, 255, 128), width=2), 
                                         brush=pg.mkBrush(None), 
                                         symbol='s', # square symbol
                                         pxMode=False)
        
        self.plot_widget.addItem(self.cursor)

        tr = QTransform()
        tr.translate(-0.5, -0.5)
        self.image_item.setTransform(tr)       

        self.x_axis = self.plot_widget.getPlotItem().getAxis('bottom')
        self.y_axis = self.plot_widget.getPlotItem().getAxis('left')

        # Create a histogram widget
        self.histogram = pg.HistogramLUTWidget()
        self.histogram.setImageItem(self.image_item)
        self.histogram.item.gradient.loadPreset('viridis')
        self.layout.addWidget(self.histogram,0)

        self.plot_widget.getPlotItem().mouseDoubleClickEvent = self.image_double_clicked

        # get the context menu of the plot widget and add an option to transpose the map
        menu = self.plot_widget.getPlotItem().getViewBox().getMenu(None)
        action_transpose = QAction("Transpose",self)
        menu.insertAction(menu.actions()[1],action_transpose)
        action_transpose.triggered.connect(self.toggle_transpose)


    def set_data(self, im):
        """Set the data for the map."""
        if im is None:
            return
        if self.transpose:
            im = im.T
        self.image_item.setImage(im)

    def image_double_clicked(self, event):
        """Handle the double click event on the image item."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton and self.image_item.image is not None:
            event.accept()
            shape = self.image_item.image.shape
            pos = self.plot_widget.getPlotItem().vb.mapSceneToView(event.pos())
            x, y = int(pos.x()+0.5), int(pos.y()+0.5)
            # ignore clicks outside the image area or on nan values
            if x < 0 or x >= shape[0] or y < 0 or y >= shape[1] \
            or np.isnan(self.image_item.image[x, y]):
                self.hide_cursor()
            else:
                self.move_cursor(x, y)
                self.sigImageDoubleClicked.emit((x, y))
    
    def move_cursor(self, x, y):
        """Move the cursor to the specified position."""
        self.cursor.setData(x=[x], y=[y])

    def hide_cursor(self):
        """Hide the cursor."""
        self.cursor.setData(x=[], y=[])

    def updateBackground(self):
        """
        Update the background color of the plot widget to the current default
        from pyqtgraph configOptions.
        """
        self.plot_widget.setBackground('default')
        self.histogram.setBackground('default')


    def updateForeground(self):
        """
        Update the foreground color of the plot widget to the current default
        from pyqtgraph configOptions.
        """
        self.x_axis.setPen()
        self.x_axis.setTextPen()
        self.x_axis.setTickPen()
        self.y_axis.setPen()
        self.y_axis.setTextPen()
        self.y_axis.setTickPen()

        self.histogram.item.axis.setPen()
        self.histogram.item.axis.setTextPen()
        self.histogram.item.axis.setTickPen()

    def autoRange(self):
        """Auto range the plot to fit the image."""
        self.plot_widget.autoRange()

    def toggle_transpose(self):
        """Transpose the map."""
        # new transpose state
        _transpose = not self.transpose
        # always set transpose to True when updating the data
        # to either transpose or "un-transpose" the image
        self.transpose = True
        im = self.image_item.image
        self.set_data(im)
        # set the transpose state
        self.transpose = _transpose

class CorrelationMapWidget(BasicMapWidget):
    """
    A widget to display a correlation map. Inherits from BasicMapWidget.
    """
    sigImageDoubleClicked = QtCore.pyqtSignal(object)  # Signal emitted when the image is double-clicked
    def __init__(self, parent=None):
        super().__init__(parent)
        self.n = None  # Number of data points in the x-axis
        self.x_axis.setLabel("frame number #")
        self.y_axis.setLabel("frame number #")

    def set_correlation_data(self, z):
        """Set the data for the correlation map."""
        if z is None:
            return
        # compute the correlation matrix
        im = np.corrcoef(z)
        self.set_data(im)

        n = im.shape[0]
        self.n = n
        # update the limits of the plot
        self.plot_widget.setLimits(xMin=-n*.1, xMax=n*1.1, yMin=-n*0.1, yMax=n*1.1)


class DiffractionMapWidget(BasicMapWidget):
    """
    A widget to display a diffraction map. Inherits from BasicMapWidget.
    """

    def __init__(self, parent=None,map_shape_options=None):
        super().__init__(parent)

        self.map_shape = None
        self.z = None
        self.is_snake = False

        self.toolbar.setHidden(False)

        # create a "map shape" combo box
        self.map_shape_combo = QComboBox(self)
        self.map_shape_combo.setToolTip("Select the shape of the diffraction map")
        self.map_shape_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.map_shape_combo.activated.connect(self.map_shape_changed)

        self.toolbar.addWidget(QLabel("Map shape: "))
        self.toolbar.addWidget(self.map_shape_combo)

        # create an aspect ratio double spin box
        self.aspect_ratio_spin = QDoubleSpinBox(self)
        self.aspect_ratio_spin.setToolTip("Set the pixel aspect ratio (width/height)")
        self.aspect_ratio_spin.setRange(0.1, 10.0)
        self.aspect_ratio_spin.setSingleStep(0.1)
        self.aspect_ratio_spin.setValue(1.0)
        self.aspect_ratio_spin.valueChanged.connect(self.update_aspect_ratio)
        self.toolbar.addWidget(QLabel("Pixel aspect ratio: "))
        self.toolbar.addWidget(self.aspect_ratio_spin)

        # create a "flip alternate rows" checkbox
        self.flip_rows_check = QCheckBox("Snake", self)
        self.flip_rows_check.setToolTip("Flip alternate rows for snake-like scanning")
        self.flip_rows_check.setChecked(self.is_snake)
        self.flip_rows_check.checkStateChanged.connect(self.update_map)
        self.toolbar.addWidget(self.flip_rows_check)

        self.x_axis.setLabel("x-axis (px)")
        self.y_axis.setLabel("y-axis (px)")

        self.set_map_shape_options(map_shape_options)

        self.update_aspect_ratio()


    def set_diffraction_data(self, z):
        """
        Set the data for the diffraction map. Takes a 1D array and
        reshapes it into a square 2D array for display.
        """
        if z is None or self.map_shape is None:
            return
        if len(z) != np.prod(self.map_shape):
            raise ValueError("The length of z does not match the product of map_shape.")
        self.z = z
        self.is_snake = False
        self.update_map()

    def update_map(self):
        """Update the diffraction map with the current data and shape."""
        if self.z is None or self.map_shape is None:
            return
        im = self.z.reshape(self.map_shape)
        if self.flip_rows_check.isChecked() != self.is_snake:
            im[1::2] = im[1::2, ::-1]
            self.is_snake = self.flip_rows_check.isChecked()
        self.set_data(im)
        self.autoRange()

    def set_map_shape_options(self, options,current_index=None):
        """Set the options for the map shape combo boxes. Options should be a list of integers."""
        self.map_shape_combo.clear()

        if not options:
            return
        for i in range(len(options)):
            shape_0 = options[i]
            shape_1 = options[-(i + 1)]
            self.map_shape_combo.addItem(f"{shape_0} × {shape_1}", (shape_0,shape_1))
        if current_index is not None and 0 <= current_index < len(options):
            self.map_shape_combo.setCurrentIndex(current_index)
        else:
            self.map_shape_combo.setCurrentIndex(len(options)//2)
        self.map_shape = self.map_shape_combo.itemData(self.map_shape_combo.currentIndex())

    def map_shape_changed(self, index):
        """Handle the change of the map shape combo box."""
        shape = self.map_shape_combo.itemData(index)
        if shape:
            # check if the rows need to be "unflipped" (snake)
            # before the shape is changed
            if self.is_snake:
                im = self.z.reshape(self.map_shape)
                im[1::2] = im[1::2, ::-1]
                self.is_snake = False
            self.map_shape = shape
            self.update_map()

    def update_aspect_ratio(self):
        """Update the aspect ratio of the diffraction map."""
        aspect_ratio = self.aspect_ratio_spin.value()
        self.plot_widget.getPlotItem().setAspectLocked(lock=True, ratio=aspect_ratio)

    


    


if __name__ == "__main__":
    pass