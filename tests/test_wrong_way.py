from wrong_way.elevator_mode import is_wrong_way_event


def test_wrong_way_detection() -> None:
    assert is_wrong_way_event("up", "down") is True
    assert is_wrong_way_event("down", "up") is True
    assert is_wrong_way_event("up", "up") is False
    assert is_wrong_way_event("down", "down") is False
