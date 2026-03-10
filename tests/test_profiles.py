import random

from wrong_way.elevator_mode import sample_request


def _is_down_trip(origin: int, destination: int) -> bool:
    return destination < origin


def _is_up_trip(origin: int, destination: int) -> bool:
    return destination > origin


def test_morning_rush_biases_downward() -> None:
    rng = random.Random(123)
    floors = 20
    requests = [sample_request(rng, "Morning Rush", floors) for _ in range(800)]
    down_share = sum(_is_down_trip(r.origin, r.destination) for r in requests) / len(requests)
    assert down_share > 0.55


def test_evening_return_biases_upward() -> None:
    rng = random.Random(321)
    floors = 20
    requests = [sample_request(rng, "Evening Return", floors) for _ in range(800)]
    up_share = sum(_is_up_trip(r.origin, r.destination) for r in requests) / len(requests)
    assert up_share > 0.55
