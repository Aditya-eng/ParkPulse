"""Demand signals specific to Jammu: festivals, market days and pilgrim inflow.

All dates and indices here are illustrative inputs for the prototype. In a pilot they
would come from JMC's event calendar and Shri Mata Vaishno Devi Shrine Board footfall data.
"""

from __future__ import annotations

from datetime import date, datetime

# Approximate festival windows that raise market and transit demand (demo values).
FESTIVAL_WINDOWS: tuple[tuple[date, date, str], ...] = (
    (date(2026, 1, 12), date(2026, 1, 14), "Lohri"),
    (date(2026, 4, 13), date(2026, 4, 14), "Baisakhi"),
    (date(2026, 10, 11), date(2026, 10, 20), "Navratri"),
    (date(2026, 11, 5), date(2026, 11, 9), "Diwali week"),
    (date(2026, 12, 24), date(2026, 12, 31), "Year-end holidays"),
    (date(2027, 1, 12), date(2027, 1, 14), "Lohri"),
)

# Relative pilgrim inflow by month (1.0 = average). Illustrative shape only:
# summer holidays, Navratri and winter holidays are typical peaks.
PILGRIM_INDEX_BY_MONTH: dict[int, float] = {
    1: 1.05, 2: 0.80, 3: 0.90, 4: 1.00, 5: 1.25, 6: 1.30,
    7: 0.95, 8: 0.85, 9: 0.90, 10: 1.20, 11: 0.95, 12: 1.15,
}


def festival_on(day: date) -> str | None:
    for start, end, name in FESTIVAL_WINDOWS:
        if start <= day <= end:
            return name
    return None


def pilgrim_index(when: datetime | date) -> float:
    return PILGRIM_INDEX_BY_MONTH[when.month]


def demand_features(when: datetime) -> dict[str, float]:
    """Calendar features used by both the simulator and the forecaster."""
    return {
        "hour": float(when.hour),
        "dow": float(when.weekday()),
        "is_weekend": float(when.weekday() >= 5),
        "is_festival": float(festival_on(when.date()) is not None),
        "pilgrim_index": pilgrim_index(when),
    }
