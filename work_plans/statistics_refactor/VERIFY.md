# Verify after every statistics refactor PR

```sh
uv run pytest src/lib/test_statistics_characterization.py -q
```

Optional (PR 03+ with `brainwash_stats/`):

```sh
uv run flake8 src/lib/statistics.py src/lib/brainwash_stats/
```

**Do not** run distribution builds, `uv sync --group build`, or app launch unless the user asks.

## If pytest fails

1. Revert the extraction (do not “fix” golden tests without written justification).
2. Narrow the PR to fewer moved lines.
3. Only then consult `_archive_full_spec.md` for the specific branch.