import warnings

import numpy as np
from scipy.stats import levene, shapiro

from .data import _aggregate_to_unit_level


def _apply_assumption_tests(
    set_result,
    *,
    short,
    obs1,
    obs2,
    g2,
    shown_groups,
    test_type,
    shown_sets,
    sid,
    fetch_group_testset_observations,
    n_unit,
    col,
    do_sw: bool = True,
    do_levene: bool = True,
):
    """SW / Levene for formal tests. Gated by do_sw / do_levene (UI checkboxes).

    SW needs ≥3 finite values in the primary sample (scipy Shapiro).
    Levene needs ≥2 groups with ≥2 finite values each (not the old n≥3 gate).
    Skip reasons are stored as sw_skip_{short} / levene_skip_{short} for statusbar.
    """
    if not do_sw and not do_levene:
        return
    if short not in ("amp", "slope"):
        return

    valid_obs1 = obs1[np.isfinite(obs1)]
    n_obs1 = int(len(valid_obs1))

    if do_sw:
        if n_obs1 >= 3:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    sw_stat, sw_p = shapiro(valid_obs1)
                set_result[f"sw_stat_{short}"] = float(sw_stat)
                set_result[f"sw_p_{short}"] = float(sw_p)
            except Exception:
                set_result[f"sw_stat_{short}"] = np.nan
                set_result[f"sw_p_{short}"] = np.nan
                set_result[f"sw_skip_{short}"] = "failed"
        else:
            set_result[f"sw_skip_{short}"] = f"n={n_obs1}<3"

    if do_levene:
        can_multi = len(shown_groups) >= 2 or (test_type == "ANOVA" and len(shown_sets) >= 2)
        if not can_multi:
            set_result[f"levene_skip_{short}"] = "need ≥2 groups/sets"
            return
        try:
            groups_for_lev = [valid_obs1]
            if g2 is not None:
                groups_for_lev.append(obs2[np.isfinite(obs2)])
            elif test_type == "ANOVA" and len(shown_groups) == 1:
                for sid2, tset2 in shown_sets:
                    if sid2 == sid:
                        continue
                    try:
                        o_df = fetch_group_testset_observations(shown_groups[0], tset2, col)
                        o_df = _aggregate_to_unit_level(o_df, n_unit)
                        o_vals = o_df["value"].to_numpy(dtype=float)
                        groups_for_lev.append(o_vals[np.isfinite(o_vals)])
                    except Exception:
                        pass
            groups_for_lev = [np.asarray(g, dtype=float) for g in groups_for_lev if len(g) >= 2]
            if len(groups_for_lev) >= 2:
                lev_stat, lev_p = levene(*groups_for_lev, center="mean")
                if np.isfinite(lev_stat) and np.isfinite(lev_p):
                    set_result[f"levene_stat_{short}"] = float(lev_stat)
                    set_result[f"levene_p_{short}"] = float(lev_p)
                else:
                    set_result[f"levene_skip_{short}"] = "degenerate"
            else:
                set_result[f"levene_skip_{short}"] = "n<2 per group"
        except Exception:
            set_result[f"levene_stat_{short}"] = np.nan
            set_result[f"levene_p_{short}"] = np.nan
            set_result[f"levene_skip_{short}"] = "failed"
