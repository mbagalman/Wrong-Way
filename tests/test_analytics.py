from wrong_way.analytics import build_frustration_heatmap, run_batch_for_observer
from wrong_way.config import ObserverConfig, SimulationConfig


def test_heatmap_shape_and_non_negative_values() -> None:
    config = SimulationConfig(floors=12, elevators=2, seed=7)
    heatmap = build_frustration_heatmap(config=config, profile="Random Midday", trials_per_cell=8)

    assert set(heatmap.keys()) == {"up", "down"}
    assert len(heatmap["up"]) == 12
    assert len(heatmap["down"]) == 12
    assert all(value >= 0 for value in heatmap["up"])
    assert all(value >= 0 for value in heatmap["down"])


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
