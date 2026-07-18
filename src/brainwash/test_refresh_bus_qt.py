"""pytest-qt: graph refresh bus coalesces within one event-loop tick."""

from ui_graph import GraphCoordinatorMixin


class _RefreshSpy(GraphCoordinatorMixin):
    def __init__(self) -> None:
        self.impl_calls: list[bool] = []

    def _graph_refresh_impl(self, reeval_formal_test: bool = True) -> None:
        self.impl_calls.append(reeval_formal_test)

    def usage(self, msg: str) -> None:
        pass


def test_graph_refresh_bus_coalesces_same_tick(qtbot):
    spy = _RefreshSpy()
    spy.request_graph_refresh(reeval_formal_test=False)
    spy.request_graph_refresh(reeval_formal_test=True)
    assert spy.impl_calls == []
    qtbot.wait(50)
    assert spy.impl_calls == [True]


def test_graph_refresh_bus_second_tick_flushes_again(qtbot):
    spy = _RefreshSpy()
    spy.request_graph_refresh(reeval_formal_test=False)
    qtbot.wait(50)
    assert spy.impl_calls == [False]
    spy.request_graph_refresh(reeval_formal_test=True)
    qtbot.wait(50)
    assert spy.impl_calls == [False, True]