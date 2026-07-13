"""Pure testset span and sample-overlay descriptors (no matplotlib/Qt)."""

from __future__ import annotations

from dataclasses import dataclass

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