"""Fire severity (dNBR and RBR) from Sentinel-2 via Earth Engine.

RBR (Relativized Burn Ratio) = dNBR / (NBR_pre + 1.001), the standard refinement
of dNBR (used in later USGS/MTBS products): it normalises dNBR by how dense the
pre-fire vegetation was, so severity is more comparable across forest types with
very different baseline NBR, which plain dNBR does not correct for. Both bands
are computed and exported together (one Sentinel-2 composite step), so this is
not a second, separate Earth Engine cost on top of dNBR.

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


def build_severity(aoi, pre_start, pre_end, post_start, post_end):
    """Pre/post composite, returning a 2-band image: dNBR = NBR_pre - NBR_post,
    and RBR = dNBR / (NBR_pre + 1.001), clipped to `aoi`.

    `pre_start`/`pre_end` should span a clear window before the fire started;
    `post_start`/`post_end` the same season one year later (see README Section 9
    on why same-season is used, and why dNBR near 0 at a burn's edge can still be
    unreliable due to regrowth - the same caveat applies to RBR near 0).
    """
    nbr_pre, n_pre = _composite(aoi, pre_start, pre_end)
    nbr_post, n_post = _composite(aoi, post_start, post_end)
    print(f"pre {pre_start}..{pre_end}: {n_pre} images; post {post_start}..{post_end}: {n_post} images")
    dnbr = nbr_pre.subtract(nbr_post).rename("dNBR").toFloat()
    # toFloat(): divide() promotes to Float64, but dNBR stays Float32 - Earth
    # Engine's exporter rejects a multi-band image with mismatched band dtypes
    # ("Exported bands must have compatible data types"), so both bands must
    # match explicitly rather than relying on each band's natural output type.
    rbr = dnbr.divide(nbr_pre.add(1.001)).rename("RBR").toFloat()
    return dnbr.addBands(rbr).clip(aoi)


def export_severity(severity_image, uid, aoi, scale=30, max_pixels=1e9):
    """Start a batch export of `severity_image` (dNBR + RBR bands) to GCS. Direct
    getDownloadURL/geemap download fails with "User memory limit exceeded" for an
    AOI and compositing job this size, so this always goes through a batch export
    (takes ~10-15 min).

    A new filename prefix (`severity_`, not the old `dnbr_`), deliberately not
    reusing the old single-band dNBR-only cache from before RBR was added, to
    avoid any risk of code expecting 2 bands silently reading a stale 1-band file.

    Returns the started ee.batch.Task; poll with task.active()/task.status().
    """
    task = ee.batch.Export.image.toCloudStorage(
        image=severity_image,
        description=f"severity_{uid}",
        bucket=GCS_BUCKET,
        fileNamePrefix=f"{GCS_PREFIX}/severity_{uid}",
        region=aoi,
        scale=scale,
        maxPixels=max_pixels,
    )
    task.start()
    return task


def download_severity(uid, local_dir="../data/severity"):
    """Pull a completed export down onto the instance via gsutil. Call only after
    task.status()["state"] == "COMPLETED".
    """
    os.makedirs(local_dir, exist_ok=True)
    out_path = os.path.join(local_dir, f"severity_{uid}.tif")
    src = f"gs://{GCS_BUCKET}/{GCS_PREFIX}/severity_{uid}.tif"
    subprocess.run(["gsutil", "cp", src, out_path], check=True)
    return out_path
