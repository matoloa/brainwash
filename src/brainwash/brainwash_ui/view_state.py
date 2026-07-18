"""Pure helpers for group/testset visibility."""

from __future__ import annotations

_SHOW_TRUTHY = (True, "True", "true", 1, "1")

# Volley has no relative/normalised series; suppress these on output axes when
# Relative (norm_EPSP) is on. Checkbox state is preserved and re-applied when
# leaving relative mode.
VOLLEY_ASPECTS_NO_NORM = frozenset(
    {
        "volley_amp",
        "volley_slope",
        "volley_amp_mean",
        "volley_slope_mean",
    }
)


def suppress_volley_under_norm(
    aspect: str | None,
    *,
    norm_active: bool,
    axis: str | None = None,
) -> bool:
    """True when volley output (incl. means) must stay hidden under Relative mode.

    Event-window markers (axis ``axe``) are not suppressed — only ax1/ax2 (and
    group series with no axis / output axes). Pass ``axis=None`` for group
    artists that are always on output axes.
    """
    if not norm_active or aspect not in VOLLEY_ASPECTS_NO_NORM:
        return False
    if axis is not None and axis not in ("ax1", "ax2"):
        return False
    return True


def aspect_counts_for_output_view(aspect: str, checkbox: dict) -> bool:
    """Whether a checkbox aspect contributes to amp/slope output visibility.

    Volley checkboxes are ignored while Relative (norm_EPSP) is active; state
    is left unchanged so they apply again when relative mode is turned off.
    """
    if not checkbox.get(aspect, False):
        return False
    if aspect in VOLLEY_ASPECTS_NO_NORM and checkbox.get("norm_EPSP", False):
        return False
    return True


def visible_group_ids(dd_groups: dict | None) -> list:
    if not dd_groups:
        return []
    return [gid for gid, g in dd_groups.items() if g.get("show") in _SHOW_TRUTHY]


def visible_testset_ids(dd_testsets: dict | None) -> list:
    if not dd_testsets:
        return []
    return [tid for tid, t in dd_testsets.items() if t.get("show", False)]


def groups_with_recordings(dd_groups: dict | None, group_ids: list) -> list:
    if not dd_groups:
        return []
    return [gid for gid in group_ids if len(dd_groups.get(gid, {}).get("rec_IDs", [])) > 0]


def should_show_stat_test_frame(experiment_type: str, view_tools: dict | None) -> bool:
    if view_tools and "frameToolTest" in view_tools:
        return bool(view_tools["frameToolTest"][1])
    return experiment_type != "io"