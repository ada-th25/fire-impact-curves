"""NDVI (vegetation greenness) from Sentinel-2 via Earth Engine, pre/post fire.

Built to test a specific question (README discussion): does NDVI track carbon
loss the way the biomass data does, or does it recover faster than carbon stock
actually does, since NDVI measures leaf greenness, not biomass, and post-fire
regrowth (grass, shrubs, resprouting) can green up long before the mature trees
that held most of the carbon do. This module only computes NDVI; comparing it
against the existing biomass-based loss is done separately, the same way the
Artio biomass comparison was done, not inside this module.

Mirrors severity.py's composite/export/download pattern exactly (same cloud
mask, same batch-export-to-GCS approach, same explicit toFloat() cast) rather
than introducing a new convention.

Requires ee.Authenticate() + ee.Initialize(project=<project ID>) to have
already been run in the calling notebook.
"""

import os
import subprocess

import ee

from src.severity import mask_s2_clouds

GCS_BUCKET = "tree-fire-510209-data"
GCS_PREFIX = "fire-impact-curves/data/ndvi"


def _ndvi(img):
    return img.normalizedDifference(["B8", "B4"]).rename("NDVI")


def _composite(aoi, start, end, max_cloud_pct=30):
    coll = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(start, end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", max_cloud_pct))
        .map(mask_s2_clouds)
    )
    n = coll.size().getInfo()
    if n == 0:
        raise RuntimeError(f"no cloud-free Sentinel-2 images for {start}..{end} in this AOI")
    return _ndvi(coll.median()), n


def build_ndvi(aoi, pre_start, pre_end, post_start, post_end):
    """Pre/post composite, returning a 2-band image: NDVI_pre, NDVI_post, clipped
    to `aoi`. Use the SAME pre_start/pre_end/post_start/post_end windows already
    used for that fire's dNBR, so this is measuring the same before/after period,
    not a different comparison.

    Loss is computed downstream from these two bands (NDVI_pre - NDVI_post, or
    normalised by NDVI_pre), not inside this function, to keep this module
    symmetric with how biomass before/after is handled.
    """
    ndvi_pre, n_pre = _composite(aoi, pre_start, pre_end)
    ndvi_post, n_post = _composite(aoi, post_start, post_end)
    print(f"pre {pre_start}..{pre_end}: {n_pre} images; post {post_start}..{post_end}: {n_post} images")
    # explicit toFloat() on both bands: normalizedDifference should already return
    # Float32 for both, but severity.py hit a real, confusing export failure
    # ("Exported bands must have compatible data types") from an operation
    # silently promoting one band to Float64 - cheap insurance against the same
    # class of bug here, not assumed impossible just because it looks symmetric.
    return (
        ndvi_pre.rename("NDVI_pre").toFloat()
        .addBands(ndvi_post.rename("NDVI_post").toFloat())
        .clip(aoi)
    )


def export_ndvi(ndvi_image, uid, aoi, scale=30, max_pixels=1e9):
    """Start a batch export of `ndvi_image` (NDVI_pre + NDVI_post bands) to GCS.
    Same reasoning as severity.py's export_severity: a direct download fails on
    an AOI/compositing job this size, so this always goes through a batch export
    (takes ~10-15 min).

    Returns the started ee.batch.Task; poll with task.active()/task.status().
    """
    task = ee.batch.Export.image.toCloudStorage(
        image=ndvi_image,
        description=f"ndvi_{uid}",
        bucket=GCS_BUCKET,
        fileNamePrefix=f"{GCS_PREFIX}/ndvi_{uid}",
        region=aoi,
        scale=scale,
        maxPixels=max_pixels,
    )
    task.start()
    return task


def download_ndvi(uid, local_dir="../data/ndvi"):
    """Pull a completed export down onto the instance via gsutil. Call only after
    task.status()["state"] == "COMPLETED".
    """
    os.makedirs(local_dir, exist_ok=True)
    out_path = os.path.join(local_dir, f"ndvi_{uid}.tif")
    src = f"gs://{GCS_BUCKET}/{GCS_PREFIX}/ndvi_{uid}.tif"
    subprocess.run(["gsutil", "cp", src, out_path], check=True)
    return out_path
