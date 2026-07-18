# PR-00: Bootstrap tests ✅

**Status**: DONE | **Depends on**: —

## Landed

- `src/lib/test_statistics_fixtures.py`
- `src/lib/test_statistics_characterization.py` (5 smokes)
- `src/lib/conftest.py`
- `src/lib/load_brainwash_statistics.py`

## Verify

```sh
uv run pytest src/lib/test_statistics_characterization.py -q
```

## Next

→ [01_hoist_aggregate_and_aspects.md](01_hoist_aggregate_and_aspects.md)