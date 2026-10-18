"""Illegal-parking detection by dwell time inside a no-parking polygon.

A simple centroid tracker follows stationary vehicles across frames. When a vehicle
stays inside a no-parking zone longer than the allowed limit, one violation is raised.
Only the anonymised snapshot and location are sent onward; plates are read only when
the traffic police open an enforcement case.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Track:
    id: int
    cx: float
    cy: float
    first_seen: float
    last_seen: float
    flagged: bool = False


@dataclass
class DwellEvent:
    track_id: int
    zone_id: str
    dwell_seconds: float
    position: tuple[float, float]


@dataclass
class DwellTracker:
    zone_id: str
    polygon: list[list[int]]
    limit_seconds: float = 300.0
    match_radius: float = 40.0
    forget_after: float = 60.0
    tracks: dict[int, Track] = field(default_factory=dict)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    def _inside(self, cx: float, cy: float) -> bool:
        return cv2.pointPolygonTest(np.array(self.polygon, np.int32), (float(cx), float(cy)), False) >= 0

    def update(self, centroids: list[tuple[float, float]], t: float) -> list[DwellEvent]:
        events: list[DwellEvent] = []
        unmatched = set(self.tracks)
        for cx, cy in centroids:
            if not self._inside(cx, cy):
                continue
            best, best_d = None, self.match_radius
            for tid in unmatched:
                tr = self.tracks[tid]
                d = math.hypot(tr.cx - cx, tr.cy - cy)
                if d < best_d:
                    best, best_d = tid, d
            if best is None:
                tid = next(self._ids)
                self.tracks[tid] = Track(tid, cx, cy, t, t)
            else:
                unmatched.discard(best)
                tr = self.tracks[best]
                tr.cx, tr.cy, tr.last_seen = cx, cy, t
                dwell = t - tr.first_seen
                if not tr.flagged and dwell >= self.limit_seconds:
                    tr.flagged = True
                    events.append(DwellEvent(tr.id, self.zone_id, dwell, (cx, cy)))
        for tid in list(self.tracks):
            if t - self.tracks[tid].last_seen > self.forget_after:
                del self.tracks[tid]
        return events
