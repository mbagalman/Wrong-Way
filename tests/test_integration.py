from wrong_way.config import ObserverConfig, SimulationConfig
from wrong_way.elevator_mode import ElevatorSimulation


def test_full_run_served_path() -> None:
    config = SimulationConfig(
        floors=10,
        elevators=1,
        tick_seconds=1.0,
        travel_time_per_floor=1.0,
        door_dwell_seconds=1.0,
        max_wait_seconds=60,
        seed=42,
    )
    observer = ObserverConfig(start_floor=5, destination_floor=6, desired_direction="up")
    sim = ElevatorSimulation(config=config, observer=observer, profile="Random Midday")

    elevator = sim.elevators[0]
    elevator.current_floor = 4
    elevator.direction = "up"
    elevator.pending_stops = {5, 6}

    result = sim.run()

    assert result.served is True
    assert result.timed_out is False
    assert result.actual_wait_seconds >= 0
    assert result.perceived_wait_seconds >= result.actual_wait_seconds


def test_timeout_path() -> None:
    config = SimulationConfig(
        floors=12,
        elevators=1,
        tick_seconds=1.0,
        travel_time_per_floor=10.0,
        max_wait_seconds=1.0,
        seed=99,
    )
    observer = ObserverConfig(start_floor=0, destination_floor=1, desired_direction="up")
    sim = ElevatorSimulation(config=config, observer=observer, profile="Random Midday")

    result = sim.run()

    assert result.served is False
    assert result.timed_out is True
    assert result.actual_wait_seconds == config.max_wait_seconds
