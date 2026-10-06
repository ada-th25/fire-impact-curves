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

Still TODO:
- whether a 2020/2021 edition exists, or only up to ~2019 (if only 2019, that is
  used as "pre-fire", since forest type changes far more slowly than height or
  biomass, so one map for the whole 2020-2021 fire window should be fine)
- whether to drop or keep class 0 ("Unknown") and 5 ("Mix") when grouping fires
  by forest type, since neither maps cleanly onto the Fire Atlas's own categories
"""

import ee

COLLECTION = "COPERNICUS/Landcover/100m/Proba-V-C3/Global"
BAND = "forest_type"

FOREST_TYPE_LABELS = {
    0: "unknown",
    1: "evergreen_needleleaf",
    2: "evergreen_broadleaf",
    3: "deciduous_needleleaf",
    4: "deciduous_broadleaf",
    5: "mixed",
    255: "not_forest",
}


def get_forest_type_image(year=2019):
    """One year's forest-type band, clipped to nothing (caller clips/exports)."""
    coll = ee.ImageCollection(COLLECTION).filterDate(f"{year}-01-01", f"{year}-12-31")
    n = coll.size().getInfo()
    if n == 0:
        raise RuntimeError(f"no CGLS-LC100 image for {year}; check available years in the EE catalog")
    return coll.first().select(BAND)


def download_forest_type(aoi, uid, year=2019, local_dir="../data/forest_type", scale=100):
    """Direct download (not a batch export): a single categorical band for one year
    is cheap enough that this should avoid the "User memory limit exceeded" error
    the dNBR compositing hit. If it still fails on a larger AOI, fall back to the
    same ee.batch.Export.image.toCloudStorage pattern used in severity.py.
    """
    import os
    import geemap

    img = get_forest_type_image(year).clip(aoi)
    os.makedirs(local_dir, exist_ok=True)
    out_path = os.path.join(local_dir, f"forest_type_{uid}.tif")
    geemap.ee_export_image(img, filename=out_path, scale=scale, region=aoi, file_per_band=False)
    return out_path
