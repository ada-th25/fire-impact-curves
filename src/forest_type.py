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


GCS_BUCKET = "tree-fire-510209-data"
GCS_PREFIX = "fire-impact-curves/data/forest_type"


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


def build_landcover(year=2019):
    """Both bands (`forest_type`, `discrete_classification`) from the same source
    image, as one 2-band image - one Earth Engine fetch, not two.
    """
    coll = ee.ImageCollection(COLLECTION).filterDate(f"{year}-01-01", f"{year}-12-31")
    n = coll.size().getInfo()
    if n == 0:
        raise RuntimeError(f"no CGLS-LC100 image for {year}; check available years in the EE catalog")
    return coll.first().select([FOREST_TYPE_BAND, DISCRETE_BAND])


def export_landcover(image, uid, aoi, scale=100, max_pixels=1e9):
    """Batch export to GCS, same pattern as severity.py's export_severity.

    Replaces the earlier direct-thumbnail download (`geemap.ee_export_image` /
    `getPixels`), which turned out to fail deterministically ("Invalid dataset
    dimensions: W x 0") for a large, non-geography-specific share of fires once
    run at scale (56 of 216 in one batch) - a request-size limit of the thumbnail
    endpoint, not a transient error, since retrying the same fire failed with the
    exact same malformed dimensions every time. Batch export has had zero
    failures of this kind across 200+ fires for severity, so it is used here too.
    """
    task = ee.batch.Export.image.toCloudStorage(
        image=image.clip(aoi),
        description=f"landcover_{uid}",
        bucket=GCS_BUCKET,
        fileNamePrefix=f"{GCS_PREFIX}/landcover_{uid}",
        region=aoi,
        scale=scale,
        maxPixels=max_pixels,
    )
    task.start()
    return task


def download_landcover(uid, local_dir="../data/forest_type"):
    """Pull a completed export down via gsutil. Call only after
    task.status()["state"] == "COMPLETED". Returns a 2-band file: band 1 is
    `forest_type`, band 2 is `discrete_classification`.
    """
    import os
    import subprocess

    os.makedirs(local_dir, exist_ok=True)
    out_path = os.path.join(local_dir, f"landcover_{uid}.tif")
    src = f"gs://{GCS_BUCKET}/{GCS_PREFIX}/landcover_{uid}.tif"
    subprocess.run(["gsutil", "cp", src, out_path], check=True)
    return out_path


def download_forest_type(aoi, uid, year=2019, local_dir="../data/forest_type", scale=100):
    """Deprecated single-band thumbnail download, kept only for any old caller
    that still imports it directly. Prefer build_landcover/export_landcover/
    download_landcover (see their docstrings for why).
    """
    import os
    import geemap

    img = get_forest_type_image(year).clip(aoi)
    os.makedirs(local_dir, exist_ok=True)
    out_path = os.path.join(local_dir, f"forest_type_{uid}.tif")
    geemap.ee_export_image(img, filename=out_path, scale=scale, region=aoi, file_per_band=False)
    return out_path


def download_discrete(aoi, uid, year=2019, local_dir="../data/forest_type", scale=100):
    """Deprecated, see download_forest_type's docstring."""
    import os
    import geemap

    img = get_discrete_image(year).clip(aoi)
    os.makedirs(local_dir, exist_ok=True)
    out_path = os.path.join(local_dir, f"discrete_{uid}.tif")
    geemap.ee_export_image(img, filename=out_path, scale=scale, region=aoi, file_per_band=False)
    return out_path


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
