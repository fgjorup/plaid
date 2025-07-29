# -*- coding: utf-8 -*-
"""
plaid - Plot Azimuthally Integrated Data
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides a class to handle reference data from CIF files.
"""

import numpy as np
import Dans_Diffraction as dans

def validate_cif(cif_file):
    """Validate the CIF file."""
    return dans.functions_crystallography.cif_check(dans.functions_crystallography.readcif(cif_file))

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



if __name__ == "__main__":
    pass