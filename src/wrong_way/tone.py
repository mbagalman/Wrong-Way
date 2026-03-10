"""Dryly funny copy helpers for the teaching UI."""

from __future__ import annotations

from .config import RunResult

TONE_PACK = [
    "Your wait was normal. Your emotions were not.",
    "Observed injustice: high. Statistical surprise: modest.",
    "You did not witness a conspiracy. You witnessed a boundary condition.",
    "The other elevator had momentum, not malice.",
    "The system was indifferent. Your annoyance was authentic.",
]


def complaint_generator(result: RunResult) -> str:
    severity = "minor"
    wrong_way_total = result.wrong_way_passes + result.wrong_way_stops
    if result.max_wrong_way_streak >= 3 or wrong_way_total >= 4:
        severity = "severe"
    elif wrong_way_total >= 2:
        severity = "moderate"

    return (
        f"Observed {wrong_way_total} useless elevator encounters before service. "
        f"Statistical injustice level: {severity}."
    )


def statistical_rebuttal(result: RunResult) -> str:
    if result.timed_out:
        return "That run timed out. Rare, but still explainable by queue position and flow imbalance."
    inflation = result.perceived_wait_seconds - result.actual_wait_seconds
    return (
        f"Actual wait: {result.actual_wait_seconds:.0f}s. "
        f"Perceived inflation: +{inflation:.0f}s. "
        "Sequence effects made an ordinary wait feel personal."
    )
