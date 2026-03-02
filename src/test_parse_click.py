#!/usr/bin/env python3
"""
test_parse_click.py — headless integration test for the parse → click path.

Tests both the data layer (parse, analysis) and the UI data layer
(get_dft, get_dfmean, get_dffilter, get_dfoutput, addRow simulation)
without starting Qt.

Run from repo root:
    .venv/Scripts/python.exe src/test_parse_click.py [path/to/source/file/or/folder]

If no path is given, it uses the first recording found in ~/Documents/Brainwash Projects.

Output:
    src/test_parse_click.log  (always)
    stdout                    (always, mirrored)

Exit code 0 = all steps passed, non-zero = at least one failure.
"""

import logging
import os
import sys
import tempfile
import traceback
import types
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging – file + stdout
# ---------------------------------------------------------------------------
LOG_PATH = Path(__file__).parent / "test_parse_click.log"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)
logging.getLogger("igor2").setLevel(logging.WARNING)
log = logging.getLogger("test_parse_click")

log.info(f"Python {sys.version}")
log.info(f"Log file: {LOG_PATH}")

# ---------------------------------------------------------------------------
# sys.path: add src/ and src/lib/
# ---------------------------------------------------------------------------
_src = str(Path(__file__).parent)
_lib = str(Path(__file__).parent / "lib")
for _p in (_src, _lib):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ---------------------------------------------------------------------------
# Step runner
# ---------------------------------------------------------------------------
PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []


def step(name: str, fn):
    log.info(f"--- STEP: {name} ---")
    try:
        rv = fn()
        log.info(f"    {PASS}")
        results.append((name, PASS, ""))
        return rv
    except Exception:
        tb = traceback.format_exc()
        log.error(f"    {FAIL}\n{tb}")
        results.append((name, FAIL, tb))
        return None


# ---------------------------------------------------------------------------
# Step 0 – find a source path or use existing project data
# ---------------------------------------------------------------------------
import pandas as pd  # noqa: E402 – needed after path setup


def _find_source_and_project():
    """
    Returns (source_path_or_None, project_row_or_None, project_folders_or_None).
    Tries CLI arg first, then existing Brainwash Projects.
    """
    # CLI override
    if len(sys.argv) > 1:
        p = Path(sys.argv[1])
        if p.exists():
            return str(p), None, None
        log.warning(f"CLI path {p!r} not found – will try project folders")

    # Scan existing projects for a parsed recording
    projects_root = Path.home() / "Documents" / "Brainwash Projects"
    if projects_root.exists():
        for proj_dir in sorted(projects_root.iterdir()):
            if not proj_dir.is_dir():
                continue
            proj_file = proj_dir / "project.brainwash"
            if not proj_file.exists():
                continue
            try:
                df_p = pd.read_csv(str(proj_file), dtype={"group_IDs": str})
            except Exception:
                continue
            # Look for a parsed recording (sweeps != "...")
            parsed = df_p[df_p["sweeps"] != "..."] if "sweeps" in df_p.columns else pd.DataFrame()
            if parsed.empty:
                continue
            row = parsed.iloc[0]
            # Build folder dict
            cache_candidates = list(projects_root.glob(f"cache */{proj_dir.name}"))
            cache_dir = cache_candidates[0] if cache_candidates else proj_dir / "cache"
            folders = {
                "project": proj_dir,
                "data": proj_dir / "data",
                "timepoints": proj_dir / "timepoints",
                "cache": cache_dir,
            }
            log.info(f"Found project: {proj_dir.name}, using recording: {row['recording_name']}")
            return row.get("path", None), row, folders

    # Fall back to auto-finding a raw source file
    for base in [
        Path.home() / "Documents" / "Brainwash Data Source",
        Path.home() / "Documents" / "brainwash data source",
        Path.home() / "Desktop",
    ]:
        if not base.exists():
            continue
        for f in base.rglob("*.abf"):
            return str(f), None, None
        for d in base.iterdir():
            if d.is_dir() and any(d.glob("*.ibw")):
                return str(d), None, None
        for f in base.rglob("*.ibw"):
            return str(f), None, None

    return None, None, None


source_path, existing_row, existing_folders = step("0 – find source path / project", _find_source_and_project) or (None, None, None)

if source_path is None and existing_row is None:
    log.error("No source path found. Pass a path as argv[1]. Aborting.")
    sys.exit(2)

# ---------------------------------------------------------------------------
# Import library modules
# ---------------------------------------------------------------------------
parse = step("1 – import parse", lambda: __import__("parse"))
analysis = step("1b – import analysis_v2", lambda: __import__("analysis_v2"))

if parse is None or analysis is None:
    log.error("Cannot import core modules. Aborting.")
    sys.exit(2)


# ---------------------------------------------------------------------------
# Build the default_dict_t (mirrors UIstate.reset())
# ---------------------------------------------------------------------------
def _make_default_dict_t():
    t_volley_slope_width = 0.0003
    t_EPSP_slope_width = 0.0007
    resolution = 0.0001

    def floor_to(v, r):
        return (v // r) * r

    return {
        "stim": 0,
        "t_stim": 0,
        "t_stim_method": "max prim",
        "t_stim_params": "NA",
        "amp_zero": 0,
        "t_volley_slope_width": t_volley_slope_width,
        "t_volley_slope_halfwidth": floor_to(t_volley_slope_width / 2, resolution),
        "t_volley_slope_start": 0,
        "t_volley_slope_end": 0,
        "t_volley_slope_method": "default",
        "t_volley_slope_params": "NA",
        "volley_slope_mean": 0.0,
        "t_volley_amp": 0,
        "t_volley_amp_halfwidth": 0,
        "t_volley_amp_method": "default",
        "t_volley_amp_params": "NA",
        "volley_amp_mean": 0.0,
        "t_VEB": 0,
        "t_VEB_method": 0,
        "t_VEB_params": 0,
        "t_EPSP_slope_width": t_EPSP_slope_width,
        "t_EPSP_slope_halfwidth": floor_to(t_EPSP_slope_width / 2, resolution),
        "t_EPSP_slope_start": 0,
        "t_EPSP_slope_end": 0,
        "t_EPSP_slope_method": "default",
        "t_EPSP_slope_params": "NA",
        "t_EPSP_amp": 0,
        "t_EPSP_amp_halfwidth": 0,
        "t_EPSP_amp_method": "default",
        "t_EPSP_amp_params": "NA",
        "norm_output_from": 0,
        "norm_output_to": 0,
    }


default_dict_t = _make_default_dict_t()

# ---------------------------------------------------------------------------
# PATH A: we have an existing parsed project row → use its cached parquets
# ---------------------------------------------------------------------------
if existing_row is not None and existing_folders is not None:
    log.info("=== PATH A: using existing project cache ===")
    row = existing_row
    folders = existing_folders
    rec = row["recording_name"]
    log.info(f"Recording: {rec}")

    # --- A1: load data parquet ---
    def _load_data():
        path = folders["data"] / f"{rec}.parquet"
        log.info(f"  data path: {path} exists={path.exists()}")
        df = pd.read_parquet(str(path))
        log.info(f"  shape={df.shape}, cols={list(df.columns)}")
        return df

    df_data = step("A1 – load data parquet", _load_data)

    # --- A2: load or build dfmean ---
    def _load_mean():
        path = folders["cache"] / f"{rec}_mean.parquet"
        log.info(f"  mean path: {path} exists={path.exists()}")
        if path.exists():
            df = pd.read_parquet(str(path))
        else:
            log.info("  building dfmean from scratch")
            df, _ = parse.build_dfmean(df_data)
        log.info(f"  shape={df.shape}, cols={list(df.columns)}")
        return df

    dfmean = step("A2 – load/build dfmean", _load_mean)

    # --- A3: load or build dffilter ---
    def _load_filter():
        path = folders["cache"] / f"{rec}_filter.parquet"
        log.info(f"  filter path: {path} exists={path.exists()}")
        if path.exists():
            df = pd.read_parquet(str(path))
        else:
            log.info("  building dffilter from scratch")
            df = parse.zeroSweeps(df_data, dfmean=dfmean)
        log.info(f"  shape={df.shape}, cols={list(df.columns)}")
        return df

    dffilter = step("A3 – load/build dffilter", _load_filter)

    # --- A4: load or build dft (timepoints) ---
    def _load_dft():
        path = folders["timepoints"] / f"{rec}.parquet"
        log.info(f"  timepoints path: {path} exists={path.exists()}")
        if path.exists():
            df = pd.read_parquet(str(path))
            # Migration check
            if "norm_EPSP_from" in df.columns:
                log.warning("  OLD column name norm_EPSP_from found — renaming")
                df.rename(
                    columns={
                        "norm_EPSP_from": "norm_output_from",
                        "norm_EPSP_to": "norm_output_to",
                    },
                    inplace=True,
                )
        else:
            log.info("  building dft from scratch via find_events")
            df = analysis.find_events(dfmean=dfmean, default_dict_t=default_dict_t.copy(), verbose=False)
            if df is None or df.empty:
                raise ValueError("find_events returned empty/None dft — no stims detected")
            df["norm_output_from"] = 0
            df["norm_output_to"] = 0
            df["t_EPSP_amp_halfwidth"] = 0
            df["t_volley_amp_halfwidth"] = 0
        log.info(f"  shape={df.shape}, cols={list(df.columns)}")
        # Verify required keys
        required = [
            "norm_output_from",
            "norm_output_to",
            "t_EPSP_amp",
            "t_EPSP_slope_start",
            "t_EPSP_slope_end",
            "t_volley_amp",
            "t_volley_slope_start",
            "t_volley_slope_end",
        ]
        missing = [k for k in required if k not in df.columns]
        if missing:
            raise KeyError(f"dft missing required columns: {missing}")
        bad = [c for c in df.columns if c in ("norm_EPSP_from", "norm_EPSP_to")]
        if bad:
            raise AssertionError(f"dft still has OLD column names: {bad}")
        return df

    dft = step("A4 – load/build dft (timepoints)", _load_dft)

    # --- A5: build dfoutput ---
    def _build_output():
        if dft is None:
            raise ValueError("dft is None, cannot build output")
        path = folders["cache"] / f"{rec}_output.parquet"
        log.info(f"  output path: {path} exists={path.exists()}")
        if path.exists():
            df = pd.read_parquet(str(path))
            # Migration: drop spurious 'index' column
            if "index" in df.columns:
                log.warning("  Dropping spurious 'index' column from output parquet")
                df.drop(columns=["index"], inplace=True)
            df.reset_index(drop=True, inplace=True)
            log.info(f"  loaded from cache: shape={df.shape}, cols={list(df.columns)}")
        else:
            log.info("  building dfoutput from scratch")
            df = pd.DataFrame()
            for i, t_row in dft.iterrows():
                dict_t = t_row.to_dict()
                log.info(f"    stim {i}: norm_output_from={dict_t.get('norm_output_from')}, " f"norm_output_to={dict_t.get('norm_output_to')}")
                dfout_stim = analysis.build_dfoutput(df=dffilter, dict_t=dict_t)
                log.info(f"    stim {i}: output shape={dfout_stim.shape}, " f"cols={list(dfout_stim.columns)}")
                df = pd.concat([df, dfout_stim])
            df.reset_index(drop=True, inplace=True)
            log.info(f"  built: shape={df.shape}")
        # Sanity checks
        if "index" in df.columns:
            raise AssertionError("dfoutput still has spurious 'index' column after migration")
        required_out = ["stim", "sweep", "EPSP_amp"]
        missing_out = [c for c in required_out if c not in df.columns]
        if missing_out:
            raise KeyError(f"dfoutput missing columns: {missing_out}")
        return df

    dfoutput = step("A5 – build/load dfoutput", _build_output)

    # --- A6: simulate addRow (the logic that runs when user clicks a recording) ---
    def _simulate_addrow():
        if dfmean is None or dft is None or dfoutput is None:
            raise ValueError("Cannot simulate addRow — prerequisite DataFrames are None")

        rec_filter = row.get("filter", "voltage")
        log.info(f"  rec_filter='{rec_filter}'")

        # Check rec_filter column exists in dfmean
        if rec_filter not in dfmean.columns:
            raise KeyError(f"dfmean missing column '{rec_filter}' (rec_filter). " f"Available: {list(dfmean.columns)}")

        # Check rec_filter column exists in dffilter
        if rec_filter not in dffilter.columns:
            raise KeyError(f"dffilter missing column '{rec_filter}' (rec_filter). " f"Available: {list(dffilter.columns)}")

        n_stims = len(dft)
        log.info(f"  n_stims={n_stims}")

        # Walk through each stim exactly as addRow does
        settings = {
            "event_start": -0.005,
            "event_end": 0.05,
        }
        x_axis = "sweep"  # default (output_per_stim=False)

        for i_stim, t_row in dft.iterrows():
            stim_num = i_stim + 1
            t_stim = t_row["t_stim"]
            amp_zero = t_row["amp_zero"]

            # Filter dfoutput for this stim
            out = dfoutput[dfoutput["stim"] == stim_num]
            log.info(f"  stim {stim_num}: t_stim={t_stim}, out rows={len(out)}")
            if out.empty:
                log.warning(f"    dfoutput has no rows for stim {stim_num} — " f"dfoutput['stim'] unique: {dfoutput['stim'].unique().tolist()}")

            # y_position lookup (mirrors addRow line exactly)
            y_pos_series = dfmean.loc[dfmean.time == t_stim, rec_filter]
            if y_pos_series.empty:
                log.warning(
                    f"    dfmean has no row with time=={t_stim} — "
                    f"nearest times: {dfmean['time'].iloc[(dfmean['time'] - t_stim).abs().argsort()[:3]].tolist()}"
                )
            else:
                y_position = y_pos_series.values[0]
                log.info(f"    y_position={y_position:.6g}")

            # Event window
            window_start = t_stim + settings["event_start"]
            window_end = t_stim + settings["event_end"]
            df_event = dfmean[(dfmean["time"] >= window_start) & (dfmean["time"] <= window_end)].copy()
            df_event["time"] = df_event["time"] - t_stim
            log.info(f"    df_event rows={len(df_event)}")
            if df_event.empty:
                raise ValueError(
                    f"df_event is empty for stim {stim_num} "
                    f"(window [{window_start:.4f}, {window_end:.4f}]). "
                    f"dfmean time range: [{dfmean['time'].min():.4f}, {dfmean['time'].max():.4f}]"
                )

            # EPSP amp lookup
            t_EPSP_amp = t_row["t_EPSP_amp"]
            import numpy as np

            if not (isinstance(t_EPSP_amp, float) and np.isnan(t_EPSP_amp)):
                adjusted = t_EPSP_amp - t_stim
                y_epsp = df_event.loc[df_event.time == adjusted, rec_filter]
                if y_epsp.empty:
                    log.warning(
                        f"    t_EPSP_amp={t_EPSP_amp} → adjusted={adjusted:.6g} "
                        f"not found exactly in df_event['time']. "
                        f"Nearest: {df_event['time'].iloc[(df_event['time'] - adjusted).abs().argsort()[:2]].tolist()}"
                    )
                else:
                    log.info(f"    EPSP amp y={y_epsp.values[0]:.6g}")

            # out[x_axis] lookup — this is what crashes if 'sweep' column missing
            if x_axis not in out.columns:
                raise KeyError(f"dfoutput missing column '{x_axis}'. " f"Available: {list(out.columns)}")

            # EPSP_amp in output
            if "EPSP_amp" in out.columns:
                log.info(f"    out EPSP_amp mean={out['EPSP_amp'].mean():.6g}")
            else:
                log.warning(f"    out missing EPSP_amp column")

        log.info("  addRow simulation complete — no crashes")
        return True

    step("A6 – simulate addRow (click on recording)", _simulate_addrow)

# ---------------------------------------------------------------------------
# PATH B: parse from raw source (if no existing project row)
# ---------------------------------------------------------------------------
elif source_path is not None:
    log.info("=== PATH B: parse from raw source file ===")
    log.info(f"Source: {source_path}")

    # B1 – source2dfs
    def _source2dfs():
        d = parse.source2dfs(str(source_path), gain=1.0)
        log.info(f"  returned {len(d)} channel(s)")
        for ch, df in d.items():
            log.info(f"    ch {ch}: shape={df.shape}, cols={list(df.columns)}")
        return d

    dict_dfs = step("B1 – parse.source2dfs", _source2dfs)
    if not dict_dfs:
        log.error("source2dfs returned empty dict. Aborting.")
        sys.exit(2)

    ch0 = next(iter(dict_dfs))
    df_raw = dict_dfs[ch0]

    # B2 – build_dfmean
    dfmean_result = step("B2 – build_dfmean", lambda: parse.build_dfmean(df_raw))
    if dfmean_result is None:
        sys.exit(2)
    dfmean, i_stim = dfmean_result
    log.info(f"  dfmean shape={dfmean.shape}, i_stim={i_stim}")

    # B3 – zeroSweeps
    dffilter = step("B3 – zeroSweeps", lambda: parse.zeroSweeps(df_raw, i_stim=i_stim))
    log.info(
        f"  dffilter shape={dffilter.shape if dffilter is not None else 'None'}, " f"cols={list(dffilter.columns) if dffilter is not None else []}"
    )

    # B4 – find_events
    def _find_events():
        dft = analysis.find_events(dfmean=dfmean, default_dict_t=default_dict_t.copy(), verbose=True)
        if dft is None or dft.empty:
            raise ValueError("find_events returned empty/None — no stims detected")
        # apply column name fix
        dft["norm_output_from"] = 0
        dft["norm_output_to"] = 0
        dft["t_EPSP_amp_halfwidth"] = 0
        dft["t_volley_amp_halfwidth"] = 0
        bad = [c for c in dft.columns if c in ("norm_EPSP_from", "norm_EPSP_to")]
        if bad:
            raise AssertionError(f"dft has OLD column names: {bad}")
        required = ["norm_output_from", "norm_output_to"]
        missing = [k for k in required if k not in dft.columns]
        if missing:
            raise KeyError(f"dft missing: {missing}")
        log.info(f"  dft shape={dft.shape}, cols={list(dft.columns)}")
        return dft

    dft = step("B4 – find_events", _find_events)

    # B5 – build_dfoutput
    def _build_output_b():
        if dft is None or dffilter is None:
            raise ValueError("dft or dffilter is None")
        dfout = pd.DataFrame()
        for i, t_row in dft.iterrows():
            dict_t = t_row.to_dict()
            log.info(f"  stim {i}: norm_output_from={dict_t.get('norm_output_from')}, " f"norm_output_to={dict_t.get('norm_output_to')}")
            dfout_stim = analysis.build_dfoutput(df=dffilter, dict_t=dict_t)
            log.info(f"    shape={dfout_stim.shape}, cols={list(dfout_stim.columns)}")
            dfout = pd.concat([dfout, dfout_stim])
        dfout.reset_index(drop=True, inplace=True)
        if "index" in dfout.columns:
            raise AssertionError("dfoutput has spurious 'index' column")
        log.info(f"  final shape={dfout.shape}")
        return dfout

    dfoutput = step("B5 – build_dfoutput", _build_output_b)


# ---------------------------------------------------------------------------
# Step 5 – parquet round-trip sanity check
# ---------------------------------------------------------------------------
def _parquet_roundtrip():
    df = pd.DataFrame(
        {
            "stim": [1, 1, 2, 2],
            "sweep": [0, 1, 0, 1],
            "EPSP_amp": [0.1, 0.2, 0.3, 0.4],
            "volley_amp": [0.05, 0.06, 0.07, 0.08],
        }
    )
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        path = f.name
    try:
        df.reset_index(drop=True, inplace=True)
        df.to_parquet(path, index=False)
        df2 = pd.read_parquet(path)
        df2.reset_index(drop=True, inplace=True)
        if "index" in df2.columns:
            raise AssertionError(f"Parquet round-trip added spurious 'index' column: {list(df2.columns)}")
        log.info(f"  round-trip OK, cols={list(df2.columns)}")
        return df2
    finally:
        os.unlink(path)


step("5 – parquet round-trip (no spurious index col)", _parquet_roundtrip)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log.info("")
log.info("=" * 60)
log.info("SUMMARY")
log.info("=" * 60)
any_fail = False
for name, status, detail in results:
    icon = "✓" if status == PASS else "✗"
    log.info(f"  {icon} {status}  {name}")
    if status == FAIL and detail:
        last_line = detail.strip().splitlines()[-1]
        log.info(f"       → {last_line}")
    if status == FAIL:
        any_fail = True

log.info("=" * 60)
if any_fail:
    log.error("RESULT: FAILURES DETECTED — see details above")
    sys.exit(1)
else:
    log.info("RESULT: ALL STEPS PASSED")
    sys.exit(0)
