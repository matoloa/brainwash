"""Pure helpers for group/testset visibility."""

from __future__ import annotations

_SHOW_TRUTHY = (True, "True", "true", 1, "1")


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