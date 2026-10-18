"""Per-slot occupancy from a single camera frame.

Two backends:

* ``classical`` (default): edge density, texture and colour statistics inside each
  slot polygon, optionally compared against an empty-lot reference frame. Runs on a
  Raspberry Pi-class device with only OpenCV and NumPy.
* ``yolo``: if the ``ultralytics`` package and a model file are available, vehicles are
  detected and assigned to slots by overlap. Better under shadows and odd angles.

Slot polygons are drawn once per camera during installation (see ``slots/``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


@dataclass
class SlotState:
    id: str
    occupied: bool
    score: float


def load_slots(path: str | Path) -> list[dict]:
    return json.loads(Path(path).read_text())["slots"]


def _mask(shape, points, erode: int = 0) -> np.ndarray:
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(m, [np.array(points, np.int32)], 255)
    if erode:
        m = cv2.erode(m, np.ones((erode, erode), np.uint8))
    return m


class SlotDetector:
    def __init__(self, slots: list[dict], backend: str = "classical", threshold: float = 0.25,
                 empty_reference: np.ndarray | None = None, yolo_model: str | None = None):
        self.slots = slots
        self.backend = backend
        self.threshold = threshold
        self.empty_reference = empty_reference
        self._yolo = None
        if backend == "yolo":
            try:
                from ultralytics import YOLO  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError("Install 'ultralytics' to use the yolo backend") from exc
            self._yolo = YOLO(yolo_model or "yolo11n.pt")

    # ------------------------------------------------------------------ classical
    def _classical_score(self, frame: np.ndarray, gray: np.ndarray, edges: np.ndarray, points) -> float:
        m = _mask(frame.shape, points, erode=9)
        area = max(1, int(np.count_nonzero(m)))
        edge_density = np.count_nonzero(edges & m) / area
        texture = float(np.std(gray[m > 0])) / 64.0
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        sat = float(np.mean(hsv[..., 1][m > 0])) / 255.0
        score = 0.55 * min(1.0, edge_density * 12) + 0.35 * min(1.0, texture) + 0.10 * min(1.0, sat * 3)
        if self.empty_reference is not None:
            ref = cv2.cvtColor(self.empty_reference, cv2.COLOR_BGR2GRAY)
            diff = float(np.mean(cv2.absdiff(gray, ref)[m > 0])) / 40.0
            score = 0.5 * score + 0.5 * min(1.0, diff)
        return float(score)

    # ------------------------------------------------------------------ yolo
    def _yolo_states(self, frame: np.ndarray) -> list[SlotState]:  # pragma: no cover - optional
        res = self._yolo(frame, verbose=False)[0]
        boxes = [b.xyxy[0].tolist() for b in res.boxes if int(b.cls) in VEHICLE_CLASSES and float(b.conf) > 0.35]
        states = []
        for slot in self.slots:
            m = _mask(frame.shape, slot["points"])
            area = max(1, int(np.count_nonzero(m)))
            best = 0.0
            for x1, y1, x2, y2 in boxes:
                bm = np.zeros_like(m)
                cv2.rectangle(bm, (int(x1), int(y1)), (int(x2), int(y2)), 255, -1)
                best = max(best, np.count_nonzero(bm & m) / area)
            states.append(SlotState(slot["id"], best >= 0.4, best))
        return states

    # ------------------------------------------------------------------ public
    def detect(self, frame: np.ndarray) -> list[SlotState]:
        if self.backend == "yolo":
            return self._yolo_states(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120)
        out = []
        for slot in self.slots:
            s = self._classical_score(frame, gray, edges, slot["points"])
            out.append(SlotState(slot["id"], s >= self.threshold, s))
        return out

    @staticmethod
    def summarize(states: list[SlotState]) -> dict:
        occ = sum(s.occupied for s in states)
        return {"total": len(states), "occupied": occ, "free": len(states) - occ}

    def annotate(self, frame: np.ndarray, states: list[SlotState], title: str = "") -> np.ndarray:
        out = frame.copy()
        overlay = frame.copy()
        by_id = {s.id: s for s in states}
        for slot in self.slots:
            st = by_id[slot["id"]]
            colour = (60, 60, 230) if st.occupied else (70, 200, 90)
            pts = np.array(slot["points"], np.int32)
            cv2.fillPoly(overlay, [pts], colour)
            cv2.polylines(out, [pts], True, colour, 3)
            x, y = pts[0]
            cv2.putText(out, slot["id"], (int(x) + 6, int(y) + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
        out = cv2.addWeighted(overlay, 0.28, out, 0.72, 0)
        summary = self.summarize(states)
        banner = f"{title}  Free: {summary['free']}/{summary['total']}" if title else f"Free: {summary['free']}/{summary['total']}"
        cv2.rectangle(out, (0, 0), (out.shape[1], 40), (25, 25, 25), -1)
        cv2.putText(out, banner, (14, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
        return out
