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
| Above-ground biomass (AGB) and its per-pixel SD | Carbon before and after the fire (outcome variable) | ESA CCI Biomass v6.0, 100 m, years 2007, 2010, 2015-2022 | Earth Engine (`ESA/CCI/Above_Ground_Biomass/V6_0`), superseded the original CEDA tile download | Implemented, any fire globally (Section 11) |
| Canopy height | Pre-fire height class | GLAD global forest canopy height 2019 (Potapov et al.), 30 m, continental mosaics | Direct download | All 7 continental mosaics downloaded and confirmed (Section 11); GLAD itself covers ~52°S-52°N only |
| Fire severity | Explanatory variable | Sentinel-2 (dNBR, RBR) via Earth Engine | Earth Engine | Implemented (Sections 9, 15) |
| Fire vs non-fire forest loss | Remove logging, clearing, storms | Tyukavina et al. fire-loss layer (Earth Engine asset, covers 2001-2023 in the version I found) | Earth Engine | Used once as a cross-check (Section 8), not part of the main pipeline |
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

**Conclusion.** Infrastructure milestone, not a results milestone. The pipeline (height, biomass, severity, forest type) now works for an arbitrary fire anywhere the GLAD mosaics cover. Producing an actual height x forest-type curve still needs many more fires pooled per group, which is a scope decision (how many fires, which regions, how much further to investigate the open data-quality questions in Sections 8 to 10).

## 12. First fitted curve, with by-fire uncertainty

Three more fires were added (two more Evergreen Broadleaf, one Deciduous Broadleaf, one Mixed, by the Fire Atlas's own labels), bringing the total to 8 fires, 282,107 cells. Curve fitting (`src/curves.py`) fits a three-parameter logistic per height x forest-type group, requiring at least 3 fires and 200 cells, and flags any fit where the steepness parameter hits its upper bound as `degenerate_fit` rather than reporting it as real, this correctly caught both `<10m` groups, consistent with the known height-on-steep-terrain issue (#8).

**A per-fire label mismatch.** Two of the three new fires' Fire Atlas `landcover` label did not match their actual pixel-level forest type: one labelled "Deciduous Broadleaf" was 79% Evergreen Broadleaf at the pixel level, one labelled "Mixed forest" was 95% Evergreen Broadleaf. The Atlas's per-fire dominant-landcover label cannot be relied on to find fires of a given forest type, only the pixel-level `forest_type` column (used throughout the pipeline) can.

**Usable fits, superseded by Section 13's full 11-fire, fallback-corrected numbers below, kept here only as the original by-fire uncertainty example:**

| Group | Fires | Cells | l_max | x0 (dNBR midpoint) |
|---|---|---|---|---|
| Evergreen Broadleaf, 10-20m | 4 | 1,522 | 49.4% | 0.25 |
| Evergreen Needleleaf, 10-20m | 5 | 71,620 | 20.0% | 0.52 |
| Evergreen Needleleaf, >20m | 5 | 136,962 | 46.0% | 0.58 |

`Deciduous Broadleaf`, `Mixed`, and `Evergreen Broadleaf >20m` still have insufficient data (1-3 fires, as few as 41 cells).

**By-fire uncertainty is large.** A by-fire bootstrap (resample fires with replacement, not pixels, refit, repeat 500 times, `bootstrap_curve_band`) on the Evergreen Broadleaf group shows an 80% band of roughly 26% to 67% predicted loss at moderate-to-severe severity (dNBR >= 0.5), around a median of 46%, more than a 2.5x range. The underlying per-fire severity means bear this out directly: `mild` loss alone ranges from -3.9% to 32.2% across the four fires. The curve's shape (rising from near zero at mild severity to a plateau around dNBR 0.5-0.6) matches what the roadmap expects, but the uncertainty is too wide yet to be a useful number on its own.

**Conclusion.** This is the first result close to the actual deliverable, a fitted curve with uncertainty computed by fire, as the roadmap specifies, not by pixel. It also confirms the band is still far too wide with only 4 fires per group. More fires per group are needed before any curve here is narrow enough to be useful, and the Atlas-label mismatch means fires cannot be pre-selected by forest type with confidence, composition has to be checked per fire after running the pipeline.

## 13. Forest-type fallback, a degenerate-fit gap, and a dedicated runner notebook

The recurring `unknown` forest-type share (flagged across Sections 11 and 12) is now addressed with a fallback: `src/forest_type.py` also reads CGLS-LC100's `discrete_classification` band (closed/open forest sub-type, legend confirmed against the product's documentation) and uses it wherever the primary `forest_type` band is `unknown` or `not_forest`. `build_cell_table` now returns the resolved label directly as `forest_type_label`.

Rerunning all 11 fires through this: `unknown` dropped from 20.7% to 14.9% of all cells, a real but modest recovery. More tellingly, `Evergreen Broadleaf, 10-20m` went from drawing on 4 fires to 6, two fires that previously had too few classified cells to count now contribute, confirming the fallback changes which fires qualify for a group, not just overall accuracy.

**A second degenerate-fit mode found.** `Evergreen Broadleaf, >20m` (5 fires, only 563 cells) fitted with `l_max = 1.0`, pegged exactly at its upper bound, and a parameter standard error of 31 on a parameter that can only range 0 to 1, nonsensical, the fit is not actually constrained by the data. The earlier degenerate check only looked at the steepness parameter `k` hitting its bound; it has been extended to also flag `l_max` pegging and implausibly large parameter standard errors. Same lesson as the `k`-pegging case: a "fitted" status alone is not enough to trust a curve, always check `status == "fitted"` specifically, not just that a result came back.

**Batch runs now live in `notebooks/run_pipeline.ipynb`**, not `data.ipynb`. It defines every fire's config in one place, loops `build_cell_table`, saves the pooled table to `data/processed/all_cells.parquet`, and reports the forest-type recovery comparison. `data.ipynb` remains as the exploratory/diagnostic record of how the issues in Sections 8 to 13 were found.

With all 11 fires and the fallback applied, the usable curves are:

| Group | Fires | Cells | l_max | x0 (dNBR midpoint) |
|---|---|---|---|---|
| Evergreen Broadleaf, 10-20m | 6 | 15,324 | 36.4% | 0.35 |
| Evergreen Needleleaf, 10-20m | 5 | 73,784 | 19.9% | 0.52 |
| Evergreen Needleleaf, >20m | 5 | 137,223 | 46.0% | 0.58 |

`<10m` (both forest types), `Evergreen Broadleaf >20m`, `Deciduous Broadleaf`, and `Mixed` remain excluded (degenerate or insufficient data).

**Conclusion.** The forest-type fallback is a genuine, if modest, improvement, worth keeping. The new degenerate-fit case is a reminder that small-sample curve fits need active scrutiny, not just a status check, every group should be eyeballed before being trusted, not assumed safe because `curve_fit` didn't raise an exception.

## 14. Scaling to many more fires: parallel exports, and a sampling-bias caveat

The curves need many more fires to be representative, not a handful. Running fires one at a time, each waiting ~10-15 minutes for its own dNBR export before the next one starts, does not scale to dozens of fires. `src/pipeline.py` now splits the dNBR step into `submit_dnbr_tasks` (submit every fire's export to Earth Engine at once) and `wait_and_download_dnbr` (poll all of them together, downloading each as it finishes), since Earth Engine runs exports independently on its own servers, N fires submitted together take roughly as long as 1, not N times as long. `build_cell_table` accepts a pre-fetched `dnbr_path` to skip its own export step when called this way. `notebooks/run_pipeline.ipynb` uses this two-phase pattern.

**A sampling-bias caveat worth fixing before scaling.** Every fire chosen so far (Sections 9-11, 14) was picked as the *largest* fire of its forest type within a region, for a practical reason (a bigger fire gives more cells to work with), but this is not a representative sample: it systematically oversamples large, likely high-exposure fires and undersamples the small-to-medium fires that make up most of the Section 5 candidate list (median fire size in that list is about 10 km2, versus several hundred km2 for everything chosen so far). A curve built only from large fires may not generalise to a typical one. Scaling up should sample more broadly within each stratum (for example, a random or size-stratified draw within each region x forest-type group), not just take the top 1-2 by size again.

**`uid` is not always unique.** Section 5 already found that most repeated `fire_ID`s across files are genuinely different fires, not duplicate rows, and treated those as distinct. It did not check for the same problem *within* one file: sampling many fires at once turned up `fire_ID` 78182 in the 2020 file matching two different fires, so `uid = file_year_fire_ID` is ambiguous for it, and `load_fire()` has no way to tell which one is meant. The stratified sampling in `notebooks/run_pipeline.ipynb` now drops any `uid` that is not unique in the candidate list before sampling, rather than guessing. `submit_severity_tasks` was also made resilient to a single fire failing (catches the error and continues) after an early version of this crash lost track of several already-submitted Earth Engine exports on the first attempt.

**Scaling-up result: the curves actually moved, not just their confidence.** 105 fires, 482,257 cells. Evergreen Broadleaf 10-20m's l_max dropped from 36.4% (6 fires) to 19.4%, and a new group, Mixed forest 10-20m, reached enough data to fit for the first time. This is concrete evidence that the small-sample curves in Sections 12-13 were not stable, confirming that more fires were needed before trusting any of them.

**Fitted curve parameters and uncertainty bands are now saved**, not just plot images: `data/processed/curves/fit_parameters.csv` (l_max, k, x0 per usable group) and `uncertainty_bands.csv` (the by-fire bootstrap band at each dNBR point per group), moving towards the roadmap's "saved in a format CLIMADA can read" deliverable. The plotting step also now excludes `<10m` from "usable" by policy, not just by whether `curve_fit` happened to flag it degenerate that run, since the underlying height data is known-unreliable there (issue #8) regardless of how the fit numbers come out.

**Brightness temperature (FIRMS) tested as an alternative severity measure, and found not viable at the per-pixel level.** Coverage was 0.016% of cells (19 of 120,632) even on the pilot fire, the largest and longest-burning fire run so far, since VIIRS only catches a spot mid-flame once or twice a day, versus dNBR's full-coverage satellite image. The detected temperatures (295-367K) were also well below real flame temperature, since VIIRS brightness temperature averages the whole 375m pixel, diluting the actual hot spot with surrounding unburnt ground. `src/temperature.py` implements the fetch and grid-alignment (`fetch_firms`, `aggregate_to_grid`) and `build_cell_table` can optionally add a `brightness_temp` column (`firms_map_key`/`fire_start_end`, off by default), but a per-fire summary temperature (one value per fire, used as a fire-level covariate alongside dNBR, not a per-pixel replacement for it) is the realistic use of this data, not yet implemented.

## 15. RBR added alongside dNBR

About getting more accuracy out of fire intensity than dNBR: RBR (Relativized Burn Ratio), `RBR = dNBR / (NBR_pre + 1.001)`, is now computed and exported alongside dNBR (`src/severity.py`'s `build_severity`, one 2-band image, not a second Earth Engine cost). RBR is the standard refinement used in later USGS/MTBS products, normalising dNBR by how dense the vegetation was before the fire, which should make severity more comparable across forest types with very different baseline NBR, plain dNBR does not correct for this, and may partly explain some of the forest-type inconsistency seen in Sections 10-14.

`build_cell_table` now reads both bands into `dnbr` and `rbr` columns. The severity classification (`SEVERITY_BINS`, the `DNBR_DROP_BELOW` edge-regrowth exclusion) still runs on `dnbr`, unchanged, RBR is available as an additional continuous column, e.g. via `fit_group(df, dnbr_col="rbr")`, to compare directly against the dNBR-based curves.

**Cost of this change: every fire needed a fresh severity export**, including all those already run before RBR was added. The new 2-band file uses a new filename prefix (`severity_{uid}.tif`), deliberately not reusing the old single-band `dnbr_{uid}.tif` cache, to avoid code expecting 2 bands silently misreading a stale 1-band file. `submit_severity_tasks`/`wait_and_download_severity` (renamed from the dNBR-only versions) still submit all fires in parallel. One bug surfaced during this re-export: Earth Engine's `divide()` promotes to Float64 while the Sentinel-2 bands stay Float32, so the dNBR/RBR image had two bands with mismatched dtypes and every export failed with "Exported bands must have compatible data types" until `build_severity` explicitly cast both bands with `.toFloat()`. `wait_and_download_severity` was also made resilient to one fire's export failing (prints and continues, rather than raising and losing track of every other fire's already-completed download), the same resilience pattern already applied to the submit step.

**Result: RBR did not improve cross-forest-type consistency over dNBR, at 118 fires.** `fit_all_groups(all_cells, dnbr_col="dnbr")` vs `dnbr_col="rbr"`, compared on the one height class with enough forest types reaching `fitted` status to actually test this (10-20m, the best-populated class):

| forest type | l_max (dNBR) | l_max (RBR) |
|---|---|---|
| evergreen_broadleaf | 0.194 | 0.181 |
| evergreen_needleleaf | 0.169 | 0.181 |
| mixed | 0.153 | 0.248 |

Under dNBR these three are already close together (spread ~0.04). Under RBR, Mixed jumps to 0.248 while the other two stay similar, a *wider* spread, not tighter (though Mixed has only 18 fires, so part of this is likely small-sample noise rather than a real RBR effect either way). Elsewhere, RBR made one group worse (Evergreen Broadleaf `<10m` went from cleanly `fitted` under dNBR to `degenerate_fit` under RBR) and one group arguably better (Evergreen Needleleaf `<10m`'s dNBR fit gave a physically meaningless `l_max=0.0008`, not flagged degenerate despite being implausible; RBR gave a more plausible `l_max=0.174`, though still flagged degenerate under the stricter checks). Net effect across the usable groups: a wash, not an improvement.

**Likely reason RBR didn't help here**: RBR's normalisation (dividing dNBR by pre-fire NBR density) only corrects for something when pre-fire vegetation density varies a lot across what's being compared, which is why it is used for cross-biome severity mapping (forest vs. shrubland vs. grassland). This comparison is within forest only, every group already passes the same minimum-biomass filter, so pre-fire NBR is fairly similar across Evergreen Broadleaf/Needleleaf/Mixed to begin with, leaving RBR's correction little to actually do. The forest-type inconsistency and the loss plateau are more likely caused by something downstream of the severity metric, in the biomass estimate itself, not by which optical reflectance index is used as the severity axis.

**Decision**: keep `dnbr` as the primary severity axis (unchanged `SEVERITY_BINS`/classification), keep `rbr` available as a column for future revisiting once more fires are collected (especially Mixed and Deciduous, still thin), but do not prioritise further severity-metric engineering. Effort is better spent on the two open questions below, which are more likely the actual source of the inconsistency.

Two open questions that this still does not answer: (1) why loss plateaus around 50-60% rather than closer to 90% - the leading hypothesis is CCI biomass counting standing dead trees as still present, plus 100 m pixel averaging and only 1-2 years elapsed since the fire, not tree height specifically (Evergreen Needleleaf's >20m group actually shows a *higher* l_max than its 10-20m group, the opposite of what "tall trees survive better" would predict); (2) Sentinel-1 SAR-based burn severity (Bilal's suggestion) has a plausible rationale (CCI biomass is itself partly SAR-derived, and SAR penetrates cloud/smoke, useful for the cloudier tropical fires in this project) but no standardised formula like dNBR exists for it, so it needs real investigation before it could be added, not a quick formula swap like RBR was.

## 16. Plot clarity fix, and targeting underrepresented forest types

**The uncertainty band was being misread.** Most per-fire dots fall outside the shaded band, which reads at a glance like the curve is wrong. The band is a confidence interval for the *pooled curve*, built by resampling which fires are included and refitting, it narrows as fires are added because it reflects confidence in the average, not the spread of individual fires. Individual fires vary for real reasons (local conditions, measurement noise) that more data does not shrink, so dots outside this band are expected, not a fault. More fires would in fact narrow the band further and push *more* dots outside it, the opposite of what was hoped. The plotting cell now adds a second band, the 10th-90th percentile of actual per-fire severity-class means, so the chart shows both "confidence in the trend" and "spread of real fires" side by side, clearly labelled. A proper test of whether the curve predicts well, leave-one-fire-out cross-validation (`leave_one_fire_out_cv`/`cross_validate_all_groups` in `src/curves.py`), refit on every fire but one, predict that fire's own loss, compare, is now implemented, not yet run on the current dataset.

**Forest-type coverage check.** CGLS-LC100 has 5 real forest classes; at 118 fires only 3 reach a usable (`fitted`) curve in any height class, Evergreen Needleleaf, Evergreen Broadleaf, Mixed. Deciduous Broadleaf has a reasonable fire count (10-40 per height class) but stays `degenerate_fit` throughout, likely too little spread of severity values within those fires rather than too few fires. Deciduous Needleleaf is stuck at `insufficient_data` (1-3 fires per height class).

**Targeted top-up, given Artio insures globally and the sample so far is geographically narrow.** Checked the full candidate list directly: 1,840 unused Deciduous Broadleaf fires exist (healthy pool), sampled 49 across six GFED regions (8 per region, `size >= 20 km2`). Deciduous Needleleaf is genuinely scarce, only 16 fires exist globally in the whole 2020-2021 window, 5 at the usual `size >= 20` threshold; lowered the threshold to `size >= 5` to recover 11 fires, essentially all of what exists. This is a real data scarcity, not a sampling gap, Deciduous Needleleaf may stay thin regardless of effort here. Combined sample: 216 fires queued (two excluded for the known ambiguous-`uid` issue, Section 14). Re-run not yet complete at time of writing.

## 17. Height-mosaic routing bug: a silent cause of bad data, not just failed downloads

Scaling the sample to 216 fires surfaced 56 build failures, all with the same cryptic GDAL error, `Invalid dataset dimensions: W x 0`. First suspected the AGB and forest-type downloads (both use a thumbnail-style `geemap.ee_export_image` call with a known request-size limit), and migrated both to the same batch-export-to-GCS pattern already used for severity (`submit_agb_tasks`/`wait_and_download_agb` in `biomass.py`, `submit_landcover_tasks`/`wait_and_download_landcover` in `forest_type.py`, mirroring `severity.py`). That fixed some of the 56, but most still failed identically, with files confirmed healthy on disk (correct width and height, valid CRS and bounds, checked directly with `rasterio.open`).

Tracing one failure end to end (`build_cell_table` without its `try/except`, full traceback) showed the actual failure point was `reproject_to_grid` on the **height** array, not AGB or severity. `height_mosaic_for` picks a continental GLAD mosaic by checking a fire's (lon, lat) against a routing box per mosaic, `CONTINENT_MOSAICS` in `height.py`. Those boxes were rough, generous guesses (e.g. NAM claimed lat 5-75°N), not the mosaic files' real extent. Checking all seven mosaics directly (`rasterio.open` against each live URL) showed the real extents are tighter and don't overlap the way the routing boxes implied, NAM's real coverage is lat ~13-52°N. Two distinct failure modes followed from this:

- **Misrouting**: fires at ~10°N (Colombia, Venezuela) fall inside SAM's real coverage (real top ~13°N) but were sent to NAM instead, because NAM's routing box wrongly claimed down to 5°N. `read_window` against NAM for a fire NAM doesn't actually cover returned a 0-height array, which only blew up later, deep inside `reproject_to_grid`, with no indication the real cause was a height-mosaic mismatch.
- **Genuinely out of coverage**: the remaining fires (a cluster in boreal Russia/Siberia, lon ~88-153°E lat ~52-63°N, plus one in Canada at ~52.5°N) sit outside every mosaic's real extent, GLAD's actual global coverage stops at ~52°N (the boreal limitation already noted in known issue #4). No routing fix recovers these, this is a genuine data gap.

Fixed `CONTINENT_MOSAICS` to each mosaic's real bounds (confirmed per-file, not re-estimated), and changed `height_mosaic_for`'s failure mode: a fire outside every mosaic's real coverage now raises immediately and clearly (`"no height mosaic covers (lon, lat)"`), instead of silently returning bad data that fails unpredictably three steps later. Of the 56 original failures, 28 were misrouted and now succeed, 28 are genuinely beyond GLAD's coverage and are excluded, correctly and explicitly, rather than failing with a misleading error.

**A second, separate issue found while reviewing the resulting curves**: `fit_group`'s degenerate check only caught the steepness parameter `k` pegged at its *upper* bound (a step function). `mixed, >20m` pegged at the *opposite* extreme, `k` near 0 (an almost flat line), and was reported as `fitted` even though the fitted line visibly ignored a real upward trend in the underlying per-fire data. Added a matching check for `k` near its lower bound; verified it doesn't reclassify any currently-fitted group (the smallest genuine `k` across all fitted groups is ~13.8, the new threshold is 0.5).

**Result after both fixes**: 154 fires, 507,016 cells (up from 135/499,036 before this round). Deciduous Broadleaf reaches `fitted` status in two of three height classes for the first time (`<10m`: `l_max=0.166`, 54 fires; `10-20m`: `l_max=0.182`, 71 fires), both bug fixes contributed, not just the Section 16 sampling top-up. `mixed, >20m` dropped out of the usable set, correctly, it was never a real fit.

**Deciduous Needleleaf confirmed as a genuine data-scarcity limit, not a sampling gap.** Scanned the pooled cell table directly by pixel-level `forest_type_label` (not the Fire Atlas's per-fire landcover label, which Section 12 already showed is unreliable) to check for fires containing Deciduous Needleleaf that the label-based sampling in Section 16 might have missed. Found only 4 fires with any such cells at all, the same 4 already counted in the fit table, no hidden pool. One fire (`2021_731492`) accounts for 1,316 of the 1,743 total cells (75%), so even the `10-20m` group, which technically clears the `min_fires=3`/`min_cells=200` bar, is really dominated by one fire's conditions, not a population average, consistent with its `degenerate_fit` status. More sampling within the current 2020-2021 window will not fix this; the fix would need a wider time window (which conflicts with the height-snapshot constraint in Section 4) or more fires accumulating in later Fire Atlas releases.

## 18. A second data-handling bug, found via an external biomass model, verified to not change existing conclusions

Tested Artio's own biomass model (a Cloud Function-triggered Vertex AI pipeline, 10 m resolution, separate from this project's infrastructure) against CCI AGB on the pilot fire, as a first check of whether it might be a cleaner alternative to CCI's known per-fire sensitivity issues (Sections 8/10). Output is in `tCO2e/ha` (carbon-equivalent), not `Mg biomass/ha`, converted using the standard IPCC factor (`AGB = tCO2e/ha / (0.47 x 3.67)`, carbon fraction x CO2:C molecular weight ratio). First comparison gave an unusable result, Artio's mean came out 3-4x lower than CCI's for the same area, with over half the pixels reading exactly 0.

Traced this to a second bug in `reproject_to_grid` (`src/grids.py`), the shared resampling function used everywhere in this pipeline. It never told GDAL's resampler which value counts as nodata, it just filled missing pixels with a `-9999` sentinel and averaged everything, nodata included, cleaning up afterward only if an output cell's whole average fell below a threshold. Where an output cell mixed mostly-valid input pixels with some nodata ones, the average got pulled down but often not far enough to be caught, letting a biased value through silently. Artio's raster has a genuine 35% internal nodata fraction (cloud gaps), making the bug obvious there. Fixed by passing `src_nodata` through to `reproject()` properly (GDAL then excludes those pixels from the resampling kernel, instead of blending them in). After the fix, Artio's biomass values landed close to CCI's in magnitude (84 vs 90 and 70 Mg/ha mean) and correlated with it spatially (r=0.67-0.71), encouraging, though the two Artio model IDs used disagree with each other more than either disagrees with CCI, which model is the intended one is still an open question.

**On the two `MODEL_IDS`: confirmed they are two separately-trained models, not a typo or a single model under two names, trained on different input feature sets (terrain/DEM included in one, not the other, exact difference not yet documented). Both are legitimate, picking one over the other isn't the right framing, the better approach is fitting curves against each separately and comparing, the same pattern already used for dNBR vs RBR. Not pursued yet: each fire costs roughly 1-1.5 hours of Vertex AI compute (stage1 data prep + stage2 inference), so scaling this to a usable sample size is a real, deliberate commitment, not a quick addition.

**Tested across more forest types, result is mixed, not a clean win.** Scaled from the single pilot fire (Evergreen Needleleaf) to 7 more fires, 2 each of Evergreen Broadleaf, Mixed, Deciduous Broadleaf, plus one more Evergreen Needleleaf. Needleleaf held up (correlation 0.71-0.72 with CCI, consistent with the pilot). The other three types did not: correlation ranged 0.01-0.54, one fire (`2021_745780`, Deciduous Broadleaf) showed a *negative* correlation for one model. More notably, Artio's values came out 2-4x lower than CCI's, consistently, across all 6 non-needleleaf fires, not noisy around the right value, systematically low every time. With only 2 fires per type this is too small a sample to conclude the model fails for these types outright (Mixed alone showed correlations of 0.35 and 0.01 between its two fires, as much evidence of real fire-to-fire variability as of anything about the forest type), but the consistent low-magnitude bias across every non-needleleaf fire looks more structural than noise, and is the more concerning of the two findings. Open question for whoever owns the model: whether training data skews toward conifer-dominated regions, not yet answered.

Checked whether this same bug affected the main 154-fire dataset.** Scanned every cached severity file for internal NaN fraction directly (not via `masked=True`, which can't detect nodata unless the file declares a formal nodata tag, these Earth Engine exports don't): 13 of 223 fires had over 5% NaN, one as high as 85%, confirming this was a real risk here too, not just in the Artio test. Fixed the same bug in `pipeline.py`'s `dnbr`/`rbr` reprojection calls and re-ran the 17 affected fires that are part of the main dataset (2 of the top-NaN fires, `2017_17487` and `2016_35438`, belong to a separate, not-yet-written-up exploratory test of whether loss keeps rising for several years after a fire using older 2016-2018 fires, not this dataset). **Result: no group's `fitted`/`degenerate_fit`/`insufficient_data` status changed**, and almost every `l_max` is unchanged or barely moved. The one real shift is Deciduous Needleleaf `10-20m` (`l_max` 0.092 to 0.163, that group contained one of the worst-affected fires), but it was `degenerate_fit` before and still is, so no existing conclusion changes. Worth having found and fixed regardless, confirms the pipeline handles nodata correctly going forward, but the bug's actual impact on results already reported was minimal.

## 19. Leave-one-fire-out cross-validation: a real accuracy number, not just fit quality

Fit quality on the fires a curve was built from does not say whether it predicts a *new* fire well, a curve can look clean on its own training data while still generalising poorly. Implemented `leave_one_fire_out_cv`/`cross_validate_all_groups` (`src/curves.py`): for each fire in a group, refit on every other fire, then predict that held-out fire's own per-severity-class loss and compare to what actually happened. Run on the 154-fire dataset:

| Group | n_folds | MAE | RMSE | bias |
|---|---|---|---|---|
| `<10m` deciduous_broadleaf | 80 | 0.258 | 0.441 | +0.090 |
| `<10m` evergreen_broadleaf | 121 | 0.238 | 0.358 | -0.001 |
| `<10m` mixed | 6 | 0.285 | 0.313 | -0.285 |
| `10-20m` deciduous_broadleaf | 102 | 0.265 | 0.337 | +0.115 |
| `10-20m` evergreen_broadleaf | 137 | 0.204 | 0.289 | +0.069 |
| `10-20m` evergreen_needleleaf | 93 | 0.162 | 0.224 | +0.014 |
| `10-20m` mixed | 50 | 0.156 | 0.235 | +0.027 |
| `>20m` evergreen_needleleaf | 84 | 0.215 | 0.333 | +0.007 |

(Every other group shows `n_folds=0`: these all match groups already `degenerate_fit`/`insufficient_data` in the main fit table, removing one fire from an already-thin or unstable group just keeps it thin or unstable, not a new failure, a consistency check that passed.)

Two findings. First, `10-20m` Evergreen Needleleaf and Mixed are the most trustworthy groups by this test (most folds, lowest error, close to zero bias), a new fire's loss is typically predictable to within ~15-16 percentage points there. Second, **almost every group with enough data to test shows a positive bias**, the curve systematically underpredicts a held-out fire's actual loss. This is independent evidence for the same thing Section 14's year-over-year check suggested, loss is still rising within the 1-2 year window most curves are built from, so a curve fitted on that window understates the eventual true loss. `<10m` Mixed is a genuine edge case: only 6 of its 22 fires produce a stable refit when left out, most single-fire removals leave that group unstable, meaning it sits right on the boundary of being usable rather than clearly on one side.

## 20. Does loss keep rising after a fire? A 5-fire time-elapsed check

The main dataset only has 1-2 years of post-fire biomass data per fire (CCI AGB's own availability caps at 2022), so it cannot directly show whether loss is still increasing when a curve is fitted, only whether it looks lower than expected (Sections 14, 19). To test this directly, picked fires from 2016-2018 instead, old enough that CCI already has 4-7 years of post-fire data for them. Height and forest-type labels are not valid pre-fire snapshots for fires this old (Section 4's 2019-height constraint), so this check does not use them, it only needs severity and biomass loss over time, pooled by severity class.

Built 7 candidate fires (2016-2018, North America, picked directly from the Fire Atlas shapefiles rather than the main candidate list, which excludes this period), requesting every CCI year from the fire onward instead of the usual 1-2. 2 failed for reasons unrelated to this check (height-mosaic and forest-type export issues already covered in Sections 17-18), leaving 5 usable fires with 4-6 years of data each.

**First pass, pooling all 5 fires per "years since fire", was misleading.** It showed a dramatic jump in loss around year 5 for every severity class. This turned out to be a composition artefact, not a time effect: the two fires with data out to year 5-6 are 2016 fires, and the fires that drop out past year 4 (the 2018 fires) happen to sit at a lower loss level to begin with. The pooled average rising sharply at year 5 just reflects which fires are still contributing, not those fires' own loss changing.

**Re-did it per fire instead** (this fixes the composition problem, since each line only compares a fire against itself over time): results are mixed, not a single clean story. Two fires (`2016_21304`, `2016_7022`) keep rising through year 2, then genuinely plateau by year 3, flat out to year 6. One fire (`2017_17487`) is still rising at year 4-5, no plateau reached within the data available. Two fires (`2018_7021`, `2018_215`) show no rising trend at all, one even dips slightly before flattening.

**Reburn check, and a correction to the above.** Checked each of the 5 fires against the Fire Atlas for any other fire overlapping the same area in a later year through 2022 (a second fire within the observation window would show up as "continued loss" that has nothing to do with the original fire slowly decaying). 3 of 5 have confirmed overlapping later fires: `2016_21304` (2018, 2020 x6, 2021 x6, 2022), `2017_17487` (2018 x8, 2021 x4), `2018_215` (2019, 2020 x3). Only `2016_7022` and `2018_7021` are clean.

This matters a lot: `2017_17487`, the fire still rising at year 4-5 and the strongest evidence for a multi-year effect, is one of the contaminated ones, its continued rise could easily be a second fire, not the first one still settling. Of the two genuinely clean fires, `2016_7022` plateaus by year 2-3 and `2018_7021` shows no rise at all. Neither clean fire supports a multi-year rise.

**Revised conclusion**: this 5-fire check is inconclusive, not supportive, of the "loss keeps rising for years" hypothesis. The apparent rising-trend evidence was concentrated in the fires most likely to be contaminated by later, unrelated fires; the clean fires do not show it. Section 19's cross-validation bias (curves tend to underpredict held-out fires) still stands as a separate, dataset-wide finding, but this specific test does not independently confirm a time-elapsed explanation for it, and should not be cited as if it does. A proper version of this check would need either a larger sample of fires confirmed free of later disturbance, or a way to mask out/exclude the overlapping fire's own footprint from the loss calculation, neither attempted here.

## 21. Cross-validation, in concrete terms: two real held-out fires

Section 19's error numbers are averages over many folds, worth grounding in two actual examples, a typical case from each of the two best-validated groups, not cherry-picked best cases.

`2020_167823` (Evergreen Needleleaf, 10-20m), held out while refitting on every other fire in its group: in its `severe` class (273 cells), the refit curve predicted 17.0% loss, the fire actually lost 4.8%, an error of about 12 points, and in this case an overprediction, not an underprediction. `2021_169679` (Mixed, 10-20m): in its `moderate` class (99 cells), predicted 0.4% loss against an actual 9.7%, an underprediction, consistent with this group's measured average bias.

Worth keeping the first example specifically because it cuts against the "curves underpredict" pattern from Section 19. The bias found there is a tendency across many fires, not a rule every individual fire obeys, and a worked example that happens to overpredict is more honest to show than only picking ones that confirm the average.

## 22. A bias correction, tested properly, fixes the ceiling but not the per-fire error

Section 19 found that most groups' curves underpredict a held-out fire's loss, by a measured, group-specific amount. Tried correcting for it: shift each group's `l_max` up by its measured bias, capped at 1.0. Applied only to `l_max` (steepness and midpoint unchanged), a deliberate simplification, the real underprediction may not be uniform across severity classes, and this has not been checked.

**The correction was itself validated, not just assumed to help**, using a leave-one-out version of the bias (each held-out fire's correction computed from every *other* fire's residuals, not its own, to avoid testing the correction against the data it was built from):

| Group | Raw MAE / bias | Corrected MAE / bias |
|---|---|---|
| Evergreen Needleleaf, 10-20m | 0.162 / 0.014 | 0.165 / -0.000 |
| Mixed, 10-20m | 0.156 / 0.027 | 0.157 / -0.000 |
| Evergreen Broadleaf, 10-20m | 0.204 / 0.069 | 0.205 / -0.000 |
| Deciduous Broadleaf, 10-20m | 0.265 / 0.115 | 0.258 / -0.000 |
| Evergreen Needleleaf, >20m | 0.215 / 0.007 | 0.217 / -0.000 |

The bias is reliably removed (correction works as designed), but MAE barely moves, and gets slightly worse for three of five groups. Only `Deciduous Broadleaf`, which had the largest bias relative to its noise, improved meaningfully. **Conclusion**: the remaining error in most groups is genuine fire-to-fire variation, not a shared, correctable offset, a bias correction can only fix the latter. Keep the correction for reporting a more honest eventual-loss ceiling (it is evidence-based, not a guess), but it is not a substitute for more fires, which is the only lever that addresses noise.

Adjusted ceilings (the five usable groups, raw l_max vs corrected): Deciduous Broadleaf 10-20m 18.1% -> 29.6%, Evergreen Broadleaf 10-20m 24.0% -> 30.9%, Evergreen Needleleaf 10-20m 17.1% -> 18.5%, Mixed 10-20m 15.4% -> 18.1%, Evergreen Needleleaf >20m 39.6% -> 40.3%. Even corrected, none of these approach 60-90%, the shifts are real but modest, which is itself evidence that the gap to near-total loss is not a measurement-bias artefact.

## 23. NDVI tested as an alternative to biomass loss, found not to track it

Tested whether NDVI (vegetation greenness from Sentinel-2) could supplement or replace biomass as the loss measure, same before/after composite approach as dNBR (`src/ndvi.py`, mirrors `severity.py`'s pattern exactly, including the explicit `toFloat()` cast that fixed the earlier dNBR/RBR dtype export bug). Ran it on 15 fires across multiple forest types.

**Result: no usable relationship.** Of the 15 fires, only 3 had enough valid cells to test at all (an NDVI loss value needs both the pre- and post-fire pixel to be cloud-free, so any gap in either kills that cell, a stricter requirement than dNBR's own, and 12 of 15 fires lost nearly all their cells to this). In the 3 fires that could be tested, correlation between NDVI loss and biomass loss was essentially zero (-0.006, +0.002, +0.030), and the magnitudes did not agree either, in one fire NDVI showed a much larger drop than biomass (41% vs 6%), in another they coincided (18% vs 18%), in a third NDVI actually increased after the fire while biomass showed almost no change, consistent with fast-regrowing understory vegetation greening up well before the actual carbon loss is reflected.

**Conclusion**: NDVI, computed this directly, is not a usable substitute or supplement for biomass as a carbon-loss measure here. It also showed a second, independent weakness, markedly higher sensitivity to cloud cover than dNBR, on top of not tracking the thing we need measured.

## 24. Two externally-suggested resources evaluated, both ruled out

**A Hugging Face biomass model** (`vertify/biomass-model`, StableResNet architecture): checked both its model card and underlying GitHub repo. Trained and validated against LiDAR reference maps from four tropical research sites only (two in India, one in India, one in Thailand), despite the model card describing broad applicability across tropical, temperate and boreal forest. No comparison against CCI or GEDI reported. Requires Sentinel-1 radar and a DEM as inputs, infrastructure not built in this project. As a passive biomass estimator, it most likely shares CCI's own core limitation (slow to register loss from standing dead trees), not a different one, so even disregarding the infrastructure cost and narrow validation, it is unlikely to solve the actual problem this project has with CCI.

**A Hugging Face wildfire dataset** (`moritzrengert1/wildfire_global`): built for evaluating vision-language models on burn severity classification, not a biomass or carbon dataset. Contains only severity labels and 224x224 pixel image chips, no biomass measurements, so it cannot supply the before/after carbon measurement the curves are built from, under any framing.

Neither pursued further.

## 25. Checked for a newer biomass release, not actually available yet

Considered adopting a newer CCI Biomass release (covering through 2024, not just 2022) to directly address the limited post-fire observation window (Sections 19, 22). Checked two sources before committing to this: an Earth Engine community-hosted asset (`projects/sat-io/open-datasets/ESA/ESA_CCI_AGB`) turned out, on inspection, to be a mirror of the existing v6.0 data (same years, 2007-2022, explicit `'product_version': '6.0'` in its metadata), not a newer version. CEDA, the dataset's own official host, confirms directly that v6.0 is current and 2023/2024 data "are not yet available." **No usable newer release exists yet.** Worth re-checking periodically, not worth building anything around until it actually ships.

## 26. Steep terrain confirmed as a cause of implausible short-height readings, but not a universal one

Known issue #8 (GLAD height unreliable on steep terrain) was a suspected cause, based on one fire's implausible height/biomass combinations, never directly checked against a terrain layer. Pulled SRTM-derived slope (`USGS/SRTMGL1_003` via Earth Engine) and compared it directly against cells flagged as implausible (height under 10m but biomass over 200 Mg/ha, far more than genuinely short vegetation carries), across three fires in different regions.

**`2020_135`** (Sierra Nevada, where this was first noticed): a clean, strong confirmation. Implausible cells average 27.4 degrees of slope against 16.4 degrees for normal cells (n=1,460 vs 109,641), the two distributions barely overlap. **`2020_112`** (same general Northern California region): same direction, implausible cells steeper (22.8 vs 18.2 degrees), but a much weaker, noisier signal, and far fewer implausible cells (36). **`2020_841874`** (Southeast Asia, a genuinely different region): **the pattern reverses.** Implausible cells show *lower* slope than normal cells (14.9 vs 18.2 degrees), the opposite of the hypothesis.

**Revised conclusion**: steep terrain is a real, confirmed cause of this problem, at least in mountainous temperate terrain (both California fires point the same direction, even if the effect size varies a lot). It is not a universal explanation, the Southeast Asia fire shows no such relationship, and if anything points the other way, meaning something else, most likely dense tropical canopy structure interacting with the height model differently, is responsible for at least some implausible `<10m` readings elsewhere. A usable fix is therefore more likely to need a region- or terrain-type-aware approach than a single global slope threshold, and there may be more than one distinct cause behind the broader `<10m` reliability issue, not one. Worth testing more fires per region before building anything, not generalising from the strong single-fire result that started this.

## 27. A second, targeted scaling round: a mixed result, not a clean win

Section 19's cross-validation and the noise diagnosis that followed it (checked `Evergreen Broadleaf >20m` and `Deciduous Broadleaf 10-20m` directly: both show a sensible average loss-vs-severity trend, but cell-level standard deviation as large as or larger than the mean, i.e. genuine fire-to-fire noise, not a biased or absent relationship) pointed at more fires, specifically for these two groups, as the correct next fix, not further correction or a different severity metric.

Selected 113 additional fires (53 Deciduous Broadleaf, 60 Evergreen Broadleaf, stratified by GFED region, same method as Section 16's top-up). 111 of 113 succeeded (2 failed, not investigated, a small enough loss not to chase). Dataset grew from 154 to 265 fires, 507,169 to 592,048 cells.

**A third bug found during this round, same family as the nodata issue in Section 18.** `height_class` (the `<10m`/`10-20m`/`>20m` category) is not part of `build_cell_table`'s output, it is derived separately, by the pooling step that first builds `full`, from the raw `height` column. That derivation was never reapplied to the 111 new fires before concatenating them in, so they carried a missing `height_class`, and every group-by silently dropped them, no error, just quietly excluded, producing results identical to the pre-top-up run despite `full` genuinely containing the new cells. Caught by checking `full["height_class"].isna().sum()` directly rather than trusting that a non-error result was a correct one. Fixed by reapplying the original binning (`pd.cut(full["height"], [0, 10, 20, 100], labels=[...])`) to the whole, combined table.

**The actual result, once the data was genuinely updated:**

| Group | Before: status / l_max / n_fires / cells | After: status / l_max / n_fires / cells |
|---|---|---|
| Mixed, >20m | degenerate / - / 18 / 303 | **fitted** / 18.3% / 24 / 842 |
| Deciduous Broadleaf, 10-20m | fitted / 18.1% / 71 / 6,508 | fitted / 20.2% / 102 / 8,014 |
| Evergreen Broadleaf, >20m | degenerate / - / 48 / 31,339 | still degenerate / - / 93 / 76,745 |
| Evergreen Broadleaf, 10-20m | fitted / 24.0% / 75 / 52,865 | fitted / 31.4% / 145 / 72,625 |

One genuine new group (`Mixed, >20m`, thin and noisy, MAE 0.237, the weakest of the six, worth saying so plainly rather than presenting it with the same confidence as the better-validated groups). One target partially helped (`Deciduous Broadleaf, 10-20m`'s cross-validated MAE improved from 0.265 to 0.249, though its bias did not improve). One target unresolved (`Evergreen Broadleaf, >20m` is still degenerate, nearly doubling its fires changed *which* parameter fails, not whether it fails, its ceiling parameter now has a standard error in the millions). And one group that was not a target and was not broken got measurably worse (`Evergreen Broadleaf, 10-20m`'s cross-validated MAE rose from 0.204 to 0.216, and its curve shape shifted substantially, despite looking visually plausible on the plot, a good concrete example of why a clean-looking chart is not the same as a validated one).

**Conclusion**: "more fires fixes noise" was too simple a rule. It worked for one group, partially helped another, did not fix the main target, and destabilised a group that was already fine. The most likely explanation is that this batch of fires is not simply "more of the same", it introduces real heterogeneity (different regions, conditions) that does not blend cleanly into `Evergreen Broadleaf` specifically. Reporting this honestly, including the regression, rather than keeping whichever version of the data makes each group look best.

**Bias correction, redone on this updated dataset** (supersedes Section 22's table, same method):

| Group | Raw l_max | Adjusted l_max |
|---|---|---|
| Deciduous Broadleaf, 10-20m | 20.2% | 32.3% |
| Evergreen Broadleaf, 10-20m | 31.4% | 38.3% |
| Evergreen Needleleaf, 10-20m | 17.1% | 17.9% |
| Mixed, 10-20m | 15.6% | 19.6% |
| Evergreen Needleleaf, >20m | 39.6% | 40.3% |
| Mixed, >20m | 18.3% | 21.4% |

Same conclusion as before: real, modest shifts, nothing approaching 60-90%.

## 28. Drought (SPEI-12) tested as a candidate explanatory factor, no evidence found so far

Artio supplied a global SPEI-12 drought dataset (`spei12.nc`, 0.5 degree monthly grid, 1901-2023, negative values dry, positive wet), suggested as a possible addition. SPEI's grid is far coarser than the 100m biomass grid, so unlike height or severity this is naturally a single value per fire, not a per-pixel layer, which simplifies testing it: rather than rebuilding the per-pixel pipeline, checked whether pre-fire drought conditions (nearest grid cell and month before the fire started) correlate with each fire's own residual from leave-one-fire-out cross-validation, i.e. does a fire that was drier than usual beforehand tend to lose more than the severity-only curve predicts.

**Result, on the two groups it could be tested on**: no meaningful relationship. `Evergreen Broadleaf, 10-20m` (n=144): correlation 0.055. `Evergreen Needleleaf, 10-20m` (n=40): correlation -0.020. Both close enough to zero to call null, and not a small-sample issue, 144 fires is larger than several groups already trusted elsewhere in this project, a real effect of meaningful size should show at least some signal at that scale.

**The third, most interesting group could not be tested at all.** `Evergreen Broadleaf, >20m` already has zero valid cross-validation folds (Section 27), its instability means a leave-one-out refit on 92 of its 93 fires is still usually degenerate, so there is no valid per-fire residual to correlate against anything, drought included. That is a dependency, not a workaround, this group cannot be tested this way until its own fit problem is resolved first.

**Caveats, this was a fast, narrow test, not a thorough one.** It used a single nearest-point, nearest-month drought value and averaged each fire's residual across all its severity classes, a real effect with a different lag (drought 1-2 years prior, not the month before), a severity-specific effect, or a non-linear/threshold effect (only mattering in genuinely extreme drought years) would not necessarily show up in a simple linear correlation like this.

**Separately, worth noting**: this test (does drought explain leftover error in the existing severity-based curves) is a narrower question than a planned future piece of work, building a parallel set of loss curves with drought as the primary axis instead of height, the way the current curves use height. This result does not pre-judge that, it is a different exercise, flagged as a later priority, not started.

## Infrastructure

- GCP project `tree-fire` (display name), project ID `tree-fire-510209`; Vertex AI Workbench instance `tree-fire-workbench`, zone `europe-west2-a`; Python venv `.venv` with earthengine-api, geemap, pandas, geopandas, pyarrow, ipykernel, rasterio, pyogrio.
- Earth Engine use requires the actual project ID (`tree-fire-510209`), not the display name, plus the project registered for Earth Engine access and the caller's account holding `roles/serviceusage.serviceUsageConsumer`.
- All static layers were downloaded directly to the instance's disk under `data/`, which is gitignored.
- A GCS bucket, `gs://tree-fire-510209-data`, in `europe-west2`, is a required intermediate for severity exports (`Export.image.toCloudStorage` lands there, then `gsutil cp` pulls it onto the instance). It is **not** an automatic backup of `data/`: everything else lives only on the instance's disk unless manually synced, for example `gsutil -m rsync -r data/processed gs://tree-fire-510209-data/fire-impact-curves/data/processed`.
- As of the `src/` pipeline (see "Reproducibility"), biomass and forest type are pulled from Earth Engine directly rather than downloaded per tile, so any fire globally works for those two without manual downloads. Height needs the right GLAD continental mosaic looked up by location (`src/height.py`); all seven mosaics are now confirmed and configured (Section 11), though GLAD's own coverage stops at roughly 52°S-52°N, so high-latitude boreal fires have no usable height regardless of mosaic.

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
- `severity.py`: dNBR and RBR (Section 15) from Sentinel-2 via Earth Engine.
- `ndvi.py`: NDVI pre/post fire from Sentinel-2, tested as an alternative loss measure (Section 23), not part of the main pipeline, found not to track biomass loss.
- `temperature.py`: brightness temperature from FIRMS, optional, off by default (Section 14).
- `forest_type.py`: forest type (CGLS-LC100, Earth Engine asset `COPERNICUS/Landcover/100m/Proba-V-C3/Global`, band `forest_type`), any fire globally, legend confirmed in that module's docstring.
- `height.py`: canopy height (GLAD), continental mosaic looked up by the fire's location, all seven mosaics confirmed and configured (Section 11); GLAD's own data only covers ~52°S-52°N regardless.
- `pipeline.py`: `build_cell_table(uid, ...)`, ties the above together for one fire; `submit_severity_tasks`/`wait_and_download_severity` for running many fires in parallel (Section 14).

Batch runs live in `notebooks/run_pipeline.ipynb` (Section 13), run top to bottom: imports, fire configs, stratified sampling, submit/wait/build, pooling, curve fitting, plotting. `notebooks/data.ipynb` is the exploratory record of Sections 8-13's one-off diagnostics, not used for batch runs. `notebooks/terrain_exploration.ipynb` is a new, separate exploratory notebook for the steep-terrain check in Section 26, kept apart from the other two so it doesn't compete for resources with an active batch run. Remaining open item: the steep-terrain height reliability issue (known issue #8), now with direct evidence behind it (Section 26), not yet built into the pipeline as an actual filter.

## References

- Andela, N. et al. (2019). The Global Fire Atlas of individual fire size, duration, speed and direction. *Earth System Science Data* 11, 529-552. Updated version: Andela, N., Jones, M., Zenodo, doi:10.5281/zenodo.11400062 (v20240409).
- Santoro, M., Cartus, O. (2025). ESA Biomass CCI: global datasets of forest above-ground biomass for 2007, 2010, 2015-2022, v6.0. NERC EDS CEDA. doi:10.5285/95913ffb6467447ca72c4e9d8cf30501.
- Potapov, P. et al. (2021). Mapping global forest canopy height through integration of GEDI and Landsat data. *Remote Sensing of Environment* 253, 112165. doi:10.1016/j.rse.2020.112165.
- Cansler, C.A. et al. (2020). The Fire and Tree Mortality Database, for empirical modeling of individual tree mortality after fire. *Scientific Data* 7, 194. doi:10.1038/s41597-020-0522-7. Archive: doi:10.2737/RDS-2020-0001.
- Hood, S.M. et al. (2018). Fire and tree death: understanding and improving modeling of fire-induced tree mortality. *Environmental Research Letters*.
- Van Wagner, C.E. (1973). Height of crown scorch in forest fires. *Canadian Journal of Forest Research*.