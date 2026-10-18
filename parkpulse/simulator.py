"""Synthetic occupancy and violation data for demos and tests.

The prototype has no access to live Jammu camera feeds, so this module produces
realistic-looking hourly occupancy using demand shapes per zone type plus Jammu
calendar signals. Everything it outputs is simulated and labelled as such in the UI.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from .demand_calendar import demand_features
from .zones import NO_PARKING_SEGMENTS, ZONES, Zone


def _bump(hour: float, centre: float, width: float) -> float:
    return math.exp(-((hour - centre) ** 2) / (2 * width**2))


def base_occupancy(zone: Zone, when: datetime) -> float:
    """Expected occupancy fraction (0..1) before noise."""
    f = demand_features(when)
    h = when.hour + when.minute / 60
    if zone.near_transit:
        shape = 0.25 + 0.45 * _bump(h, 8.5, 1.8) + 0.50 * _bump(h, 18.5, 2.2) + 0.15 * _bump(h, 13, 3)
        shape *= 0.85 + 0.25 * (f["pilgrim_index"] - 0.8)
    else:
        shape = 0.15 + 0.55 * _bump(h, 12.5, 2.0) + 0.75 * _bump(h, 18.5, 1.7)
        if f["is_weekend"]:
            shape *= 1.12
    if f["is_festival"]:
        shape *= 1.22
    if h < 6 or h > 23:
        shape *= 0.35
    return max(0.02, min(1.0, shape))


@dataclass
class Snapshot:
    zone_id: str
    when: datetime
    occupied: int
    capacity: int

    @property
    def free(self) -> int:
        return max(0, self.capacity - self.occupied)

    @property
    def occupancy(self) -> float:
        return self.occupied / self.capacity


def occupancy_at(zone: Zone, when: datetime, rng: random.Random | None = None) -> Snapshot:
    rng = rng or random.Random(hash((zone.id, when.strftime("%Y%m%d%H%M"))) & 0xFFFFFFFF)
    frac = base_occupancy(zone, when) + rng.gauss(0, 0.05)
    frac = max(0.0, min(1.0, frac))
    return Snapshot(zone.id, when, round(frac * zone.capacity), zone.capacity)


def history(days: int = 56, end: datetime | None = None, seed: int = 7) -> list[Snapshot]:
    """Hourly occupancy history for every zone, oldest first."""
    end = (end or datetime.now()).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    rng = random.Random(seed)
    out: list[Snapshot] = []
    t = start
    while t < end:
        for zone in ZONES:
            out.append(occupancy_at(zone, t, rng))
        t += timedelta(hours=1)
    return out


@dataclass
class Violation:
    id: str
    segment_id: str
    segment_name: str
    lat: float
    lon: float
    detected_at: datetime
    dwell_minutes: int
    vehicle_class: str
    status: str = "open"  # open -> dispatched -> cleared


def simulate_violations(now: datetime, rng: random.Random, count: int | None = None) -> list[Violation]:
    """Violations in no-parking segments, more frequent at market peaks."""
    h = now.hour + now.minute / 60
    rate = 1.5 + 4.0 * _bump(h, 12.5, 2) + 5.0 * _bump(h, 18.5, 1.8)
    n = count if count is not None else min(8, max(0, int(rng.gauss(rate, 1.2))))
    out = []
    for i in range(n):
        seg = rng.choice(NO_PARKING_SEGMENTS)
        out.append(
            Violation(
                id=f"V{now.strftime('%H%M')}{i:02d}{rng.randint(100, 999)}",
                segment_id=seg["id"],
                segment_name=seg["name"],
                lat=seg["lat"] + rng.uniform(-0.0004, 0.0004),
                lon=seg["lon"] + rng.uniform(-0.0004, 0.0004),
                detected_at=now - timedelta(minutes=rng.randint(0, 40)),
                dwell_minutes=rng.randint(6, 45),
                vehicle_class=rng.choice(["car", "car", "car", "suv", "auto-rickshaw", "two-wheeler", "goods carrier"]),
            )
        )
    return sorted(out, key=lambda v: v.detected_at, reverse=True)
