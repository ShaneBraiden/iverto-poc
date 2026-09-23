"""Offline validation: run the exact live pipeline over a clip and compare with a hand count.

    python validate.py                                  # default clip, print system counts
    python validate.py --truth-in 14 --truth-out 11     # compare with a manual count
    python validate.py --save ../data/validation.mp4    # also write the annotated video

Timing uses video time (frame index / fps), so results do not depend on machine speed.
"""
import argparse
import json
import time
from pathlib import Path

import cv2
import yaml

from pipeline.analytics import Analytics
from pipeline.annotate import Annotator
from pipeline.detector import PersonDetector
from pipeline.tracker import PersonTracker

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent


def agreement(system: int, truth: int) -> float:
    if truth == 0:
        return 100.0 if system == 0 else 0.0
    return max(0.0, 100.0 * (1 - abs(system - truth) / truth))


def main():
    cfg = yaml.safe_load((BACKEND / "config" / "sources.yaml").read_text())
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(ROOT / cfg["sources"]["file"]["uri"]))
    ap.add_argument("--zones", default=str(BACKEND / "config" / "zones.json"))
    ap.add_argument("--truth-in", type=int)
    ap.add_argument("--truth-out", type=int)
    ap.add_argument("--save", help="write annotated video here")
    args = ap.parse_args()

    zones = json.loads(Path(args.zones).read_text())
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    detector = PersonDetector(cfg.get("model", "auto"), cfg.get("imgsz", 640), cfg.get("conf", 0.3))
    tracker = PersonTracker(fps)
    analytics = Analytics(zones, cfg.get("wait_window_s", 120))
    annotator = Annotator()
    max_w = int(cfg.get("max_width", 1280))
    writer = None

    frames, peak_area, peak_queue, metrics = 0, 0, 0, {}
    t0 = time.perf_counter()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        if w > max_w:
            frame = cv2.resize(frame, (max_w, int(h * max_w / w)), interpolation=cv2.INTER_AREA)
            h, w = frame.shape[:2]
        ts = frames / fps
        detections = tracker.update(detector(frame), ts)
        metrics, _, member = analytics.update(detections, ts, (w, h))
        peak_area = max(peak_area, metrics["area"])
        peak_queue = max(peak_queue, metrics["queue"])
        if args.save:
            out = annotator.draw(frame, detections, member, analytics, metrics, ts)
            if writer is None:
                writer = cv2.VideoWriter(args.save, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            writer.write(out)
        frames += 1
    elapsed = time.perf_counter() - t0
    if writer:
        writer.release()

    print(f"clip            {Path(args.video).name}  ({frames} frames, {frames / fps:.1f}s)")
    print(f"model           {detector.name} on {detector.device}  ->  {frames / elapsed:.1f} FPS end-to-end")
    print(f"entries / exits {metrics['entries']} / {metrics['exits']}")
    print(f"peak area/queue {peak_area} / {peak_queue}")
    print(f"avg queue dwell {metrics['dwell_s'] or 0:.1f}s   avg area stay {metrics['area_stay_s'] or 0:.1f}s")

    if args.truth_in is not None and args.truth_out is not None:
        pairs = [("entries", metrics["entries"], args.truth_in), ("exits", metrics["exits"], args.truth_out)]
        print("\n| metric  | system | manual | abs error | agreement |")
        print("|---------|-------:|-------:|----------:|----------:|")
        for name, s, t in pairs:
            print(f"| {name:<7} | {s:>6} | {t:>6} | {abs(s - t):>9} | {agreement(s, t):>8.1f}% |")
        mae = sum(abs(s - t) for _, s, t in pairs) / len(pairs)
        print(f"\nMAE = {mae:.2f}")


if __name__ == "__main__":
    main()
