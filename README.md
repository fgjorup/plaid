# plaid - plaid looks at integrated data  
plaid is a simple visualization tool intended to quickly evaluate azimuthally integrated powder diffraction data and compare to known structures, provided by the user in the form of CIF files.  
The main data format is HDF5 files, inspired by the [NeXus](https://www.nexusformat.org/) file formats.  

## Installation

You can install `plaid` using pip ([PyPi](https://www.pypi.org/)). For most users, the following command is all you need:

```bash
pip install plaid-xrd
```

**Tip:**  
For a cleaner Python setup, you can use a [virtual environment](https://docs.python.org/3/tutorial/venv.html) to keep your packages organized. This is optional, but recommended if you work on multiple Python projects.

To create and activate a virtual environment (optional):

<details>
  <summary>Show virtual environment instructions</summary>

  **Windows:**
  ```bash
  python -m venv plaid-env
  plaid-env\Scripts\activate
  ```

  **macOS/Linux:**
  ```bash
  python3 -m venv plaid-env
  source plaid-env/bin/activate
  ```
</details>

If you are unsure which Python interpreter to use, you might need to specify the full path. You can find your Python path by running:

```bash
where python   # on Windows
which python   # on macOS/Linux
```

Once your environment is ready, install plaid as shown above.

Start the application from a terminal with:  
```bash
plaid
```

or you can run:

```bash
plaid -h
```

to see a list of available command-line arguments and options for plaid.

## Using plaid to read nxazint HDF5 files  
plaid is intended as a visualization tool, but the `plaid.nexus` module can also be used as a library of convienience functions for reading nxazint files. The [plot_nxazint_demo.ipynb](https://github.com/fgjorup/plaid/blob/main/plot_nxazint_demo.ipynb) jupyter notebook demonstrate how the `plaid.nexus` module can be used to read and plot 1D and 2D diffraction data from a _multi-modal_ nxazint file.  

```python
import h5py as h5
import plaid.nexus as pnx
import matplotlib.pyplot as plt

fname = "tests/scan-0100_multi_demo.h5" # your file name
# open the file with h5py
with h5.File(fname,'r') as f: 
    # get the nxazint1d entry (or subentry)
    azint1d = pnx.get_nx_entry(f,definition='NXazint1d')
    
    # get the axes group - radial axis (2theta or Q) is the last index
    axes_gr = pnx.get_nx_axes(azint1d)
    x = axes_gr[-1][:]
        
    # get the signal group i.e. the intensity
    signal_gr = pnx.get_nx_signal(azint1d)
    I = signal_gr[:]

# plot the first diffraction pattern
plt.figure()
plt.plot(x,I[0])
plt.show()       
```

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
| C   | Show/hide the auto-correlation map          |
| M   | Show/hide the diffraction map               |
| B   | Subtract the active pattern as background   |
| ↑   | Move the active line one frame up           |
| ↓   | Move the active line one frame down         |
| ←   | Move the active line several frames down    |
| →   | Move the active line several frames up      |
