# PR-11: Host Protocol contracts

**Status**: DONE | **Depends on**: PR-10

## Goal

Promote mixin host requirements to `protocols.py` `Protocol` types for `StatTestMixin`, `SelectionMixin`, `DataFrameMixin`.

## Tasks

1. Add `src/lib/protocols.py` with `StatTestHost`, `SelectionHost`, `DataFrameHost`
2. Reference protocols in mixin docstrings (no runtime enforcement yet)

## Forbidden

- mypy adoption / CI typing gate in this PR
- Behavior changes

## Verify

```sh
uv run pytest src/lib/ -q
```

## Next

Human review: UIplot model/view split (evaluation Tier B4).