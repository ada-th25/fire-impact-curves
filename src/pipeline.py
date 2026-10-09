"""Per-fire pipeline: align height, biomass and dNBR onto one 100 m grid and
return a cell-level table ready to bin into severity x height x forest-type curves.

This is the refactored version of the manual steps in notebooks/data.ipynb
(cells under "Fire severity (dNBR) for the pilot fire" onward). Run it once per
fire in the stratified sample, then concatenate the results.

Biomass now comes from Earth Engine (ESA/CCI/Above_Ground_Biomass/V6_0), not manually
downloaded tiles, so there is no tile-boundary problem for AGB any more. Height still
uses a continental GLAD mosaic looked up by the fire's location (src/height.py), only
North America is confirmed so far, see that module's docstring.

Still TODO, not solved by this module yet (see README "Known issues"):
- height.py's CONTINENT_MOSAICS only has NAM confirmed; a fire outside North America
  will raise until the right mosaic URL is added there.
- The dNBR < 0.1 edge-regrowth exclusion (README Section 9) was tuned on one fire
  in one biome; it may need revisiting per biome once more fires are run.
- GLAD height looks unreliable on steep terrain (README "Known issues" #8); height
  is included here but should not be trusted for curves yet.
"""

import os

import numpy as np
import pandas as pd
from rasterio.warp import Resampling

from .biomass import download_agb
from .fires import inner_burn_area, load_fire
from .forest_type import download_discrete, download_forest_type, resolve_label
from .grids import pad_bounds, read_window, reproject_to_grid
from .height import height_mosaic_for
from .severity import build_severity, download_severity, export_severity

DNBR_DROP_BELOW = 0.1   # see README Section 9
SEVERITY_BINS = [DNBR_DROP_BELOW, 0.27, 0.66, 2.0]
SEVERITY_LABELS = ["mild", "moderate", "severe"]


def submit_severity_tasks(fire_configs, pad=0.15):
    """Phase 1 of a batch run: submit every fire's severity (dNBR + RBR) export to
    Earth Engine at once, rather than one fire at a time inside build_cell_table.
    Earth Engine runs each export independently on its own servers, so N fires
    submitted together take roughly as long as 1, not N times as long - this is
    what makes running "many fires" (per the roadmap/supervisor) practical instead
    of an all-day wait.

    `fire_configs` is the same list of dicts passed to build_cell_table (must
    include uid, pre_fire_window, post_fire_window). Returns a dict
    {uid: {"task": Task or None, "severity_path": str or None}} - `task` is None
    and `severity_path` is already set for any fire whose severity file is already
    cached locally. Pass this dict's per-uid entry to build_cell_table's
    `severity_path=` after calling `wait_and_download_severity` on it.

    Note: this uses a new filename prefix (`severity_`), not the old `dnbr_`-only
    cache from before RBR was added, so every fire needs a fresh export here even
    if its old dNBR-only file is still on disk (that file only has one band, not
    the two RBR needs - see severity.py).
    """
    submitted = {}
    for cfg in fire_configs:
        uid = cfg["uid"]
        severity_path = f"../data/severity/severity_{uid}.tif"
        if os.path.exists(severity_path):
            print(f"reusing cached severity for {uid}: {severity_path}")
            submitted[uid] = {"task": None, "severity_path": severity_path}
            continue
        try:
            fire = load_fire(uid)
            bounds = pad_bounds(fire.total_bounds, pad)
            aoi_ee = _ee_rectangle(bounds)
            severity_image = build_severity(aoi_ee, *cfg["pre_fire_window"], *cfg["post_fire_window"])
            task = export_severity(severity_image, uid, aoi_ee)
            print(f"submitted severity export for {uid}")
            submitted[uid] = {"task": task, "severity_path": None}
        except Exception as e:
            # one fire failing (e.g. an ambiguous uid, see fires.py) must not lose
            # the Task handles for every other fire already submitted this run
            print(f"{uid} FAILED to submit: {e}")
            submitted[uid] = {"task": None, "severity_path": None, "error": str(e)}
    return submitted


def wait_and_download_severity(submitted, poll_seconds=30):
    """Phase 2: wait for every submitted task together (polling all of them, not
    one at a time), downloading each as soon as it completes. Mutates and returns
    `submitted` with `severity_path` filled in for every fire.
    """
    import time

    pending = {uid: s for uid, s in submitted.items() if s["task"] is not None}
    while pending:
        done = []
        for uid, s in pending.items():
            if not s["task"].active():
                status = s["task"].status()
                if status["state"] != "COMPLETED":
                    # one fire's export failing (e.g. a transient EE error, or a
                    # bug like the dNBR/RBR dtype mismatch) must not stop polling
                    # or lose the severity_path already downloaded for every
                    # other fire in this batch
                    print(f"{uid} FAILED: {status}")
                    s["error"] = status
                else:
                    s["severity_path"] = download_severity(uid)
                    print(f"{uid}: severity ready")
                done.append(uid)
        for uid in done:
            pending.pop(uid)
        if pending:
            time.sleep(poll_seconds)
    return submitted


def build_cell_table(
    uid,
    utm_epsg,             # fire's local UTM zone, for the inner-burn buffer
    pre_fire_window,      # (start, end) strings, season before the fire started
    post_fire_window,     # (start, end) strings, same season one year later
    agb_before_year,
    agb_after_years,      # list of years to compute loss against, e.g. [2021, 2022]
    height_path=None,     # override the auto-looked-up GLAD mosaic if needed
    pad=0.15,
    min_agb_before=10,
    forest_type_year=2019,
    severity_path=None,   # pass a path already fetched via submit_severity_tasks/wait_and_download_severity
    fire_start_end=None,  # (start_date, end_date) of the fire itself; required only if firms_map_key is set
    firms_map_key=None,   # set to also fetch brightness_temp (src/temperature.py); off by default
):
    """Returns a per-cell DataFrame for one fire: dnbr, rbr, severity, height,
    forest_type, and biomass loss against each year in `agb_after_years`. Earth
    Engine must already be initialised (ee.Authenticate() + ee.Initialize(project=...))
    before calling.

    Biomass and forest type are fetched from Earth Engine directly (any fire,
    anywhere); height still needs a continental mosaic looked up by location
    (src/height.py), and raises if that fire's continent isn't configured yet.

    Pass `firms_map_key` (and `fire_start_end`) to also fetch brightness
    temperature (src/temperature.py) as an extra `brightness_temp` column,
    alongside `dnbr`, not replacing it - off by default, so existing callers
    are unaffected.
    """
    fire = load_fire(uid)
    bounds = pad_bounds(fire.total_bounds, pad)
    inner = inner_burn_area(fire, utm_epsg=utm_epsg)
    aoi_ee = _ee_rectangle(bounds)

    agb, tr_ref, crs_ref, shape = {}, None, None, None
    agb_years = sorted(set([agb_before_year, *agb_after_years]))
    for yr in agb_years:
        agb_path = download_agb(aoi_ee, uid, yr)
        agb[yr], tr_ref, crs_ref = read_window(agb_path, bounds)
        shape = agb[yr].shape

    from rasterio.features import rasterize

    mask_inner = rasterize(
        [(g, 1) for g in inner.geometry], out_shape=shape,
        transform=tr_ref, fill=0, dtype="uint8",
    ).astype(bool)
    valid = np.isfinite(agb[agb_before_year]) & (agb[agb_before_year] > min_agb_before)
    for yr in agb_after_years:
        valid &= np.isfinite(agb[yr])
    keep = mask_inner & valid

    if height_path is None:
        lon, lat = fire.geometry.iloc[0].centroid.x, fire.geometry.iloc[0].centroid.y
        height_path = height_mosaic_for(lon, lat)
    height_arr, tr_h, crs_h = read_window(height_path, bounds, masked=False)
    height_100m = reproject_to_grid(
        height_arr.astype("float32"), tr_h, crs_h, shape, tr_ref, crs_ref,
        resampling=Resampling.average,
    )

    if severity_path is None:
        severity_path = f"../data/severity/severity_{uid}.tif"
        if not os.path.exists(severity_path):
            severity_image = build_severity(aoi_ee, *pre_fire_window, *post_fire_window)
            task = export_severity(severity_image, uid, aoi_ee)
            _wait_for_task(task)
            severity_path = download_severity(uid)
        else:
            print(f"reusing cached severity for {uid}: {severity_path}")

    dnbr_arr, tr_d, crs_d = read_window(severity_path, bounds, band=1)
    dnbr_100m = reproject_to_grid(
        np.nan_to_num(dnbr_arr, nan=-9999).astype("float32"), tr_d, crs_d, shape, tr_ref, crs_ref,
        resampling=Resampling.average, nodata_below=-100,
    )

    rbr_arr, tr_r, crs_r = read_window(severity_path, bounds, band=2)
    rbr_100m = reproject_to_grid(
        np.nan_to_num(rbr_arr, nan=-9999).astype("float32"), tr_r, crs_r, shape, tr_ref, crs_ref,
        resampling=Resampling.average, nodata_below=-100,
    )

    ft_path = download_forest_type(aoi_ee, uid, year=forest_type_year)
    ft_arr, tr_ft, crs_ft = read_window(ft_path, bounds, masked=False)
    # nearest, not average: forest type is categorical, a mean of class codes is meaningless
    forest_type_100m = reproject_to_grid(
        ft_arr.astype("float32"), tr_ft, crs_ft, shape, tr_ref, crs_ref,
        resampling=Resampling.nearest,
    )

    discrete_path = download_discrete(aoi_ee, uid, year=forest_type_year)
    discrete_arr, tr_disc, crs_disc = read_window(discrete_path, bounds, masked=False)
    discrete_100m = reproject_to_grid(
        discrete_arr.astype("float32"), tr_disc, crs_disc, shape, tr_ref, crs_ref,
        resampling=Resampling.nearest,
    )

    data = {"uid": uid, "height": height_100m[keep], "dnbr": dnbr_100m[keep],
            "rbr": rbr_100m[keep],
            "forest_type": forest_type_100m[keep],
            "forest_type_label": resolve_label(forest_type_100m[keep], discrete_100m[keep])}

    if firms_map_key is not None:
        if fire_start_end is None:
            raise ValueError("fire_start_end=(start_date, end_date) is required when firms_map_key is set")
        from .temperature import aggregate_to_grid, fetch_firms

        firms_df = fetch_firms(bounds, *fire_start_end, map_key=firms_map_key)
        bt_100m, bt_count_100m = aggregate_to_grid(firms_df, shape, tr_ref)
        print(f"{uid}: {len(firms_df)} FIRMS detections, covering "
              f"{(bt_count_100m[keep] > 0).sum()} of {keep.sum()} kept cells")
        data["brightness_temp"] = bt_100m[keep]
    data[f"a{agb_before_year}"] = agb[agb_before_year][keep]
    for yr in agb_after_years:
        data[f"a{yr}"] = agb[yr][keep]
    d = pd.DataFrame(data)

    d = d[d["dnbr"] >= DNBR_DROP_BELOW].copy()
    d["severity"] = pd.cut(d["dnbr"], SEVERITY_BINS, labels=SEVERITY_LABELS)
    for yr in agb_after_years:
        d[f"loss{yr}"] = 1 - d[f"a{yr}"] / d[f"a{agb_before_year}"]

    return d


def _ee_rectangle(bounds):
    import ee
    w, s, e, n = bounds
    return ee.Geometry.Rectangle([w, s, e, n])


def _wait_for_task(task, poll_seconds=15):
    import time
    while task.active():
        time.sleep(poll_seconds)
    status = task.status()
    if status["state"] != "COMPLETED":
        raise RuntimeError(f"Earth Engine export failed: {status}")
