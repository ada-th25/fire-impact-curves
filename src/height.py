"""Pre-fire canopy height (GLAD, Potapov et al. 2019), picking the right continental
mosaic for a fire's location.

Filenames confirmed against the directory listing at
https://glad.geog.umd.edu/Potapov/Forest_height_2019/ (there is no separate EUR file;
Europe falls inside NAFR/NASIA's bounds).

`bounds` below are each mosaic's REAL on-disk extent (confirmed via `rasterio.open`
against the live URL for all seven files), not a rough/generous routing guess. An
earlier version used generous, overlapping boxes on the assumption that "picking
either neighbouring mosaic for a borderline fire gives the same underlying data
where they overlap" - this was wrong: NAM's routing box claimed lat 5-75 but its
real data only covers lat ~13-52, so fires at ~10N (genuinely SAM's territory, SAM
real top is ~13N) were silently misrouted to NAM and read a window entirely outside
its actual raster, producing a 0-height array deep inside reprojection with a
cryptic GDAL error ("Invalid dataset dimensions: W x 0"), not caught until a batch
of 216 fires surfaced it (56 failures, of which most were this misrouting, not a
download problem). Using real bounds fixes the misrouted cases and ensures a
genuinely out-of-coverage fire (e.g. >52N, the real global GLAD limit, see README
"Known issues" #4, boreal limitation) raises a clear error immediately below,
rather than failing silently later.
"""

_BASE = "https://glad.geog.umd.edu/Potapov/Forest_height_2019/Forest_height_2019_{code}.tif"

CONTINENT_MOSAICS = {
    "NAM":   {"url": _BASE.format(code="NAM"),   "bounds": (-161.1, 12.9, -51.9, 52.1)},
    "SAM":   {"url": _BASE.format(code="SAM"),   "bounds": (-88.1, -56.1, -33.9, 13.1)},
    "NAFR":  {"url": _BASE.format(code="NAFR"),  "bounds": (-26.1, 9.9, 63.1, 52.1)},
    "SAFR":  {"url": _BASE.format(code="SAFR"),  "bounds": (-15.1, -35.1, 51.1, 10.1)},
    "NASIA": {"url": _BASE.format(code="NASIA"), "bounds": (62.9, 24.9, 159.1, 52.1)},
    "SASIA": {"url": _BASE.format(code="SASIA"), "bounds": (65.9, -11.1, 168.1, 25.1)},
    "AUS":   {"url": _BASE.format(code="AUS"),   "bounds": (111.9, -48.1, 180.1, -10.9)},
}


def height_mosaic_for(lon, lat):
    """Return the mosaic URL covering (lon, lat), or raise if none covers it (e.g.
    genuinely beyond GLAD's ~52S-52N global coverage, the boreal limitation).
    """
    for code, info in CONTINENT_MOSAICS.items():
        w, s, e, n = info["bounds"]
        if w <= lon <= e and s <= lat <= n:
            return info["url"]
    raise ValueError(
        f"no height mosaic covers ({lon}, {lat}) - likely beyond GLAD's real coverage "
        "(~52S-52N, see README known issue #4, boreal limitation), not a missing config entry"
    )
