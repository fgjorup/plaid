# -*- coding: utf-8 -*-
"""
plaid - Plot Azimuthally Integrated Data
F.H. Gjørup 2025
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides functions for miscellaneous calculations related to diffraction data,
including conversions between q and 2theta.
"""
import numpy as np


def q_to_tth(q, E):
    """Convert q to 2theta."""
    # Convert 2theta to radians
    wavelength = 12.398 / E
    tth = 2 * np.degrees(np.arcsin(q * wavelength / (4 * np.pi)))
    return tth

def tth_to_q(tth, E):
    """Convert 2theta to q."""
    # Convert 2theta to radians
    wavelength = 12.398 / E
    q = (4 * np.pi / wavelength) * np.sin(np.radians(tth) / 2)
    return q

if __name__ == "__main__":
    pass