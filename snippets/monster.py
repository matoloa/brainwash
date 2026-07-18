        eff = self._effective_test_type()
        if eff == "None":
            uistate.statusbar_state = None
            return None
        if eff == "ANCOVA":
            # Dedicated IO regression path (Phase 3 + debug fix): always defer to formal_test_results/config (bypasses ANOVA guard).
            # This prevents "ANCOVA requires >=2 groups" even with valid groups (the config check at top of function now takes precedence via early formal check).
            formal = getattr(uistate, "formal_test_results", None)
            if formal:
                # Defensive shape handling (per plan_v0.16.4 Phase 2b): supports [config], [{"config": ...}], bare dict, etc.
                if isinstance(formal, list) and formal:
                    item = formal[0]
                    if isinstance(item, dict):
                        cfg = item.get("config") or item
                elif isinstance(formal, dict):
                    cfg = formal.get("config") or formal
                else:
                    cfg = None
                if isinstance(cfg, dict) and cfg.get("type") == "IO regression":
                    prefix = "IO regression"
                    global_notes = []
                    slope_p = cfg.get("slope_p") or (formal[0] if isinstance(formal, list) else formal).get("slope_p")
                    if isinstance(slope_p, (int, float)) and np.isfinite(slope_p):
                        pstr = f"{slope_p:.3g}" if slope_p >= 0.001 else "<0.001"
                        global_notes.append(f"slope p={pstr}")
                    for g, r2v in cfg.get("r2_per_group", {}).items():
                        if isinstance(r2v, (int, float)) and np.isfinite(r2v):
                            global_notes.append(f"r²({g})={r2v:.2f}")
                            break
                    n_report = ""
                    group_ns = cfg.get("group_ns") or (formal[0] if isinstance(formal, list) else formal).get("group_ns", {})
                    if group_ns:
                        ns = [f"{g}={n}" for g, n in group_ns.items()]
                        n_report = ", ".join(ns)
                    if n_report:
                        global_notes.append(f"({n_report})")
                    if global_notes:
                        prefix = f"{prefix} ({' '.join(global_notes)})"
                    uistate.statusbar_state = "info"
                    return prefix
            # No valid config/results yet (common on initial IO switch): clear and hint
            uistate.statusbar_state = None
            return "Select ≥2 groups for IO regression (computes slope via ANCOVA)"

        # Non-IO explicit test path
        test_type = eff
        ref_attr = "label_test_wilcox_one_sample_value" if test_type == "Wilcoxon" else "label_test_t_one_sample_value"
        ref_value = getattr(uistate, ref_attr, 0.0)
        if test_type not in ("t-test", "ANOVA", "Wilcoxon", "Friedman", "Cluster perm."):
            uistate.statusbar_state = "warning"
            return f"Statistical test '{test_type}' is not implemented"
        # Groups with data
        if not hasattr(self, "dd_groups") or not isinstance(self.dd_groups, dict) or not self.dd_groups:
            uistate.statusbar_state = "warning"
            return "Create groups to use statistical test"
        shown_groups = self._get_shown_group_ids()
        shown_groups = [gid for gid in shown_groups if len(self.dd_groups.get(gid, {}).get("rec_IDs", [])) > 0]
        variant = getattr(uistate, "test_t_variant", "unpaired")
        if test_type == "t-test":
            if variant == "one-sample":
                if len(shown_groups) != 1:
                    uistate.statusbar_state = "warning"
                    return "t-test (one-sample) requires exactly 1 group with data"
            elif variant == "paired":
                shown_ts = self._get_shown_testsets()
                if len(shown_groups) != 1 or len(shown_ts) != 2:
                    uistate.statusbar_state = "warning"
                    return "t-test (paired) requires exactly 1 group and exactly 2 test sets"
                n1 = len(self.dd_groups.get(shown_groups[0], {}).get("rec_IDs", []))
                if n1 < 2:
                    uistate.statusbar_state = "warning"
                    return "t-test (paired) requires N ≥ 2 recordings per group"
            else:
                if len(shown_groups) != 2:
                    uistate.statusbar_state = "warning"
                    return "t-test requires exactly 2 groups with data"
        elif test_type == "ANOVA":
            shown_ts = self._get_shown_testsets()
            is_io = getattr(uistate, "experiment_type", "time") == "io"
            # ANOVA allows: >=2 groups (between-subjects), or 1 group + >=2 test sets (repeated-measures).
            # IO (ANCOVA effective) allows 0 test sets (implicit via _effective_test_type).
            if len(shown_groups) < 2 and len(shown_ts) < 2 and not (self._is_io_mode() and len(shown_ts) == 0):
                uistate.statusbar_state = "warning"
                return "ANOVA requires either >=2 groups with data, or 1 group with >=2 test sets (repeated-measures)"
            if not shown_ts and not self._is_io_mode():
                uistate.statusbar_state = "warning"
                return "Show at least one test set to run the test"
        elif test_type == "Wilcoxon":
            shown_ts = self._get_shown_testsets()
            variant = getattr(uistate, "test_wilcox_variant", "paired")
            if variant == "paired":
                if len(shown_groups) != 1 or len(shown_ts) != 2:
                    uistate.statusbar_state = "warning"
                    return "Wilcoxon (paired) requires exactly 1 group and exactly 2 test sets"
                n1 = len(self.dd_groups.get(shown_groups[0], {}).get("rec_IDs", []))
                if n1 < 2:
                    uistate.statusbar_state = "warning"
                    return "Wilcoxon (paired) requires N ≥ 2 recordings per group"
            else:
                # one-sample
                if len(shown_groups) != 1:
                    uistate.statusbar_state = "warning"
                    return "Wilcoxon (one-sample) requires exactly 1 group with data"
            if not shown_ts:
                uistate.statusbar_state = "warning"
                return "Show at least one test set to run the test"
        elif test_type == "Friedman":
            shown_ts = self._get_shown_testsets()
            if len(shown_groups) != 1 or len(shown_ts) < 3:
                uistate.statusbar_state = "warning"
                return f"Friedman requires exactly 1 group and at least 3 test sets (repeated-measures omnibus) (shown_groups={len(shown_groups)}, shown_ts={len(shown_ts)})"
            if not shown_ts and not self._is_io_mode():
                uistate.statusbar_state = "warning"
                return "Show at least one test set to run the test"
        elif test_type == "Cluster perm.":
            shown_ts = self._get_shown_testsets()
            if len(shown_groups) >= 2:
                # Between-subjects: ok (uses first 2 groups)
                pass
            elif len(shown_groups) == 1 and len(shown_ts) == 2:
                # Paired: check sweeps >=2 per set
                for _, tset in shown_ts:
                    if len(tset.get("sweeps", [])) < 2:
                        uistate.statusbar_state = "warning"
                        return "Cluster perm. requires each test set to have >=2 sweeps (for adjacency)"
            else:
                uistate.statusbar_state = "warning"
                return "Cluster perm. requires either >=2 groups (between-subjects) or exactly 1 group + exactly 2 test sets (within-subjects/paired)"
            if not shown_ts and not self._is_io_mode():
                uistate.statusbar_state = "warning"
                return "Cluster perm. requires at least one shown test set (to define sweep windows)"
        else:
            # Must have at least one shown test set (for t-test)
            shown_ts = self._get_shown_testsets()
            if not shown_ts and not self._is_io_mode():
                uistate.statusbar_state = "warning"
                return "Show at least one test set to run the test"

        # Success path: build p-value summary for statusbar (uses uistate.formal_test_results)
        # v0.16_n_stats: also check comp for n_unit / hierarchy warnings (error key or config["n_unit"]).
        # Old projects trigger exact statusbar string "<n_unit> not assigned for included recording(s)".
        if hasattr(uistate, "formal_test_results") and uistate.formal_test_results:
            # Check first result for hierarchy warning from compute_statistical_comparison (Phase 0)
            first_res = uistate.formal_test_results[0] if uistate.formal_test_results else {}
            # v0.17_io_statusbar_fix + Phase 3: support config-only or "IO regression" result for implicit IO (no out_results but config with type/slope_p/r2_per_group). For ANOVA implicit, first_res has real set_result.
            if isinstance(first_res, dict) and "config" in first_res and not first_res.get("p_amp") and not first_res.get("set_id"):
                first_res = {"config": first_res.get("config", {})}
            if first_res.get("error") and "not assigned" in str(first_res.get("error", "")):
                uistate.statusbar_state = "warning"
                return first_res["error"]
            n_unit = first_res.get("n_unit") or first_res.get("config", {}).get("n_unit") or getattr(uistate, "buttonGroup_test_n", "subject")
            amp_enabled = bool(getattr(uistate, "checkBox", {}).get("EPSP_amp", True))
            slope_enabled = bool(getattr(uistate, "checkBox", {}).get("EPSP_slope", True))
            fdr = bool(getattr(uistate, "test_fdr", False))
            global_notes = []
            if fdr:
                global_notes.append("(FDR)")
            if test_type == "t-test":
                tails = getattr(uistate, "test_t_tails", "two-sided")
                if variant != "unpaired":
                    global_notes.append(f"({variant})")
                if tails != "two-sided":
                    global_notes.append(f"({tails})")
            elif test_type == "Wilcoxon":
                tails = getattr(uistate, "test_wilcox_tails", "two-sided")
                if variant != "paired":
                    global_notes.append(f"({variant})")
                if tails != "two-sided":
                    global_notes.append(f"({tails})")
                if variant == "one-sample" and ref_value != 0.0:
                    global_notes.append(f"(vs {ref_value})")
            elif test_type == "ANOVA" and any(r.get("set_id") == "__anova_rm_omnibus__" for r in uistate.formal_test_results):
                global_notes.append("(simplified; RM-ANOVA+post-hoc deferred)")
            elif test_type == "Friedman" and any(r.get("set_id") == "__friedman_rm_omnibus__" for r in uistate.formal_test_results):
                global_notes.append("(repeated-measures omnibus)")
            elif test_type == "Cluster perm.":
                global_notes.append("(cluster)")
                if variant == "paired" and len(shown_groups or []) == 1:
                    global_notes.append("(paired)")
                # Phase 1/2: check for cluster recording-level note from config
                if first_res.get("config", {}).get("note"):
                    global_notes.append("(recording-level n)")
            # v0.16_n_stats: n1/n2 must be bound unconditionally before use (Phase 0 regression fix). Use n from results.
            n1 = first_res.get("n1") or first_res.get("n") or getattr(uistate, "n1", None) or "?"
            n2 = first_res.get("n2") or getattr(uistate, "n2", None) or "?"
            n_unit = first_res.get("n_unit") or first_res.get("config", {}).get("n_unit") or getattr(uistate, "buttonGroup_test_n", "subject")
            if n_unit == "subject":
                unit_str = "subjects"
            elif n_unit == "slice":
                unit_str = "slices"
            else:
                unit_str = "recordings"
            # Phase 2: proposed per-group n format using dd_groups names + aggregated n from results/config
            # e.g. "t-test (SAL/SAL=5, SAL/KETA=4, DEXA/SAL=4, DEXA/KETA=5): ..."
            n_report_parts = []
            for gid in shown_groups:
                gname = self.dd_groups.get(gid, {}).get("group_name", str(gid))
                g_n = len(self.dd_groups.get(gid, {}).get("rec_IDs", []))  # fallback; results provide unit n in Phase 1+
                # v0.17_io_statusbar_fix: support group_ns from implicit ANOVA set_result (precise per-group unit count after aggregation)
                for r in uistate.formal_test_results:
                    if (
                        r.get("group1") == gid
                        or isinstance(r.get("group1"), list)
                        and gid in r.get("group1", [])
                        or str(r.get("set_id", "")).startswith(str(gid))
                    ):
                        if "group_ns" in r and gid in r["group_ns"]:
                            g_n = r["group_ns"][gid]
                        else:
                            g_n = r.get("n1") or r.get("n") or g_n
                        break
                n_report_parts.append(f"{gname}={g_n}")
            n_report = ", ".join(n_report_parts)
            if n_report:
                global_notes.append(f"({n_report})")
            else:
                n_count = len(first_res.get("value", [])) or n1 or "?"
                global_notes.append(f"(n={n_count} {unit_str})")
            # v0.16_n_stats_IO + v0.17 + Phase 3: handle "IO regression" config (real slope p + r² from ANCOVA/linregress). Suppress old dummy/mean-collapse language. Reuse implicit_testset + group_ns.
            config = first_res.get("config", {})
            if config.get("type") == "IO regression":
                prefix = "IO regression"
                # slope p (primary ANCOVA interaction), per-group r², n_report
                slope_p = config.get("slope_p") or first_res.get("slope_p")
                if isinstance(slope_p, (int, float)) and np.isfinite(slope_p):
                    pstr = f"{slope_p:.3g}" if slope_p >= 0.001 else "<0.001"
                    global_notes.append(f"slope p={pstr}")
                for g, r2v in config.get("r2_per_group", {}).items():
                    if isinstance(r2v, (int, float)) and np.isfinite(r2v):
                        global_notes.append(f"r²({g})={r2v:.2f}")
                        break
                # n_report from group_ns or n_unit
                n_report = ""
                group_ns = config.get("group_ns") or first_res.get("group_ns", {})
                if group_ns:
                    ns = [f"{g}={n}" for g, n in group_ns.items()]
                    n_report = ", ".join(ns)
                if n_report:
                    global_notes.append(f"({n_report})")
                if global_notes:
                    prefix = f"{prefix} ({' '.join(global_notes)})"
            elif first_res.get("config", {}).get("implicit_testset") and test_type == "ANOVA":
                for short in ("amp", "slope"):
                    r2 = first_res.get("config", {}).get(f"r2_{short}") or first_res.get(f"r2_{short}")
                    if isinstance(r2, (int, float)) and np.isfinite(r2):
                        global_notes.append(f"r²={r2:.2f}")
                        break
                prefix = f"IO - {test_type}"
                if global_notes:
                    # filter redundant IO note for clean prefix
                    filtered_notes = [n for n in global_notes if "IO: all sweeps" not in n]
                    prefix = f"{prefix} {' '.join(filtered_notes)}"
            else:
                if first_res.get("config", {}).get("implicit_testset"):
                    global_notes.append("(IO: all sweeps)")
                prefix = test_type
                if global_notes:
                    prefix = f"{test_type} {' '.join(global_notes)}"
            parts = []
            # Special handling for t-test (paired): use ONLY first result (set 1), no set name prefix
            results_to_report = uistate.formal_test_results
            if (test_type in ("t-test", "Wilcoxon") and variant in ("paired", "one-sample") or test_type == "Cluster perm.") and results_to_report:
                # For Cluster with multiple test sets (between-subjects), report all; paired-cluster would have 1 combined row.
                if test_type == "Cluster perm." and len(results_to_report) > 1:
                    pass  # keep all
                else:
                    results_to_report = results_to_report[:1]
            for r in results_to_report:
                set_name = r.get("set_name")
                name = str(set_name or f"set {r.get('set_id', '?')}")
                if test_type == "ANOVA" and (set_name == "IO all sweeps" or set_name is None):
                    name = ""  # suppress set name for implicit IO ANOVA ("IO - ANOVA (n_report): p=...") per debug plan
                if test_type == "Cluster perm." and "_" in str(r.get("set_id", "")):
                    # Paired cluster uses combined set_id; name already includes "paired ..."
                    name = r.get("set_name", name)
                subparts = []
                for aspect, prefix_key in [("amp", "amp"), ("slope", "slope")]:
                    if (aspect == "amp" and not amp_enabled) or (aspect == "slope" and not slope_enabled):
                        continue
                    # Prefer q_* (FDR) then p_* for this aspect
                    pkey = next((k for k in r.keys() if k.startswith(f"q_{prefix_key}")), None)
                    if not pkey:
                        pkey = next((k for k in r.keys() if k.startswith(f"p_{prefix_key}")), None)
                    pval = r.get(pkey) if pkey else None
                    if isinstance(pval, (int, float)) and np.isfinite(pval):
                        pstr = f"{pval:.3g}"
                        if pval < 0.001:
                            pstr = "<0.001"
                        subparts.append(f"{aspect} p={pstr}")
                    else:
                        subparts.append(f"{aspect} p=NA")
                # Add effect size for ANOVA (eta2 from compute_statistical_comparison)
                if test_type == "ANOVA" and "eta2" in r:
                    eta = r.get("eta2")
                    if isinstance(eta, (int, float)) and np.isfinite(eta):
                        subparts.append(f"η²={eta:.3f}")
                if subparts:  # only show test set if at least one aspect is enabled
                    if (test_type == "t-test" or test_type == "Wilcoxon") and variant in ("paired", "one-sample"):
                        parts.append(", ".join(subparts))  # no set name
                    elif name == "Friedman (repeated, omnibus)":
                        # Special case for Friedman omnibus: omit redundant set_name (it's already in prefix/global_notes)
                        parts.append(", ".join(subparts))
                    else:
                        parts.append(f"{name}: {', '.join(subparts)}")
            if parts and any(bool(p and p.strip()) for p in parts):  # avoid trailing ": " when name suppressed for implicit IO ANOVA
                status = f"{prefix}: {' | '.join(parts)}"
            else:
                status = prefix
            # Add SW/Levene assumption test summary if enabled (per v0.16 request + proposed compact format).
            # Moved outside `if parts` so SW always reports (even if no main p-values).
            sw = bool(getattr(uistate, "test_sw", False))
            lev = bool(getattr(uistate, "test_levene", False))
            assumption_parts = []
            if sw or lev:
                for r in uistate.formal_test_results:
                    for aspect in ["amp", "slope"]:
                        # SW (Shapiro-Wilk) per aspect per set - proposed compact: SW ✓ 0.97 (0.21) or SW ✗ 0.91 (0.01)
                        if sw:
                            w_key = f"sw_stat_{aspect}"
                            p_key = f"sw_p_{aspect}"
                            w = r.get(w_key)
                            p = r.get(p_key)
                            if isinstance(w, (int, float)) and np.isfinite(w) and isinstance(p, (int, float)) and np.isfinite(p):
                                pstr = f"{p:.3g}" if p >= 0.001 else "<0.001"
                                symbol = "✓" if p >= 0.05 else "✗"
                                assumption_parts.append(f"SW {symbol} {w:.2f} ({pstr})")
                                if p < 0.05:
                                    assumption_parts.append("Distribution NOT normal")
                        # Levene per aspect - proposed compact: Lev ✓ F=1.80 (0.22) or Lev ✗ F=3.40 (0.03)
                        if lev:
                            w_key = f"levene_stat_{aspect}"
                            p_key = f"levene_p_{aspect}"
                            w = r.get(w_key)
                            p = r.get(p_key)
                            if isinstance(w, (int, float)) and np.isfinite(w) and isinstance(p, (int, float)) and np.isfinite(p):
                                pstr = f"{p:.3g}" if p >= 0.001 else "<0.001"
                                symbol = "✓" if p >= 0.05 else "✗"
                                assumption_parts.append(f"Lev {symbol} F={w:.2g} ({pstr})")
                                if p < 0.05:
                                    assumption_parts.append("Variances NOT equal")
            if assumption_parts:
                if not parts:
                    status = f"{prefix}:"
                status += " | " + " | ".join(assumption_parts)
            elif sw:
                # SW requested but no valid results (e.g., n<3 per group)
                if not parts:
                    status = f"{prefix}:"
                status += " | SW n<3"
            # Violation notes were appended above; promote state here (results always shown per prior request).
            if any(note in part for part in assumption_parts for note in ("NOT normal", "NOT equal")):
                uistate.statusbar_state = "warning"
            else:
                uistate.statusbar_state = "info"
            return status
        uistate.statusbar_state = None
        return None
