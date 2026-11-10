"""Computed heart-rate zones (spec 02 §3.5, decision D2). Pure: no I/O, never stored."""

from dataclasses import dataclass

# (zone, low %, high %) — same split as Garmin's default %max-HR zones.
ZONE_BOUNDS: tuple[tuple[int, float, float], ...] = (
    (1, 0.50, 0.60),
    (2, 0.60, 0.70),
    (3, 0.70, 0.80),
    (4, 0.80, 0.90),
    (5, 0.90, 1.00),
)


@dataclass(frozen=True)
class HrZone:
    zone: int
    min_bpm: int
    max_bpm: int


def estimate_max_hr(age: int) -> int:
    """Tanaka formula: 208 − 0.7 × age."""
    return round(208 - 0.7 * age)


def resolve_max_hr(max_hr: int | None, birth_year: int | None, current_year: int) -> int | None:
    if max_hr is not None:
        return max_hr
    if birth_year is not None:
        return estimate_max_hr(current_year - birth_year)
    return None


def compute_zones(
    max_hr: int, resting_hr: int | None = None, hr_ceiling: int | None = None
) -> list[HrZone]:
    """Karvonen (HR reserve) when resting HR is known, else % of max. Ceiling caps every zone."""

    def bpm(pct: float) -> int:
        if resting_hr is not None:
            return round(resting_hr + pct * (max_hr - resting_hr))
        return round(pct * max_hr)

    zones = []
    for zone, lo, hi in ZONE_BOUNDS:
        low, high = bpm(lo), bpm(hi)
        if hr_ceiling is not None:
            low, high = min(low, hr_ceiling), min(high, hr_ceiling)
        zones.append(HrZone(zone=zone, min_bpm=low, max_bpm=high))
    return zones
