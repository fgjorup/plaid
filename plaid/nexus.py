# -*- coding: utf-8 -*-
"""
plaid - plaid looks at integrated data
F.H. Gjørup 2025-2026
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides functions to interact with NeXus HDF5 files

"""
import h5py as h5

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

def get_h5_dset_path(gr,name):
    """Utility function to get the full path of a dataset in an HDF5 file group."""
    if gr is None:
        return None
    if name in gr:
        return gr[name].name
    return None

def get_nx_entry(f,definition=None,allow_subentry=True):
    """
    Get the entry nexus group from a nexus hdf5 instance.
    If a definition is given (e.g. 'NXazint1d'), return the entry or subentry
    with the matching definition attribute. If no matching definition is found,
    return None. If allow_subentry is True, also search for subentries.
    If no definition is given, return the main entry or subentry (if allow_subentry is True).
    """

    def matching_definition(gr,definition):
        """Check if the group has a matching definition attribute. Case insensitive."""
        if 'definition' in gr:
            entry_definition = gr['definition'][()]
            if isinstance(entry_definition, bytes):
                entry_definition = entry_definition.decode('utf-8')
            if entry_definition.lower() == definition.lower():
                return True
        return False
    
    allowed_classes = ['NXentry', 'NXsubentry'] if allow_subentry else ['NXentry']
    if isinstance(f, h5.Group):
        # if f is already a group, check if it is an entry or subentry
        if 'NX_class' in f.attrs and f.attrs['NX_class'] in allowed_classes:
            # if a definition is given, check if it matches
            if definition is None or matching_definition(f,definition):
                return f
        # if the group is not an entry or subentry with the correct definition
        # or no definition was given, start from the root of the file
        f = f.file
    # if f is a file, get the entry group
    entry = get_nx_group(f, 'entry', 'NXentry')
    if entry is None:
        return None
    if definition is None or matching_definition(entry,definition):
        return entry
    if not allow_subentry:
        return None
    # check the nxentry for all nxsubentries and return the one with the correct definition
    for key in entry.keys():
        if "NX_class" in entry[key].attrs and entry[key].attrs["NX_class"] == "NXsubentry":
            if matching_definition(entry[key],definition):
                return entry[key]
    # if no valid definition was found, use the group names as a fallback
    for key in entry.keys():
        if "NX_class" in entry[key].attrs and entry[key].attrs["NX_class"] == "NXsubentry":
            if key.lower() in definition.lower():
                return entry[key]
    # else return None
    return None

def get_nx_monitor(gr):
    """Get the monitor nexus group from a nexus hdf5 file."""
    gr = get_nx_entry(gr)
    return get_nx_group(gr, 'monitor', 'NXmonitor')

def get_nx_sample(gr):
    """Get the sample nexus group from a nexus hdf5 file."""
    gr = get_nx_entry(gr)
    return get_nx_group(gr, 'sample', 'NXsample')

def get_nx_transformations(gr):
    """Get the transformations nexus group from a nexus hdf5 file."""
    gr = get_nx_sample(gr)
    return get_nx_group(gr, 'transformations', 'NXtransformations')

def get_nx_instrument(gr):
    """Get the instrument nexus group from a nexus hdf5 file."""
    if gr is None:
        return None
    # check if the group is already an instrument
    if 'NX_class' in gr.attrs and gr.attrs['NX_class'] == 'NXinstrument':
        return gr
    gr = get_nx_entry(gr)
    return get_nx_group(gr, 'instrument', 'NXinstrument')

def get_nx_monochromator(gr):
    """Get the nxmonochromator group from a nexus hdf5 file."""
    gr = get_nx_instrument(gr)
    return get_nx_group(gr, 'monochromator', 'NXmonochromator')

def get_nx_source(gr):
    """Get the source nexus group from a nexus hdf5 file."""
    gr = get_nx_instrument(gr)
    return get_nx_group(gr, 'source', 'NXsource')

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
    if "NX_class" in gr.attrs and not gr.attrs["NX_class"] == "NXdata":
        gr = get_nx_default(gr)
    if gr is None:
        return None
    if 'signal' in gr.attrs:
        signal = gr.attrs['signal']
        if signal in gr:
            return gr[signal]
    return None

def get_nx_signal_errors(gr):
    """Get the signal errors nexus dset from a nexus group."""
    if gr is None:
        return None
    signal = get_nx_signal(gr)
    if signal is None:
        return None
    error_name = signal.name + '_errors'
    if error_name in gr:
        return gr[error_name]
    return None

def get_nx_axes(gr):
    """Get a list of the axes nexus dsets from a nexus group."""
    if gr is None:
        return []
    if "NX_class" in gr.attrs and not gr.attrs["NX_class"] == "NXdata":
        gr = get_nx_default(gr)
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

def get_instrument_name(gr):
    """Get the instrument name from a nexus file and return it as a string."""
    instrument = get_nx_instrument(gr)
    if instrument is not None and 'name' in instrument:
        name =  instrument['name'][()]
        # Check if the name is a bytes object and decode it
        if isinstance(name, bytes):
            return name.decode('utf-8')
        return name
    return None

def get_source_name(gr):
    """Get the source name from a nexus file and return it as a string."""
    source = get_nx_source(gr)
    if source is not None and 'name' in source:
        name = source['name'][()]
        # Check if the name is a bytes object and decode it
        if isinstance(name, bytes):
            return name.decode('utf-8')
        return name
    return None

def get_translations_from_nx_transformations(gr):
    """
    Get the translations from the nxtransformations group in a nexus hdf5 file.
    Use the 'transformation_type' attribute to identify translations, and the
    'vector' attribute to identify the axis.
    Returns a dictionary with keys 'x', 'y', 'z' and values as the corresponding datasets.
    """
    transformations = get_nx_transformations(gr)
    if transformations is not None:
        translations = {}
        for name, dset in transformations.items():
            if hasattr(dset, 'attrs') and "transformation_type" in dset.attrs:
                v = dset.attrs.get("vector",None)
                if v is None:
                    continue
                name = [["x","y","z"][i] for i, comp in enumerate(v) if comp == 1][0]
                translations[name] = dset[:]
    return translations

if __name__ == "__main__":
    pass