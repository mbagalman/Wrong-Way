from dataclasses import replace
from statistics import mean

import pytest

from wrong_way.config import SubwayConfig, SubwayObserver
from wrong_way.subway_mode import SubwaySimulation


def _scripted_sampler(*deltas: float):
    """Return a sampler that yields each delta in order."""

    iterator = iter(deltas)

    def sampler(rng, rate):  # type: ignore[no-untyped-def]
        return next(iterator)

    return sampler


def test_served_when_desired_arrives_first() -> None:
    sampler = _scripted_sampler(10.0, 30.0)
    config = SubwayConfig(seed=1, max_wait_seconds=60.0)
    observer = SubwayObserver(desired_direction="up")
    result = SubwaySimulation(config, observer, sampler=sampler).run()

    assert result.served is True
    assert result.timed_out is False
    assert result.actual_wait_seconds == 10.0
    assert result.wrong_way_stops == 0
    assert result.max_wrong_way_streak == 0


def test_records_wrong_way_train_before_useful() -> None:
    # Trace: desired sampled 20.0; other sampled 5.0 -> other wins at t=5
    # (wrong-way). Resample other: 20.0 -> next_other = 25.0. Compare desired
    # 20.0 vs other 25.0 -> desired wins, served at t=20.
    sampler = _scripted_sampler(20.0, 5.0, 20.0)
    result = SubwaySimulation(
        SubwayConfig(seed=1, max_wait_seconds=60.0),
        SubwayObserver(desired_direction="up"),
        sampler=sampler,
    ).run()

    assert result.served is True
    assert result.actual_wait_seconds == 20.0
    assert result.wrong_way_stops == 1
    assert result.max_wrong_way_streak == 1
    # The single wrong-way stop should inflate perceived wait by exactly b=18s
    # over actual wait, with no streak penalty (streak^2 == 1, c=6).
    assert result.perceived_wait_seconds == pytest.approx(20.0 + 18.0 + 6.0)


def test_consecutive_wrong_way_trains_compound_streak() -> None:
    # Trace: desired at t=200 (never within window). Other arrives at
    # t=10, 20, 30 (resampled +10 each time). After the third wrong-way the
    # resampled other lands at t=130, beyond max_wait — timeout fires.
    sampler = _scripted_sampler(200.0, 10.0, 10.0, 10.0, 100.0)
    result = SubwaySimulation(
        SubwayConfig(seed=1, max_wait_seconds=60.0),
        SubwayObserver(desired_direction="up"),
        sampler=sampler,
    ).run()

    assert result.served is False
    assert result.timed_out is True
    assert result.wrong_way_stops == 3
    assert result.max_wrong_way_streak == 3


def test_timeout_when_no_useful_train_in_window() -> None:
    sampler = _scripted_sampler(100.0, 30.0, 30.0)
    result = SubwaySimulation(
        SubwayConfig(seed=1, max_wait_seconds=60.0),
        SubwayObserver(desired_direction="up"),
        sampler=sampler,
    ).run()

    assert result.served is False
    assert result.timed_out is True
    assert result.actual_wait_seconds == 60.0
    assert result.wrong_way_stops == 1


def test_run_result_shape_compatible_with_metric_helpers() -> None:
    # Smoke: a fresh run produces a fully populated RunResult — all the fields
    # the existing UI panels (truth screen, complaint generator, replay) read.
    result = SubwaySimulation(
        SubwayConfig(seed=42),
        SubwayObserver(desired_direction="up"),
    ).run()

    assert result.profile == "Subway"
    assert result.rage_score >= 0
    assert result.perceived_wait_seconds >= result.actual_wait_seconds
    assert result.wrong_way_passes == 0  # subway never has pass-bys


def test_asymmetric_rates_produce_meaningful_wrong_way_count() -> None:
    # Other-direction trains arrive 3× as often as the useful direction. The
    # observer should see multiple wrong-way trains on average before the
    # useful one shows up; if average wrong-way is near zero, the simulation
    # isn't carrying the asymmetry signal.
    base = SubwayConfig(
        desired_direction_rate=1 / 120.0,
        other_direction_rate=1 / 40.0,
        max_wait_seconds=300.0,
    )
    observer = SubwayObserver(desired_direction="up")

    counts = []
    for s in range(80):
        result = SubwaySimulation(replace(base, seed=s), observer).run()
        counts.append(result.wrong_way_stops)

    # Loose bound: if the asymmetry is actually being applied, the average
    # should comfortably exceed 1.0. (Theoretical expected E[W]
    # ≈ rate_other / rate_desired ≈ 3 over an unbounded window; bounded at
    # 300s with timeouts, ~2 is typical.)
    assert mean(counts) > 1.0


def test_subway_config_rejects_non_positive_rates() -> None:
    with pytest.raises(ValueError, match="desired_direction_rate"):
        SubwayConfig(desired_direction_rate=0.0)
    with pytest.raises(ValueError, match="other_direction_rate"):
        SubwayConfig(other_direction_rate=-0.1)
