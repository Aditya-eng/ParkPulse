"""Draw slot polygons on a real camera frame and save them as a slot file.

Click four corners per slot, press 'n' for the next slot, 'u' to undo, 's' to save, 'q' to quit.

    python scripts/calibrate_slots.py frame.jpg slots/my_camera.json --prefix A
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frame")
    ap.add_argument("out")
    ap.add_argument("--prefix", default="S")
    a = ap.parse_args()

    img = cv2.imread(a.frame)
    if img is None:
        raise SystemExit(f"Could not read {a.frame}")
    slots, current = [], []

    def redraw():
        view = img.copy()
        for s in slots:
            cv2.polylines(view, [np.array(s["points"], np.int32)], True, (70, 200, 90), 2)
            cv2.putText(view, s["id"], tuple(s["points"][0]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        for p in current:
            cv2.circle(view, tuple(p), 4, (0, 200, 255), -1)
        cv2.imshow("calibrate", view)

    def on_click(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN and len(current) < 4:
            current.append([x, y])
            redraw()

    cv2.namedWindow("calibrate")
    cv2.setMouseCallback("calibrate", on_click)
    redraw()
    while True:
        k = cv2.waitKey(50) & 0xFF
        if k == ord("n") and len(current) == 4:
            slots.append({"id": f"{a.prefix}{len(slots) + 1}", "points": current.copy()})
            current.clear()
            redraw()
        elif k == ord("u"):
            (current.pop() if current else slots.pop() if slots else None)
            redraw()
        elif k == ord("s"):
            Path(a.out).write_text(json.dumps({"camera": Path(a.frame).stem, "slots": slots}, indent=2))
            print(f"Saved {len(slots)} slots to {a.out}")
        elif k == ord("q"):
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
