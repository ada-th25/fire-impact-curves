"""Generic helpers for reading a windowed array from a raster and reprojecting
one raster's array onto another raster's grid. Pulled out of the pilot notebook
so every fire can reuse the same alignment logic instead of copy-pasting it.
"""

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject
from rasterio.windows import from_bounds


def read_window(path, bounds, masked=True):
    """Read the sub-array of `path` covering `bounds` (w, s, e, n in the raster's CRS).

    Returns (array, transform, crs) for just that window, rounded to whole pixels.
    """
    w, s, e, n = bounds
    with rasterio.open(path) as src:
        win = from_bounds(w, s, e, n, src.transform).round_offsets().round_lengths()
        arr = src.read(1, window=win, masked=masked)
        if masked:
            arr = arr.astype("float64").filled(np.nan)
        transform = src.window_transform(win)
        return arr, transform, src.crs


def reproject_to_grid(arr, src_transform, src_crs, dst_shape, dst_transform, dst_crs,
                       resampling=Resampling.average, nodata_below=None):
    """Resample `arr` onto a different grid (e.g. 30 m dNBR onto a 100 m biomass grid).

    `nodata_below`, if set, replaces output values below that threshold with NaN
    after reprojecting (useful when NaNs had to be filled with a sentinel before
    reprojecting, since `reproject` does not handle NaN source pixels well).
    """
    out = np.zeros(dst_shape, dtype="float32")
    reproject(
        arr.astype("float32"), out,
        src_transform=src_transform, src_crs=src_crs,
        dst_transform=dst_transform, dst_crs=dst_crs,
        resampling=resampling,
    )
    if nodata_below is not None:
        out[out < nodata_below] = np.nan
    return out


def pad_bounds(bounds, pad):
    w, s, e, n = bounds
    return (w - pad, s - pad, e + pad, n + pad)
