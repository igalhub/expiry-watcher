import pytest
from checker.severity import compute_severity


@pytest.mark.parametrize("days_remaining,expected", [
    (-1,  "expired"),
    (0,   "expired"),
    (1,   "critical"),
    (7,   "critical"),
    (8,   "warning"),
    (30,  "warning"),
    (31,  "healthy"),
    (365, "healthy"),
], ids=[
    "minus_one",
    "zero",
    "one",
    "seven",
    "eight",
    "thirty",
    "thirty_one",
    "three_sixty_five",
])
def test_compute_severity(days_remaining, expected):
    assert compute_severity(days_remaining) == expected
