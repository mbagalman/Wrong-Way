import pytest

from wrong_way.config import ObserverConfig, SimulationConfig, validate_observer_against_config
from wrong_way.elevator_mode import ElevatorSimulation


def test_helper_accepts_in_range_observer() -> None:
    config = SimulationConfig(floors=10)
    observer = ObserverConfig(start_floor=0, destination_floor=9, desired_direction="up")
    validate_observer_against_config(observer, config)  # no raise


def test_helper_rejects_start_floor_above_top() -> None:
    config = SimulationConfig(floors=10)
    observer = ObserverConfig(start_floor=10, destination_floor=9, desired_direction="down")
    with pytest.raises(ValueError, match="start_floor"):
        validate_observer_against_config(observer, config)


def test_helper_rejects_start_floor_below_zero() -> None:
    config = SimulationConfig(floors=10)
    observer = ObserverConfig(start_floor=-1, destination_floor=2, desired_direction="up")
    with pytest.raises(ValueError, match="start_floor"):
        validate_observer_against_config(observer, config)


def test_helper_rejects_destination_floor_above_top() -> None:
    config = SimulationConfig(floors=10)
    observer = ObserverConfig(start_floor=5, destination_floor=10, desired_direction="up")
    with pytest.raises(ValueError, match="destination_floor"):
        validate_observer_against_config(observer, config)


def test_simulation_constructor_uses_helper() -> None:
    # Smoke test: bad observer flagged at sim construction, before any
    # event-loop work begins.
    config = SimulationConfig(floors=10)
    observer = ObserverConfig(start_floor=99, destination_floor=98, desired_direction="up")
    with pytest.raises(ValueError, match="start_floor"):
        ElevatorSimulation(config=config, observer=observer, profile="Random Midday")
