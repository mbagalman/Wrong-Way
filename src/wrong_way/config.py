"""Typed configuration and result models for Wrong-Way."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Direction = Literal["up", "down", "idle"]
EventType = Literal[
    "pass_by",
    "stop",
    "served",
    "timeout",
    "direction_change",
    "request_assigned",
    "tick",
]


@dataclass(frozen=True)
class PerceivedCoefficients:
    """Penalty weights for the perceived wait formula."""

    a: float = 8.0
    b: float = 18.0
    c: float = 6.0


@dataclass(frozen=True)
class SimulationConfig:
    """Global simulation settings for a single run."""

    floors: int = 20
    elevators: int = 3
    tick_seconds: float = 1.0
    max_wait_seconds: float = 240.0
    seed: int | None = None
    travel_time_per_floor: float = 3.0
    door_dwell_seconds: float = 4.0
    perceived_coeffs: PerceivedCoefficients = field(default_factory=PerceivedCoefficients)

    def __post_init__(self) -> None:
        if self.floors < 2:
            raise ValueError("floors must be >= 2")
        if self.elevators < 1:
            raise ValueError("elevators must be >= 1")
        if self.tick_seconds <= 0:
            raise ValueError("tick_seconds must be > 0")
        if self.max_wait_seconds <= 0:
            raise ValueError("max_wait_seconds must be > 0")
        if self.travel_time_per_floor <= 0:
            raise ValueError("travel_time_per_floor must be > 0")
        if self.door_dwell_seconds < 0:
            raise ValueError("door_dwell_seconds must be >= 0")


@dataclass(frozen=True)
class ObserverConfig:
    """User waiting at a floor for a direction/destination."""

    start_floor: int
    destination_floor: int
    arrival_time: float = 0.0
    desired_direction: Direction = "up"

    def __post_init__(self) -> None:
        if self.start_floor == self.destination_floor:
            raise ValueError("destination floor must differ from start floor")
        if self.desired_direction not in ("up", "down"):
            raise ValueError("desired_direction must be 'up' or 'down'")


@dataclass(frozen=True)
class Event:
    """Single event in the run log."""

    timestamp: float
    event_type: EventType
    elevator_id: int | None
    floor: int | None
    direction: Direction
    is_wrong_way: bool = False
    is_stop: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunResult:
    """Aggregated metrics for one simulation run."""

    served: bool
    timed_out: bool
    actual_wait_seconds: float
    perceived_wait_seconds: float
    wrong_way_passes: int
    wrong_way_stops: int
    max_wrong_way_streak: int
    rage_score: float
    complaint_strength_score: float
    rigged_system_belief_score: float
    event_log: list[Event]
    arrival_snapshot: list[dict[str, Any]]
    profile: str


@dataclass(frozen=True)
class BatchSummary:
    """Batch-level analytics for many runs."""

    profile: str
    run_count: int
    actual_wait_seconds: list[float]
    perceived_wait_seconds: list[float]
    wrong_way_streaks: list[int]
    wrong_way_passes: list[int]
    wrong_way_stops: list[int]
    percentile_p50_wait: float
    percentile_p90_wait: float
    percentile_p95_wait: float
    long_gap_hit_rate: float
    heatmap_matrix: dict[str, list[float]]
