from wrong_way.config import ObserverConfig, SimulationConfig
from wrong_way.elevator_mode import ElevatorSimulation


def test_state_log_seeded_with_initial_state() -> None:
    config = SimulationConfig(floors=10, elevators=2, seed=1)
    observer = ObserverConfig(start_floor=4, destination_floor=5, desired_direction="up")
    sim = ElevatorSimulation(config=config, observer=observer, profile="Random Midday")

    # Replay should always start from the moment of arrival, before any tick has run.
    assert len(sim.state_log) == 1
    initial = sim.state_log[0]
    assert initial["time"] == 0.0
    assert initial["wrong_way_passes"] == 0
    assert initial["wrong_way_stops"] == 0
    assert initial["max_streak"] == 0
    assert initial["observer_floor"] == 4
    assert len(initial["elevators"]) == config.elevators


def test_state_log_grows_monotonically_in_time() -> None:
    config = SimulationConfig(
        floors=12, elevators=3, tick_seconds=1.0, max_wait_seconds=240.0, seed=42
    )
    observer = ObserverConfig(start_floor=10, destination_floor=11, desired_direction="up")
    result = ElevatorSimulation(config=config, observer=observer, profile="Morning Rush").run()

    timestamps = [s["time"] for s in result.state_log]
    assert all(later >= earlier for earlier, later in zip(timestamps, timestamps[1:]))
    # First entry is arrival; final entry is at served-or-timeout time.
    assert timestamps[0] == 0.0
    if result.served:
        assert timestamps[-1] == result.actual_wait_seconds
    else:
        assert timestamps[-1] >= result.actual_wait_seconds


def test_state_log_final_entry_matches_run_result_counts() -> None:
    config = SimulationConfig(floors=20, elevators=3, seed=7, max_wait_seconds=240.0)
    observer = ObserverConfig(start_floor=10, destination_floor=11, desired_direction="up")
    result = ElevatorSimulation(config=config, observer=observer, profile="Morning Rush").run()

    final = result.state_log[-1]
    assert final["wrong_way_passes"] == result.wrong_way_passes
    assert final["wrong_way_stops"] == result.wrong_way_stops
    assert final["max_streak"] == result.max_wrong_way_streak


def test_state_log_entries_are_independent_snapshots() -> None:
    # Each tick must record its own dict, not aliases of a shared mutable.
    # Otherwise replay would show the final state at every slider position.
    config = SimulationConfig(floors=10, elevators=2, seed=3)
    observer = ObserverConfig(start_floor=5, destination_floor=6, desired_direction="up")
    result = ElevatorSimulation(config=config, observer=observer, profile="Morning Rush").run()

    if len(result.state_log) < 2:
        return  # too short to test independence — corner case, skip
    first = result.state_log[0]
    last = result.state_log[-1]
    assert first is not last
    # The first elevator snapshot in the first state should not be the same
    # object as the first elevator snapshot in any later state.
    assert first["elevators"][0] is not last["elevators"][0]
