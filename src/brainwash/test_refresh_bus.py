from brainwash_ui.refresh_bus import GraphRefreshRequest, merge_graph_refresh_requests


def test_merge_prefers_reeval_true():
    a = GraphRefreshRequest(reeval_formal_test=False)
    b = GraphRefreshRequest(reeval_formal_test=True)
    merged = merge_graph_refresh_requests(a, b)
    assert merged.reeval_formal_test is True


def test_merge_stays_false_when_both_false():
    a = GraphRefreshRequest(reeval_formal_test=False)
    b = GraphRefreshRequest(reeval_formal_test=False)
    merged = merge_graph_refresh_requests(a, b)
    assert merged.reeval_formal_test is False


def test_merge_from_none():
    incoming = GraphRefreshRequest(reeval_formal_test=False)
    assert merge_graph_refresh_requests(None, incoming) == incoming