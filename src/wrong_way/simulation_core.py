"""Core event queue and simulation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
from typing import Callable


Action = Callable[[], None]


@dataclass(order=True)
class ScheduledEvent:
    """Event scheduled to run at a specific simulation time."""

    timestamp: float
    priority: int
    action: Action = field(compare=False)


class SimulationClock:
    """Small event queue clock used by scenario modules."""

    def __init__(self) -> None:
        self._queue: list[ScheduledEvent] = []
        self.now: float = 0.0
        self._counter = 0

    def schedule(self, delay_seconds: float, action: Action) -> None:
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be >= 0")
        self._counter += 1
        heapq.heappush(
            self._queue,
            ScheduledEvent(self.now + delay_seconds, self._counter, action),
        )

    def has_events(self) -> bool:
        return bool(self._queue)

    def pop_next(self) -> ScheduledEvent:
        event = heapq.heappop(self._queue)
        self.now = event.timestamp
        return event

    def step(self) -> bool:
        if not self._queue:
            return False
        event = self.pop_next()
        event.action()
        return True

    def run_until(self, stop_condition: Callable[[], bool]) -> None:
        while self._queue and not stop_condition():
            self.step()
