"""Generic helpers for reading a windowed array from a raster and reprojecting
one raster's array onto another raster's grid. Pulled out of the pilot notebook
so every fire can reuse the same alignment logic instead of copy-pasting it.
"""

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds


def read_window(path, bounds, masked=True, bounds_crs="EPSG:4326", band=1):
    """Read the sub-array of `path` covering `bounds` (w, s, e, n, in `bounds_crs`,
    EPSG:4326/lon-lat by default, which is what every bounds tuple in this project
    is computed in). `bounds` is reprojected into the raster's own CRS first, so
    this works regardless of what CRS the file itself happens to be in (the CCI/GLAD/
    dNBR files are all EPSG:4326, but an Earth Engine export, e.g. forest_type, can
    come back in something else, like EPSG:3857 - using the lon/lat bounds directly
    against such a file's transform silently produces an empty, ~0x0 window).

    `band` selects which band to read (1-indexed, rasterio convention), for
    multi-band files such as the dNBR+RBR severity export.

    Returns (array, transform, crs) for just that window, rounded to whole pixels.
    """
    with rasterio.open(path) as src:
        w, s, e, n = transform_bounds(bounds_crs, src.crs, *bounds)
        win = from_bounds(w, s, e, n, src.transform).round_offsets().round_lengths()
        arr = src.read(band, window=win, masked=masked)
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
