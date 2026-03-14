import pytest

streamlit = pytest.importorskip("streamlit")

from wrong_way.ui_streamlit import (  # noqa: E402
    _render_building_figure,
    _render_heatmap,
    _render_streak_distribution,
    _render_wait_distribution,
)


def test_chart_helpers_render_without_exception() -> None:
    fig0 = _render_building_figure(
        {
            "elevators": [
                {"elevator_id": 0, "floor": 2, "direction": "up"},
                {"elevator_id": 1, "floor": 5, "direction": "down"},
            ],
            "observer_floor": 4,
        },
        floors=8,
    )
    fig1 = _render_wait_distribution([10, 20, 30], [15, 35, 50])
    fig2 = _render_streak_distribution([0, 1, 2, 4, 5])
    fig3 = _render_heatmap({"up": [0.1, 0.2, 0.3], "down": [0.5, 0.4, 0.3]})

    assert fig0 is not None
    assert fig1 is not None
    assert fig2 is not None
    assert fig3 is not None
