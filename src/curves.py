"""Fit a smooth loss-vs-severity curve per height x forest-type group (roadmap Step 6).

Loss is expected to rise with dNBR in a roughly S-shaped way: low for mild fires,
rising fast through moderate, levelling off near total loss for severe fires. A
three-parameter logistic captures that shape with a sensible number of parameters
for the small number of fires available early on; revisit if the data outgrows it.

Uncertainty is computed by fire, not by pixel (roadmap Step 6, README Section 6/10's
findings on fire-to-fire variation): for each fire, compute its own mean loss per
severity bin, then the spread across those per-fire means is the uncertainty, not
the spread across pixels within one fire (pixels within a fire are not independent
observations of the loss-severity relationship).
"""

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit


def logistic(x, l_max, k, x0):
    """l_max: loss share as dNBR -> infinity (should end up <= 1).
    k: steepness. x0: dNBR at the curve's midpoint (half of l_max)."""
    return l_max / (1 + np.exp(-k * (x - x0)))


def fit_group(df, dnbr_col="dnbr", loss_col="loss2022", min_fires=3, min_cells=200):
    """Fit one logistic curve to one height x forest-type group's pooled cells.

    Returns a dict with the fitted parameters, or None if there isn't enough data
    yet to fit (fewer than `min_fires` distinct fires, or `min_cells` total cells) -
    a curve from 1-2 fires is not a curve, it is that fire's noise.
    """
    n_fires = df["uid"].nunique()
    if n_fires < min_fires or len(df) < min_cells:
        return {"status": "insufficient_data", "n_fires": n_fires, "n_cells": len(df)}

    x = df[dnbr_col].to_numpy()
    y = df[loss_col].to_numpy()
    k_upper_bound = 50
    try:
        popt, pcov = curve_fit(
            logistic, x, y,
            p0=[0.5, 5, 0.4],             # rough starting guess: l_max=0.5, midpoint dNBR=0.4
            bounds=([0, 0, -1], [1, k_upper_bound, 2]),
            maxfev=5000,
        )
    except RuntimeError as e:
        return {"status": "fit_failed", "error": str(e), "n_fires": n_fires, "n_cells": len(df)}

    # k pegged against its upper bound means curve_fit found an (almost) step function,
    # not a real smooth logistic - the data didn't constrain steepness. Flag rather than
    # report alongside genuine fits; seen so far concentrated in the <10m height class,
    # consistent with the known GLAD-height-on-steep-terrain issue (README #8).
    degenerate = popt[1] >= k_upper_bound * 0.999

    return {
        "status": "degenerate_fit" if degenerate else "fitted",
        "l_max": popt[0], "k": popt[1], "x0": popt[2],
        "param_std_err": np.sqrt(np.diag(pcov)).tolist(),
        "n_fires": n_fires, "n_cells": len(df),
    }


def per_fire_severity_means(df, severity_col="severity", loss_col="loss2022"):
    """Per-fire, per-severity-class mean loss, the basis for by-fire uncertainty:
    spread these across fires within a class, not pixels within a fire.
    """
    return (
        df.groupby(["uid", severity_col], observed=True)[loss_col]
        .mean()
        .reset_index()
        .pivot(index="uid", columns=severity_col, values=loss_col)
    )


def fit_all_groups(all_cells, height_col="height_class", forest_type_col="forest_type_label",
                    dnbr_col="dnbr", loss_col="loss2022",
                    exclude_forest_types=("unknown", "not_forest")):
    """Fit (or report insufficient data for) every height x forest-type group present.

    `unknown` ("tree cover present but CGLS-LC100 couldn't classify the type") and
    `not_forest` are excluded by default, fitting a curve to "unclassified forest"
    is meaningless, not a real group to report.
    """
    results = {}
    usable = all_cells[~all_cells[forest_type_col].isin(exclude_forest_types)]
    for (h, ft), grp in usable.groupby([height_col, forest_type_col], observed=True):
        results[(h, ft)] = fit_group(grp, dnbr_col=dnbr_col, loss_col=loss_col)
    return pd.DataFrame(results).T
