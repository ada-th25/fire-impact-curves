"""Loading fires from the Global Fire Atlas candidate list built in notebooks/data.ipynb.

The candidate sample itself (filters, stratification) is still built in the notebook,
since choosing fires is an exploratory, judgement-heavy step. This module only covers
the reusable part: looking up one fire's geometry and attributes by its uid, which
every per-fire pipeline step (height, biomass, dNBR) needs.
"""

import geopandas as gpd

ATLAS_SHP_TEMPLATE = "../data/fire_atlas/SHP_perimeters/GFA_v20240409_perimeters_{year}.shp"


def load_fire(uid):
    """Look up one fire's geometry and attributes by its uid ('<file_year>_<fire_ID>').

    Matches the convention used in notebooks/data.ipynb: uid = f"{file_year}_{fire_ID}".
    """
    file_year, fire_id = uid.split("_", 1)
    path = ATLAS_SHP_TEMPLATE.format(year=file_year)
    fire = gpd.read_file(path, engine="pyogrio", where=f"fire_ID = {fire_id}")
    if len(fire) != 1:
        raise ValueError(f"expected exactly one match for uid {uid!r} in {path}, got {len(fire)}")
    return fire


def derive_fire_params(row, window_days=75, gap_days=14):
    """Generic pre/post-fire windows and AGB before/after years from a fire's own
    start_date, instead of hand-picking dates per fire (needed to scale beyond a
    handful of fires - see README Section 14). `row` needs start_date (a
    pd.Timestamp), uid, lon, lat (as in the Section 5 candidate parquet).

    Pre-fire window: `window_days` long, ending `gap_days` before the fire started.
    Post-fire window: the same window, exactly one year later (same season, per
    README Section 9's rationale for why same-season is used).
    AGB before year: the year before the fire started (matches every fire run so
    far: 2019 for 2020 fires, 2020 for 2021 fires). After years: the following one
    or two years, capped at 2022 (last available CCI AGB v6.0 year).
    """
    import pandas as pd

    start = pd.Timestamp(row["start_date"])
    pre_end = start - pd.Timedelta(days=gap_days)
    pre_start = pre_end - pd.Timedelta(days=window_days)
    post_start = pre_start + pd.DateOffset(years=1)
    post_end = pre_end + pd.DateOffset(years=1)

    fire_year = start.year
    agb_after_years = [y for y in (fire_year + 1, fire_year + 2) if y <= 2022]
    if not agb_after_years:
        agb_after_years = [2022]

    return dict(
        uid=row["uid"], lon=row["lon"], lat=row["lat"],
        pre_fire_window=(pre_start.strftime("%Y-%m-%d"), pre_end.strftime("%Y-%m-%d")),
        post_fire_window=(post_start.strftime("%Y-%m-%d"), post_end.strftime("%Y-%m-%d")),
        agb_before_year=fire_year - 1,
        agb_after_years=agb_after_years,
    )


def utm_epsg_for(lon, lat):
    """UTM zone EPSG code for a point, e.g. for `inner_burn_area`'s buffer distance
    to be in real metres. Standard 6-degree UTM zones; not valid above ~84N/80S.
    """
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def inner_burn_area(fire, buffer_m=-500, utm_epsg=None):
    """Fire perimeter minus its outer `buffer_m` (negative = shrink), in UTM so the
    buffer distance is in metres. `utm_epsg` must be supplied per fire (it depends on
    the fire's location); the pilot fire used 32610 (UTM zone 10N).
    """
    if utm_epsg is None:
        raise ValueError("utm_epsg must be set to the fire's local UTM zone")
    return fire.to_crs(utm_epsg).buffer(buffer_m).to_crs(4326)
