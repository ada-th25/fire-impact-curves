"""Pre/post-fire above-ground biomass (ESA CCI Biomass v6.0), via Earth Engine
rather than manually downloaded tiles.

Replaces the earlier approach (wget-ing N40W130_*.tif per year) which required
knowing, per fire, which 10x10 degree CCI tile(s) it falls in, and handling fires
that straddle a tile boundary. The same product is available as a single global
Earth Engine ImageCollection, one image per year, so a fire's AOI is just clipped
out of it directly, same pattern as severity.py and forest_type.py.

Confirmed asset id: ESA/CCI/Above_Ground_Biomass/V6_0 (official EE catalog).
Band name confirmed as "agb" (lowercase; the collection also has "agb_sd" for the
per-pixel standard deviation), from the error EE itself returns when a wrong band
name is requested: "Available bands: [agb, agb_sd]".
"""

import ee

COLLECTION = "ESA/CCI/Above_Ground_Biomass/V6_0"
BAND = "agb"
GCS_BUCKET = "tree-fire-510209-data"
GCS_PREFIX = "fire-impact-curves/data/cci_agb_ee"


def get_agb_image(year):
    coll = ee.ImageCollection(COLLECTION).filterDate(f"{year}-01-01", f"{year}-12-31")
    n = coll.size().getInfo()
    if n == 0:
        raise RuntimeError(f"no CCI AGB image for {year}; check available years in the EE catalog")
    return coll.first().select(BAND)


def export_agb(image, uid, year, aoi, scale=100, max_pixels=1e9):
    """Batch export to GCS, same pattern as severity.py/forest_type.py.

    Replaces the earlier direct-thumbnail download (`geemap.ee_export_image`),
    which failed deterministically ("Invalid dataset dimensions: W x 0") for a
    non-trivial share of fires once run at scale, the same request-size limit
    already found and fixed for forest_type.py. The old download_agb's cache
    check only looked at file existence, not validity, so a corrupted file from
    an early run (when batches were small enough to rarely hit the limit) kept
    being silently reused on every later retry.
    """
    task = ee.batch.Export.image.toCloudStorage(
        image=image.clip(aoi),
        description=f"agb_{uid}_{year}",
        bucket=GCS_BUCKET,
        fileNamePrefix=f"{GCS_PREFIX}/agb_{uid}_{year}",
        region=aoi,
        scale=scale,
        maxPixels=max_pixels,
    )
    task.start()
    return task


def download_agb_from_bucket(uid, year, local_dir="../data/cci_agb_ee"):
    """Pull a completed export down via gsutil. Call only after
    task.status()["state"] == "COMPLETED".
    """
    import os
    import subprocess

    os.makedirs(local_dir, exist_ok=True)
    out_path = os.path.join(local_dir, f"agb_{uid}_{year}.tif")
    src = f"gs://{GCS_BUCKET}/{GCS_PREFIX}/agb_{uid}_{year}.tif"
    subprocess.run(["gsutil", "cp", src, out_path], check=True)
    return out_path


def download_agb(aoi, uid, year, local_dir="../data/cci_agb_ee", scale=100):
    """Deprecated single-shot thumbnail download, kept only for any old caller
    that still imports it directly. Prefer export_agb/download_agb_from_bucket
    (see export_agb's docstring for why).
    """
    import os
    import geemap

    img = get_agb_image(year).clip(aoi)
    os.makedirs(local_dir, exist_ok=True)
    out_path = os.path.join(local_dir, f"agb_{uid}_{year}.tif")
    if not os.path.exists(out_path):
        geemap.ee_export_image(img, filename=out_path, scale=scale, region=aoi, file_per_band=False)
    else:
        print(f"reusing cached AGB {year} for {uid}: {out_path}")
    return out_path
