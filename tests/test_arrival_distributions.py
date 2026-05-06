import math
import random
from statistics import mean, stdev

import pytest

from wrong_way.config import SubwayConfig, SubwayObserver
from wrong_way.subway_mode import (
    SubwaySimulation,
    _exponential_inter_arrival,
    _gamma_inter_arrival,
    _lognormal_inter_arrival,
    make_sampler,
)


def _sample_many(sampler, rate, n=10_000, seed=1):  # type: ignore[no-untyped-def]
    rng = random.Random(seed)
    return [sampler(rng, rate) for _ in range(n)]


def test_each_sampler_preserves_mean_at_one_over_rate() -> None:
    target_mean = 1.0 / 0.5  # rate = 0.5 → mean inter-arrival = 2.0
    rate = 0.5
    for sampler in (
        _exponential_inter_arrival,
        _gamma_inter_arrival,
        _lognormal_inter_arrival,
    ):
        samples = _sample_many(sampler, rate=rate, n=20_000)
        observed = mean(samples)
        # ±5% tolerance — Lognormal has the heaviest tail and converges
        # slowest; 20k samples is plenty for all three.
        assert abs(observed - target_mean) / target_mean < 0.05, (
            f"{sampler.__name__}: observed mean {observed:.3f} vs target {target_mean}"
        )


def test_gamma_produces_fewer_near_zero_gaps_than_exponential() -> None:
    # Shape > 1 gamma is unimodal — the peak is away from zero, so the
    # fraction of samples below ~10% of the mean should be lower than
    # Exponential (which has a mode at 0).
    rate = 1.0
    threshold = 0.1  # 10% of mean (mean is 1.0)
    exp_samples = _sample_many(_exponential_inter_arrival, rate=rate, n=20_000, seed=7)
    gam_samples = _sample_many(_gamma_inter_arrival, rate=rate, n=20_000, seed=7)
    exp_near_zero = sum(1 for s in exp_samples if s < threshold) / len(exp_samples)
    gam_near_zero = sum(1 for s in gam_samples if s < threshold) / len(gam_samples)
    assert gam_near_zero < exp_near_zero


def test_lognormal_has_higher_dispersion_than_exponential() -> None:
    # Lognormal with sigma=1 has CV ≈ sqrt(exp(σ²) - 1) ≈ 1.31; Exponential
    # has CV = 1 by construction. Lognormal should look noticeably more
    # dispersed when measured by sample stdev / sample mean.
    rate = 1.0
    exp_samples = _sample_many(_exponential_inter_arrival, rate=rate, n=20_000, seed=11)
    log_samples = _sample_many(_lognormal_inter_arrival, rate=rate, n=20_000, seed=11)
    exp_cv = stdev(exp_samples) / mean(exp_samples)
    log_cv = stdev(log_samples) / mean(log_samples)
    assert log_cv > exp_cv * 1.1  # at least 10% more dispersed


def test_make_sampler_returns_each_distribution() -> None:
    rng = random.Random(0)
    for name in ("exponential", "gamma", "lognormal"):
        sampler = make_sampler(name)
        value = sampler(rng, rate=1.0)
        assert value > 0
        assert math.isfinite(value)


def test_make_sampler_rejects_unknown_distribution() -> None:
    with pytest.raises(ValueError, match="unknown arrival_distribution"):
        make_sampler("uniform")  # type: ignore[arg-type]


def test_subway_config_rejects_unknown_distribution() -> None:
    with pytest.raises(ValueError, match="unknown arrival_distribution"):
        SubwayConfig(arrival_distribution="weibull")  # type: ignore[arg-type]


def test_simulation_resolves_sampler_from_config_when_none_supplied() -> None:
    # Sanity: passing arrival_distribution through config alone (no explicit
    # sampler) should produce a working sim.
    for dist in ("exponential", "gamma", "lognormal"):
        config = SubwayConfig(seed=42, arrival_distribution=dist, max_wait_seconds=300.0)
        observer = SubwayObserver(desired_direction="up")
        result = SubwaySimulation(config=config, observer=observer).run()
        assert result.profile == "Subway"
        assert result.actual_wait_seconds >= 0


def test_distribution_choice_changes_run_outcomes() -> None:
    # Same rate, same seed, different distributions — outcomes should differ
    # (not by mean, but by individual-run shape). Otherwise the experimental
    # surface isn't actually doing anything.
    base = SubwayConfig(seed=99, max_wait_seconds=300.0)
    observer = SubwayObserver(desired_direction="up")

    waits = {}
    for dist in ("exponential", "gamma", "lognormal"):
        result = SubwaySimulation(
            config=SubwayConfig(
                seed=99,
                max_wait_seconds=300.0,
                arrival_distribution=dist,
                desired_direction_rate=base.desired_direction_rate,
                other_direction_rate=base.other_direction_rate,
            ),
            observer=observer,
        ).run()
        waits[dist] = result.actual_wait_seconds

    distinct = len(set(waits.values()))
    assert distinct >= 2, f"distributions produced identical outcomes: {waits}"
