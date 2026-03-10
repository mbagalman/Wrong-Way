from statistics import mean

from wrong_way.config import ObserverConfig, SimulationConfig
from wrong_way.elevator_mode import ElevatorSimulation


def _avg_wrong_way(profile: str, seeds: range) -> float:
    waits = []
    for seed in seeds:
        config = SimulationConfig(floors=20, elevators=3, seed=seed, max_wait_seconds=200)
        observer = ObserverConfig(start_floor=18, destination_floor=19, desired_direction="up")
        result = ElevatorSimulation(config=config, observer=observer, profile=profile).run()
        waits.append(result.wrong_way_passes + result.wrong_way_stops)
    return mean(waits)


def test_morning_rush_has_more_wrong_way_than_random_midday_for_top_floor_upward() -> None:
    morning = _avg_wrong_way("Morning Rush", range(200, 280))
    midday = _avg_wrong_way("Random Midday", range(200, 280))

    assert morning > midday
