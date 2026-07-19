# TODO / Experimental triage (#9)

**Date:** 2026-07-19 · **Branch:** `1.0.0`  
**Policy:** Grep inventory; **issue** / **drop** / **keep-in-legacy** / **roadmap**. Do not implement backlog here. Do not gut `legacy/`.

---

## Experimental surface

| Hit | Action |
|-----|--------|
| `Config.hide_experimental` (unused) | **Dropped** (attribute removed) |
| `export_image` “experimental context” caption template | **Keep** (figure-text prose, not a feature flag) |
| `legacy/… “Experimental: not used”` | **keep-in-legacy** |

No Experimental menu or toolframe found.

---

## Non-legacy TODOs

| Location | Summary | Bucket | Notes |
|----------|---------|--------|--------|
| Export “Copy project summary” + stub | Silent no-op | **roadmap** | Menu + function **removed**; **1.0.1:** export `dfp` → `.csv` / `.xls` |
| Undo (was commented in menus) | Undo feature | **issue** | Stubs removed (not user-visible). 1.1 theme if wanted |
| `ui_groups.py` max 9 groups/sets | Hardcoded caps | **issue** | Config caps theme |
| `parse.py` sample_rate / multi-type dir / channel | Import metadata | **issue** | Parse metadata theme |
| `ui_project.py` set_rec_status by name | Should use ID | **issue** | Small bugfix |
| `ui_project.py` expand rec status | Status vocabulary | **issue** / NTH |
| `ui_project.py` window position in cfg | Geometry persist | **issue** / NTH |
| `ui.py` show selection on graph | Sweep range viz | **issue** |
| `ui_interactive.py` slope flip / magic-string drag | UX / maintainability | **issue** (larger → post-1.0) |
| `ui_plot.py` sweep range in text boxes | Live update | **issue** / NTH |
| `ui_data_frames.py` paired recording check | PP | **issue** / NTH |
| `ui_widgets.py` file dialog / progress TODOs | NTH | **issue** / NTH |
| Stale zoom TODOs, `if False` debug, pathlib note, Line2D import, etc. | Noise | **Dropped** |

---

## Legacy (`src/brainwash/legacy/`)

| Count | Bucket |
|------|--------|
| ~23 TODO/FIXME | **keep-in-legacy** bulk |

No edits to legacy analysis for #9.

---

## Roadmap

1. **1.0.1:** Export project table (`dfp`) to `.csv` / `.xls` — **on ROADMAP** (no menu until implemented)  
2. **1.0.1/1.1 parse:** sample_rate, multi-type folder, channel from filename (not yet on ROADMAP)  
3. **1.1+:** undo; drag-release overhaul; group/set caps in cfg (not yet on ROADMAP)  

---

## Code changes in this pass

- Removed unused `Config.hide_experimental`  
- Removed dead debug/noise comments and never-run zoom debug block  
- Removed never-enabled Undo menu stubs  
- Removed Export **Copy project summary** action and `triggerCopyProjectSummary`  

---

## Still open (optional)

- File GitHub issues for remaining **issue** bucket?  
- Close **#9**?  
