"""Pre-fire canopy height (GLAD, Potapov et al. 2019), picking the right continental
mosaic for a fire's location.

Only NAM is confirmed (it's the one already downloaded and used for the pilot).
To add the others, visit the directory listing at
https://glad.geog.umd.edu/Potapov/Forest_height_2019/ and confirm the exact
filenames and bounding boxes before adding entries below, rather than guessing them.
"""

CONTINENT_MOSAICS = {
    "NAM": {
        "url": "https://glad.geog.umd.edu/Potapov/Forest_height_2019/Forest_height_2019_NAM.tif",
        "bounds": (-180, 5, -30, 75),   # rough, not the raster's exact extent; good enough to pick a mosaic
    },
    # "SAM": {...},
    # "EUR": {...},
    # "AFR": {...},
    # "ASIA": {...},
    # "AUS": {...},
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
