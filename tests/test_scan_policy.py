from wrong_way.config import ObserverConfig, SimulationConfig
from wrong_way.elevator_mode import ElevatorSimulation


def test_scan_reverses_at_top_boundary() -> None:
    config = SimulationConfig(floors=10, elevators=1, seed=1)
    observer = ObserverConfig(start_floor=2, destination_floor=3, desired_direction="up")
    sim = ElevatorSimulation(config=config, observer=observer, profile="Random Midday")

    elevator = sim.elevators[0]
    elevator.current_floor = 9
    elevator.direction = "up"
    elevator.pending_stops = set()

    sim._apply_scan_direction(elevator)

    assert elevator.direction == "down"


def test_scan_reverses_when_queue_exhausted_in_current_direction() -> None:
    config = SimulationConfig(floors=10, elevators=1, seed=2)
    observer = ObserverConfig(start_floor=2, destination_floor=3, desired_direction="up")
    sim = ElevatorSimulation(config=config, observer=observer, profile="Random Midday")

    elevator = sim.elevators[0]
    elevator.current_floor = 5
    elevator.direction = "up"
    elevator.pending_stops = {1}

    sim._apply_scan_direction(elevator)

    assert elevator.direction == "down"
