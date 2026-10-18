"""Run the vision pipeline on a synthetic frame and save the raw, anonymised and annotated images.

    python scripts/demo_vision.py --occupancy 0.55 --seed 6 --out docs/img
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from pathlib import Path

import cv2

from parkpulse.vision.privacy import anonymise
from parkpulse.vision.slot_detector import SlotDetector
from parkpulse.vision.synthetic import make_lot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--occupancy", type=float, default=0.55)
    ap.add_argument("--seed", type=int, default=6)
    ap.add_argument("--out", default="docs/img")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lot = make_lot(occupancy=a.occupancy, seed=a.seed)
    safe, n = anonymise(lot.image)
    det = SlotDetector(lot.slots)
    states = det.detect(lot.image)
    cv2.imwrite(str(out / "frame_raw.png"), lot.image)
    cv2.imwrite(str(out / "frame_anonymised.png"), safe)
    cv2.imwrite(str(out / "frame_annotated.png"), det.annotate(safe, states, title="Demo camera (synthetic)"))
    correct = sum(s.occupied == lot.truth[s.id] for s in states)
    print(json.dumps({"summary": det.summarize(states), "accuracy": correct / len(states), "regions_blurred": n}, indent=2))


if __name__ == "__main__":
    main()
