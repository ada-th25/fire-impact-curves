"""Pre-fire canopy height (GLAD, Potapov et al. 2019), picking the right continental
mosaic for a fire's location.

Filenames confirmed against the directory listing at
https://glad.geog.umd.edu/Potapov/Forest_height_2019/ (there is no separate EUR file;
Europe falls inside NAFR/NASIA's bounds). GLAD's own coverage is roughly 52S-52N
regardless of mosaic bounds (see README "Known issues" #4, boreal limitation); the
`bounds` below are rough boxes just for picking the right file, not the raster's
exact extent, deliberately generous/overlapping is fine since picking either
neighbouring mosaic for a borderline fire gives the same underlying data where they
overlap.
"""

_BASE = "https://glad.geog.umd.edu/Potapov/Forest_height_2019/Forest_height_2019_{code}.tif"

CONTINENT_MOSAICS = {
    "NAM":   {"url": _BASE.format(code="NAM"),   "bounds": (-180, 5, -30, 75)},
    "SAM":   {"url": _BASE.format(code="SAM"),   "bounds": (-90, -60, -30, 15)},
    "NAFR":  {"url": _BASE.format(code="NAFR"),  "bounds": (-20, 0, 55, 75)},    # also covers Europe
    "SAFR":  {"url": _BASE.format(code="SAFR"),  "bounds": (-20, -40, 55, 0)},
    "NASIA": {"url": _BASE.format(code="NASIA"), "bounds": (55, 35, 180, 75)},
    "SASIA": {"url": _BASE.format(code="SASIA"), "bounds": (55, -12, 180, 35)},
    "AUS":   {"url": _BASE.format(code="AUS"),   "bounds": (110, -50, 180, -5)},
}


def height_mosaic_for(lon, lat):
    """Return the mosaic URL covering (lon, lat), or raise if none is configured yet."""
    for code, info in CONTINENT_MOSAICS.items():
        w, s, e, n = info["bounds"]
        if w <= lon <= e and s <= lat <= n:
            return info["url"]
    raise ValueError(
        f"no height mosaic configured for ({lon}, {lat}); add it to CONTINENT_MOSAICS "
        "after confirming the filename at https://glad.geog.umd.edu/Potapov/Forest_height_2019/"
    )
