# -*- coding: utf-8 -*-
"""
plaid - plaid looks at integrated data
F.H. Gjørup 2025-2026
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides a class to hold azimuthal integration data and perform various operations on it,
including loading data from HDF5 files, converting between q and 2theta, and normalizing intensity data.

"""
import numpy as np
from PyQt6.QtWidgets import  QInputDialog, QMessageBox
import h5py as h5
from plaid.nexus import (get_nx_monitor, get_nx_sample, get_nx_transformations, 
                         get_translations_from_nx_transformations)
from plaid.misc import q_to_tth, tth_to_q, get_map_shape_and_indices, average_blocks
from plaid.io import export_xy

class AzintData():
    """
    A class to hold azimuthal integration data.
    Parameters:
    - parent: The parent widget, usually the main window.
    - fnames: A list of file names to load the azimuthal integration data from.
    Attributes:
    - x: The radial axis data (2theta or q).
    - I: The intensity data.
    - is_q: A boolean indicating if the radial axis is in q or 2theta.
    - E: The energy data, if available.
    - I0: The I0 data, if available.
    - shape: The shape of the intensity data.
    - instrument_name: The name of the instrument, if available.
    - source_name: The name of the source, if available.
    """

    def __init__(self, parent=None,fnames=None):
        self.parent = parent
        if isinstance(fnames, str):
            fnames = [fnames]
        self.fnames = fnames
        self.x = None
        self.I = None
        self.I_error = None
        #self.y_avg = None
        self.is_q = False
        self.E = None
        self.I0 = None
        self.shape = None  # Shape of the intensity data
        self._shapes = []  # Shapes of individual files loaded
        self.reduction_factor = 1 # Reduction factor applied to the data (compounded if multiple reductions are applied)
        self.instrument_name = None  # Name of the instrument, if available
        self.source_name = None  # Name of the source, if available
        self._load_func = None
        self.map_shape = None  # Shape of the loaded data files used for mapping (PLACEHOLDER)
        self.map_indices = None  # Indices of the loaded data files used for mapping (PLACEHOLDER)

        self.y_bgr = None  # Background intensity data

        #self.aux_data = {} # {alias: np.array}

    def set_secondary_data(self, data_dict):
        """Set the "secondary" azimuthal integration data from a dictionary."""
        is_q = data_dict["q"] is not None
        self.is_q = is_q
        self.x = data_dict["q"] if is_q else data_dict["tth"]
        self.E = data_dict.get("energy", None)
        self.instrument_name = data_dict.get("instrument_name", None)
        self.source_name = data_dict.get("source_name", None)
        self.map_shape = data_dict.get("map_shape", None)
        self.map_indices = data_dict.get("map_indices", None)
    
    def load_I0_from_nxmonitor(self):
        """
        Load the I0 data from a nxmonitor dataset in the HDF5 file(s).
        All files in self.fnames are expected to have a nxmonitor dataset,
        otherwise, it returns None.
        """
        I0 = np.array([])
        for fname in self.fnames:
            with h5.File(fname, 'r') as f:
                monitor = get_nx_monitor(f)
                if monitor is None or 'data' not in monitor:
                    I0_ = None
                else:
                    I0_ = monitor['data'][:]
                if I0_ is None:
                    self.I0 = None
                    return False
                I0 = np.append(I0, I0_) if I0.size else I0_
        self.I0 = I0
        return True
    
    def load_map_shape_and_indices(self):
        """
        Load the map shape and pixel indices from an nxtransformations group
        in the HDF5 file(s). All files in self.fnames are expected to have
        a nxtransformations group, otherwise, it returns None.
        """
        x,y = np.array([]), np.array([])
        for fname in self.fnames:
            with h5.File(fname, 'r') as f:
                sample = get_nx_sample(f)
                if sample is None:
                    self.map_shape = None
                    self.pixel_indices = None
                    return False
                transformations = get_nx_transformations(sample)
                if transformations is None:
                    self.map_shape = None
                    self.pixel_indices = None
                    return False
                translations = get_translations_from_nx_transformations(transformations)
                if translations is None or "x" not in translations or "y" not in translations:
                    self.map_shape = None
                    self.pixel_indices = None
                    return False
                x = np.append(x, translations["x"]) if x.size else translations["x"]
                y = np.append(y, translations["y"]) if y.size else translations["y"]
        self.map_shape, self.map_indices = get_map_shape_and_indices(y, x)
        return True

    def reduce_data(self, reduction_factor=2, axes=(0,)):
        """Reduce the azimuthal integration data by averaging non-overlapping blocks."""
        
        if self.I is None:
            return
        self.I = average_blocks(self.I, reduction_factor=reduction_factor, axes=axes)
        if self.I_error is not None:
            self.I_error = average_blocks(self.I_error, reduction_factor=reduction_factor, axes=axes)
        if self.I0 is not None:
            self.I0 = average_blocks(self.I0, reduction_factor=reduction_factor, axes=axes)
        #self.y_avg = self.I.mean(axis=0) if self.I is not None else None
        self.shape = self.I.shape if self.I is not None else None
        self.map_shape, self.map_indices = None, None  # Invalidate map shape and indices after reduction
        self.reduction_factor *= reduction_factor

    def user_E_dialog(self):
        """Prompt the user for the energy value if not available in the file."""
        if self.E is None:
            E, ok = QInputDialog.getDouble(self.parent, "Energy Input", "Enter the energy in keV:", value=35.0, min=1.0, max=200.0)
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
        
    def get_I(self, index=None, I0_normalized=True, bgr_subtracted=True):
        """
        Get the intensity data at I[index] if index not None, otherwise return I.
        By default, it returns the normalized intensity data by dividing by I0 if I0 is set.
        """
        if self.I is None:
            print("No intensity data loaded.")
            return None
        I0 = 1
        if self.I0 is not None and I0_normalized:
            if self.I0.shape[0] != self.shape[0]:
                print(f"I0 data shape {self.I0.shape} must match the number of frames {self.shape} in the azimuthal integration data.")
                return None
            I0 = self.I0
        if index is not None:
            I = self.I[index, :]  # Get the intensity data for the specified index
            I0 = I0[index] if isinstance(I0, np.ndarray) else I0  # Get the corresponding I0 value
        else:
            I = self.I
        if bgr_subtracted and self.y_bgr is not None:
            I = I - self.y_bgr
        return (I.T / I0).T
    
    def get_average_I(self, I0_normalized=True,bgr_subtracted=True):
        """Get the average intensity data, normalized by I0 if set."""
        if self.I is None:
            print("No intensity data loaded.")
            return None
        I = self.get_I(index=None, I0_normalized=I0_normalized,bgr_subtracted=bgr_subtracted)
        return np.mean(I, axis=0) if I is not None else None

    def get_I_error(self, index=None, I0_normalized=True):
        """
        Get the intensity errors at I_error[index] if index is not None, otherwise return I_error.
        If I0_normalized is True, normalize the intensity errors by I0.
        """
        if self.I_error is None:
            return None
        I0 = 1
        if self.I0 is not None and I0_normalized:
            if self.I0.shape[0] != self.shape[0]:
                print(f"I0 data shape {self.I0.shape} must match the number of frames {self.shape} in the azimuthal integration data.")
                return None
            I0 = self.I0
        if index is not None:
            I_error = self.I_error[index, :]
            I0 = I0[index] if isinstance(I0, np.ndarray) else I0
        else:
            I_error = self.I_error
        return (I_error.T / I0).T if I_error is not None else None

    def get_average_I_error(self, I0_normalized=True):
        """Get the average intensity errors, normalized by I0 if set."""
        if self.I_error is None:
            return None
        I_error = self.get_I_error(index=None, I0_normalized=I0_normalized)
        return np.mean(I_error, axis=0) if I_error is not None else None

    def set_y_bgr(self, y_bgr):
        """Set the background intensity data."""
        if y_bgr is None:
            self.y_bgr = None
            return
        if isinstance(y_bgr, np.ndarray):
            self.y_bgr = y_bgr
        elif isinstance(y_bgr, (list, tuple)):
            self.y_bgr = np.array(y_bgr)
        else:
            print("Background intensity data must be a numpy array or a list/tuple.")
            return
        if self.y_bgr.shape[0] != self.x.shape[0]:
            print(f"Background intensity data shape {self.y_bgr.shape} must match the radial axis shape {self.x.shape}.")
            self.y_bgr = None
            return
        
    def set_I0(self, I0):
        """Set the I0 data."""
        if isinstance(I0, np.ndarray):
            self.I0 = I0
        elif isinstance(I0, (list, tuple)):
            self.I0 = np.array(I0)
        else:
            print("I0 data must be a numpy array or a list/tuple.")
            return
        
        if self.I is None:
            # Don't normalize (yet)
            return
        
        if self.I.shape[0]  != self.I0.shape[0]:
            print(f"I0 data shape {self.I0.shape} must match the number of frames {self.I.shape} in the azimuthal integration data.")
            return
    
    def export_pattern(self, fname, index, is_Q=False, I0_normalized=True, kwargs={}):
        """
        Export the azimuthal integration data at the current index to a text file.  
        If I0_normalized is True, normalize the intensity data by I0.  
        kwargs passed to np.savetxt  
        """
        if self.I is None:
            print("No intensity data loaded.")
            return False
        if is_Q:
            x = self.get_q()
        else:
            x = self.get_tth()
        y = self.get_I(index=index, I0_normalized=I0_normalized)
        y_e = self.get_I_error(index=index, I0_normalized=I0_normalized)
        if x is None or y is None:
            print("Error retrieving data for export.")
            return False
        
        export_xy(fname,x,y,y_e, kwargs)
        return True
    
    def export_average_pattern(self, fname, is_Q=False, I0_normalized=True, bgr_subtracted=True, kwargs={}):
        """
        Export the average azimuthal integration data to a text file.  
        If I0_normalized is True, normalize the intensity data by I0.  
        kwargs passed to np.savetxt  
        """
        if self.I is None:
            print("No intensity data loaded.")
            return False
        if is_Q:
            x = self.get_q()
        else:
            x = self.get_tth()
        y = self.get_average_I(I0_normalized=I0_normalized, bgr_subtracted=bgr_subtracted)
        y_e = self.get_average_I_error(I0_normalized=I0_normalized, bgr_subtracted=bgr_subtracted)
        
        if x is None or y is None:
            print("Error retrieving data for export.")
            return False

        export_xy(fname,x,y,y_e, kwargs)
        return True
    
    def get_info_string(self):
        """Get the instrument (and source) name from the azimuthal integration data."""
        name = ""
        if self.instrument_name is not None:
            name += self.instrument_name
        if self.source_name is not None:
            if name:
                name += " - "
            name += self.source_name
        if self.E is not None:
            if name:
                name += " - "
            name += f"energy: {self.E:.2f} keV"
        if self.I0 is not None:
            if name:
                name += " - "
            name += f"I0 corrected"
        if self.reduction_factor != 1:
            if name:
                name += " - "
            name += f"reduced x{self.reduction_factor}"
        return name

class AuxData:
    """A class to hold auxiliary data for azimuthal integration."""
    def __init__(self,parent=None):
        self._parent = parent
        self.I0 = None
        self._E = None

    def set_energy(self, E):
        """Set energy"""
        self._E = E
        
    def get_energy(self):
        """Get energy"""
        return self._E

    def set_I0(self, I0):
        """Set I0"""
        if isinstance(I0, (tuple, list)):
            I0 = np.array(I0)

        # check if the I0 data are close to unity
        # otherwise, normalize it and print a warning
        if I0.min() <= 0 or I0.max() < 0.5 or I0.max() > 2:
            if self._parent:
                message = ("Warning: I0 data should be close to unity and >0. Normalizing it.\n"
                            f" I0 [{I0.min():.2e}, {I0.max():.2e}] normalized to [{I0.min()/I0.max():.2f}, 1.00]")
                QMessageBox.warning(self._parent, "I0 Data Warning", message)
            else:
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


if __name__ == "__main__":
    pass