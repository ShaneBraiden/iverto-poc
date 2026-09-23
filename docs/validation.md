# Accuracy validation

Goal: show the numbers are measured, not mocked, and quantify the error.
Target: **≥ 95 % agreement** with a manual count (the usual bar for people counters).

## Procedure

1. Pick a representative clip and set the zones (`backend/config/zones.json`).
2. Export an annotated copy to see the line and zones while counting:
   `python validate.py --save ../data/validation.mp4`
3. A person counts **entries** (crossing in the arrow's direction) and **exits** by hand,
   frame by frame, on the annotated video.
4. Compare:
   `python validate.py --truth-in <entries> --truth-out <exits>`
   This prints system vs manual, absolute error, agreement and MAE.
5. For occupancy: pause on 3–5 frames, count people in each zone, compare with the chips.

## Results

| Clip | Metric | System | Manual | Abs. error | Agreement |
|---|---|---:|---:|---:|---:|
| people-walking.mp4 (13.6 s) | Entries | 11 | _to count_ | | |
| people-walking.mp4 (13.6 s) | Exits | 9 | _to count_ | | |

System values above are from `python validate.py` with the default zones (yolo11s, GPU).

## Known limits

- Tight groups (e.g. the standing cluster in the sample clip) cause occlusion and occasional
  ID switches; counts stay stable but per-person dwell for those people is underestimated.
- Detection-based counting degrades in packed crowds (occlusion can hide 40–60 % of people);
  a density model (CSRNet) is the upgrade path there.
- Little's Law is an average for a roughly stable queue; on short or bursty clips treat the
  wait time as an estimate.
