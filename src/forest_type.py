"""Pre-fire forest type (broadleaf/needleleaf, evergreen/deciduous) from the
Copernicus Global Land Cover product (CGLS-LC100, Collection 3), via Earth Engine.

100 m resolution, matching the CCI biomass grid, so no extra resampling-alignment
step is needed beyond what pipeline.py already does for dNBR and height.

Band "forest_type" and its legend, confirmed against the pilot fire (2020_112,
labelled "Evergreen Needleleaf forest" by the Fire Atlas, which matched class 1
being the dominant value found):
    0   Unknown
    1   Evergreen needleleaf
    2   Evergreen broadleaf
    3   Deciduous needleleaf
    4   Deciduous broadleaf
    5   Mix of forest types
    255 Not applicable (tree cover < 1%, i.e. not forest)

`unknown` (class 0) turned out to be large and recurring across fires (37.5% of the
pilot, up to 96% in one southern Africa fire). `discrete_classification`, a second
band in the same product, assigns forest sub-type independently (closed forest
111-115, open forest 121-125, canopy >70% vs 15-70% respectively; legend confirmed
against official CGLS-LC100 documentation), so a pixel `unknown` in `forest_type`
may still get a confident type from `discrete_classification`. `resolve_label`
below uses `forest_type` first, falling back to `discrete_classification` only
where `forest_type` is 0 or 255.

Still TODO:
- whether a 2020/2021 edition exists, or only up to ~2019 (if only 2019, that is
  used as "pre-fire", since forest type changes far more slowly than height or
  biomass, so one map for the whole 2020-2021 fire window should be fine)
- how much `discrete_classification` actually recovers in practice is untested;
  check the `unknown` share before/after on a few already-run fires
"""

import ee

COLLECTION = "COPERNICUS/Landcover/100m/Proba-V-C3/Global"
FOREST_TYPE_BAND = "forest_type"
DISCRETE_BAND = "discrete_classification"

FOREST_TYPE_LABELS = {
    0: "unknown",
    1: "evergreen_needleleaf",
    2: "evergreen_broadleaf",
    3: "deciduous_needleleaf",
    4: "deciduous_broadleaf",
    5: "mixed",
    255: "not_forest",
}

# closed (>70% canopy) and open (15-70%) forest collapse to the same leaf-type label;
# canopy density isn't a distinction the rest of the pipeline uses yet
DISCRETE_TO_LABEL = {
    111: "evergreen_needleleaf", 121: "evergreen_needleleaf",
    112: "evergreen_broadleaf", 122: "evergreen_broadleaf",
    113: "deciduous_needleleaf", 123: "deciduous_needleleaf",
    114: "deciduous_broadleaf", 124: "deciduous_broadleaf",
    115: "mixed", 125: "mixed",
    116: "unknown", 126: "unknown",   # "not matching any of the other definitions"
}


def _get_band_image(band, year):
    coll = ee.ImageCollection(COLLECTION).filterDate(f"{year}-01-01", f"{year}-12-31")
    n = coll.size().getInfo()
    if n == 0:
        raise RuntimeError(f"no CGLS-LC100 image for {year}; check available years in the EE catalog")
    return coll.first().select(band)


def get_forest_type_image(year=2019):
    return _get_band_image(FOREST_TYPE_BAND, year)


def get_discrete_image(year=2019):
    return _get_band_image(DISCRETE_BAND, year)


def _download_band(image, aoi, uid, band_name, year, local_dir, scale):
    import os
    import geemap

    img = image.clip(aoi)
    os.makedirs(local_dir, exist_ok=True)
    out_path = os.path.join(local_dir, f"{band_name}_{uid}.tif")
    geemap.ee_export_image(img, filename=out_path, scale=scale, region=aoi, file_per_band=False)
    return out_path


def download_forest_type(aoi, uid, year=2019, local_dir="../data/forest_type", scale=100):
    """Direct download (not a batch export): a single categorical band for one year
    is cheap enough that this should avoid the "User memory limit exceeded" error
    the dNBR compositing hit. If it still fails on a larger AOI, fall back to the
    same ee.batch.Export.image.toCloudStorage pattern used in severity.py.
    """
    return _download_band(get_forest_type_image(year), aoi, uid, "forest_type", year, local_dir, scale)


def download_discrete(aoi, uid, year=2019, local_dir="../data/forest_type", scale=100):
    return _download_band(get_discrete_image(year), aoi, uid, "discrete", year, local_dir, scale)


def resolve_label(forest_type_code, discrete_code):
    """Combine the two bands into one label per cell: `forest_type` first, falling
    back to `discrete_classification` only where `forest_type` is unknown (0) or
    not forest (255). Vectorised (works on numpy arrays, not just scalars).
    """
    import numpy as np
    import pandas as pd

    primary = pd.Series(forest_type_code).map(FOREST_TYPE_LABELS)
    needs_fallback = primary.isin(["unknown", "not_forest"])
    fallback = pd.Series(discrete_code).map(DISCRETE_TO_LABEL).fillna("not_forest")
    resolved = primary.where(~needs_fallback, fallback)
    return resolved.to_numpy()
