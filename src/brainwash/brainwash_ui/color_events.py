"""Color events by Rec | Stim | Group (#6) — pure helpers, no Qt/matplotlib."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

COLOR_EVENTS_MODES = frozenset({"rec", "stim", "group"})
AMBIGUOUS_GROUP_COLOR = "black"

# Roles recolored on axe/axm (stim-related chrome; mean trace stays black).
EVENT_COLOR_ROLES = frozenset(
    {
        "event_trace",
        "stim_marker",
        "stim_selection",
        "aspect_marker",
        "amp_width",
        "amp_x",
        "amp_y",
        "amp_zero",
        "series_mean_hline",  # volley mean hlines on axe sometimes
    }
)


def normalize_color_events_by(raw) -> str:
    s = str(raw or "rec").strip().lower()
    if s in ("stim", "stim_number", "stim_nr"):
        return "stim"
    if s == "group":
        return "group"
    return "rec"


def effective_color_events_mode(radio: str, n_rec_selected: int, n_stim_selected: int) -> str:
    """Resolve encoding from radio preference + selection multiplicity."""
    radio = normalize_color_events_by(radio)
    if radio == "group":
        return "group"
    n_rec = max(int(n_rec_selected or 0), 0)
    n_stim = max(int(n_stim_selected or 0), 0)
    if n_rec == 1 and n_stim > 1:
        return "stim"
    if n_rec > 1 and n_stim == 1:
        return "rec"
    if n_rec > 1 and n_stim > 1:
        return radio
    return radio


def selected_rec_ids_in_display_order(
    display_id_order: Sequence,
    selected_ids: Iterable,
) -> list:
    """Preserve table model order; keep only selected IDs."""
    selected = {str(x) for x in (selected_ids or [])}
    # also allow int equality via dual key set
    selected_raw = set(selected_ids or [])
    out = []
    seen = set()
    for rid in display_id_order or []:
        key = str(rid)
        if key in seen:
            continue
        if rid in selected_raw or key in selected:
            out.append(rid)
            seen.add(key)
    return out


def rec_gradient_index_map(display_ordered_ids: Sequence) -> dict[str, int]:
    """str(rec_ID) → index into gradient over the *full* display-order domain.

    Domain should be the largest relevant list (entire table order), not only
    the current selection, so hues stay fixed when selection shrinks.
    """
    return {str(rid): i for i, rid in enumerate(display_ordered_ids or [])}


def stim_gradient_index_map(stim_domain: Sequence) -> dict[int, int]:
    """stim number → index into gradient over full *detected* stim domain.

    Domain is sorted unique stim numbers (all detected), not the current
    selection, so blob color matches event color for the same stim.
    """
    nums = []
    for s in stim_domain or []:
        try:
            nums.append(int(s))
        except (TypeError, ValueError):
            continue
    ordered = sorted(set(nums))
    return {s: i for i, s in enumerate(ordered)}


def collect_stim_domain_for_recs(store: Mapping, rec_ids: Iterable) -> list[int]:
    """Union of stim numbers on event/stim artists for the given rec IDs."""
    want = {str(r) for r in (rec_ids or [])}
    want_raw = set(rec_ids or [])
    found: set[int] = set()
    for _k, entry in (store or {}).items():
        if not isinstance(entry, dict):
            continue
        rid = entry.get("rec_ID")
        if want and rid not in want_raw and str(rid) not in want:
            continue
        stim = entry.get("stim")
        if stim is None:
            continue
        try:
            found.add(int(stim))
        except (TypeError, ValueError):
            pass
    return sorted(found)


def group_color_for_rec(
    rec_ID,
    *,
    dd_groups: Mapping | None,
    ambiguous_color: str = AMBIGUOUS_GROUP_COLOR,
) -> str:
    """Color from exactly one *shown* group; else black.

    Hidden groups are ignored for membership.
    """
    if not dd_groups:
        return ambiguous_color
    rid = str(rec_ID)
    colors = []
    for g in dd_groups.values():
        if not isinstance(g, dict):
            continue
        show = g.get("show", True)
        if isinstance(show, str):
            shown = show.strip().lower() in ("true", "1", "yes", "t")
        else:
            shown = bool(show)
        if not shown:
            continue
        rec_ids = g.get("rec_IDs") or []
        if any(str(r) == rid for r in rec_ids):
            colors.append(g.get("color") or ambiguous_color)
    if len(colors) == 1:
        return str(colors[0])
    return ambiguous_color


def resolve_event_artist_color(
    *,
    mode: str,
    rec_ID,
    stim,
    stim_index_map: Mapping[Any, int] | None,
    rec_index_map: Mapping[str, int] | None,
    gradient: Mapping[int, Any] | None,
    dd_groups: Mapping | None,
    fallback: Any = "black",
) -> Any:
    """Pick color for one rec×stim event artist given effective mode."""
    mode = normalize_color_events_by(mode)
    if mode == "group":
        return group_color_for_rec(rec_ID, dd_groups=dd_groups)
    grad = gradient or {}
    if mode == "rec":
        idx_map = rec_index_map or {}
        idx = idx_map.get(str(rec_ID))
        if idx is None:
            return fallback
        return grad.get(int(idx), fallback)
    # stim mode — index into full-domain map (not selection-rebased)
    idx_map = stim_index_map or {}
    if stim is None:
        return fallback
    i = None
    if stim in idx_map:
        i = idx_map[stim]
    else:
        try:
            si = int(stim)
            if si in idx_map:
                i = idx_map[si]
            elif str(si) in idx_map:
                i = idx_map[str(si)]
        except (TypeError, ValueError):
            if str(stim) in idx_map:
                i = idx_map[str(stim)]
    if i is None:
        return fallback
    return grad.get(int(i), fallback)


def artist_should_receive_event_color(entry: dict) -> bool:
    """True for axe/axm stim-related artists (not mean trace, not output series)."""
    if not isinstance(entry, dict):
        return False
    axis = entry.get("axis")
    if axis not in ("axe", "axm"):
        return False
    role = entry.get("role")
    if role == "mean_trace":
        return False
    if role in EVENT_COLOR_ROLES:
        return True
    # Legacy / incomplete role: stim-tagged markers and event lines on axe/axm
    if entry.get("stim") is not None:
        return True
    if axis == "axe" and role in (None, "event_trace", "series"):
        return True
    return False
