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


def get_agb_image(year):
    coll = ee.ImageCollection(COLLECTION).filterDate(f"{year}-01-01", f"{year}-12-31")
    n = coll.size().getInfo()
    if n == 0:
        raise RuntimeError(f"no CCI AGB image for {year}; check available years in the EE catalog")
    return coll.first().select(BAND)


def download_agb(aoi, uid, year, local_dir="../data/cci_agb_ee", scale=100):
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
