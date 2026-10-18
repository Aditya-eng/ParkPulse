"""Privacy by default: blur faces and number plates before any frame is stored or shown.

Faces use OpenCV's bundled Haar cascade. Plates use a light morphological heuristic
(bright, text-filled rectangles with plate-like aspect ratio). In a pilot the plate
step would be replaced by a trained Indian-plate detector; the interface stays the same.
"""

from __future__ import annotations

import cv2
import numpy as np

_face_cascade = None


def _faces(gray: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Haar-cascade faces. OpenCV 5 builds may ship without cascades; then faces are skipped
    and a DNN face detector (cv2.FaceDetectorYN with a YuNet model) should be configured."""
    global _face_cascade
    if _face_cascade is None:
        if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data"):
            _face_cascade = False
        else:
            _face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if _face_cascade is False:
        return []
    return [tuple(map(int, f)) for f in _face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(24, 24))]


def plate_candidates(frame: np.ndarray) -> list[tuple[int, int, int, int]]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, bright = cv2.threshold(gray, 215, 255, cv2.THRESH_BINARY)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((3, 9), np.uint8))
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if h < 8 or w < 25 or not (2.0 <= w / h <= 7.0):
            continue
        roi = gray[y:y + h, x:x + w]
        dark_ratio = float(np.mean(roi < 160))
        if 0.02 <= dark_ratio <= 0.6:  # contains characters, not a blank line marking
            out.append((x, y, w, h))
    return out


def blur_regions(frame: np.ndarray, boxes, pad: int = 4) -> np.ndarray:
    out = frame.copy()
    H, W = out.shape[:2]
    for x, y, w, h in boxes:
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
        roi = out[y0:y1, x0:x1]
        if roi.size:
            k = max(9, (min(roi.shape[:2]) // 2) | 1)
            out[y0:y1, x0:x1] = cv2.GaussianBlur(roi, (k, k), 0)
    return out


def anonymise(frame: np.ndarray) -> tuple[np.ndarray, int]:
    """Return a blurred copy and the number of regions blurred."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    boxes = _faces(gray) + plate_candidates(frame)
    return blur_regions(frame, boxes), len(boxes)
