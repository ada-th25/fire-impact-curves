# Fire impact curves for forest carbon

## 1. Problem

Goal: estimate what share of a forest's above-ground carbon is lost when it burns, as a function of

- pre-fire tree height, and
- fire severity (dNBR from Landsat/Sentinel-2, with VIIRS fire radiative power as a second measure),

and express the result as impact curves per height class and forest type. The intended use is carbon-insurance risk assessment at Artio.

Approach: for every burned 100 m pixel inside a sample of fires, compute

`loss share = (AGB_before - AGB_after) / AGB_before`

from annual biomass maps, attach the pixel's pre-fire height class, forest type and fire severity, then fit a curve of loss share against severity within each height class and forest type, with uncertainty computed by fire (not by pixel).

## 2. Background reading

Mortality models for individual trees are empirical logistic regressions. The most widely used (Ryan and Amman) predicts mortality from percent crown volume scorched and bark thickness (a function of DBH and species). Fire intensity enters through scorch height (Van Wagner 1973, from fireline intensity). The Fire and Tree Mortality (FTM) database (Cansler et al. 2020; 164,293 trees in the first edition) is the main open dataset for fitting such models. Most calibration data are western-US conifers.

Consequence for this project: tree-level equations cannot be applied directly at 100 m pixels, and fireline intensity is not observable from space, so the project uses remotely sensed severity (dNBR, FRP) and observed biomass change instead. The FTM database could not be downloaded yet (the Forest Service archive returned "request is blocked"), so it is not used so far.

## 3. Data

| Layer | Role | Source and version | Access | Status |
|---|---|---|---|---|
| Fire list (location, start/end date, size, land cover) | Which fires to study | Global Fire Atlas, updated version v20240409, Zenodo record 11400062 (`SHP_perimeters.zip`, 2.84 GB, yearly shapefiles 2002-2024) | Direct download | Downloaded |
| Above-ground biomass (AGB) and its per-pixel SD | Carbon before and after the fire (outcome variable) | ESA CCI Biomass v6.0, 100 m, years 2007, 2010, 2015-2022, from CEDA archive, tile N40W130 for the pilot | Direct download (`wget`) | Pilot tile for 2019, 2021, 2022 downloaded |
| Canopy height | Pre-fire height class | GLAD global forest canopy height 2019 (Potapov et al.), 30 m, continental mosaic `Forest_height_2019_NAM.tif` (5.7 GB) | Direct download | Downloaded |
| Fire severity | Explanatory variable | Landsat 8/9, Sentinel-2 (dNBR); VIIRS FRP from FIRMS | Planned via Earth Engine | Not started |
| Fire vs non-fire forest loss | Remove logging, clearing, storms | Tyukavina et al. fire-loss layer (Earth Engine asset, covers 2001-2023 in the version I found) | Earth Engine | Not started |
| Biome | Stratify sampling | WWF/RESOLVE ecoregions | Direct download | Not started (GFED region code used as a stand-in) |

Why each was chosen:

- **Global Fire Atlas**: provides per-fire start/end date, size and dominant land cover, which allows filtering without manual work. The original release covers 2003-2016 only; the updated Zenodo version covers 2002 to February 2024, so it includes 2020-2021.
- **ESA CCI Biomass**: global, open, annual (from 2015) AGB at 100 m with a per-pixel uncertainty, which makes before/after comparison possible. It is the only global annual biomass series I found at this resolution.
- **GLAD height 2019**: 30 m global height map calibrated on 2019 GEDI lidar and Landsat. I could not find a 2015 GLAD height map (the roadmap assumed one).
- **Severity from Landsat/Sentinel-2 dNBR** (planned): dNBR responds to canopy damage under dense cover, unlike NDVI.

## 4. Choice of temporal window: fires starting in 2020 and 2021

Evidence that constrains the window:

| Fact | Consequence |
|---|---|
| GLAD height map is calibrated for 2019 (GEDI data from April-October 2019 plus Landsat 2019). Versions for 2000 and 2020 exist from the same model. | The 2019 map is a true pre-fire snapshot only for fires after 2019. For fires in 2016-2018 it would show post-fire forest. |
| CCI AGB v6 has annual maps for 2015-2022. (A v7 covering 2015-2024 is listed by ESA and is not used yet.) | A 2020 fire has 2019 (before) and 2021, 2022 (after). A 2021 fire has 2020 (before) and only 2022 (after). |
| The 2020 AGB map straddles the fire year. | It is not used as "before" or "after" for 2020 fires; 2019 is the pre-fire map. |

So the window is fires with `start_date` from 2020-01-01 to 2021-12-31. Fires that started in late 2019 are excluded even if they continued into 2020.

## 5. Choice of spatial extent: global sample, stratified

Why a sample and not wall-to-wall: the aim is curves that generalise across forest types, so fires are sampled worldwide and the pipeline runs only inside their perimeters.

How the candidate list was built (all steps on the Atlas attributes, no geometry loaded):

1. Loaded yearly shapefiles 2019-2022 (the file year is a fire season; each file's start dates span about 23 months, e.g. the 2020 file runs 2019-07-01 to 2021-05-31, so file year was never used for filtering).
2. **`fire_ID` is not a unique identifier across files**: of the IDs that repeat, essentially all have different latitude, start date and size. Rows that matched on lat, lon, start date, end date and size were treated as true duplicates (39,410 removed of 3,436,580 rows). A unique key `uid = <file year>_<fire_ID>` is used instead.
3. Filters: `start_date` in 2020-2021; `size >= 5` (about 500 ha, **assuming size is in km2, to verify**: the minimum value of 0.21 is about one 500 m pixel); dominant `landcover` one of Evergreen/Deciduous Broadleaf, Evergreen/Deciduous Needleleaf, Mixed forest; `landc_frac >= 0.5`.
4. Woody savannas (332,643 rows across the four files) were left out for now as not dense forest.

Result: **16,240 candidate forest fires**.

| Land cover | Fires |
|---|---|
| Deciduous Broadleaf | 7,736 |
| Mixed | 5,091 |
| Evergreen Broadleaf | 3,048 |
| Evergreen Needleleaf | 349 |
| Deciduous Needleleaf | 16 |

By GFED region (code as in the Atlas `GFED_regio`; names are the standard GFED basis regions, **to verify**): 1 (boreal N. America) 124; 2 (temperate N. America) 238; 3: 287; 4: 59; 5 (southern S. America) 1,986; 6 (Europe) 15; 7: 10; 8 (N. Africa) 2,167; 9 (S. Africa) 7,161; 10 (boreal Asia) 181; 11: 79; 12 (SE Asia) 3,781; 13: 17; 14 (Australia) 135.

The sample is heavily imbalanced (southern Africa alone is 44%), which is why selection will be a fixed number of fires per stratum (region or biome by land cover), not random or by size. Within each stratum fires will be chosen by biomass exposed (size times mean pre-fire biomass), with some mid-sized fires included so that mild and moderate severities are represented. Southern Africa "forest" is probably mostly open woodland **(inference from counts, to verify with the biomass layer)**, so a minimum pre-fire biomass filter will be applied once biomass is loaded.

Boreal limitation: the GLAD 2019 continental mosaics cover roughly 52 degrees S to 52 degrees N, so fires further north have no 2019 height in the files used here.

## 6. Pilot fire: `2020_112`

Selected because it is large (1,206 km2), starts in August 2020 (clean pre-fire biomass and height from 2019, two post-fire biomass years), lies in layers all datasets cover, and is in the US where MTBS severity could be used for validation later. Attributes: Atlas fire_ID 112 (2020 file), start 2020-08-14, end 2020-09-27, lat 39.69, lon -122.78, landcover Evergreen Needleleaf forest, `landc_frac` 0.50 (passes the threshold exactly, so about half the perimeter is another class). I think it is part of California's August Complex, **(to verify against the polygon)**. Bounding box: lon -123.093 to -122.558, lat 39.513 to 39.879.

### Pilot processing

- Burned area = Atlas perimeter minus its outer 500 m (buffer in UTM zone 10N), because the 500 m fire product is least accurate at the edges.
- Pixels kept where 2019 AGB > 10 Mg/ha (placeholder threshold).
- Control = all pixels more than 1 km outside the perimeter in the same window (crude; may include other burns).
- Loss share per pixel clipped to [0, 1]; aggregate loss fraction = 1 - sum(AGB after) / sum(AGB before).


## 7. Known issues and open questions

1. **Date window**: confirm 2020-2021 (Section 4) or choose an alternative.
2. **Noise in annual CCI AGB**: needs a proper control (exclude all Atlas perimeters 2019-2022, match on biomass and terrain) and use of ESA's AGB-change maps with their uncertainty and quality flags. I have not yet checked ESA's guidance on year-to-year change detection.
3. **Earth Engine access**: Fire severity (dNBR) and the Tyukavina layer are much easier through Earth Engine.
4. **Boreal coverage**: needs a different height source or acceptance of exclusion.
5. **Height saturation**: GLAD heights saturate above about 30 m; the 95th percentile in the pilot box is 34 m.
6. **Definition of "forest"**: MODIS land cover as used in the Atlas; may differ from dense forest in biomass terms.
7. **Prescribed or agricultural burns**: some candidate fires (for example in the southeastern US in spring) may not be wildfires. Decide whether to include them.
8. **GLAD height looks unreliable on steep terrain, height-class results are not ready.** In the four-fire batch (Section 10), fire `2020_135` (steep Sierra Nevada terrain) has implausible height/biomass combinations in about 31% of its cells classed as under 10 m tall, pre-fire biomass up to almost 400 Mg/ha, which genuinely short stands do not carry. This is probably GLAD's GEDI/Landsat height model being less reliable on steep slopes, not a pipeline bug, but it is not confirmed against a terrain layer. Do not treat any height-class breakdown (loss by height x severity) as usable until this is resolved, it currently makes the height axis unreliable for at least some fires. Needs either a terrain/slope-based filter or a sanity check such as dropping height/biomass combinations outside a plausible range before grouping by height class.

## 8. Pilot result: CCI biomass sensitivity to fire loss

Using the Tyukavina fire-loss layer only as a check (not as part of the modelling pipeline), cells in the pilot fire were grouped by the share of the 100 m cell flagged as fire-driven tree loss in 2020 or 2021.

| Share of cell flagged as fire loss | Cells | CCI biomass loss by 2021 | CCI biomass loss by 2022 |
|---|---|---|---|
| 0 to 5% | 24,760 | 0.5% | 4.4% |
| 5 to 25% | 9,957 | 1.9% | 3.8% |
| 25 to 50% | 10,083 | 2.8% | 5.1% |
| 50 to 75% | 11,440 | 3.2% | 4.5% |
| 75 to 95% | 15,090 | 4.0% | 6.6% |
| 95 to 100% | 40,191 | 6.5% | 10.5% |

The loss rises steadily with the flagged share, so the two datasets agree on where the fire hit. The size of the response is small though. Cells almost entirely flagged as fire loss lose only 6.5% of CCI biomass by 2021 and 10.5% by 2022, well short of the 60 to 90% the roadmap's illustrative table assumed for severe fire.

**Placebo check.** The same grouping was applied to 2018 to 2019 biomass change, a period with no fire, using the 2018 AGB tile for N40W130.

| Share of cell flagged as fire loss | "Loss" 2018 to 2019 (no fire) | Mean 2019 biomass (Mg/ha) |
|---|---|---|
| 0 to 5% | -3.5% (gain) | 93.5 |
| 5 to 25% | -2.4% (gain) | 93.9 |
| 25 to 50% | -2.2% (gain) | 92.5 |
| 50 to 75% | -1.6% (gain) | 90.4 |
| 75 to 95% | -1.5% (gain) | 88.1 |
| 95 to 100% | -0.4% (gain) | 86.1 |

Every group gains biomass between 2018 and 2019, as expected with no fire, but the gain is not even across groups. Cells that would later be heavily fire-flagged already show less pre-fire gain and a lower starting biomass than lightly-flagged cells. This points to a pre-existing difference between the groups (likely in forest composition or site conditions), not a flaw in the fire flagging.

Subtracting this baseline trend from the 2021 figures gives a fire-attributable signal of about 4.0% (lightly flagged cells) rising to 6.9% (fully flagged cells). The fire effect is real and monotonic, but still small, on the order of single-digit percentage points, not tens of percent.

**Conclusion.** CCI annual biomass at 100 m does register fire-driven canopy loss in the correct direction, but its magnitude is far below what full carbon loss from a stand-replacing fire should look like. Likely causes include standing dead trees still counted as woody biomass, and the annual product being too coarse or too smoothed to register abrupt loss. This is a one-fire result and not conclusive on its own, but it is a serious caution against using CCI annual biomass change as the sole outcome variable for the impact curves, and should be tested on more fires and forest types before the main sample is built.

## 9. Pilot result: loss against fire severity (dNBR)

The Tyukavina layer is now used only as a cross-check, not as part of the modelling pipeline. The core relationship to establish is loss against pre-fire canopy height, forest type and fire severity, so this step replaces the Tyukavina flag share with dNBR as the severity axis.

dNBR was computed from Sentinel-2 (via Earth Engine) as the difference between a cloud-filtered median NBR composite from the season before the fire (July 2020) and the same season one year later (July-August 2021), following the roadmap's guidance to compare like seasons. It was then averaged onto the 100 m CCI biomass grid.

Cells with dNBR below 0.1 are excluded from the severity scale (see below), then the rest are binned into the roadmap's rough severity classes:

| Severity (dNBR) | Cells | CCI biomass loss by 2021 | CCI biomass loss by 2022 |
|---|---|---|---|
| mild (0.1 to 0.27) | 22,214 | 1.0% | 5.1% |
| moderate (0.27 to 0.66) | 60,292 | 2.8% | 4.5% |
| severe (> 0.66) | 23,956 | 6.8% | 11.6% |

A finer 0.05-step binning across this range shows a broadly monotonic rise in loss with severity, from about 1 to 9% in the mild to moderate range up to about 24% by 2022 at the most severe end, with a small bump and dip around dNBR 0.4 to 0.6 that is most likely genuine heterogeneity within this one large, complex fire rather than noise (the bins there hold tens of thousands of cells each). This is the first result in the project that shows the shape the roadmap is after, loss increasing with fire severity, though the magnitude at the severe end is still well below the roadmap's illustrative 60 to 90%, consistent with the CCI sensitivity finding in Section 8.

**Cells with dNBR below 0.1 are not usable as a severity measurement and are dropped.** Loss in this range is elevated and not monotonic with the rest of the curve, which is the wrong direction for low severity (a dNBR near or below 0 means the post-fire image looked as healthy as, or healthier than, the pre-fire one). Mapping these cells shows them scattered broadly across the whole burn scar rather than confined to a thin band at the perimeter, which points to patches of already-sparse vegetation, water, rock or riparian understory that regrow quickly regardless of where they sit, rather than a processing error such as cloud or smoke contamination. These cells are dropped from the fitted curve rather than treated as "unburnt" or "very low severity".

**Conclusion.** Loss and fire severity are now linked for the pilot fire, with a believable, broadly monotonic relationship from mild to severe dNBR, once cells below dNBR 0.1 are excluded. As with Section 8, this is a one-fire, one-forest-type result, and the next step is repeating this across fires that span more height classes and forest types, which the pipeline in `src/` is now set up to do (see "Reproducibility"). **This step's result turned out not to generalise, see Section 10.**

## 10. Three more fires: the pilot's low magnitude does not generalise

The pipeline in `src/` (Section 9's "next step") was run on three more fires in the pilot's CCI tile, one more Evergreen Needleleaf fire (`2020_135`), one Evergreen Needleleaf fire from 2021 (`2021_190`), and one small Evergreen Broadleaf fire (`2020_464`, only 64 cells total, too small to trust on its own but included as a pipeline stress test). CCI biomass loss by the final available year, by severity class:

| Fire | Forest type | mild | moderate | severe |
|---|---|---|---|---|
| 2020_112 (pilot) | Evergreen Needleleaf | 5.1% | 4.5% | 11.6% |
| 2020_135 | Evergreen Needleleaf | 17.3% | 23.8% | 26.7% |
| 2021_190 | Evergreen Needleleaf | 11.2% | 36.5% | 54.3% |
| 2020_464 | Evergreen Broadleaf | 21.7% | 51.7% | 52.3% |

All three new fires show a monotonic rise in loss with severity, and three of the four fires reach magnitudes much closer to the roadmap's illustrative 60 to 90% than the pilot did, `2021_190` reaches 54.3% at severe. **The pilot fire now looks like the outlier, not the typical case.** The cautious conclusions in Sections 8 and 9, that CCI annual biomass barely registers fire loss, were drawn from the pilot alone and do not hold up once more fires are added. CCI biomass can apparently register a much larger loss than the pilot showed, this looks like a property of that one fire rather than of the CCI product in general.

No confirmed cause for the pilot's low magnitude yet. Candidates considered: the pilot is the largest and most structurally complex of the four fires, which could mean a patchier internal mix of severities; residual smoke or haze in its pre-fire Sentinel-2 composite (weakened as an explanation since `2020_135`, also a 2020 Northern California fire with an overlapping pre-fire window, did not show the same dampening); or a genuine ecological difference in stand density, drought stress or terrain between fires nominally in the same forest type. This has not been investigated further, in favour of continuing to build out the multi-fire sample, since fire-to-fire variation of this kind is exactly what Section 6 of the roadmap expects the curves' uncertainty (computed by fire, not by pixel) to capture.

**Conclusion.** Do not treat Sections 8 and 9's magnitude findings as settled. CCI biomass's sensitivity to fire loss appears to vary a great deal by fire, for reasons not yet understood, and a larger sample across forest types and biomes is needed before concluding anything about typical magnitude.

## 11. Pipeline validated outside North America: a Southeast Asia fire

Biomass and forest type were moved from manually downloaded tiles to Earth Engine (`src/biomass.py`, `src/forest_type.py`, see "Reproducibility"), removing the tile-boundary problem for those two layers. Height still needs the right GLAD continental mosaic for a fire's location (`src/height.py`); all seven mosaic filenames were confirmed against GLAD's own directory listing and added, though only the pilot's NAM fire has so far tested any of them end to end.

Fire `2020_841874` (GFED region 12, Southeast Asia, Laos/Thailand area, 82.1 km2, started 2020-03-22) was run as the first real test outside North America and outside the pilot's CCI tile. Result:

| | n | mean loss by 2022 |
|---|---|---|
| mild | 308 | 8.2% |
| moderate | 153 | 25.3% |
| severe | 1 | not usable, n=1 |

460 of 462 cells were correctly classified as Evergreen Broadleaf forest type, a genuinely different forest type from every fire tested so far (all Evergreen Needleleaf, bar one small Evergreen Broadleaf fire too small to be informative). This confirms the pipeline, tile lookup and forest-type classification work correctly outside the original test region, not just by coincidence of one convenient tile.

The result itself is not yet usable as a broadleaf curve: this is one small fire (462 cells total, against tens of thousands for the NAM fires), its `severe` bin has a single cell, and `mild` to `moderate` is the only comparison available. The mild-to-moderate magnitude (8.2% to 25.3%) is broadly in range with the other fires in Section 10, not an outlier in either direction, but one fire is not enough to say anything about a Southeast Asia or broadleaf-specific curve.

**Conclusion.** Infrastructure milestone, not a results milestone. The pipeline (height, biomass, severity, forest type) now works for an arbitrary fire anywhere the GLAD mosaics cover. Producing an actual height x forest-type curve still needs many more fires pooled per group, which is a scope decision (how many fires, which regions, how much further to investigate the open data-quality questions in Sections 8 to 10) that should be checked with the supervisor before continuing to scale.

## Infrastructure

- GCP project `tree-fire` (display name), project ID `tree-fire-510209`; Vertex AI Workbench instance `tree-fire-workbench`, zone `europe-west2-a`; Python venv `.venv` with earthengine-api, geemap, pandas, geopandas, pyarrow, ipykernel, rasterio, pyogrio.
- Earth Engine use requires the actual project ID (`tree-fire-510209`), not the display name, plus the project registered for Earth Engine access and the caller's account holding `roles/serviceusage.serviceUsageConsumer`.
- All static layers were downloaded directly to the instance's disk under `data/`, which is gitignored.
- A GCS bucket, `gs://tree-fire-510209-data`, in `europe-west2`, backs up `data/` and receives Earth Engine export outputs (such as dNBR) under `fire-impact-curves/data/...`, matching the local layout.
- As of the `src/` pipeline (see "Reproducibility"), biomass and forest type are pulled from Earth Engine directly rather than downloaded per tile, so any fire globally works for those two without manual downloads. Height still needs a GLAD continental mosaic looked up by location (`src/height.py`), and only North America is confirmed so far, a fire elsewhere will raise until its mosaic is added.

## Reproducibility

On the instance:

```bash
# environment
python -m venv .venv && source .venv/bin/activate
pip install earthengine-api geemap pandas geopandas pyarrow ipykernel pyogrio rasterio scipy

# 1. fire list (Global Fire Atlas v20240409, Zenodo 11400062)
mkdir -p data/fire_atlas && cd data/fire_atlas
wget -c -O SHP_perimeters.zip "https://zenodo.org/records/11400062/files/SHP_perimeters.zip?download=1"
unzip SHP_perimeters.zip && cd ../..

# 2. canopy height (GLAD 2019, North America mosaic, 5.7 GB)
mkdir -p data/glad && cd data/glad
wget -c https://glad.geog.umd.edu/Potapov/Forest_height_2019/Forest_height_2019_NAM.tif
cd ../..

# 3. biomass, pilot tile N40W130, years 2019, 2021, 2022 (AGB and AGB_SD)
mkdir -p data/cci_agb && cd data/cci_agb
base="https://dap.ceda.ac.uk/neodc/esacci/biomass/data/agb/maps/v6.0/geotiff"
for yr in 2019 2021 2022; do for kind in AGB AGB_SD; do
  f="N40W130_ESACCI-BIOMASS-L4-${kind}-MERGED-100m-${yr}-fv6.0.tif"
  wget -c -O "$f" "${base}/${yr}/${f}?download=1"
done; done
```

Downloaded on 2 Oct 2026, superseded for biomass by the Earth Engine source below. Fire selection and exploratory/diagnostic work stay in `notebooks/`. The per-fire alignment steps have been refactored into reusable functions in `src/`, callable as `build_cell_table(uid, ...)` for one fire at a time:

- `fires.py`: look up a fire's geometry and attributes by uid.
- `grids.py`: generic windowed-read and reproject-to-grid helpers.
- `biomass.py`: above-ground biomass (ESA CCI Biomass v6.0, Earth Engine asset `ESA/CCI/Above_Ground_Biomass/V6_0`, band `agb`), any fire globally, no tile download needed.
- `severity.py`: dNBR from Sentinel-2 via Earth Engine.
- `forest_type.py`: forest type (CGLS-LC100, Earth Engine asset `COPERNICUS/Landcover/100m/Proba-V-C3/Global`, band `forest_type`), any fire globally, legend confirmed in that module's docstring.
- `height.py`: canopy height (GLAD), still needs the right continental mosaic looked up by the fire's location, only North America is confirmed so far.
- `pipeline.py`: `build_cell_table(uid, ...)`, ties the above together for one fire.

See the pipeline cells near the end of `notebooks/data.ipynb` for example calls across the four fires run so far (Sections 9 and 10). Still needed before running this over the full Section 5 sample: GLAD height mosaics for continents other than North America, and resolving the steep-terrain height reliability issue (known issue #8).

## References

- Andela, N. et al. (2019). The Global Fire Atlas of individual fire size, duration, speed and direction. *Earth System Science Data* 11, 529-552. Updated version: Andela, N., Jones, M., Zenodo, doi:10.5281/zenodo.11400062 (v20240409).
- Santoro, M., Cartus, O. (2025). ESA Biomass CCI: global datasets of forest above-ground biomass for 2007, 2010, 2015-2022, v6.0. NERC EDS CEDA. doi:10.5285/95913ffb6467447ca72c4e9d8cf30501.
- Potapov, P. et al. (2021). Mapping global forest canopy height through integration of GEDI and Landsat data. *Remote Sensing of Environment* 253, 112165. doi:10.1016/j.rse.2020.112165.
- Cansler, C.A. et al. (2020). The Fire and Tree Mortality Database, for empirical modeling of individual tree mortality after fire. *Scientific Data* 7, 194. doi:10.1038/s41597-020-0522-7. Archive: doi:10.2737/RDS-2020-0001.
- Hood, S.M. et al. (2018). Fire and tree death: understanding and improving modeling of fire-induced tree mortality. *Environmental Research Letters*.
- Van Wagner, C.E. (1973). Height of crown scorch in forest fires. *Canadian Journal of Forest Research*.