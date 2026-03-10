"""Console runner for Wrong-Way."""

from .config import ObserverConfig, SimulationConfig
from .elevator_mode import ElevatorSimulation


def main() -> None:
    config = SimulationConfig(seed=42)
    observer = ObserverConfig(start_floor=18, destination_floor=19, desired_direction="up")
    result = ElevatorSimulation(config=config, observer=observer, profile="Morning Rush").run()

    print("Wrong-Way quick run")
    print(f"Served: {result.served}")
    print(f"Actual wait: {result.actual_wait_seconds:.1f}s")
    print(f"Perceived wait: {result.perceived_wait_seconds:.1f}s")


if __name__ == "__main__":
    main()
