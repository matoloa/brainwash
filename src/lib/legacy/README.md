# Legacy analysis engines (retained)

`analysis_v1.py` and `analysis_v2.py` are **kept permanently** for scientific proof,
reproducibility, and comparison against `analysis_v3.py` via `analysis_evaluation.py`.

- **Do not delete** these files.
- **Do not import** from v1/v2 in new production code (`ui.py`, mixins, `brainwash_ui/`).
- Agents: edit only when explicitly asked to reproduce or compare historical pipelines.

Compatibility shims at `src/lib/analysis_v1.py` and `src/lib/analysis_v2.py` preserve
existing imports (`import analysis_v1`, notebook paths).