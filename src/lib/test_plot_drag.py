from brainwash_ui import plot_drag


def test_amp_move_zone():
    zone = plot_drag.amp_move_zone(1.0, 2.0, x_margin=0.1, y_margin=0.2)
    assert zone == {"x": (0.9, 1.1), "y": (1.8, 2.2)}


def test_slope_drag_state():
    start, end, move, resize = plot_drag.slope_drag_state(
        [0.0, 1.0, 2.0],
        [1.0, 3.0, 2.0],
        x_margin=0.1,
        y_margin=0.2,
    )
    assert start == (0.0, 1.0)
    assert end == (2.0, 2.0)
    assert move == {"x": (-0.1, 2.1), "y": (0.8, 3.2)}
    assert resize == {"x": (1.9, 2.1), "y": (1.8, 2.2)}


def test_point_in_zone():
    zone = {"x": (1.0, 2.0), "y": (3.0, 4.0)}
    assert plot_drag.point_in_zone(1.5, 3.5, zone)
    assert not plot_drag.point_in_zone(0.5, 3.5, zone)
    assert not plot_drag.point_in_zone(1.5, 3.5, {})