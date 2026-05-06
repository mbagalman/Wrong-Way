"""Subway-mode simulation: two-direction independent arrivals.

The classic inspection-paradox setup. The observer wants one direction;
trains arrive in each direction as independent Poisson processes
(Exponential inter-arrival times). When a useful train arrives the
observer is served; opposite-direction arrivals beforehand count as
ghost-train wrong-way stops.

Reuses :class:`RunResult` and the metric helpers from ``metrics.py`` so
subway runs feed the same UI panels as elevator runs. The inter-arrival
sampler is plugged in as a callable so future tickets can swap Exponential
for Gamma/lognormal without touching the simulation loop.
"""

from __future__ import annotations

import random
from typing import Callable

from .config import (
    Direction,
    Event,
    RunResult,
    SubwayConfig,
    SubwayObserver,
)
from .metrics import (
    complaint_strength_score,
    perceived_wait_seconds,
    rage_score,
    rigged_belief_score,
)

InterArrivalSampler = Callable[[random.Random, float], float]


def _exponential_inter_arrival(rng: random.Random, rate: float) -> float:
    """Sample an inter-arrival time from ``Exp(rate)``.

    ``rate`` is arrivals per second (λ); the mean inter-arrival is ``1/rate``.
    """

    return rng.expovariate(rate)


class SubwaySimulation:
    """Single-observer two-direction arrival simulation.

    Each call to :meth:`run` deterministically simulates one observer's
    experience under the configured rates and seed, and returns a populated
    :class:`RunResult` matching the same shape elevator-mode runs produce.
    """

    def __init__(
        self,
        config: SubwayConfig,
        observer: SubwayObserver,
        sampler: InterArrivalSampler = _exponential_inter_arrival,
    ) -> None:
        self.config = config
        self.observer = observer
        self.rng = random.Random(config.seed)
        self.sampler = sampler

        self._now: float = observer.arrival_time
        self.event_log: list[Event] = []
        self._served = False
        self._timed_out = False
        self._served_time: float | None = None
        self._wrong_way_stops = 0
        self._current_streak = 0
        self._max_streak = 0

    @property
    def done(self) -> bool:
        return self._served or self._timed_out

    def run(self) -> RunResult:
        max_time = self.observer.arrival_time + self.config.max_wait_seconds
        next_desired = self._now + self.sampler(
            self.rng, self.config.desired_direction_rate
        )
        next_other = self._now + self.sampler(
            self.rng, self.config.other_direction_rate
        )

        while not self.done:
            next_event_time = min(next_desired, next_other)
            if next_event_time >= max_time:
                self._now = max_time
                self._mark_timeout()
                break
            self._now = next_event_time

            if next_desired <= next_other:
                self._mark_served()
            else:
                self._record_wrong_way()
                next_other = self._now + self.sampler(
                    self.rng, self.config.other_direction_rate
                )

        return self._build_result()

    def _mark_served(self) -> None:
        self._served = True
        self._served_time = self._now
        self._current_streak = 0
        self.event_log.append(
            Event(
                timestamp=self._now,
                event_type="served",
                elevator_id=None,
                floor=None,
                direction=self.observer.desired_direction,
                is_stop=True,
            )
        )

    def _record_wrong_way(self) -> None:
        self._wrong_way_stops += 1
        self._current_streak += 1
        self._max_streak = max(self._max_streak, self._current_streak)
        opposite: Direction = "down" if self.observer.desired_direction == "up" else "up"
        self.event_log.append(
            Event(
                timestamp=self._now,
                event_type="stop",
                elevator_id=None,
                floor=None,
                direction=opposite,
                is_wrong_way=True,
                is_stop=True,
            )
        )

    def _mark_timeout(self) -> None:
        self._timed_out = True
        self.event_log.append(
            Event(
                timestamp=self._now,
                event_type="timeout",
                elevator_id=None,
                floor=None,
                direction="idle",
            )
        )

    def _actual_wait(self) -> float:
        if self._served and self._served_time is not None:
            return max(0.0, self._served_time - self.observer.arrival_time)
        return self.config.max_wait_seconds

    def _build_result(self) -> RunResult:
        actual_wait = self._actual_wait()
        perceived = perceived_wait_seconds(
            actual_wait_seconds=actual_wait,
            wrong_way_passes=0,
            wrong_way_stops=self._wrong_way_stops,
            max_streak=self._max_streak,
            coeffs=self.config.perceived_coeffs,
        )
        return RunResult(
            served=self._served,
            timed_out=self._timed_out,
            actual_wait_seconds=actual_wait,
            perceived_wait_seconds=perceived,
            wrong_way_passes=0,
            wrong_way_stops=self._wrong_way_stops,
            max_wrong_way_streak=self._max_streak,
            rage_score=rage_score(0, self._wrong_way_stops, self._max_streak),
            complaint_strength_score=complaint_strength_score(actual_wait, perceived),
            rigged_system_belief_score=rigged_belief_score(
                wrong_way_passes=0,
                wrong_way_stops=self._wrong_way_stops,
                max_streak=self._max_streak,
                timed_out=self._timed_out,
            ),
            event_log=self.event_log,
            arrival_snapshot=[],
            profile="Subway",
        )
