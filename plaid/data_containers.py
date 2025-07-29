# -*- coding: utf-8 -*-
"""
plaid - Plot Azimuthally Integrated Data
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides a class to hold azimuthal integration data and perform various operations on it,
including loading data from HDF5 files, converting between q and 2theta, and normalizing intensity data.

"""
import numpy as np
from PyQt6.QtWidgets import  QInputDialog, QMessageBox
import h5py as h5
from plaid.nexus import get_nx_default, get_nx_signal, get_nx_axes, get_nx_energy
from plaid.misc import q_to_tth, tth_to_q


class AzintData():
    """A class to hold azimuthal integration data."""

    def __init__(self, parent=None,fnames=None):
        self.parent = parent
        if isinstance(fnames, str):
            fnames = [fnames]
        self.fnames = fnames
        self.x = None
        self.I = None
        self.y_avg = None
        self.is_q = False
        self.E = None
        self.I0 = None
        self.shape = None  # Shape of the intensity data
        self._load_func = None
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
        
        if self._load_func is None:
            # Determine the load function based on the first file
            self._determine_load_func(self.fnames[0])
            if self._load_func is None:
                print("No valid load function found. Please provide a valid azimuthal integration file.")
                return False

        I = np.array([[],[]])
        for fname in self.fnames:
            x, I_, is_q, E = self._load_func(fname)
            I = np.append(I, I_, axis=0) if I.size else I_
        #I = np.array(I)
        self.x = x
        self.I = I
        self.is_q = is_q
        self.E = E
        self.y_avg = I.mean(axis=0)
        self.shape = I.shape
        return True

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
        
    def get_I(self, index=None, I0_normalized=True):
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
        return (I.T / I0).T
    
    def get_average_I(self, I0_normalized=True):
        """Get the average intensity data, normalized by I0 if set."""
        if self.I is None:
            print("No intensity data loaded.")
            return None
        I = self.get_I(index=None, I0_normalized=I0_normalized)
        return np.mean(I, axis=0) if I is not None else None


    def set_I0(self, I0):
        """Set the I0 data."""
        if isinstance(I0, np.ndarray):
            self.I0 = I0
        elif isinstance(I0, (list, tuple)):
            self.I0 = np.array(I0)
        else:
            print("I0 data must be a numpy array or a list/tuple.")
            return
        
        # # check if the I0 data are close to unity
        # # otherwise, normalize it and print a warning
        # if self.I0.min() <= 0 or self.I0.max() < 0.5 or self.I0.max() > 2:
        #     message = ("Warning: I0 data should be close to unity and >0. Normalizing it.")
        #     QMessageBox.warning(self.parent, "I0 Data Warning", message)
            
        #     print(f"I0 [{self.I0.min():.2e}, {self.I0.max():.2e}] normalized to [{self.I0.min()/self.I0.max():.2f}, 1.00]")
        #     self.I0 = self.I0 / np.max(self.I0)
        #     self.I0[self.I0<=0] = 1  # Set any zero values to 1 to avoid division by zero


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
        
        if x is None or y is None:
            print("Error retrieving data for export.")
            return False
        
        self._export_xy(fname,x,y, kwargs)
        return True
    
    def export_average_pattern(self, fname, is_Q=False, I0_normalized=True, kwargs={}):
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
        y = self.get_average_I(I0_normalized=I0_normalized)
        
        if x is None or y is None:
            print("Error retrieving data for export.")
            return False
        
        self._export_xy(fname,x,y, kwargs)
        return True

    def _determine_load_func(self, fname):
        """Determine the appropriate load function based on the file structure."""
        with h5.File(fname, 'r') as f:
            if 'entry/data1d' in f:
                self._load_func =  self._load_azint_old
            elif 'entry/data' in f:
                self._load_func =   self._load_azint
            elif 'I' in f:
                self._load_func =   self._load_DM_old
            else:
                print("File type not recognized. Please provide a valid azimuthal integration file.")
                self._load_func =   None

    def _load_azint(self, fname):
        """Load azimuthal integration data from a nxazint HDF5 file."""
        with h5.File(fname, 'r') as f:
            default = get_nx_default(f)
            if default is None:
                print(f"File {fname} does not contain a valid azimuthal integration dataset.")
                return None, None, None, None
            signal = get_nx_signal(default)
            axis = get_nx_axes(default)[-1] # Get the last axis, which is usually the radial axis
            if signal is None or axis is None:
                print(f"File {fname} does not contain a valid azimuthal integration dataset.")
                return None, None, None, None
            x = axis[:]
            is_Q = 'q' in axis.attrs['long_name'].lower() if 'long_name' in axis.attrs else False
            I = signal[:]
            E = get_nx_energy(f)
            return x, I, is_Q, E 
        # with h5.File(fname, 'r') as f:
        #     data_group = f['entry/data']
        #     x = data_group['radial_axis'][:]
        #     I = data_group['I'][:]
        #     is_q = 'q' in data_group['radial_axis'].attrs['long_name'].lower()

        #     if 'entry/instrument/monochromator/energy' in f:
        #         E = f['entry/instrument/monochromator/energy'][()]
        #     elif 'entry/instrument/monochromator/wavelength' in f:
        #         wavelength = f['entry/instrument/monochromator/wavelength'][()]
        #         E = 12.398 / wavelength  # Convert wavelength to energy in keV
        #     else:
        #         E = None
        # return x, I, is_q, E

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
    

    def _export_xy(self, fname, x, y, kwargs={}):
        """
        Export the azimuthal integration data to a text file.  
        kwargs are passed to np.savetxt.
        """      
        np.savetxt(fname, np.column_stack((x, y)),comments='#',**kwargs)
        return True

class AuxData:
    def __init__(self,parent=None):
        self._parent = parent
        self.I0 = None

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