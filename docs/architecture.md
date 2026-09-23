# Architecture

Every stream configured in `sources.yaml` (plus anything added from the dashboard and
stored in `config/streams.json`) gets its own worker, and they all run at once. A worker
owns its reader, tracker, analytics, zones, heatmap and settings; the only shared piece is
the YOLO model.

## Data flow

1. **Reader** (`pipeline/reader.py`) — dedicated capture thread per source.
   - Keeps only the newest frame (drop-old), so analytics never lag behind on buffered frames.
   - File: paced at native FPS and rewound at EOF, so it behaves like a live camera.
   - RTSP: TCP transport, `CAP_PROP_BUFFERSIZE=1`, 5 s open/read timeouts, reconnect with
     exponential backoff (1 → 10 s). A reconnect bumps an `epoch` so tracker IDs restart cleanly.
   - Web: a public live page (e.g. a YouTube street cam) is resolved to its HLS URL with yt-dlp
     on every connect (those URLs expire), then paced like a file, because HLS arrives in bursts of
     whole segments. Same reconnect/backoff as RTSP. Zones are stored per source (`zones` in
     `sources.yaml`), since every camera sees a different scene.
2. **Detector** (`pipeline/detector.py`) — YOLO11 (COCO class 0 = person). `yolo11s` FP16 on GPU,
   `yolo11n` on CPU. Low confidence threshold (0.15) on purpose: ByteTrack uses weak detections
   to keep existing tracks alive through partial occlusion. One instance is shared by every
   worker and `__call__` is serialised with a lock, so N streams queue for the GPU instead of
   loading N copies of the model.
3. **Tracker** (`pipeline/tracker.py`) — ByteTrack from Roboflow `trackers`. Real timestamps are
   passed in, so frames skipped under load don't break the motion model.
4. **Analytics** (`pipeline/analytics.py`) — pure functions of tracked boxes + a timestamp:
   - `LineZone` in/out counts, anchored on the feet (bottom-centre of the box).
   - `PolygonZone` occupancy for the queue and waiting area.
   - Per-track dwell timers. A *departure* requires the person to be seen outside the zone for
     0.5 s; tracks that vanish inside (occlusion, ID switch) are dropped, not counted, so tracker
     glitches don't inflate throughput.
   - Wait time via Little's Law over a 120 s window: `W = L / λ`.
   - Debounced threshold alerts (must hold for `hold_s` to fire and to clear).
5. **Annotator** (`pipeline/annotate.py`) — boxes coloured by zone, zone overlays, entrance line
   with "in" arrow, optional blur and heatmap.
6. **Worker** (`pipeline/worker.py`) — `SourceWorker` owns one source: publishes the latest JPEG +
   metrics and writes one row per second (occupancy averaged over that second) to SQLite under
   that source's name. `Pipeline` is the manager: it builds one worker per stream, hands them the
   shared detector, and adds/removes streams at runtime (writing `config/streams.json` and that
   stream's zones file).
7. **Reporting** (`reporting.py` + the report queries in `storage/db.py`) — period aggregates
   over the rows already in SQLite: averages, peaks (with the timestamp of each peak), and the
   alert log, per stream and facility-wide. Nothing is recomputed from video, so a report can
   only ever restate what was measured.
   - Entries/exits are running totals, so a period count is the sum of the *positive* steps
     between consecutive samples: a worker restart (counter back to zero) subtracts nothing.
   - Occupancy across streams is summed per second *before* it is averaged, so the facility
     peak is a real simultaneous head count, not the sum of peaks that never coincided.
   - `samples / period seconds` is reported as coverage, since one row is written per second:
     it says how much of the period a feed was actually analysed rather than reconnecting.
   - The chart series is bucketed to ~120 points whatever the period, so 24 h is one request.
8. **API** (`main.py`) — FastAPI: MJPEG stream and REST per stream (`/api/streams/{name}/…`), one
   WebSocket (`/api/ws`) carrying metrics for *all* streams at 2 Hz so the overview grid stays
   live without one socket per feed. Reports are JSON (`/api/report`) or CSV (`/api/report.csv`,
   encoded utf-8-sig so Excel reads it). Serves the built dashboard from `frontend/dist`.

## Why these choices

| Choice | Reason | Production upgrade |
|---|---|---|
| MJPEG video | trivial to serve and display in an `<img>` | WebRTC (~300 ms latency) |
| WebSocket metrics | push, no polling | same |
| SQLite | zero-config, file-based | PostgreSQL / TimescaleDB |
| Detection + tracking | accurate for sparse-to-moderate crowds | CSRNet density maps for packed crowds |
| One worker per camera, one shared model | every feed is analysed at once without N model copies | batched inference across cameras, or one process per GPU |
| Streams split across `sources.yaml` (hand-edited) and `streams.json` (app-written) | the documented config keeps its comments; the app never rewrites it | a `streams` table in the database |
| PDF export via the browser's print dialog | no PDF dependency, vector output, the report sheet is the same React components as the dashboard | server-side rendering to a stored, schedulable PDF |

## Performance (RTX 4050 laptop, 1280 px frames, yolo11s FP16)

- ~27 FPS end-to-end offline (`validate.py`), which keeps up with the 25 FPS sample clip live.
- Two concurrent feeds still measured ~27 FPS each; beyond that, inference time is shared and
  each feed's FPS falls proportionally.
- Heatmap adds ~7 ms/frame, blur ~1 ms/frame.
- On CPU-only machines, `model: auto` picks `yolo11n`; the reader drops frames automatically
  when inference is slower than the source. Dropping frames costs accuracy on line crossings,
  so on CPU keep the number of simultaneous streams small.
