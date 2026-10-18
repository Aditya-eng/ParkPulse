"""Short-term occupancy forecasting per zone.

One gradient-boosted model per zone uses calendar signals (hour, weekday, festival,
pilgrim index) plus same-hour-yesterday and same-hour-last-week occupancy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from .demand_calendar import demand_features
from .simulator import Snapshot

FEATURES = ("hour", "dow", "is_weekend", "is_festival", "pilgrim_index", "lag_24", "lag_168")


@dataclass
class Forecast:
    zone_id: str
    when: datetime
    occupancy: float  # predicted fraction 0..1

    def free_slots(self, capacity: int) -> int:
        return max(0, round(capacity * (1 - self.occupancy)))


def _row(when: datetime, series: dict[datetime, float]) -> list[float] | None:
    lag24 = series.get(when - timedelta(hours=24))
    lag168 = series.get(when - timedelta(hours=168))
    if lag24 is None or lag168 is None:
        return None
    f = demand_features(when)
    return [f["hour"], f["dow"], f["is_weekend"], f["is_festival"], f["pilgrim_index"], lag24, lag168]


class ZoneForecaster:
    def __init__(self, zone_id: str):
        self.zone_id = zone_id
        self.model = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.08, random_state=0)
        self.series: dict[datetime, float] = {}
        self.mae: float | None = None
        self.baseline_mae: float | None = None

    def fit(self, snapshots: list[Snapshot], holdout_days: int = 7) -> "ZoneForecaster":
        self.series = {s.when: s.occupancy for s in snapshots if s.zone_id == self.zone_id}
        times = sorted(self.series)
        if not times:
            raise ValueError(f"no history for zone {self.zone_id}")
        cutoff = times[-1] - timedelta(days=holdout_days)
        X_tr, y_tr, X_te, y_te, base = [], [], [], [], []
        for t in times:
            row = _row(t, self.series)
            if row is None:
                continue
            (X_tr if t <= cutoff else X_te).append(row)
            (y_tr if t <= cutoff else y_te).append(self.series[t])
            if t > cutoff:
                base.append(row[-1])  # seasonal-naive: same hour last week
        self.model.fit(np.array(X_tr), np.array(y_tr))
        if X_te:
            pred = self.model.predict(np.array(X_te))
            self.mae = float(np.mean(np.abs(pred - np.array(y_te))))
            self.baseline_mae = float(np.mean(np.abs(np.array(base) - np.array(y_te))))
        # refit on everything for live use
        X_all = X_tr + X_te
        y_all = y_tr + y_te
        self.model.fit(np.array(X_all), np.array(y_all))
        return self

    def predict(self, start: datetime, hours: int = 6) -> list[Forecast]:
        start = start.replace(minute=0, second=0, microsecond=0)
        series = dict(self.series)
        out = []
        for i in range(1, hours + 1):
            t = start + timedelta(hours=i)
            row = _row(t, series)
            if row is None:
                break
            y = float(np.clip(self.model.predict(np.array([row]))[0], 0, 1))
            series[t] = y  # allows chaining beyond 24h if needed
            out.append(Forecast(self.zone_id, t, y))
        return out


def fit_all(snapshots: list[Snapshot]) -> dict[str, ZoneForecaster]:
    zone_ids = sorted({s.zone_id for s in snapshots})
    return {z: ZoneForecaster(z).fit(snapshots) for z in zone_ids}
