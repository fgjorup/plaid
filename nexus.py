# -*- coding: utf-8 -*-
"""
plaid - Plot Azimuthally Integrated Data
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides functions to interact with NeXus HDF5 files

"""
import h5py as h5

def get_nx_entry(f):
    """Get the entry nexus group from a nexus hdf5 instance."""
    if 'entry' in f:
        return f['entry']
    elif 'NXentry' in f:
        return f['NXentry']
    else:
        return None

def get_nx_default(f):
    """Get the default nexus group from a nexus hdf5 instance."""
    entry = get_nx_entry(f)
    if entry is None:
        return None
    if 'default' in entry.attrs:
        default = entry.attrs['default']
        if default in entry:
            return entry[default]
    elif 'default' in f:
        default = f.attrs['default']
        if default in f:
            return f[default]
    return None

def get_nx_signal(gr):
    """Get the signal nexus dset from a nexus group."""
    if gr is None:
        return None
    if 'signal' in gr.attrs:
        signal = gr.attrs['signal']
        if signal in gr:
            return gr[signal]
    return None

def get_nx_axes(gr):
    """Get a list of the axes nexus dsets from a nexus group."""
    if gr is None:
        return []
    axes = []
    if 'axes' in gr.attrs:
        axes_names = gr.attrs['axes']
        for ax in axes_names:
            if ax in gr and isinstance(gr[ax], h5.Dataset):
                axes.append(gr[ax])
            else:
                axes.append(None)
    return axes
        
def get_nx_energy(f):
    """Attempt to get the energy from the nxmonochromator group in a nexus hdf5 file"""
    entry = get_nx_entry(f)
    if entry is None:
        return None
    monochromator = get_nx_monochromator(entry)
    if monochromator is None:
        return None
    if 'energy' in monochromator:
        return monochromator['energy'][()]
    elif 'wavelength' in monochromator:
        wavelength = monochromator['wavelength'][()]
        return 12.398 / wavelength  # Convert wavelength to energy in keV
# If no energy or wavelength is found, return None
    return None    

def get_nx_group(gr, name, nxclass=None):
    """Get a generic nexus group with a specific name or nxclass from a group."""
    if gr is None:
        return None
    if name in gr:
        return gr[name]
    if nxclass is not None:
        for key in gr.keys():
            if "NX_class" in gr[key].attrs and gr[key].attrs["NX_class"] == nxclass:
                return gr[key]

def get_nx_instrument(gr):
    """Get the instrument nexus group from a nexus hdf5 file."""
    return get_nx_group(gr, 'instrument', 'NXinstrument')

def get_nx_monochromator(gr):
    """Get the nxmonochromator group from a nexus hdf5 file."""
    if gr is None:
        return None
    if 'NX_class' in gr.attrs and not gr.attrs['NX_class'] == 'NXinstrument':
        # If the group is not an instrument, try to get the instrument group
        gr = get_nx_instrument(gr)
    return get_nx_group(gr, 'monochromator', 'NXmonochromator')


if __name__ == "__main__":
    pass