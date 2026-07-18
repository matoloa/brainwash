import warnings

import numpy as np
from scipy.stats import levene, shapiro

from .data import _aggregate_to_unit_level


def _sw_on_sample(values) -> tuple[float | None, str | None]:
    """Return (p, skip_reason). Shapiro needs ≥3 finite values."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    n = int(len(v))
    if n < 3:
        return None, f"n={n}<3"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _stat, p = shapiro(v)
        if np.isfinite(p):
            return float(p), None
        return None, "nonfinite"
    except Exception:
        return None, "failed"


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

    SW is run **per group** when two groups are compared (unpaired); for one-sample /
    paired only the primary sample is tested. Keys:
      sw_p_{aspect}_g1, sw_p_{aspect}_g2  (and sw_p_{aspect} = min for statusbar)
      sw_skip_{aspect}_g1 / _g2 when not computable

    Levene needs ≥2 groups with ≥2 finite values each.
    """
    if not do_sw and not do_levene:
        return
    if short not in ("amp", "slope"):
        return

    valid_obs1 = obs1[np.isfinite(obs1)]
    valid_obs2 = obs2[np.isfinite(obs2)] if obs2 is not None else np.array([])

    if do_sw:
        p1, sk1 = _sw_on_sample(valid_obs1)
        if p1 is not None:
            set_result[f"sw_p_{short}_g1"] = p1
        else:
            set_result[f"sw_skip_{short}_g1"] = sk1 or "n<3"

        between_groups = g2 is not None and len(valid_obs2) > 0
        p2, sk2 = None, None
        if between_groups:
            p2, sk2 = _sw_on_sample(valid_obs2)
            if p2 is not None:
                set_result[f"sw_p_{short}_g2"] = p2
            else:
                set_result[f"sw_skip_{short}_g2"] = sk2 or "n<3"

        # Aggregate for statusbar: worst (min) p among groups that were tested
        ps = [p for p in (p1, p2) if p is not None]
        if ps:
            set_result[f"sw_p_{short}"] = float(min(ps))
        elif sk1:
            set_result[f"sw_skip_{short}"] = sk1

    if do_levene:
        can_multi = len(shown_groups) >= 2 or (test_type == "ANOVA" and len(shown_sets) >= 2)
        if not can_multi:
            set_result[f"levene_skip_{short}"] = "need ≥2 groups/sets"
            return
        try:
            groups_for_lev = [valid_obs1]
            if g2 is not None:
                groups_for_lev.append(valid_obs2)
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
