from wrong_way.analytics import sample_god_mode_trajectories
from wrong_way.config import ElevatorTrajectory, GodModeSample, ObserverConfig, SimulationConfig


def test_sample_count_matches_request() -> None:
    config = SimulationConfig(floors=10, elevators=2, seed=1)
    observer = ObserverConfig(start_floor=4, destination_floor=5, desired_direction="up")
    samples = sample_god_mode_trajectories(
        config=config, observer=observer, profile="Random Midday", n_samples=8
    )
    assert len(samples) == 8


def test_each_sample_has_one_trajectory_per_elevator() -> None:
    config = SimulationConfig(floors=10, elevators=3, seed=1)
    observer = ObserverConfig(start_floor=4, destination_floor=5, desired_direction="up")
    samples = sample_god_mode_trajectories(
        config=config, observer=observer, profile="Random Midday", n_samples=4
    )
    for sample in samples:
        assert len(sample.elevators) == 3
        assert all(isinstance(traj, ElevatorTrajectory) for traj in sample.elevators)


def test_trajectory_times_and_floors_are_paired() -> None:
    config = SimulationConfig(floors=8, elevators=2, seed=2)
    observer = ObserverConfig(start_floor=3, destination_floor=4, desired_direction="up")
    samples = sample_god_mode_trajectories(
        config=config, observer=observer, profile="Morning Rush", n_samples=3
    )
    for sample in samples:
        for traj in sample.elevators:
            assert len(traj.times) == len(traj.floors)
            assert len(traj.times) >= 1  # at least the arrival snapshot
            # Times should be monotonic non-decreasing.
            assert all(b >= a for a, b in zip(traj.times, traj.times[1:]))
            # Floors should always be in [0, floors-1].
            assert all(0 <= f <= config.floors - 1 for f in traj.floors)


def test_observer_metadata_preserved_on_each_sample() -> None:
    config = SimulationConfig(floors=12, elevators=2, seed=3)
    observer = ObserverConfig(start_floor=7, destination_floor=8, desired_direction="up")
    samples = sample_god_mode_trajectories(
        config=config, observer=observer, profile="Morning Rush", n_samples=5
    )
    for sample in samples:
        assert sample.observer_floor == 7
        assert sample.observer_desired_direction == "up"


def test_samples_are_deterministic_for_same_config() -> None:
    config = SimulationConfig(floors=10, elevators=2, seed=42)
    observer = ObserverConfig(start_floor=5, destination_floor=6, desired_direction="up")
    s1 = sample_god_mode_trajectories(
        config=config, observer=observer, profile="Random Midday", n_samples=3
    )
    s2 = sample_god_mode_trajectories(
        config=config, observer=observer, profile="Random Midday", n_samples=3
    )
    # Two calls with the same config should produce the same trajectories.
    assert [s.elevators[0].floors for s in s1] == [s.elevators[0].floors for s in s2]


def test_samples_use_disjoint_seed_range_from_main_batch() -> None:
    # If the god-mode seed offset accidentally collided with the batch seed
    # range we'd be reusing identical seeds across the two analyses, which
    # would distort comparisons. Eyeball check: god mode produces results
    # that don't trivially equal a fresh sim with seed=0,1,2 (the batch range).
    from wrong_way.elevator_mode import ElevatorSimulation

    config = SimulationConfig(floors=10, elevators=2, seed=0)
    observer = ObserverConfig(start_floor=5, destination_floor=6, desired_direction="up")
    god_samples = sample_god_mode_trajectories(
        config=config, observer=observer, profile="Morning Rush", n_samples=3
    )
    batch_floors = []
    for idx in range(3):
        run_config = SimulationConfig(
            floors=10, elevators=2, seed=0 + idx
        )
        sim = ElevatorSimulation(run_config, observer, "Morning Rush")
        sim.run()
        batch_floors.append(
            [snap["elevators"][0]["floor"] for snap in sim.state_log]
        )
    god_floors = [s.elevators[0].floors for s in god_samples]
    # Different seed offsets ⇒ different trajectories on at least one sample.
    assert god_floors != batch_floors


def test_god_mode_sample_is_a_dataclass_instance() -> None:
    config = SimulationConfig(floors=8, elevators=1, seed=4)
    observer = ObserverConfig(start_floor=3, destination_floor=4, desired_direction="up")
    samples = sample_god_mode_trajectories(
        config=config, observer=observer, profile="Random Midday", n_samples=1
    )
    assert isinstance(samples[0], GodModeSample)
