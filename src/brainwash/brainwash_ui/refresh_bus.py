"""Pure graph-refresh request coalescing (no Qt)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphRefreshRequest:
    reeval_formal_test: bool = True


def merge_graph_refresh_requests(
    pending: GraphRefreshRequest | None,
    incoming: GraphRefreshRequest,
) -> GraphRefreshRequest:
    if pending is None:
        return incoming
    return GraphRefreshRequest(reeval_formal_test=pending.reeval_formal_test or incoming.reeval_formal_test)