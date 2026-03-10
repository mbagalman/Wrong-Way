"""Elevator mode simulation for the Wrong-Way MVP."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Literal

from .config import Direction, Event, ObserverConfig, RunResult, SimulationConfig
from .metrics import (
    complaint_strength_score,
    perceived_wait_seconds,
    rage_score,
    rigged_belief_score,
)
from .simulation_core import SimulationClock


DemandProfile = Literal[
    "Morning Rush",
    "Evening Return",
    "Random Midday",
    "Penthouse Cruelty",
]


@dataclass
class RideRequest:
    origin: int
    destination: int


@dataclass
class ElevatorState:
    elevator_id: int
    current_floor: int
    direction: Direction = "idle"
    pending_stops: set[int] = field(default_factory=set)
    travel_progress: float = 0.0
    door_timer: float = 0.0


def desired_direction(start_floor: int, destination_floor: int) -> Direction:
    return "up" if destination_floor > start_floor else "down"


def is_wrong_way_event(user_direction: Direction, car_direction: Direction) -> bool:
    """Returns true when the car is clearly traveling opposite the user's goal."""

    if user_direction not in ("up", "down"):
        return False
    if car_direction not in ("up", "down"):
        return False
    return user_direction != car_direction


def profile_request_probability(profile: DemandProfile) -> float:
    return {
        "Morning Rush": 0.5,
        "Evening Return": 0.34,
        "Random Midday": 0.18,
        "Penthouse Cruelty": 0.42,
    }[profile]


def sample_request(
    rng: random.Random,
    profile: DemandProfile,
    floors: int,
) -> RideRequest:
    """Sample one request using a profile-specific directional bias."""

    top_band_start = max(1, math.floor(floors * 0.65))

    if profile == "Morning Rush":
        if rng.random() < 0.9:
            if rng.random() < 0.75:
                origin = floors - 1
            else:
                origin = rng.randint(top_band_start, floors - 1)
            destination = 0
        else:
            origin = rng.randint(0, floors - 1)
            destination = rng.randint(0, floors - 1)
    elif profile == "Evening Return":
        if rng.random() < 0.72:
            origin = 0
            destination = rng.randint(top_band_start, floors - 1)
        else:
            origin = rng.randint(0, floors - 1)
            destination = rng.randint(0, floors - 1)
    elif profile == "Penthouse Cruelty":
        if rng.random() < 0.8:
            origin = rng.randint(max(top_band_start, floors - 3), floors - 1)
            destination = rng.randint(0, max(0, top_band_start - 1))
        else:
            origin = rng.randint(0, floors - 1)
            destination = rng.randint(0, floors - 1)
    else:  # Random Midday
        origin = rng.randint(0, floors - 1)
        destination = rng.randint(0, floors - 1)

    while destination == origin:
        destination = rng.randint(0, floors - 1)

    return RideRequest(origin=origin, destination=destination)


class ElevatorSimulation:
    """Tick-based simulation using an event queue clock."""

    def __init__(
        self,
        config: SimulationConfig,
        observer: ObserverConfig,
        profile: DemandProfile = "Morning Rush",
    ) -> None:
        self.config = config
        self.observer = observer
        self.profile = profile
        self.rng = random.Random(config.seed)
        self.clock = SimulationClock()

        if observer.start_floor < 0 or observer.start_floor >= config.floors:
            raise ValueError("observer start_floor out of bounds")
        if observer.destination_floor < 0 or observer.destination_floor >= config.floors:
            raise ValueError("observer destination_floor out of bounds")

        self.elevators = self._initial_elevators(config)
        self.event_log: list[Event] = []
        self._served = False
        self._timed_out = False
        self._served_time: float | None = None
        self._wrong_way_passes = 0
        self._wrong_way_stops = 0
        self._current_streak = 0
        self._max_streak = 0

        self.arrival_snapshot = [self._snapshot_elevator(e) for e in self.elevators]
        self.clock.schedule(max(0.0, observer.arrival_time), self._tick)

    @property
    def done(self) -> bool:
        return self._served or self._timed_out

    @property
    def current_wait_seconds(self) -> float:
        return max(0.0, self.clock.now - self.observer.arrival_time)

    @property
    def wrong_way_passes(self) -> int:
        return self._wrong_way_passes

    @property
    def wrong_way_stops(self) -> int:
        return self._wrong_way_stops

    @property
    def max_wrong_way_streak(self) -> int:
        return self._max_streak

    def step(self) -> bool:
        """Advance one scheduled event. Returns true when an event was processed."""

        return self.clock.step()

    def run(self) -> RunResult:
        self.clock.run_until(lambda: self.done)
        if not self.done:
            self._mark_timeout()
        return self._build_result()

    def _initial_elevators(self, config: SimulationConfig) -> list[ElevatorState]:
        elevators: list[ElevatorState] = []
        for idx in range(config.elevators):
            if config.elevators == 1:
                floor = config.floors // 2
            else:
                floor = round((config.floors - 1) * idx / (config.elevators - 1))
            direction: Direction = "up" if idx % 2 == 0 else "down"
            elevators.append(
                ElevatorState(
                    elevator_id=idx,
                    current_floor=floor,
                    direction=direction,
                )
            )
        return elevators

    def _tick(self) -> None:
        if self.done:
            return

        elapsed = self.current_wait_seconds
        if elapsed >= self.config.max_wait_seconds:
            self._mark_timeout()
            return

        self.event_log.append(
            Event(
                timestamp=self.clock.now,
                event_type="tick",
                elevator_id=None,
                floor=self.observer.start_floor,
                direction="idle",
                metadata={"elapsed": elapsed},
            )
        )

        self._generate_demand_if_needed()

        for elevator in self.elevators:
            self._process_elevator(elevator)
            if self.done:
                break

        if not self.done:
            self.clock.schedule(self.config.tick_seconds, self._tick)

    def _generate_demand_if_needed(self) -> None:
        req_rate = profile_request_probability(self.profile)
        probability = req_rate * self.config.tick_seconds
        if self.rng.random() >= min(1.0, probability):
            return

        request = sample_request(self.rng, self.profile, self.config.floors)
        elevator = min(
            self.elevators,
            key=lambda e: (
                abs(e.current_floor - request.origin)
                + (2 if e.direction != "idle" else 0)
                + len(e.pending_stops)
            ),
        )

        elevator.pending_stops.add(request.origin)
        elevator.pending_stops.add(request.destination)

        if elevator.direction == "idle":
            elevator.direction = "up" if request.origin > elevator.current_floor else "down"

        self.event_log.append(
            Event(
                timestamp=self.clock.now,
                event_type="request_assigned",
                elevator_id=elevator.elevator_id,
                floor=request.origin,
                direction=elevator.direction,
                metadata={
                    "origin": request.origin,
                    "destination": request.destination,
                },
            )
        )

    def _process_elevator(self, elevator: ElevatorState) -> None:
        if elevator.door_timer > 0:
            elevator.door_timer = max(0.0, elevator.door_timer - self.config.tick_seconds)
            return

        self._apply_scan_direction(elevator)

        if elevator.direction == "idle":
            return

        elevator.travel_progress += self.config.tick_seconds
        while elevator.travel_progress >= self.config.travel_time_per_floor:
            elevator.travel_progress -= self.config.travel_time_per_floor
            self._advance_one_floor(elevator)
            if self.done or elevator.door_timer > 0:
                break

    def _apply_scan_direction(self, elevator: ElevatorState) -> None:
        top = self.config.floors - 1
        previous = elevator.direction

        has_above = any(stop > elevator.current_floor for stop in elevator.pending_stops)
        has_below = any(stop < elevator.current_floor for stop in elevator.pending_stops)

        if elevator.direction == "up":
            if elevator.current_floor >= top:
                elevator.direction = "down"
            elif not has_above and has_below:
                elevator.direction = "down"
            elif not has_above and not has_below and not elevator.pending_stops:
                elevator.direction = "idle"
        elif elevator.direction == "down":
            if elevator.current_floor <= 0:
                elevator.direction = "up"
            elif not has_below and has_above:
                elevator.direction = "up"
            elif not has_above and not has_below and not elevator.pending_stops:
                elevator.direction = "idle"
        else:
            if has_above:
                elevator.direction = "up"
            elif has_below:
                elevator.direction = "down"

        if elevator.direction != previous:
            self.event_log.append(
                Event(
                    timestamp=self.clock.now,
                    event_type="direction_change",
                    elevator_id=elevator.elevator_id,
                    floor=elevator.current_floor,
                    direction=elevator.direction,
                    metadata={"from": previous, "to": elevator.direction},
                )
            )

    def _advance_one_floor(self, elevator: ElevatorState) -> None:
        top = self.config.floors - 1

        if elevator.direction == "up" and elevator.current_floor >= top:
            elevator.direction = "down"
        elif elevator.direction == "down" and elevator.current_floor <= 0:
            elevator.direction = "up"

        if elevator.direction == "up":
            elevator.current_floor += 1
        elif elevator.direction == "down":
            elevator.current_floor -= 1

        elevator.current_floor = max(0, min(top, elevator.current_floor))

        should_stop = elevator.current_floor in elevator.pending_stops

        if should_stop:
            elevator.pending_stops.discard(elevator.current_floor)
            elevator.door_timer = self.config.door_dwell_seconds
            self._record_observer_interaction(elevator, is_stop=True)
            self.event_log.append(
                Event(
                    timestamp=self.clock.now,
                    event_type="stop",
                    elevator_id=elevator.elevator_id,
                    floor=elevator.current_floor,
                    direction=elevator.direction,
                    is_wrong_way=is_wrong_way_event(
                        self.observer.desired_direction,
                        elevator.direction,
                    )
                    and elevator.current_floor == self.observer.start_floor,
                    is_stop=True,
                )
            )
        else:
            self._record_observer_interaction(elevator, is_stop=False)
            if elevator.current_floor == self.observer.start_floor:
                self.event_log.append(
                    Event(
                        timestamp=self.clock.now,
                        event_type="pass_by",
                        elevator_id=elevator.elevator_id,
                        floor=elevator.current_floor,
                        direction=elevator.direction,
                        is_wrong_way=is_wrong_way_event(
                            self.observer.desired_direction,
                            elevator.direction,
                        ),
                        is_stop=False,
                    )
                )

    def _record_observer_interaction(self, elevator: ElevatorState, is_stop: bool) -> None:
        if elevator.current_floor != self.observer.start_floor or self.done:
            return

        wrong_way = is_wrong_way_event(self.observer.desired_direction, elevator.direction)

        if wrong_way and is_stop:
            self._wrong_way_stops += 1
            self._current_streak += 1
        elif wrong_way:
            self._wrong_way_passes += 1
            self._current_streak += 1
        else:
            self._current_streak = 0

        self._max_streak = max(self._max_streak, self._current_streak)

        can_serve = (
            is_stop
            and not wrong_way
            and elevator.direction == self.observer.desired_direction
        )

        if can_serve:
            self._served = True
            self._served_time = self.clock.now
            self.event_log.append(
                Event(
                    timestamp=self.clock.now,
                    event_type="served",
                    elevator_id=elevator.elevator_id,
                    floor=elevator.current_floor,
                    direction=elevator.direction,
                    is_wrong_way=False,
                    is_stop=True,
                )
            )

    def _mark_timeout(self) -> None:
        self._timed_out = True
        self.event_log.append(
            Event(
                timestamp=self.clock.now,
                event_type="timeout",
                elevator_id=None,
                floor=self.observer.start_floor,
                direction="idle",
                is_wrong_way=False,
                is_stop=False,
            )
        )

    def _build_result(self) -> RunResult:
        if self._served and self._served_time is not None:
            actual_wait = max(0.0, self._served_time - self.observer.arrival_time)
        else:
            actual_wait = self.config.max_wait_seconds

        perceived_wait = perceived_wait_seconds(
            actual_wait_seconds=actual_wait,
            wrong_way_passes=self._wrong_way_passes,
            wrong_way_stops=self._wrong_way_stops,
            max_streak=self._max_streak,
            coeffs=self.config.perceived_coeffs,
        )

        return RunResult(
            served=self._served,
            timed_out=self._timed_out,
            actual_wait_seconds=actual_wait,
            perceived_wait_seconds=perceived_wait,
            wrong_way_passes=self._wrong_way_passes,
            wrong_way_stops=self._wrong_way_stops,
            max_wrong_way_streak=self._max_streak,
            rage_score=rage_score(
                wrong_way_passes=self._wrong_way_passes,
                wrong_way_stops=self._wrong_way_stops,
                max_streak=self._max_streak,
            ),
            complaint_strength_score=complaint_strength_score(actual_wait, perceived_wait),
            rigged_system_belief_score=rigged_belief_score(
                wrong_way_passes=self._wrong_way_passes,
                wrong_way_stops=self._wrong_way_stops,
                max_streak=self._max_streak,
                timed_out=self._timed_out,
            ),
            event_log=self.event_log,
            arrival_snapshot=self.arrival_snapshot,
            profile=self.profile,
        )

    def _snapshot_elevator(self, elevator: ElevatorState) -> dict[str, int | str]:
        return {
            "elevator_id": elevator.elevator_id,
            "floor": elevator.current_floor,
            "direction": elevator.direction,
            "pending": len(elevator.pending_stops),
        }

    def current_state(self) -> dict[str, object]:
        return {
            "time": self.clock.now,
            "elevators": [self._snapshot_elevator(e) for e in self.elevators],
            "observer_floor": self.observer.start_floor,
            "desired_direction": self.observer.desired_direction,
            "wrong_way_passes": self._wrong_way_passes,
            "wrong_way_stops": self._wrong_way_stops,
            "max_streak": self._max_streak,
            "current_streak": self._current_streak,
        }
