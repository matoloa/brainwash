# Package rename — `src/lib` → `src/brainwash`

> **Status**: ✅ Complete (commit 42+). Branch: `ui-refactor/phase0-3`.

## Layout

| Path | Role |
|------|------|
| `src/brainwash/` | Application package (was `src/lib/`) |
| `src/lib/__init__.py` | Deprecated import alias via `MetaPathFinder` → `brainwash.*` |
| `src/brainwash/lib_compat.py` | `install_lib_import_alias()` — called from `main.py` |

## Canonical imports

```python
from brainwash.ui import UIsub
import brainwash.statistics as stats
```

Tests still use flat imports (`from brainwash_ui import …`) via `conftest.py` path setup.

## Verify

```sh
uv run pytest src/brainwash/ -q
uv run python -c "import sys; sys.path.insert(0,'src'); from brainwash.ui import UIsub"
```