from parkpulse.vision.dwell import DwellTracker
from parkpulse.vision.privacy import anonymise, plate_candidates
from parkpulse.vision.slot_detector import SlotDetector
from parkpulse.vision.synthetic import make_lot


def test_slot_detector_accuracy_on_synthetic_lots():
    correct = total = 0
    for seed in range(15):
        lot = make_lot(occupancy=0.55, seed=seed)
        for s in SlotDetector(lot.slots).detect(lot.image):
            total += 1
            correct += s.occupied == lot.truth[s.id]
    assert correct / total >= 0.95


def test_summary_counts_match():
    lot = make_lot(occupancy=0.5, seed=2)
    det = SlotDetector(lot.slots)
    summary = det.summarize(det.detect(lot.image))
    assert summary["total"] == 20
    assert summary["free"] + summary["occupied"] == 20


def test_plates_found_and_blurred():
    lot = make_lot(occupancy=0.7, seed=6)
    found = plate_candidates(lot.image)
    hits = sum(any(abs(px - x) < 8 and abs(py - y) < 8 for x, y, _, _ in found) for px, py, _, _ in lot.plates)
    assert hits / max(1, len(lot.plates)) >= 0.7
    blurred, n = anonymise(lot.image)
    assert n >= hits and blurred.shape == lot.image.shape


def test_dwell_tracker_flags_once_after_limit():
    tr = DwellTracker("np-test", [[0, 0], [100, 0], [100, 100], [0, 100]], limit_seconds=300)
    events = []
    for t in range(0, 400, 20):
        events += tr.update([(50, 50), (500, 500)], t)  # second car is outside the zone
    assert len(events) == 1 and events[0].dwell_seconds >= 300
