import matplotlib.pyplot as plt
import pytest

streamlit = pytest.importorskip("streamlit")

from wrong_way.ui_streamlit import (  # noqa: E402
    _render_building_figure,
    _render_heatmap,
    _render_streak_distribution,
    _render_wait_distribution,
)


_BUILDING_STATE = {
    "elevators": [
        {"elevator_id": 0, "floor": 2, "direction": "up"},
        {"elevator_id": 1, "floor": 5, "direction": "down"},
    ],
    "observer_floor": 4,
}


def test_chart_helpers_render_without_exception() -> None:
    fig0 = _render_building_figure(_BUILDING_STATE, floors=8)
    fig1 = _render_wait_distribution([10, 20, 30], [15, 35, 50])
    fig2 = _render_streak_distribution([0, 1, 2, 4, 5])
    fig3 = _render_heatmap({"up": [0.1, 0.2, 0.3], "down": [0.5, 0.4, 0.3]})

    assert fig0 is not None
    assert fig1 is not None
    assert fig2 is not None
    assert fig3 is not None
    plt.close("all")


def test_building_figure_reuses_axes_across_repeated_renders() -> None:
    # Live-loop path: a single Figure/Axes pair is allocated once and
    # _render_building_figure is called many times against the same axes.
    fig, ax = plt.subplots(figsize=(4.6, 6.4))
    try:
        for floor_for_observer in (0, 4, 7):
            state = dict(_BUILDING_STATE, observer_floor=floor_for_observer)
            returned = _render_building_figure(state, floors=8, ax=ax)
            assert returned is fig
            # Each pass should leave drawable artists; redraw shouldn't accumulate
            # them past what one render produces.
            assert ax.patches  # cars + shafts redrawn
    finally:
        plt.close(fig)
