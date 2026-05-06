from wrong_way.analytics import build_frustration_heatmap, run_batch_for_observer
from wrong_way.config import ObserverConfig, SimulationConfig


def test_heatmap_shape_and_non_negative_values() -> None:
    config = SimulationConfig(floors=12, elevators=2, seed=7)
    heatmap = build_frustration_heatmap(config=config, profile="Random Midday", trials_per_cell=8)

    for matrix in (heatmap.wrong_way_encounters, heatmap.perceived_wait_inflation):
        assert set(matrix.keys()) == {"up", "down"}
        assert len(matrix["up"]) == 12
        assert len(matrix["down"]) == 12
        assert all(value >= 0 for value in matrix["up"])
        assert all(value >= 0 for value in matrix["down"])


def test_heatmap_perceived_inflation_dominates_in_morning_rush_mid_band() -> None:
    # The inflation matrix should pick up the same asymmetry the wrong-way
    # matrix does, but expressed in seconds rather than encounter counts.
    # Mid-band up under Morning Rush is the canonical hot cell.
    config = SimulationConfig(floors=20, elevators=3, seed=11, max_wait_seconds=240.0)
    heatmap = build_frustration_heatmap(
        config=config, profile="Morning Rush", trials_per_cell=12
    )
    mid = config.floors // 2
    bottom = 1
    up = heatmap.perceived_wait_inflation["up"]
    assert up[mid] > up[bottom]


def test_batch_summary_counts() -> None:
    config = SimulationConfig(floors=14, elevators=3, seed=11)
    observer = ObserverConfig(start_floor=8, destination_floor=9, desired_direction="up")
    summary = run_batch_for_observer(
        config=config,
        observer=observer,
        profile="Morning Rush",
        trials=1000,
    )

    assert summary.run_count == 1000
    assert len(summary.actual_wait_seconds) == 1000
    assert len(summary.perceived_wait_seconds) == 1000
    assert len(summary.wrong_way_streaks) == 1000
