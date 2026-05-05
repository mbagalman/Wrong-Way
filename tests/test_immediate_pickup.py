import pytest

import wrong_way.elevator_mode as em
from wrong_way.config import ObserverConfig, SimulationConfig
from wrong_way.elevator_mode import ElevatorSimulation, RideRequest


def _quiet_sim(observer_dir: str, observer_dest: int) -> ElevatorSimulation:
    config = SimulationConfig(floors=10, elevators=1, tick_seconds=1.0, seed=1)
    observer = ObserverConfig(
        start_floor=5, destination_floor=observer_dest, desired_direction=observer_dir
    )
    sim = ElevatorSimulation(config=config, observer=observer, profile="Random Midday")
    elevator = sim.elevators[0]
    elevator.current_floor = 5
    elevator.direction = "idle"
    elevator.pending_stops = set()
    elevator.door_timer = 0.0
    return sim


def test_immediate_pickup_serves_observer_when_directions_align(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sim = _quiet_sim(observer_dir="up", observer_dest=8)
    elevator = sim.elevators[0]

    monkeypatch.setattr(
        em, "sample_request", lambda rng, profile, floors: RideRequest(origin=5, destination=8)
    )

    sim._assign_one_request()

    assert elevator.door_timer > 0
    assert 5 not in elevator.pending_stops
    assert 8 in elevator.pending_stops
    assert elevator.direction == "up"
    assert sim._served is True
    stop_events = [e for e in sim.event_log if e.event_type == "stop"]
    assert len(stop_events) == 1
    assert stop_events[0].floor == 5


def test_immediate_pickup_counts_wrong_way_for_opposite_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sim = _quiet_sim(observer_dir="up", observer_dest=8)
    elevator = sim.elevators[0]

    monkeypatch.setattr(
        em, "sample_request", lambda rng, profile, floors: RideRequest(origin=5, destination=2)
    )

    sim._assign_one_request()

    assert elevator.direction == "down"
    assert sim._served is False
    assert sim._wrong_way_stops == 1


def test_immediate_pickup_during_existing_dwell_does_not_double_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sim = _quiet_sim(observer_dir="up", observer_dest=8)
    elevator = sim.elevators[0]
    elevator.direction = "down"
    elevator.door_timer = 4.0

    initial_wrong_way_stops = sim._wrong_way_stops
    initial_event_count = len(sim.event_log)

    monkeypatch.setattr(
        em, "sample_request", lambda rng, profile, floors: RideRequest(origin=5, destination=2)
    )

    sim._assign_one_request()

    assert sim._wrong_way_stops == initial_wrong_way_stops
    assert 5 not in elevator.pending_stops
    assert elevator.door_timer == 4.0
    new_events = sim.event_log[initial_event_count:]
    assert all(e.event_type == "request_assigned" for e in new_events)


def test_immediate_pickup_yields_zero_wait_for_aligned_observer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # End-to-end: an idle car at the observer's floor + an aligned-direction request
    # should serve the observer on tick 0 (actual wait ~= 0).
    config = SimulationConfig(floors=10, elevators=1, tick_seconds=1.0, seed=1)
    observer = ObserverConfig(start_floor=5, destination_floor=8, desired_direction="up")
    sim = ElevatorSimulation(config=config, observer=observer, profile="Random Midday")
    elevator = sim.elevators[0]
    elevator.current_floor = 5
    elevator.direction = "idle"
    elevator.pending_stops = set()
    elevator.door_timer = 0.0

    # Force the very first request to arrive at the observer's floor going up.
    requests = iter([RideRequest(origin=5, destination=9)])

    def fake_sample(rng, profile, floors):  # type: ignore[no-untyped-def]
        try:
            return next(requests)
        except StopIteration:
            return RideRequest(origin=0, destination=1)

    monkeypatch.setattr(em, "sample_request", fake_sample)
    # Ensure at least one demand arrives on tick 0 regardless of RNG state.
    monkeypatch.setattr(ElevatorSimulation, "_poisson_sample", lambda self, lam: 1)

    result = sim.run()

    assert result.served is True
    assert result.actual_wait_seconds == 0.0
