"""CLI entrypoint for a quick non-UI simulation run."""

from wrong_way.config import ObserverConfig, SimulationConfig
from wrong_way.elevator_mode import ElevatorSimulation


def main() -> None:
    config = SimulationConfig(seed=42)
    observer = ObserverConfig(start_floor=18, destination_floor=19, desired_direction="up")
    sim = ElevatorSimulation(config=config, observer=observer, profile="Morning Rush")
    result = sim.run()

    print("Wrong-Way quick run")
    print(f"Served: {result.served}")
    print(f"Actual wait: {result.actual_wait_seconds:.1f}s")
    print(f"Perceived wait: {result.perceived_wait_seconds:.1f}s")
    print(f"Wrong-way passes: {result.wrong_way_passes}")
    print(f"Wrong-way stops: {result.wrong_way_stops}")
    print(f"Max streak: {result.max_wrong_way_streak}")


if __name__ == "__main__":
    main()
