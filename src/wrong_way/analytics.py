"""Batch analytics and chart-ready summaries."""

from __future__ import annotations

from dataclasses import asdict, replace
import math
from statistics import mean

from .config import (
    BatchSummary,
    ElevatorTrajectory,
    FrustrationHeatmap,
    GodModeSample,
    ObserverConfig,
    SimulationConfig,
)
from .elevator_mode import DemandProfile, ElevatorSimulation

# Anchor used by tail_share_vs_balanced. "Random Midday" is the closest thing
# to symmetric demand we have, so it stands in for "what the wait distribution
# would look like if the building wasn't structurally biased against you."
REFERENCE_PROFILE: DemandProfile = "Random Midday"
DEFAULT_REFERENCE_TRIALS_CAP = 500
# Disjoint seed offsets so derived seed ranges never collide with each other
# or with user-batch seeds.
_REFERENCE_SEED_OFFSET = 10_000_000
_GOD_MODE_SEED_OFFSET = 20_000_000


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * pct
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(ordered[low])
    weight = rank - low
    return float(ordered[low] * (1 - weight) + ordered[high] * weight)


def _reference_p90_wait(
    config: SimulationConfig,
    observer: ObserverConfig,
    trials: int,
) -> float:
    base_seed = (config.seed or 0) + _REFERENCE_SEED_OFFSET
    waits: list[float] = []
    for idx in range(trials):
        run_config = replace(config, seed=base_seed + idx)
        sim = ElevatorSimulation(run_config, observer, REFERENCE_PROFILE)
        result = sim.run()
        waits.append(result.actual_wait_seconds)
    return percentile(waits, 0.9)


def run_batch_for_observer(
    config: SimulationConfig,
    observer: ObserverConfig,
    profile: DemandProfile,
    trials: int = 1000,
    seed_offset: int = 0,
    reference_trials: int | None = None,
) -> BatchSummary:
    actual_waits: list[float] = []
    perceived_waits: list[float] = []
    streaks: list[int] = []
    passes: list[int] = []
    stops: list[int] = []

    base_seed = config.seed or 0

    for idx in range(trials):
        run_config = replace(config, seed=base_seed + seed_offset + idx)
        sim = ElevatorSimulation(run_config, observer, profile)
        result = sim.run()
        actual_waits.append(result.actual_wait_seconds)
        perceived_waits.append(result.perceived_wait_seconds)
        streaks.append(result.max_wrong_way_streak)
        passes.append(result.wrong_way_passes)
        stops.append(result.wrong_way_stops)

    p50 = percentile(actual_waits, 0.5)
    p90 = percentile(actual_waits, 0.9)
    p95 = percentile(actual_waits, 0.95)

    n_reference = (
        reference_trials
        if reference_trials is not None
        else min(DEFAULT_REFERENCE_TRIALS_CAP, trials)
    )
    reference_p90 = _reference_p90_wait(config, observer, n_reference)

    if reference_p90 <= 0 or not actual_waits:
        tail_share = 0.0
    else:
        tail_share = sum(1 for w in actual_waits if w >= reference_p90) / len(actual_waits)

    return BatchSummary(
        profile=profile,
        run_count=trials,
        actual_wait_seconds=actual_waits,
        perceived_wait_seconds=perceived_waits,
        wrong_way_streaks=streaks,
        wrong_way_passes=passes,
        wrong_way_stops=stops,
        percentile_p50_wait=p50,
        percentile_p90_wait=p90,
        percentile_p95_wait=p95,
        reference_profile=REFERENCE_PROFILE,
        reference_p90_wait=reference_p90,
        tail_share_vs_balanced=tail_share,
    )


def build_frustration_heatmap(
    config: SimulationConfig,
    profile: DemandProfile,
    trials_per_cell: int = 50,
) -> FrustrationHeatmap:
    """Run a Monte Carlo sweep across (direction × floor) and capture two metrics.

    Both metrics come from the same trials, so this is one trial loop, two
    teaching surfaces: average wrong-way encounters per run, and average
    perceived-wait inflation (perceived − actual seconds) per run.
    """

    encounters: dict[str, list[float]] = {
        "up": [0.0 for _ in range(config.floors)],
        "down": [0.0 for _ in range(config.floors)],
    }
    inflation: dict[str, list[float]] = {
        "up": [0.0 for _ in range(config.floors)],
        "down": [0.0 for _ in range(config.floors)],
    }

    for floor in range(config.floors):
        for direction in ("up", "down"):
            if direction == "up" and floor >= config.floors - 1:
                continue
            if direction == "down" and floor <= 0:
                continue

            destination = floor + 1 if direction == "up" else floor - 1
            observer = ObserverConfig(
                start_floor=floor,
                destination_floor=destination,
                desired_direction=direction,
            )

            encounter_values: list[float] = []
            inflation_values: list[float] = []
            base_seed = (config.seed or 0) + floor * 100 + (0 if direction == "up" else 50_000)

            for trial in range(trials_per_cell):
                run_config = replace(config, seed=base_seed + trial)
                sim = ElevatorSimulation(run_config, observer, profile)
                result = sim.run()
                encounter_values.append(result.wrong_way_passes + result.wrong_way_stops)
                inflation_values.append(
                    result.perceived_wait_seconds - result.actual_wait_seconds
                )

            if encounter_values:
                encounters[direction][floor] = mean(encounter_values)
                inflation[direction][floor] = mean(inflation_values)

    return FrustrationHeatmap(
        wrong_way_encounters=encounters,
        perceived_wait_inflation=inflation,
    )


def sample_god_mode_trajectories(
    config: SimulationConfig,
    observer: ObserverConfig,
    profile: DemandProfile,
    n_samples: int = 40,
) -> list[GodModeSample]:
    """Run ``n_samples`` independent sims and extract per-elevator trajectories.

    The returned list is what the God Mode overlay renders translucently:
    one floor-over-time trace per elevator per run. Each sim's ``state_log``
    is already populated as part of the existing run, so this is essentially
    free on top of the simulation cost itself.
    """

    base_seed = (config.seed or 0) + _GOD_MODE_SEED_OFFSET
    samples: list[GodModeSample] = []
    for idx in range(n_samples):
        run_config = replace(config, seed=base_seed + idx)
        sim = ElevatorSimulation(run_config, observer, profile)
        result = sim.run()
        trajectories: list[ElevatorTrajectory] = []
        for elev_idx in range(config.elevators):
            times = [snapshot["time"] for snapshot in result.state_log]
            floors = [
                snapshot["elevators"][elev_idx]["floor"]
                for snapshot in result.state_log
            ]
            trajectories.append(ElevatorTrajectory(times=times, floors=floors))
        samples.append(
            GodModeSample(
                elevators=trajectories,
                observer_floor=observer.start_floor,
                observer_desired_direction=observer.desired_direction,
                served_time=result.actual_wait_seconds if result.served else None,
                timed_out=result.timed_out,
            )
        )
    return samples


def to_dict(summary: BatchSummary) -> dict[str, object]:
    return asdict(summary)
