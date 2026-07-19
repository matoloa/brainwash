"""Plot artist identity: storage keys vs display labels.

**Contract**

- ``dict_rec_labels`` / ``dict_group_labels`` keys are **identity** (``rec|…`` /
  ``grp|…`` / ``sys|…``), not user-facing legend text.
- ``entry["display_label"]`` is **presentation** (recording/group name today;
  blind aliases later). Legends and drag string bridges use this field.
- Never rewrite ``df_project["recording_name"]`` or parquet paths for display.

``display_recording_name`` is the hook for issue #5 (blinding).
"""

from __future__ import annotations

from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Roles (explicit; do not encode as free-form string suffixes alone)
# ---------------------------------------------------------------------------

ROLE_MEAN_TRACE = "mean_trace"
ROLE_EVENT_TRACE = "event_trace"
ROLE_STIM_MARKER = "stim_marker"
ROLE_STIM_SELECTION = "stim_selection"
ROLE_ASPECT_MARKER = "aspect_marker"
ROLE_AMP_WIDTH = "amp_width"
ROLE_AMP_X = "amp_x"
ROLE_AMP_Y = "amp_y"
ROLE_AMP_ZERO = "amp_zero"
ROLE_SERIES = "series"
ROLE_SERIES_NORM = "series_norm"
ROLE_SERIES_MEAN_HLINE = "series_mean_hline"
ROLE_SHADE = "shade"
ROLE_IO_SCATTER = "io_scatter"
ROLE_IO_TREND = "io_trend"
ROLE_PPR = "ppr"
ROLE_AXE_MEAN_OVERLAY = "axe_mean_overlay"
ROLE_REF_HLINE = "ref_hline"
ROLE_GROUP_MEAN = "group_mean"
ROLE_GROUP_NORM = "group_norm"
ROLE_PP_BOX = "pp_box"
ROLE_PP_POINT = "pp_point"

REC_ROLES = frozenset(
    {
        ROLE_MEAN_TRACE,
        ROLE_EVENT_TRACE,
        ROLE_STIM_MARKER,
        ROLE_STIM_SELECTION,
        ROLE_ASPECT_MARKER,
        ROLE_AMP_WIDTH,
        ROLE_AMP_X,
        ROLE_AMP_Y,
        ROLE_AMP_ZERO,
        ROLE_SERIES,
        ROLE_SERIES_NORM,
        ROLE_SERIES_MEAN_HLINE,
        ROLE_SHADE,
        ROLE_IO_SCATTER,
        ROLE_IO_TREND,
        ROLE_PPR,
        ROLE_AXE_MEAN_OVERLAY,
        ROLE_REF_HLINE,
    }
)

GROUP_ROLES = frozenset(
    {
        ROLE_GROUP_MEAN,
        ROLE_GROUP_NORM,
        ROLE_IO_SCATTER,
        ROLE_IO_TREND,
        ROLE_PP_BOX,
        ROLE_PP_POINT,
        ROLE_SHADE,
    }
)


def _tok(value) -> str:
    if value is None or value == "":
        return "-"
    return str(value).replace("|", "_")


def display_recording_name(
    rec_ID,
    real_name: str,
    *,
    blind: bool = False,
    aliases: dict | None = None,
) -> str:
    """Human-facing recording name for table/legend (identity keys stay real).

    When *blind* is True, prefer *aliases[rec_ID]* (e.g. ``Rec 1``); never mutate
    the underlying project table or storage keys.
    """
    if not blind:
        return real_name if real_name is not None else ""
    if aliases:
        for key in (rec_ID, str(rec_ID)):
            if key in aliases:
                return str(aliases[key])
    # Stable fallback until alias map is built by the UI
    return f"Rec {rec_ID}"


def build_blind_aliases(
    rec_ids: Iterable,
    existing: dict | None = None,
    *,
    rng=None,
) -> dict[str, str]:
    """Map str(rec_ID) → ``Rec n``.

    New episode (*existing* empty): random bijection of ``Rec 1..N`` (not ID order).
    Within an episode (*existing* set): keep labels; new IDs get the next free ``Rec n``.
    Unblind clears *existing*; the next Blind must pass empty *existing* for a fresh shuffle.
    """
    import random as _random

    ids = list(rec_ids or [])
    try:
        ordered = sorted(ids, key=lambda x: int(x))
    except (TypeError, ValueError):
        ordered = sorted(ids, key=lambda x: str(x))
    live = {str(rid) for rid in ordered}
    prev = {str(k): str(v) for k, v in (existing or {}).items() if str(k) in live}
    if not prev:
        labels = [f"Rec {i}" for i in range(1, len(ordered) + 1)]
        shuffler = rng if rng is not None else _random
        shuffler.shuffle(labels)
        return {str(rid): lab for rid, lab in zip(ordered, labels)}
    used = set(prev.values())
    n = 1
    for rid in ordered:
        key = str(rid)
        if key in prev:
            continue
        while f"Rec {n}" in used:
            n += 1
        label = f"Rec {n}"
        prev[key] = label
        used.add(label)
        n += 1
    return prev


def recording_name_sort_key(display_name: str):
    """Sort key for table: natural order for ``Rec N``, else casefold string."""
    import re

    s = "" if display_name is None else str(display_name)
    m = re.fullmatch(r"Rec\s+(\d+)", s.strip(), flags=re.IGNORECASE)
    if m:
        return (0, int(m.group(1)))
    return (1, s.casefold())


def replace_recording_stem(label: str, old_stem: str, new_stem: str) -> str:
    """Swap recording name stem inside a plot display_label (legend presentation).

    Handles exact match, leading stem (``name - stim…``), and ``mean {stem}…``.
    """
    if not label or not old_stem or old_stem == new_stem:
        return label if label is not None else ""
    s = str(label)
    old = str(old_stem)
    new = str(new_stem)
    if s == old:
        return new
    mean_prefix = f"mean {old}"
    if s.startswith(mean_prefix):
        return f"mean {new}" + s[len(mean_prefix) :]
    if s.startswith(old):
        return new + s[len(old) :]
    if old in s:
        return s.replace(old, new)
    return s


def storage_key_rec(
    *,
    rec_ID,
    axis: str,
    role: str,
    stim=None,
    aspect=None,
    variant: str = "raw",
    x_mode: str | None = None,
) -> str:
    """Opaque storage key for a recording artist (no recording_name)."""
    if role not in REC_ROLES and role != ROLE_REF_HLINE:
        # Allow forward-compatible roles without hard fail; still require non-empty.
        if not role:
            raise ValueError("role is required")
    return "|".join(
        [
            "rec",
            _tok(rec_ID),
            _tok(axis),
            _tok(role),
            f"s{_tok(stim)}",
            _tok(aspect),
            _tok(variant or "raw"),
            _tok(x_mode or "-"),
        ]
    )


def storage_key_group(
    *,
    group_ID,
    axis: str,
    role: str,
    aspect=None,
    variant: str = "raw",
    level: str | None = None,
    x_mode: str | None = None,
    unit_id=None,
) -> str:
    """Opaque storage key for a group artist (no group_name)."""
    parts = [
        "grp",
        _tok(group_ID),
        _tok(axis),
        _tok(role),
        _tok(aspect),
        _tok(variant or "raw"),
        _tok(level or "recording"),
        _tok(x_mode or "-"),
    ]
    if unit_id is not None:
        parts.append(f"u{_tok(unit_id)}")
    return "|".join(parts)


def storage_key_sys(name: str) -> str:
    """System / shared artists (reference hlines, axe mean overlay, …)."""
    if not name:
        raise ValueError("sys name required")
    return f"sys|{_tok(name)}"


def _ids_equal(a, b) -> bool:
    if a is None or b is None:
        return a is b
    if a == b:
        return True
    try:
        return str(a) == str(b)
    except Exception:
        return False


def _stim_equal(a, b) -> bool:
    if a is None or b is None:
        return a is b
    if a == b:
        return True
    try:
        return int(a) == int(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def find_rec_entries(
    store: dict,
    *,
    rec_ID=None,
    stim=None,
    aspect=None,
    role=None,
    axis=None,
    variant=None,
    x_mode=None,
) -> list[tuple[Any, dict]]:
    """Return (storage_key, entry) pairs matching metadata filters (AND)."""
    out: list[tuple[Any, dict]] = []
    for key, entry in (store or {}).items():
        if not isinstance(entry, dict):
            continue
        if rec_ID is not None and not _ids_equal(entry.get("rec_ID"), rec_ID):
            continue
        if stim is not None and not _stim_equal(entry.get("stim"), stim):
            continue
        if aspect is not None and entry.get("aspect") != aspect:
            continue
        if role is not None and entry.get("role") != role:
            continue
        if axis is not None and entry.get("axis") != axis:
            continue
        if variant is not None and entry.get("variant") != variant:
            continue
        if x_mode is not None and entry.get("x_mode") != x_mode:
            continue
        out.append((key, entry))
    return out


def require_one_rec_entry(store: dict, **filters) -> dict:
    """Return the single matching entry value or raise LookupError."""
    hits = find_rec_entries(store, **filters)
    if not hits:
        raise LookupError(f"no artist entry matching {filters}")
    if len(hits) > 1:
        raise LookupError(f"ambiguous artist entries ({len(hits)}) matching {filters}")
    return hits[0][1]


def find_entry_by_display_label(store: dict, display_label: str) -> tuple[Any, dict] | tuple[None, None]:
    """Resolve an entry by display_label, then by legacy storage key == label."""
    if not display_label:
        return None, None
    store = store or {}
    if display_label in store and isinstance(store[display_label], dict):
        return display_label, store[display_label]
    for key, entry in store.items():
        if isinstance(entry, dict) and entry.get("display_label") == display_label:
            return key, entry
    return None, None


def require_entry_by_display_label(store: dict, display_label: str) -> dict:
    _key, entry = find_entry_by_display_label(store, display_label)
    if entry is None:
        raise LookupError(f"no artist entry with display_label={display_label!r}")
    return entry


def infer_rec_role(
    label: str,
    *,
    kind: str,
    axid: str | None = None,
    aspect=None,
    variant: str = "raw",
) -> str:
    """Best-effort role from legacy label string + registration kind.

    Used until specs carry explicit roles. ``kind`` is the plot_* channel:
    line | marker | vline | hline | shade | amp_x | amp_y | io_scatter | io_trend | ref_hline.
    """
    lab = str(label or "")
    if kind == "shade":
        return ROLE_SHADE
    if kind == "amp_x":
        return ROLE_AMP_X
    if kind == "amp_y":
        return ROLE_AMP_Y
    if kind == "io_scatter":
        return ROLE_IO_SCATTER
    if kind == "io_trend":
        return ROLE_IO_TREND
    if kind == "ref_hline":
        return ROLE_REF_HLINE
    if "selection marker" in lab:
        return ROLE_STIM_SELECTION
    if "amp_zero" in lab:
        return ROLE_AMP_ZERO
    if kind == "vline":
        return ROLE_STIM_SELECTION
    if kind == "marker" or lab.endswith(" marker"):
        if lab.startswith("mean ") and " - stim " in lab:
            return ROLE_STIM_MARKER
        return ROLE_ASPECT_MARKER
    if "slope marker" in lab or " amp marker" in lab:
        return ROLE_ASPECT_MARKER
    if kind == "hline" or lab.endswith(" mean") or " mean" in lab and lab.endswith("mean"):
        # volley amp/slope mean hlines
        if " mean" in lab or lab.endswith("mean"):
            return ROLE_SERIES_MEAN_HLINE
    if kind == "hline":
        return ROLE_SERIES_MEAN_HLINE
    if "PPR" in lab:
        return ROLE_PPR
    if lab.startswith("axe mean selected"):
        return ROLE_AXE_MEAN_OVERLAY
    if lab.startswith("mean ") and (axid == "axm" or axid is None):
        # full mean trace on axm (not stim marker)
        if " - stim " not in lab:
            return ROLE_MEAN_TRACE
    if axid == "axe" and not aspect and kind == "line":
        return ROLE_EVENT_TRACE
    if variant == "norm" or lab.endswith(" norm") or " norm" in lab:
        return ROLE_SERIES_NORM
    if axid in ("ax1", "ax2") or aspect:
        return ROLE_SERIES
    if axid == "axe":
        return ROLE_EVENT_TRACE
    return ROLE_SERIES


def legend_label_for_entry(entry: dict, *, fallback_key: str = "") -> str:
    """Presentation string for legends; prefers display_label on the entry."""
    if not isinstance(entry, dict):
        return fallback_key
    label = entry.get("display_label")
    if label:
        return str(label)
    # Matplotlib artist may still carry the display string
    line = entry.get("line")
    if line is not None and hasattr(line, "get_label"):
        try:
            gl = line.get_label()
            if gl and not str(gl).startswith("_"):
                return str(gl)
        except Exception:
            pass
    return fallback_key


def output_axis_legend_map_from_entries(
    dd_recs: dict,
    dd_group_show: dict,
    *,
    axid: str,
    current_level: str,
    include_groups: bool,
) -> dict[str, object]:
    """Legend display_label → artist, preferring entry display_label over storage key.

    Drop markers and IO trendlines (same rules as plot_model.output_axis_legend_map).
    """
    axis_legend: dict[str, object] = {}
    for key, value in (dd_recs or {}).items():
        if not isinstance(value, dict):
            continue
        if value.get("axis") != axid:
            continue
        role = value.get("role")
        if role in (ROLE_ASPECT_MARKER, ROLE_STIM_MARKER, ROLE_STIM_SELECTION, ROLE_AMP_X, ROLE_AMP_Y, ROLE_AMP_ZERO, ROLE_REF_HLINE):
            continue
        if str(key).endswith(" marker") and role is None:
            # Legacy name-based keys until migration completes
            continue
        if role == ROLE_IO_TREND or " IO trendline" in str(key) or " IO trendline" in str(value.get("display_label", "")):
            continue
        label = legend_label_for_entry(value, fallback_key=str(key))
        if label and not label.endswith(" marker"):
            axis_legend[label] = value.get("line")
    if include_groups:
        for key, value in (dd_group_show or {}).items():
            if not isinstance(value, dict):
                continue
            if value.get("axis") != axid:
                continue
            if value.get("role") == ROLE_IO_TREND or " IO trendline" in str(key):
                continue
            level = value.get("level")
            if level is not None and level != current_level:
                continue
            label = legend_label_for_entry(value, fallback_key=str(key))
            # Strip legacy level suffixes if display_label missing
            for suf in ("_subject", "_slice", "_recording"):
                if label.endswith(suf):
                    label = label[: -len(suf)]
                    break
            axis_legend[label] = value.get("line")
    return axis_legend
