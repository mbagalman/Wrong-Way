from wrong_way.analytics import REFERENCE_PROFILE, run_batch_for_observer
from wrong_way.config import ObserverConfig, SimulationConfig


def test_tail_share_against_balanced_baseline_for_random_midday() -> None:
    # Sanity: when the user profile IS the reference profile, the tail share
    # should sit near the tautological 10% baseline (it's the same distribution
    # measured against its own p90, modulo Monte Carlo noise across two
    # independent batches).
    config = SimulationConfig(floors=14, elevators=3, seed=11)
    observer = ObserverConfig(start_floor=8, destination_floor=9, desired_direction="up")
    summary = run_batch_for_observer(
        config=config,
        observer=observer,
        profile=REFERENCE_PROFILE,
        trials=300,
        reference_trials=300,
    )

    assert summary.reference_profile == REFERENCE_PROFILE
    assert summary.reference_p90_wait > 0
    # Independent batches with the same generator → expected ~0.10, allow generous slack.
    assert 0.03 <= summary.tail_share_vs_balanced <= 0.20


def test_tail_share_exceeds_baseline_for_morning_rush_mid_floor_up() -> None:
    # Mid-floor going up under Morning Rush is the canonical asymmetric case:
    # demand is dominated by top→lobby trips, so cars spend most of their time
    # passing the observer going down. Tail share against a balanced baseline
    # should sit well above the tautological 10%; if it doesn't, the metric
    # isn't carrying any signal.
    config = SimulationConfig(floors=20, elevators=3, seed=42, max_wait_seconds=240.0)
    observer = ObserverConfig(start_floor=10, destination_floor=11, desired_direction="up")
    summary = run_batch_for_observer(
        config=config,
        observer=observer,
        profile="Morning Rush",
        trials=300,
        reference_trials=300,
    )

    assert summary.tail_share_vs_balanced > 0.20


def test_tail_share_threshold_matches_reference_p90() -> None:
    # The tail share must equal the empirical fraction of waits that exceed
    # reference_p90_wait — guards against the threshold drifting out of sync
    # with the reported numerator/denominator.
    config = SimulationConfig(floors=12, elevators=2, seed=7)
    observer = ObserverConfig(start_floor=6, destination_floor=7, desired_direction="up")
    summary = run_batch_for_observer(
        config=config,
        observer=observer,
        profile="Morning Rush",
        trials=200,
        reference_trials=200,
    )

    expected = sum(
        1 for w in summary.actual_wait_seconds if w >= summary.reference_p90_wait
    ) / summary.run_count
    assert summary.tail_share_vs_balanced == expected
