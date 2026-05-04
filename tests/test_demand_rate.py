from wrong_way.config import ObserverConfig, SimulationConfig
from wrong_way.elevator_mode import ElevatorSimulation, profile_request_probability


def _measured_rate(profile: str, tick_seconds: float, seeds: range, duration: float) -> float:
    total_requests = 0
    ticks_per_trial = int(duration / tick_seconds)
    for seed in seeds:
        config = SimulationConfig(
            floors=20,
            elevators=3,
            tick_seconds=tick_seconds,
            max_wait_seconds=duration,
            seed=seed,
        )
        observer = ObserverConfig(start_floor=0, destination_floor=19, desired_direction="up")
        sim = ElevatorSimulation(config, observer, profile)
        for _ in range(ticks_per_trial):
            sim._generate_demand_if_needed()
        total_requests += sum(1 for e in sim.event_log if e.event_type == "request_assigned")
    return total_requests / (len(seeds) * duration)


def test_request_rate_invariant_under_tick_seconds() -> None:
    profile = "Morning Rush"
    expected = profile_request_probability(profile)
    seeds = range(30)
    duration = 600.0

    for tick in (0.5, 1.0, 2.0):
        observed = _measured_rate(profile, tick, seeds, duration)
        assert abs(observed - expected) / expected < 0.10, (
            f"tick={tick}: observed={observed:.3f}, expected={expected}"
        )


def test_large_tick_does_not_saturate() -> None:
    # Pre-fix bug: tick_seconds * req_rate >= 1.0 used to force one request every tick,
    # capping arrivals at exactly 1/tick. Poisson sampling can produce 0, 2, 3, ... too.
    config = SimulationConfig(
        floors=20,
        elevators=3,
        tick_seconds=2.0,
        max_wait_seconds=600.0,
        seed=0,
    )
    observer = ObserverConfig(start_floor=0, destination_floor=19, desired_direction="up")
    sim = ElevatorSimulation(config, observer, "Morning Rush")

    multi_request_ticks = 0
    for _ in range(300):
        before = len(sim.event_log)
        sim._generate_demand_if_needed()
        new_requests = sum(
            1 for e in sim.event_log[before:] if e.event_type == "request_assigned"
        )
        if new_requests > 1:
            multi_request_ticks += 1

    assert multi_request_ticks > 0
