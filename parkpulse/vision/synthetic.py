"""Render a synthetic top-down parking lot frame with known ground truth.

Used for demos and tests because the prototype has no access to Jammu CCTV.
Real deployments feed camera frames into the same SlotDetector.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import cv2
import numpy as np

CAR_COLOURS = [
    (235, 235, 235), (40, 40, 40), (180, 180, 185), (30, 30, 150), (150, 40, 30),
    (30, 110, 200), (60, 60, 60), (200, 200, 120), (90, 130, 60), (20, 20, 200),
]


@dataclass
class SyntheticLot:
    image: np.ndarray
    slots: list[dict]  # [{"id": "A1", "points": [[x, y], ...]}]
    truth: dict[str, bool]  # slot id -> occupied
    plates: list[tuple[int, int, int, int]]  # x, y, w, h of each plate


def make_lot(occupancy: float = 0.6, cols: int = 10, seed: int = 3,
             width: int = 1100, height: int = 620) -> SyntheticLot:
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    img = np.full((height, width, 3), 92, np.uint8)
    noise = nrng.normal(0, 7, (height, width, 1)).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    margin_x, slot_w = 60, (width - 120) // cols
    slot_h = 190
    rows = [(60, "A"), (height - 60 - slot_h, "B")]
    slots, truth, plates = [], {}, []

    # driving lane marking
    cv2.line(img, (40, height // 2), (width - 40, height // 2), (200, 200, 60), 3)
    for x in range(60, width - 60, 60):
        cv2.line(img, (x, height // 2 - 1), (x + 30, height // 2 - 1), (230, 230, 230), 2)

    for y0, row in rows:
        for c in range(cols):
            x0 = margin_x + c * slot_w
            pts = [[x0 + 6, y0 + 6], [x0 + slot_w - 6, y0 + 6], [x0 + slot_w - 6, y0 + slot_h - 6], [x0 + 6, y0 + slot_h - 6]]
            sid = f"{row}{c + 1}"
            slots.append({"id": sid, "points": pts})
            cv2.line(img, (x0, y0), (x0, y0 + slot_h), (235, 235, 235), 3)
            cv2.line(img, (x0 + slot_w, y0), (x0 + slot_w, y0 + slot_h), (235, 235, 235), 3)
            occupied = rng.random() < occupancy
            truth[sid] = occupied
            if occupied:
                plates.append(_draw_car(img, x0, y0, slot_w, slot_h, row, rng))
        cv2.line(img, (margin_x, y0 if row == "A" else y0 + slot_h),
                 (margin_x + cols * slot_w, y0 if row == "A" else y0 + slot_h), (235, 235, 235), 3)
    img = cv2.GaussianBlur(img, (3, 3), 0)
    return SyntheticLot(img, slots, truth, plates)


def _draw_car(img, x0, y0, sw, sh, row, rng) -> tuple[int, int, int, int]:
    pad_x = int(sw * rng.uniform(0.12, 0.2))
    pad_y = int(sh * rng.uniform(0.06, 0.12))
    x1, y1, x2, y2 = x0 + pad_x, y0 + pad_y, x0 + sw - pad_x, y0 + sh - pad_y
    colour = rng.choice(CAR_COLOURS)
    # shadow
    cv2.rectangle(img, (x1 + 4, y1 + 6), (x2 + 4, y2 + 6), (55, 55, 55), -1)
    cv2.rectangle(img, (x1, y1), (x2, y2), colour, -1)
    cv2.rectangle(img, (x1, y1), (x2, y2), tuple(max(0, v - 50) for v in colour), 2)
    # windscreens (front faces the lane)
    h = y2 - y1
    if row == "A":
        front, back = (y2 - int(h * 0.38), y2 - int(h * 0.22)), (y1 + int(h * 0.15), y1 + int(h * 0.27))
    else:
        front, back = (y1 + int(h * 0.22), y1 + int(h * 0.38)), (y2 - int(h * 0.27), y2 - int(h * 0.15))
    cv2.rectangle(img, (x1 + 8, front[0]), (x2 - 8, front[1]), (35, 45, 55), -1)
    cv2.rectangle(img, (x1 + 10, back[0]), (x2 - 10, back[1]), (45, 55, 65), -1)
    # number plate on the lane side
    pw, ph = int((x2 - x1) * 0.6), 14
    px = x1 + ((x2 - x1) - pw) // 2
    py = y2 - ph - 2 if row == "A" else y1 + 2
    cv2.rectangle(img, (px, py), (px + pw, py + ph), (245, 245, 245), -1)
    cv2.putText(img, f"JK02 {rng.randint(1000, 9999)}", (px + 3, py + ph - 3),
                cv2.FONT_HERSHEY_PLAIN, 0.75, (20, 20, 20), 1, cv2.LINE_AA)
    return px, py, pw, ph
