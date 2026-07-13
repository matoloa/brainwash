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
):
    valid_obs1 = obs1[np.isfinite(obs1)]
    n_obs1 = len(valid_obs1)
    if (short == "amp" or short == "slope") and n_obs1 >= 3:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                sw_stat, sw_p = shapiro(valid_obs1)
            set_result[f"sw_stat_{short}"] = float(sw_stat)
            set_result[f"sw_p_{short}"] = float(sw_p)
        except Exception:
            set_result[f"sw_stat_{short}"] = np.nan
            set_result[f"sw_p_{short}"] = np.nan
        if len(shown_groups) >= 2 or (test_type == "ANOVA" and len(shown_sets) >= 2):
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
                if len(groups_for_lev) >= 2:
                    lev_stat, lev_p = levene(*groups_for_lev, center="mean")
                    set_result[f"levene_stat_{short}"] = float(lev_stat)
                    set_result[f"levene_p_{short}"] = float(lev_p)
                else:
                    set_result[f"levene_stat_{short}"] = np.nan
                    set_result[f"levene_p_{short}"] = np.nan
            except Exception:
                set_result[f"levene_stat_{short}"] = np.nan
                set_result[f"levene_p_{short}"] = np.nan