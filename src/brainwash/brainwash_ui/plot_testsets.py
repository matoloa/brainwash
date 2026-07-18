"""Pure testset span and sample-overlay descriptors (no matplotlib/Qt)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from brainwash_ui import view_state

TESTSET_SPAN_ALPHA = 0.08
TESTSET_SPAN_DEFAULT_COLOR = "#a0a0a0"
TESTSET_SPAN_ZORDER = 1
TESTSET_SPAN_LABEL_PREFIX = "testset_span_"


@dataclass(frozen=True)
class TestsetSpanSpec:
    set_id: str
    ax_name: str
    start: float
    end: float
    color: str
    alpha: float = TESTSET_SPAN_ALPHA
    zorder: int = TESTSET_SPAN_ZORDER


def testset_span_specs(
    dd_testset: dict,
    *,
    visible_ids: list[str] | None = None,
    axes: tuple[str, ...] = ("ax1", "ax2"),
) -> list[TestsetSpanSpec]:
    if not dd_testset:
        return []
    if visible_ids is None:
        visible_ids = view_state.visible_testset_ids(dd_testset)
    specs: list[TestsetSpanSpec] = []
    for set_id in sorted(dd_testset.keys()):
        if set_id not in visible_ids:
            continue
        dset = dd_testset[set_id]
        sweeps = dset.get("sweeps") or []
        if not sweeps:
            continue
        start = float(min(sweeps))
        end = float(max(sweeps)) + 1.0
        color = dset.get("color", TESTSET_SPAN_DEFAULT_COLOR)
        for ax_name in axes:
            specs.append(TestsetSpanSpec(set_id, ax_name, start, end, color))
    return specs


def sample_overlay_should_show(dd_shown_samples) -> bool:
    return bool(dd_shown_samples)


SAMPLE_INSET_BOUNDS = (0.02, 0.68, 0.20, 0.30)
SAMPLE_INSET_XLIM = (-0.005, 0.035)
SAMPLE_ARTEFACT_TIME = 0.001


@dataclass(frozen=True)
class SampleOverlayTraceSpec:
    artist_key: tuple
    color: str
    linestyle: str
    time: np.ndarray
    y: np.ndarray


def visible_test_ids_ordered(dd_testset: dict | None) -> list:
    return [tid for tid, tset in sorted((dd_testset or {}).items()) if tset.get("show", False)]


def sample_overlay_linestyle(test_index: int) -> str:
    if test_index == 0:
        return "-"
    if test_index == 1:
        return "--"
    return ":"


def resolve_sample_voltage_column(df: pd.DataFrame, filter_col: str) -> str:
    if filter_col in df.columns:
        return filter_col
    return df.columns[-1]


def group_id_in_groups(group_ID, dd_groups) -> bool:
    return str(group_ID) in {str(k) for k in (dd_groups or {})}


def lookup_group_dict(dd_groups, group_ID) -> dict:
    if not dd_groups:
        return {}
    return dd_groups.get(str(group_ID), dd_groups.get(group_ID, {}))


def build_sample_overlay_trace_specs(
    dd_groups,
    dd_testset,
    dd_shown_samples,
    *,
    filter_col: str,
) -> list[SampleOverlayTraceSpec]:
    if not dd_shown_samples:
        return []
    visible_test_list = visible_test_ids_ordered(dd_testset)
    specs: list[SampleOverlayTraceSpec] = []
    for group_ID, inner in dd_shown_samples.items():
        if not inner or not group_id_in_groups(group_ID, dd_groups):
            continue
        group_dict = lookup_group_dict(dd_groups, group_ID)
        if not group_dict.get("show", True):
            continue
        color = group_dict.get("color", "#0000ff")
        inner_keys = {str(k) for k in inner.keys()}
        for t_idx, test_id_raw in enumerate(visible_test_list):
            if str(test_id_raw) not in inner_keys:
                continue
            test_id = str(test_id_raw)
            df = inner.get(test_id_raw)
            if df is None:
                df = inner.get(test_id)
            if df is None or df.empty:
                continue
            col = resolve_sample_voltage_column(df, filter_col)
            linestyle = sample_overlay_linestyle(t_idx)
            stim_vals = sorted(df.get("stim", pd.Series([1])).unique())
            for stim_num in stim_vals:
                df_event = df[df["stim"] == stim_num].copy() if "stim" in df.columns else df.copy()
                specs.append(
                    SampleOverlayTraceSpec(
                        artist_key=(group_ID, test_id, stim_num),
                        color=color,
                        linestyle=linestyle,
                        time=df_event["time"].values,
                        y=df_event[col].values,
                    )
                )
    return specs


def sample_overlay_ylim(specs: list[SampleOverlayTraceSpec]) -> tuple[float, float] | None:
    all_ys: list[float] = []
    for spec in specs:
        mask = spec.time > SAMPLE_ARTEFACT_TIME
        all_ys.extend(spec.y[mask].tolist())
    if not all_ys:
        return None
    ymin, ymax = min(all_ys), max(all_ys)
    return ymin * 1.1, ymax + 0.0001