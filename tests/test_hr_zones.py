import pytest

from app.planner.hr_zones import compute_zones, estimate_max_hr, resolve_max_hr


@pytest.mark.parametrize(("age", "expected"), [(20, 194), (30, 187), (45, 176)])
def test_tanaka_estimate(age: int, expected: int) -> None:
    assert estimate_max_hr(age) == expected


def test_resolve_prefers_measured_max_hr() -> None:
    assert resolve_max_hr(max_hr=190, birth_year=1990, current_year=2026) == 190


def test_resolve_estimates_from_birth_year() -> None:
    assert resolve_max_hr(max_hr=None, birth_year=1996, current_year=2026) == 187


def test_resolve_unknown_without_data() -> None:
    assert resolve_max_hr(max_hr=None, birth_year=None, current_year=2026) is None


def test_percent_of_max_without_resting_hr() -> None:
    zones = compute_zones(max_hr=200)

    assert [(z.zone, z.min_bpm, z.max_bpm) for z in zones] == [
        (1, 100, 120),
        (2, 120, 140),
        (3, 140, 160),
        (4, 160, 180),
        (5, 180, 200),
    ]


def test_karvonen_with_resting_hr() -> None:
    # reserve = 200 - 60 = 140; zone 2 = 60 + 0.6*140 .. 60 + 0.7*140
    zone2 = compute_zones(max_hr=200, resting_hr=60)[1]

    assert (zone2.min_bpm, zone2.max_bpm) == (144, 158)


def test_ceiling_caps_all_zones() -> None:
    zones = compute_zones(max_hr=200, hr_ceiling=150)

    assert max(z.max_bpm for z in zones) == 150
    assert zones[4].min_bpm == 150  # zone 5 collapses to the ceiling
