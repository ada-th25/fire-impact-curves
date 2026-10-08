"""Fire severity as brightness temperature (Kelvin), from FIRMS VIIRS active-fire
detections, as an additional severity axis alongside dNBR, per the supervisor's
request that the fire model should work in temperature.

Important difference from dNBR: dNBR comes from a dense satellite image, every
pixel gets a value. FIRMS active-fire detections are sparse points (375 m VIIRS
pixels, only where a satellite overpass caught an actively burning fire at that
moment, roughly 1-2 times/day). Most 100 m cells, even ones that clearly burned
per dNBR, will have NO detection at all, not because they are unburnt, but
because no overpass caught them while flaming. This is a structurally sparser
measure than dNBR, not a like-for-like replacement - treat gaps as "no data",
never as "cold"/"unburnt". It is added as an extra column (`brightness_temp`),
`dnbr` is unchanged, so the two can be compared (roadmap Step 6 suggests exactly
this, FRP vs dNBR; here it is brightness temperature vs dNBR instead of FRP,
since brightness temperature is a direct physical temperature, unlike FRP, which
conflates temperature with the fire's sub-pixel burning area - see conversation
history for why an FRP-to-temperature conversion was not used instead).

brightness_temp means VIIRS band I-4 brightness temperature (`bright_ti4`, Kelvin),
the same field already pulled for the pilot fire early in the project
(notebooks/data.ipynb, FIRMS section) but not previously used for curves.

Needs a FIRMS MAP_KEY (free, from https://firms.modaps.eosdis.nasa.gov/api/map_key/).
"""

import datetime as dt
import io

import numpy as np
import pandas as pd
import requests

FIRMS_SOURCES = ["VIIRS_SNPP_SP", "VIIRS_NOAA20_SP"]


def fetch_firms(bounds, start_date, end_date, map_key, sources=FIRMS_SOURCES):
    """`bounds` = (w, s, e, n). `start_date`/`end_date` bound the fire's own active
    burning period (its Fire Atlas start/end date, not a before/after season window
    like dNBR uses - brightness temperature only exists at the moment of burning).
    Returns a DataFrame of detections (empty if none found), with a `source` column.
    """
    w, s, e, n = bounds
    bbox = f"{w},{s},{e},{n}"
    start = pd.Timestamp(start_date).date()
    end = pd.Timestamp(end_date).date()

    frames = []
    for src in sources:
        d = start
        while d <= end:
            n_days = min(10, (end - d).days + 1)   # FIRMS area API allows up to 10 days per request
            url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{src}/{bbox}/{n_days}/{d}"
            r = requests.get(url, timeout=60)
            if r.text.startswith("latitude"):
                df = pd.read_csv(io.StringIO(r.text))
                df["source"] = src
                frames.append(df)
            d += dt.timedelta(days=n_days)

    if not frames:
        return pd.DataFrame(columns=["latitude", "longitude", "bright_ti4", "frp", "confidence"])
    return pd.concat(frames, ignore_index=True)


def aggregate_to_grid(firms_df, shape, transform, value_col="bright_ti4"):
    """Snap each detection to the nearest cell on the given grid (same transform/
    shape as the biomass grid), taking the MAX value per cell (peak temperature
    reached, not an average across the fire's duration - a cell that flared once
    at 400K and smouldered otherwise should read as 400K, not diluted by the
    smoulder readings). Cells with no detection are NaN.

    Returns (grid, detection_count_grid) - the count is useful for sanity-checking
    how sparse the coverage actually was for a given fire.
    """
    import rasterio.transform

    out = np.full(shape, np.nan, dtype="float64")
    counts = np.zeros(shape, dtype="int32")
    if len(firms_df) == 0:
        return out, counts

    rows, cols = rasterio.transform.rowcol(
        transform, firms_df["longitude"].to_numpy(), firms_df["latitude"].to_numpy()
    )
    rows, cols = np.asarray(rows), np.asarray(cols)
    valid = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
    vals = firms_df[value_col].to_numpy()

    for r, c, v in zip(rows[valid], cols[valid], vals[valid]):
        if np.isnan(out[r, c]) or v > out[r, c]:
            out[r, c] = v
        counts[r, c] += 1
    return out, counts
