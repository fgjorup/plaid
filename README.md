# plaid - plot azimuthally integrated data  
plaid is a simple visualization tool intended to quickly evaluate azimuthally integrated powder diffraction data and compare to known structures, provided by the user in the form of CIF files.  
The main data format is HDF5 files, inspired by the [NeXus](https://www.nexusformat.org/) file formats.  

## Installation  
Install plaid from the Python Package Index [PyPi](https://pypi.org/) with:  
`pip install plaid-xrd`

Start the application from a terminal with:  
`plaid`

## Example  
**The main window of plaid**  
![Example of the plaid main window](media/screenshot_main_dark.png)  
- Drag/drop an .h5 file into the main window or browse from *File* -> *Open*  
- Change the pattern by moving the horizontal lines with the mouse or the arrow keys  
- Add a new moveable line by double-clicking the heatmap, remove a line by right-clicking it  
- Click the symbols in the pattern legend to show/hide the patterns  
- Drag/drop a .cif file into the main window or browse from *File* -> *Load CIF*  
- Click on a reference line to show its reflection index  

**File tree context menu**
![Example of the file tree menu](media/screenshot_filetree_context_dark.png)
- Right-click on a file in the file tree to add $I_0$ or auxiliary data  
- Right-click on two or more selected files to group them  

**Export patterns**
![Example of the export settings window](media/screenshot_export_settings_dark.png)
- Save the export settings in *Export -> Export settings*

## Hotkeys
| Key | Action                                      |
|-----|---------------------------------------------|
| L   | Toggle log scale for the heatmap            |
| Q   | Toggle between q and 2θ axes                |
| ↑   | Move the active line one frame up           |
| ↓   | Move the active line one frame down         |
| ←   | Move the active line several frames down    |
| →   | Move the active line several frames up      |
