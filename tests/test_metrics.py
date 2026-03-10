from wrong_way.config import PerceivedCoefficients
from wrong_way.metrics import perceived_wait_seconds


def test_perceived_wait_formula_matches_spec() -> None:
    coeffs = PerceivedCoefficients(a=8, b=18, c=6)
    result = perceived_wait_seconds(
        actual_wait_seconds=73,
        wrong_way_passes=2,
        wrong_way_stops=1,
        max_streak=3,
        coeffs=coeffs,
    )
    assert result == 73 + 8 * 2 + 18 * 1 + 6 * (3**2)
