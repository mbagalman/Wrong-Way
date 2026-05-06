"""Typed configuration and result models for Wrong-Way."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

Direction = Literal["up", "down", "idle"]
ArrivalDistribution = Literal["exponential", "gamma", "lognormal"]
EventType = Literal[
    "pass_by",
    "stop",
    "served",
    "timeout",
    "direction_change",
    "request_assigned",
    "tick",
]


class ElevatorSnapshot(TypedDict):
    """One elevator's instantaneous state, used by the building renderer."""

    elevator_id: int
    floor: int
    direction: Direction
    pending: int


class BuildingRenderState(TypedDict):
    """Minimal shape the building diagram renderer reads from."""

    elevators: list[ElevatorSnapshot]
    observer_floor: int


class LiveState(BuildingRenderState):
    """Full per-tick state surfaced by ``ElevatorSimulation.current_state``."""

    time: float
    desired_direction: Direction
    wrong_way_passes: int
    wrong_way_stops: int
    max_streak: int
    current_streak: int


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
class SubwayConfig:
    """Two-direction arrival platform configuration.

    Each direction has its own rate (arrivals per second). Rates are kept
    independent rather than tied to a single ratio so asymmetric scenarios
    can be expressed naturally — "uptown one every 90s, downtown one every
    30s" for example.

    ``arrival_distribution`` chooses the inter-arrival distribution:

    - ``"exponential"`` (default): memoryless arrivals, Poisson process.
      The classic textbook setup for the inspection paradox.
    - ``"gamma"``: more "scheduled-feeling" arrivals — fewer near-zero
      gaps, less bunching. Mean preserved at ``1/rate``.
    - ``"lognormal"``: heavier-tailed gaps — long waits become more likely
      while typical waits stay similar. Mean preserved at ``1/rate``.

    All three preserve the per-direction mean so changing distribution
    doesn't shift the average wait — only the *shape* of the wait
    distribution. That's the teaching point of this experimental surface.
    """

    desired_direction_rate: float = 1.0 / 90.0
    other_direction_rate: float = 1.0 / 60.0
    max_wait_seconds: float = 600.0
    seed: int | None = None
    perceived_coeffs: PerceivedCoefficients = field(default_factory=PerceivedCoefficients)
    arrival_distribution: ArrivalDistribution = "exponential"

    def __post_init__(self) -> None:
        if self.desired_direction_rate <= 0:
            raise ValueError("desired_direction_rate must be > 0")
        if self.other_direction_rate <= 0:
            raise ValueError("other_direction_rate must be > 0")
        if self.max_wait_seconds <= 0:
            raise ValueError("max_wait_seconds must be > 0")
        if self.arrival_distribution not in ("exponential", "gamma", "lognormal"):
            raise ValueError(
                f"unknown arrival_distribution: {self.arrival_distribution!r}"
            )


@dataclass(frozen=True)
class SubwayObserver:
    """Commuter on a platform wanting one direction."""

    desired_direction: Direction = "up"
    arrival_time: float = 0.0

    def __post_init__(self) -> None:
        if self.desired_direction not in ("up", "down"):
            raise ValueError("desired_direction must be 'up' or 'down'")


def validate_observer_against_config(
    observer: ObserverConfig, config: SimulationConfig
) -> None:
    """Raise ``ValueError`` if the observer references floors outside the building.

    Floor bounds need both objects, which is why this lives outside
    ``ObserverConfig.__post_init__``. Call it from any entrypoint that builds
    a sim or batch from caller-supplied configs.
    """

    top = config.floors - 1
    if not 0 <= observer.start_floor <= top:
        raise ValueError(
            f"observer start_floor {observer.start_floor} out of range [0, {top}]"
        )
    if not 0 <= observer.destination_floor <= top:
        raise ValueError(
            f"observer destination_floor {observer.destination_floor} "
            f"out of range [0, {top}]"
        )


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
    arrival_snapshot: list[ElevatorSnapshot]
    profile: str
    state_log: list[LiveState] = field(default_factory=list)


@dataclass(frozen=True)
class ElevatorTrajectory:
    """One elevator's floor-over-time trace from a single run.

    ``times[i]`` and ``floors[i]`` are paired; the lists share the same
    cadence as ``RunResult.state_log`` (one entry per tick).
    """

    times: list[float]
    floors: list[int]


@dataclass(frozen=True)
class GodModeSample:
    """One sampled run's trajectory bundle, ready to draw on the overlay."""

    elevators: list[ElevatorTrajectory]
    observer_floor: int
    observer_desired_direction: Direction
    served_time: float | None
    timed_out: bool


@dataclass(frozen=True)
class FrustrationHeatmap:
    """Two metric matrices over (desired direction × observer floor).

    Both come from the same Monte Carlo sweep, so they're paired in one
    object — same trial cost, two different ways to read the asymmetry.

    - ``wrong_way_encounters[direction][floor]``: avg ``passes + stops`` per run.
    - ``perceived_wait_inflation[direction][floor]``: avg ``perceived - actual``
      seconds per run; the perceived-time penalty teaching metric.
    """

    wrong_way_encounters: dict[str, list[float]]
    perceived_wait_inflation: dict[str, list[float]]


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
    reference_profile: str
    reference_p90_wait: float
    tail_share_vs_balanced: float
