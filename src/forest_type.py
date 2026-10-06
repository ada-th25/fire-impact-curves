"""Pre-fire forest type (broadleaf/needleleaf, evergreen/deciduous) from the
Copernicus Global Land Cover product (CGLS-LC100, Collection 3), via Earth Engine.

100 m resolution, matching the CCI biomass grid, so no extra resampling-alignment
step is needed beyond what pipeline.py already does for dNBR and height.

TODO, not yet verified (check against the Earth Engine catalog page for
COPERNICUS/Landcover/100m/Proba-V-C3/Global before relying on this):
- the exact band name for the forest-type layer (assumed "discrete_classification"
  or "forest_type" below, confirm which)
- the value legend (which integers mean evergreen/deciduous x broadleaf/needleleaf)
- whether a 2020/2021 edition exists, or only up to ~2019 (if so, 2019 is used as
  "pre-fire", since forest type changes far more slowly than height or biomass)
"""

import ee

COLLECTION = "COPERNICUS/Landcover/100m/Proba-V-C3/Global"
BAND = "forest_type"   # TODO: confirm exact band name against the EE catalog


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
