import sys
from pathlib import Path


def test_lib_import_alias_resolves_brainwash_submodules():
    src = str(Path(__file__).resolve().parent.parent)
    if src not in sys.path:
        sys.path.insert(0, src)
    import lib.statistics as lib_stats
    import brainwash.statistics as bw_stats

    assert lib_stats.compute_statistical_comparison is bw_stats.compute_statistical_comparison