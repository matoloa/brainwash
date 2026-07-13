# statistics.py — public facade for brainwash_stats (see AGENTS.md)
from .brainwash_stats.dispatcher import compute_statistical_comparison
from .brainwash_stats.fdr import bh_fdr as _bh_fdr
from .brainwash_stats.per_sweep import ttest_per_sweep