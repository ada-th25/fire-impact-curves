"""Fire severity (dNBR) from Sentinel-2 via Earth Engine.

Requires ee.Authenticate() + ee.Initialize(project=<project ID, not display name>)
to have already been run in the calling notebook. See README "Infrastructure" for
the project ID, registration and permission requirements.
"""

import os
import subprocess

import ee

GCS_BUCKET = "tree-fire-510209-data"
GCS_PREFIX = "fire-impact-curves/data/severity"


def mask_s2_clouds(img):
    qa = img.select("QA60")
    mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    return img.updateMask(mask).divide(10000)


def _nbr(img):
    return img.normalizedDifference(["B8", "B12"]).rename("NBR")


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
    return _nbr(coll.median()), n


def build_dnbr(aoi, pre_start, pre_end, post_start, post_end):
    """Pre/post composite dNBR = NBR_pre - NBR_post, clipped to `aoi`.

    `pre_start`/`pre_end` should span a clear window before the fire started;
    `post_start`/`post_end` the same season one year later (see README Section 9
    on why same-season is used, and why dNBR near 0 at a burn's edge can still be
    unreliable due to regrowth).
    """
    nbr_pre, n_pre = _composite(aoi, pre_start, pre_end)
    nbr_post, n_post = _composite(aoi, post_start, post_end)
    print(f"pre {pre_start}..{pre_end}: {n_pre} images; post {post_start}..{post_end}: {n_post} images")
    return nbr_pre.subtract(nbr_post).rename("dNBR").clip(aoi)


def export_dnbr(dnbr_image, uid, aoi, scale=30, max_pixels=1e9):
    """Start a batch export of `dnbr_image` to GCS. Direct getDownloadURL/geemap
    download fails with "User memory limit exceeded" for an AOI and compositing job
    this size, so this always goes through a batch export (takes ~10-15 min).

    Returns the started ee.batch.Task; poll with task.active()/task.status().
    """
    task = ee.batch.Export.image.toCloudStorage(
        image=dnbr_image,
        description=f"dnbr_{uid}",
        bucket=GCS_BUCKET,
        fileNamePrefix=f"{GCS_PREFIX}/dnbr_{uid}",
        region=aoi,
        scale=scale,
        maxPixels=max_pixels,
    )
    task.start()
    return task


def download_dnbr(uid, local_dir="../data/severity"):
    """Pull a completed export down onto the instance via gsutil. Call only after
    task.status()["state"] == "COMPLETED".
    """
    os.makedirs(local_dir, exist_ok=True)
    out_path = os.path.join(local_dir, f"dnbr_{uid}.tif")
    src = f"gs://{GCS_BUCKET}/{GCS_PREFIX}/dnbr_{uid}.tif"
    subprocess.run(["gsutil", "cp", src, out_path], check=True)
    return out_path
