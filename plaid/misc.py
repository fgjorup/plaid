# -*- coding: utf-8 -*-
"""
plaid - plaid looks at integrated data
F.H. Gjørup 2025-2026
Aarhus University, Denmark
MAX IV Laboratory, Lund University, Sweden

This module provides functions for miscellaneous calculations related to diffraction data,
including conversions between q and 2theta.
"""
import numpy as np

HC = 12.3984193  # Planck constant times speed of light in keV·Å

def q_to_tth(q, E):
    """Convert q to 2theta."""
    # Convert 2theta to radians
    wavelength = HC / E
    tth = 2 * np.degrees(np.arcsin(q * wavelength / (4 * np.pi)))
    return tth

def tth_to_q(tth, E):
    """Convert 2theta to q."""
    # Convert 2theta to radians
    wavelength = HC / E
    q = (4 * np.pi / wavelength) * np.sin(np.radians(tth) / 2)
    return q

def d_to_q(d):
    """Convert d-spacing to q."""
    return 2 * np.pi / d

def q_to_d(q):
    """Convert q to d-spacing."""
    return 2 * np.pi / q

def d_to_tth(d, E):
    """Convert d-spacing to 2theta."""
    wavelength = HC / E
    tth = 2 * np.degrees(np.arcsin(wavelength / (2 * d)))
    return tth

def tth_to_d(tth, E):
    """Convert 2theta to d-spacing."""
    wavelength = HC / E
    d = wavelength / (2 * np.sin(np.radians(tth) / 2))
    return d


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

def average_blocks(arr, reduction_factor=2, axes=(0,)):
    """
    Reduce a numpy array along multiple axes by averaging non-overlapping blocks of the same size.
    If the size along any axis is not divisible by reduction_factor, the last entries are dropped.

    Parameters
    ----------
    arr : np.ndarray
        Input array.
    reduction_factor : int
        Number of adjacent entries to average along each axis.
    axes : int or tuple of int
        Axes along which to average.

    Returns
    -------
    np.ndarray
        Reduced array.
    """
    if reduction_factor is None or reduction_factor <= 1:
        return arr
    arr = np.asarray(arr)
    if not hasattr(axes, '__iter__'):
        axes = (axes,)
    for axis in axes:
        if axis < 0 or axis >= arr.ndim:
            raise ValueError(f"Axis {axis} out of bounds for array of dimension {arr.ndim}")
    for axis in sorted(axes):
        n = arr.shape[axis]
        rf = min(reduction_factor, n)
        trimmed = n - (n % rf)
        if trimmed != n:
            slc = [slice(None)] * arr.ndim
            slc[axis] = slice(0, trimmed)
            arr = arr[tuple(slc)]
        shape = list(arr.shape)
        new_shape = shape[:axis] + [shape[axis] // rf, rf] + shape[axis+1:]
        arr = arr.reshape(new_shape)
        arr = arr.mean(axis=axis+1)
    return arr

if __name__ == "__main__":  
    pass