"""Metric helpers for perceived wait and player-facing scores."""

from __future__ import annotations

from .config import PerceivedCoefficients


def perceived_wait_seconds(
    actual_wait_seconds: float,
    wrong_way_passes: int,
    wrong_way_stops: int,
    max_streak: int,
    coeffs: PerceivedCoefficients,
) -> float:
    """Perceived wait formula used by the teaching simulation."""

    return (
        actual_wait_seconds
        + coeffs.a * wrong_way_passes
        + coeffs.b * wrong_way_stops
        + coeffs.c * (max_streak**2)
    )


def rage_score(
    wrong_way_passes: int,
    wrong_way_stops: int,
    max_streak: int,
) -> float:
    """Simple bounded rage score on a 0-100 scale."""

    raw = 8 * wrong_way_passes + 15 * wrong_way_stops + 6 * (max_streak**2)
    return min(100.0, float(raw))


def complaint_strength_score(
    actual_wait_seconds: float,
    perceived_wait: float,
) -> float:
    """How compelling the complaint feels to the user (0-100)."""

    if actual_wait_seconds <= 0:
        return 0.0
    inflation = perceived_wait / actual_wait_seconds
    return min(100.0, max(0.0, (inflation - 1.0) * 60.0))


def rigged_belief_score(
    wrong_way_passes: int,
    wrong_way_stops: int,
    max_streak: int,
    timed_out: bool,
) -> float:
    """Conspiracy-style belief score for gamified teaching."""

    score = 10 + wrong_way_passes * 10 + wrong_way_stops * 15 + max_streak * 8
    if timed_out:
        score += 20
    return float(max(0, min(100, score)))


def long_gap_hit(actual_wait_seconds: float, p90_wait: float) -> bool:
    """Flag if the wait appears to have landed in a long interval."""

    return actual_wait_seconds >= p90_wait
