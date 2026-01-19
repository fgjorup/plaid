# -*- coding: utf-8 -*-
"""
plaid - plaid looks at integrated data
F.H. Gjørup 2025-2026
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides I/O functions for reading h5py files and exporting data.

FOR USER-DEFINED FILE FORMATS:
To define custom dataset paths for loading data from HDF5 files,
edit the USER_FILE_PARSER.py file in the plaid directory.

"""
import os
import h5py as h5
import numpy as np
from PyQt6.QtCore import pyqtSignal, QObject, QThread, pyqtSlot
from nexus import *
from dialogs import H5Dialog
try:
    from USER_FILE_PARSER import USER_FILE_PARSER
except Exception as e:
    # If the USER_FILE_PARSER.py file does not exist, copy the template
    if not os.path.exists(os.path.join(os.path.dirname(__file__), 'USER_FILE_PARSER.py')):
        with open(os.path.join(os.path.dirname(__file__), 'ufp_temp.py'), 'r') as src:
            content = src.readlines()
        with open(os.path.join(os.path.dirname(__file__), 'USER_FILE_PARSER.py'), 'w') as dst:
            dst.writelines(content[3:])  # Skip the first 3 lines (the comments)
    # if the file exists but cannot be imported, print the error
    else:
        print(f"Error importing USER_FILE_PARSER.py: {e}")

    USER_FILE_PARSER = {"I": None,
                        "I_error": None,
                        "tth": None,
                        "q": None,
                        "energy": None,
                        "wavelength": None,
                        "I0": None,
                        "instrument_name": None,
                        "source_name": None,
                        "map_shape": None,
                        "map_indices": None,
                        }

class Iter_H5Dataset(h5.File):
    """
    A convenient HDF5 file class for iterative data access.
    Inherits from h5py.File.
    """
    def __init__(self, name, dataset_path, **kwargs):
        super().__init__(name, **kwargs)
        self.chunk_size = None
        self.n_chunks = None
        self.dset = self[dataset_path]
        self._set_chunk_size()

    def _set_chunk_size(self, target_mem=4):
        """Attempt to determine a suitable chunk size for a dataset, using
        a target memory size. If the dataset is chunked, use its chunk size as basis.
        Parameters:
            target_mem (int): Target memory size in MB for each chunk.
        """
        single_chunk_size = self.dset.chunks if self.dset.chunks else (1,*self.dset.shape[1:])
        # estimate the memory size of a single chunk
        estimated_chunk_mem = np.prod(single_chunk_size) * self.dset.dtype.itemsize
        # set chunk size to keep memory usage around 4 MB
        target_mem = target_mem * 1024 * 1024  # Convert MB to bytes
        n = max(1, target_mem // estimated_chunk_mem)
        self.chunk_size = n * single_chunk_size[0]
        self.n_chunks = (self.dset.shape[0] + self.chunk_size - 1) // self.chunk_size

    def iter_read(self, chunk_size=None):
        """
        Generator to read a dataset in chunks.
        
        Parameters:
            chunk_size (int): Number of elements to read per chunk.
        """
        if chunk_size is None:
            chunk_size = self.chunk_size
        total_size = self.dset.shape[0]
        for start in range(0, total_size, chunk_size):
            end = min(start + chunk_size, total_size)
            yield self.dset[start:end]

class ReadWorker(QObject):
    """
    A simple QObject worker that runs a callable in a QThread for reading HDF5 
    datasets. The Worker instance owns the QThread during execution and will clean up
    the thread when finished.
    """
    sigStarted = pyqtSignal()
    sigFinished = pyqtSignal(bool, object)  # success(bool), result or exception
    sigError = pyqtSignal(object)
    sigProgress = pyqtSignal(int)  # progress in 0-10000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.fname = None
        self.dataset_path = None
        self._thread = None
        self.success = False
        self.cancelled = False

    @pyqtSlot()
    def _run(self):
        """Internal slot that executes the callable."""
        self.sigStarted.emit()
        try:
            result = self.read_iter(self.fname, self.dataset_path)
            self.sigFinished.emit(True, result)
            self.success = True
        except Exception as e:
            # emit error signals and finished with failure
            self.sigError.emit(e)
            self.sigFinished.emit(False, e)
            self.success = False

    def start(self, fname, dataset_path):
        """Start the worker in a new QThread."""
        if self._thread is not None and self._thread.isRunning():
            raise RuntimeError('Worker already running')
        self.fname = fname
        self.dataset_path = dataset_path
        self.cancelled = False
        self._thread = QThread()
        # move self to thread and start
        #self.moveToThread(self._thread)
        self._thread.started.connect(self._run)
        # ensure cleanup when finished
        self.sigFinished.connect(lambda *_: self._cleanup())
        self._thread.start()

    def read_iter(self,fname, dataset_path):
        """Utility function to read a dataset iteratively using Iter_H5Dataset."""
        import time
        with Iter_H5Dataset(fname, dataset_path) as f:
            data = np.empty_like(f.dset)
            for i,chunk in enumerate(f.iter_read()):
                start = i * f.chunk_size
                end = start + chunk.shape[0]
                data[start:end] = chunk
                self.sigProgress.emit(int(((i+1)*1e4)//f.n_chunks))
                if self.cancelled:
                    break
            return data

    def _cleanup(self):
        try:
            if self._thread is not None:
                self._thread.quit()
                self._thread.wait()
                self._thread = None
        except Exception:
            pass
        
def read_from_dict(f, file_dict):
    """Read datasets from an HDF5 file based on a provided file dictionary."""
    data = {}
    for key, path in file_dict.items():
        if path is not None and path in f:

            data[key] = f[path][()]
        else:
            data[key] = None
    return data

def _determine_file_dict(f, parent=None):
    """Initialize the file dictionary with keys for various data types."""
    file_dict = {"I": None,
                "I_error": None,
                "tth": None,
                "q": None,
                "energy": None,
                "wavelength": None,
                "I0": None,
                "instrument_name": None,
                "source_name": None,
                "map_shape": None,
                "map_indices": None,
                }
    if 'entry/data1d' in f:
        # old (DanMAX) nxazint HDF5 file
        data_group = f['entry/data1d']
        file_dict.update({"I": get_h5_dset_path(data_group,'I'),
                        "I_error": get_h5_dset_path(data_group,'I_error'),
                        "tth": get_h5_dset_path(data_group,'2th'),
                        "q": get_h5_dset_path(data_group,'q'),
                        })
        return file_dict
    elif 'entry/dataxrd1d' in f:
        # DanMAX map HDF5 file
        data_group = f['entry/dataxrd1d']
        file_dict.update({"I": get_h5_dset_path(data_group,'xrd'),
                        "I_error": get_h5_dset_path(data_group,'xrd_error'),
                        "tth": get_h5_dset_path(data_group,'tth'),
                        "q": get_h5_dset_path(data_group,'q'),
                        })
        return file_dict
    elif USER_FILE_PARSER.get("I", None) is not None:
        # Use the user-defined file parser dictionary
        for key, path in USER_FILE_PARSER.items():
            if path is not None and path in f:
                file_dict[key] = path
        # ensure that at least "I" and "tth" or "q" are defined
        if file_dict["I"] is None or (file_dict["tth"] is None and file_dict["q"] is None):
            file_dict = {key:None for key in file_dict.keys()}  
            pass
        else:
            return file_dict
        
    # Attempt to load using the H5Dialog if no specific structure is found
    _selected_dict = _load_dialog(f, parent=parent)
    if _selected_dict is not None:
        file_dict.update(_selected_dict)
    return file_dict

def _load_dialog(f, parent=None):
    """
    Load azimuthal integration data from an h5 file dialog.  
    This function is used as a last resort if no other load function is found.
    """
    dialog = H5Dialog(parent, f)
    if not dialog.exec_1d_2d_pair():
        return None

    selected = dialog.get_selected_items() # list of tuples with (alias, full_path, shape)
    axis = [item for item in selected if not "×" in item[2]][0] 
    signal = [item for item in selected if "×" in item[2]][0]
    # Check if the shape of the axis and signal match
    if not axis[2] in signal[2].split("×")[1]:
        print(f"Error: The shape of the axis {axis[2]} does not match the shape of the signal {signal[2]}.")
        return None
    # attempt to guess if the axis is q or 2theta
    is_q = 'q' in axis[0].lower() or 'q' in f[axis[1]].attrs.get('long_name', '').lower()
    file_dict = {"I": signal[1],
                 "tth": axis[1] if not is_q else None,
                 "q": axis[1] if is_q else None,
                    }
    return file_dict

def load_file(fname, parent=None):
    """
    Load azimuthal integration data from a nexus or generic HDF5 file,
    EXCLUDING the intensity data (and error). Return a dictionary with
    dataset paths for I and I_error and metadata.
    
    data_dict = {"I": None,
                "I_error": None,
                "tth": None,
                "q": None,
                "energy": None,
                "wavelength": None,
                "I0": None,
                "instrument_name": None,
                "source_name": None,
                "map_shape": None,
                "map_indices": None,
                }
    """
    with h5.File(fname, 'r') as f:
        entry = get_nx_entry(f,definition="NXazint1d",allow_subentry=True)
        if entry is not None:
            default = get_nx_default(entry)
            signal = get_nx_signal(default)
            signal_errors = get_nx_signal_errors(default)
            axis = get_nx_axes(default)[-1] # Get the last axis, which is usually the radial axis
            is_Q = 'q' in axis.attrs['long_name'].lower() if 'long_name' in axis.attrs else False
            monochromator = get_nx_monochromator(entry)
            instrument = get_nx_instrument(entry)
            source = get_nx_source(entry)
            monitor = get_nx_monitor(entry)
            data_dict = {"I": signal.name,
                        "I_error": signal_errors.name if signal_errors is not None else None,
                        "tth": axis[:] if not is_Q else None,
                        "q": axis[:] if is_Q else None,
                        "energy": get_nx_energy(monochromator),
                        "wavelength": None,
                        "I0": monitor["data"][:] if monitor is not None else None,
                        "instrument_name": get_instrument_name(instrument),
                        "source_name": get_source_name(source),
                        }

        elif 'entry/dataxrd1d/xrd' in f:
            # DanMAX map HDF5 file
            data_group = f['entry/dataxrd1d']
            data_dict = {"I": data_group['xrd'].name,
                         "I_error": data_group['xrd_error'].name if 'xrd_error' in data_group else None,
                         "tth": data_group['tth'][()] if 'tth' in data_group else None,
                         "q": data_group['q'][()] if 'q' in data_group else None,
                         "energy": f['/entry/measurement/Emax'][()] if '/entry/measurement/Emax' in f else None,
                         "wavelength": None,
                         "I0": None,
                         "instrument_name": None,
                         "source_name": None,
                         "map_shape": data_group['xrd'].shape[1:],
                         "map_indices": list(range(np.prod(data_group['xrd'].shape[1:]))),
                         }
        else:
            file_dict = _determine_file_dict(f,parent=parent)
            data_dict = {"I": file_dict.pop("I"),
                         "I_error":file_dict.pop("I_error"),
                         }

            data_dict.update(read_from_dict(f, file_dict))
    return data_dict

def export_xy(fname, x, y, y_e=None, kwargs={}):
    """
    Export the azimuthal integration data to a text file.  
    kwargs are passed to np.savetxt.
    Parameters:
        fname (str): The file name to save the data to.
        x (np.ndarray): The x-axis data (e.g., tth or q).
        y (np.ndarray): The intensity data.
        y_e (np.ndarray, optional): The intensity error data.
        kwargs (dict, optional): Additional keyword arguments for np.savetxt.
    Returns:
        bool: True if the export was successful.
    """
    if y_e is None:
        np.savetxt(fname, np.column_stack((x, y)),comments='#',**kwargs)
    else:
        np.savetxt(fname, np.column_stack((x, y, y_e)),comments='#',**kwargs)
    return True
