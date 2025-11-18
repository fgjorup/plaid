# -*- coding: utf-8 -*-
"""
plaid - plaid looks at integrated data
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

def get_divisors(x):
    """Get all divisors of an integer x."""
    divisors = []
    for i in range(1,int(x**0.5)+1):
        if x%i == 0:
            divisors.append(i)
            divisors.append(x//i)
    return sorted(list(divisors))

def get_map_shape_and_indices(y,x):
    """Get pixel indices and map shape from absolute y (fast) and  x (slow) positions."""
    def guessRes(x,decimals=3):
        """Guess the resolution based on the median of the absolute steps"""
        dx = np.abs(np.diff(x))
        return np.round(np.median(dx[dx>0.0001]),decimals)

    x_res = guessRes(x)
    y_res = guessRes(y)
    x_index = np.round((x-x.min())/x_res).astype(int)
    y_index = np.round((y-y.min())/y_res).astype(int)
    # guess the map shape from the indices
    map_shape = (x_index.max()+1,y_index.max()+1)

    pixel_indices = np.arange(np.prod(map_shape)).reshape(map_shape)
    pixel_indices = list(pixel_indices[x_index,y_index])

    return map_shape, pixel_indices

if __name__ == "__main__":
    pass