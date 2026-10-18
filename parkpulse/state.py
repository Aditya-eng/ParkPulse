"""In-memory live state for the prototype: occupancy, violations, forecasts, analytics.

A pilot would back this with PostgreSQL/TimescaleDB fed by edge devices. The prototype
drives it with the simulator so the dashboard and bot behave as they would live.
"""

from __future__ import annotations

import random
import threading
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta

from .forecasting import ZoneForecaster, fit_all
from .geo import directions_link, haversine_km, walking_minutes
from .simulator import Snapshot, Violation, history, occupancy_at, simulate_violations
from .zones import NO_PARKING_SEGMENTS, ZONES, ZONES_BY_ID

# Share of occupied bay-hours assumed to go unbilled today (demo assumption, not measured).
UNBILLED_SHARE_ASSUMPTION = 0.18


class LiveState:
    def __init__(self, history_days: int = 56, seed: int = 11, now: datetime | None = None):
        self._lock = threading.Lock()
        self.rng = random.Random(seed)
        self.clock = now or datetime.now()
        self.history: list[Snapshot] = history(days=history_days, end=self.clock, seed=seed)
        self.forecasters: dict[str, ZoneForecaster] = fit_all(self.history)
        self.live: dict[str, Snapshot] = {}
        self.violations: list[Violation] = []
        self.violation_log: list[Violation] = self._backfill_violations(days=14)
        self.tick(self.clock)

    # ------------------------------------------------------------------ simulation
    def _backfill_violations(self, days: int) -> list[Violation]:
        log: list[Violation] = []
        t = self.clock - timedelta(days=days)
        while t < self.clock:
            if 8 <= t.hour <= 21:
                log.extend(simulate_violations(t, self.rng, count=self.rng.randint(0, 5)))
            t += timedelta(hours=1)
        return log

    def tick(self, now: datetime | None = None) -> None:
        now = now or datetime.now()
        with self._lock:
            self.clock = now
            for z in ZONES:
                self.live[z.id] = occupancy_at(z, now, self.rng)
            fresh = simulate_violations(now, self.rng)
            for v in self.violations:
                age = (now - v.detected_at).total_seconds() / 60
                if v.status == "open" and age > 10:
                    v.status = "dispatched"
                if age > 45:
                    v.status = "cleared"
            self.violations = [v for v in self.violations if v.status != "cleared"] + fresh
            self.violations = sorted(self.violations, key=lambda v: v.detected_at, reverse=True)[:25]
            self.violation_log.extend(fresh)

    # ------------------------------------------------------------------ queries
    def zone_view(self, zone_id: str) -> dict:
        z = ZONES_BY_ID[zone_id]
        s = self.live[zone_id]
        fc = self.forecasters[zone_id].predict(self.clock, hours=3)
        trend = None
        if fc:
            delta = fc[-1].occupancy - s.occupancy
            trend = "filling" if delta > 0.05 else "emptying" if delta < -0.05 else "steady"
        return {
            "id": z.id, "name": z.name, "kind": z.kind, "lat": z.lat, "lon": z.lon,
            "capacity": z.capacity, "occupied": s.occupied, "free": s.free,
            "occupancy": round(s.occupancy, 3), "hourly_fee": z.hourly_fee,
            "status": "full" if s.free <= 0.05 * z.capacity else "busy" if s.occupancy > 0.75 else "available",
            "trend_3h": trend, "directions": directions_link(z.lat, z.lon),
            "updated_at": self.clock.isoformat(timespec="seconds"),
        }

    def zones(self) -> list[dict]:
        return [self.zone_view(z.id) for z in ZONES]

    def nearest(self, lat: float, lon: float, limit: int = 3, min_free: int = 1) -> list[dict]:
        rows = []
        for v in self.zones():
            km = haversine_km(lat, lon, v["lat"], v["lon"])
            if v["free"] >= min_free:
                rows.append({**v, "distance_km": round(km, 2), "walk_min": walking_minutes(km)})
        return sorted(rows, key=lambda r: (r["distance_km"] - min(r["free"], 50) / 500))[:limit]

    def forecast(self, zone_id: str, hours: int = 6) -> dict:
        z = ZONES_BY_ID[zone_id]
        f = self.forecasters[zone_id]
        pts = f.predict(self.clock, hours=hours)
        return {
            "zone_id": zone_id,
            "points": [{"at": p.when.isoformat(timespec="minutes"), "occupancy": round(p.occupancy, 3),
                        "free": p.free_slots(z.capacity)} for p in pts],
            "model_mae": None if f.mae is None else round(f.mae, 4),
            "baseline_mae": None if f.baseline_mae is None else round(f.baseline_mae, 4),
        }

    def alerts(self) -> list[dict]:
        out = []
        for v in self.violations:
            d = asdict(v)
            d["detected_at"] = v.detected_at.isoformat(timespec="minutes")
            out.append(d)
        return out

    def analytics(self) -> dict:
        by_zone_hour: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
        for s in self.history:
            by_zone_hour[s.zone_id][s.when.hour].append(s.occupancy)
        peak_hours = {}
        hourly_profile = {}
        for zid, hours in by_zone_hour.items():
            avg = {h: sum(v) / len(v) for h, v in hours.items()}
            hourly_profile[zid] = [round(avg.get(h, 0), 3) for h in range(24)]
            peak_hours[zid] = sorted(avg, key=avg.get, reverse=True)[:3]

        seg_names = {s["id"]: s["name"] for s in NO_PARKING_SEGMENTS}
        hotspot_counts = Counter(v.segment_id for v in self.violation_log)
        hotspots = [{"segment_id": k, "name": seg_names[k], "violations_14d": n}
                    for k, n in hotspot_counts.most_common()]
        by_hour = Counter(v.detected_at.hour for v in self.violation_log)

        last_week = [s for s in self.history if s.when >= self.clock - timedelta(days=7)]
        leakage = 0.0
        for s in last_week:
            leakage += s.occupied * ZONES_BY_ID[s.zone_id].hourly_fee * UNBILLED_SHARE_ASSUMPTION
        model_quality = {zid: {"mae": round(f.mae or 0, 4), "baseline_mae": round(f.baseline_mae or 0, 4)}
                         for zid, f in self.forecasters.items()}
        return {
            "peak_hours": peak_hours,
            "hourly_profile": hourly_profile,
            "hotspots": hotspots,
            "violations_by_hour": [by_hour.get(h, 0) for h in range(24)],
            "estimated_weekly_revenue_leakage_inr": round(leakage),
            "leakage_assumption": f"{int(UNBILLED_SHARE_ASSUMPTION * 100)}% of occupied bay-hours unbilled (demo assumption)",
            "forecast_quality": model_quality,
            "data_note": "Simulated data for prototype demonstration. Not measured in Jammu.",
        }

    def kpis(self) -> dict:
        zs = self.zones()
        cap = sum(z["capacity"] for z in zs)
        occ = sum(z["occupied"] for z in zs)
        return {
            "total_capacity": cap, "occupied": occ, "free": cap - occ,
            "occupancy": round(occ / cap, 3), "open_alerts": sum(v.status == "open" for v in self.violations),
            "zones_full": sum(z["status"] == "full" for z in zs), "updated_at": self.clock.isoformat(timespec="seconds"),
        }
