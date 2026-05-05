"""Console runner for Wrong-Way.

This is the single source of truth for the quick non-UI run. ``main.py``
at the repo root is a thin shim that calls into here, and the published
``wrong-way-cli`` console script (declared in ``pyproject.toml``) points
at this module's :func:`main`.
"""

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
    print(f"Wrong-way passes: {result.wrong_way_passes}")
    print(f"Wrong-way stops: {result.wrong_way_stops}")
    print(f"Max streak: {result.max_wrong_way_streak}")


if __name__ == "__main__":
    main()
