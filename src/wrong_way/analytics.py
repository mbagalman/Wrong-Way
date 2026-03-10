"""Batch analytics and chart-ready summaries."""

from __future__ import annotations

from dataclasses import asdict
import math
from statistics import mean

from .config import BatchSummary, ObserverConfig, SimulationConfig
from .elevator_mode import DemandProfile, ElevatorSimulation


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


def run_batch_for_observer(
    config: SimulationConfig,
    observer: ObserverConfig,
    profile: DemandProfile,
    trials: int = 1000,
    seed_offset: int = 0,
) -> BatchSummary:
    actual_waits: list[float] = []
    perceived_waits: list[float] = []
    streaks: list[int] = []
    passes: list[int] = []
    stops: list[int] = []

    base_seed = config.seed or 0

    for idx in range(trials):
        run_config = SimulationConfig(
            floors=config.floors,
            elevators=config.elevators,
            tick_seconds=config.tick_seconds,
            max_wait_seconds=config.max_wait_seconds,
            seed=base_seed + seed_offset + idx,
            travel_time_per_floor=config.travel_time_per_floor,
            door_dwell_seconds=config.door_dwell_seconds,
            perceived_coeffs=config.perceived_coeffs,
        )
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

    long_gap_rate = (
        sum(1 for wait in actual_waits if wait >= p90) / len(actual_waits) if actual_waits else 0.0
    )

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
        long_gap_hit_rate=long_gap_rate,
        heatmap_matrix={"up": [], "down": []},
    )


def build_frustration_heatmap(
    config: SimulationConfig,
    profile: DemandProfile,
    trials_per_cell: int = 50,
) -> dict[str, list[float]]:
    """Average wrong-way encounters by floor and desired direction."""

    heatmap: dict[str, list[float]] = {
        "up": [0.0 for _ in range(config.floors)],
        "down": [0.0 for _ in range(config.floors)],
    }

    for floor in range(config.floors):
        for direction in ("up", "down"):
            if direction == "up" and floor >= config.floors - 1:
                heatmap[direction][floor] = 0.0
                continue
            if direction == "down" and floor <= 0:
                heatmap[direction][floor] = 0.0
                continue

            destination = floor + 1 if direction == "up" else floor - 1
            observer = ObserverConfig(
                start_floor=floor,
                destination_floor=destination,
                desired_direction=direction,
            )

            values: list[float] = []
            base_seed = (config.seed or 0) + floor * 100 + (0 if direction == "up" else 50_000)

            for trial in range(trials_per_cell):
                run_config = SimulationConfig(
                    floors=config.floors,
                    elevators=config.elevators,
                    tick_seconds=config.tick_seconds,
                    max_wait_seconds=config.max_wait_seconds,
                    seed=base_seed + trial,
                    travel_time_per_floor=config.travel_time_per_floor,
                    door_dwell_seconds=config.door_dwell_seconds,
                    perceived_coeffs=config.perceived_coeffs,
                )
                sim = ElevatorSimulation(run_config, observer, profile)
                result = sim.run()
                values.append(result.wrong_way_passes + result.wrong_way_stops)

            heatmap[direction][floor] = mean(values) if values else 0.0

    return heatmap


def to_dict(summary: BatchSummary) -> dict[str, object]:
    return asdict(summary)
