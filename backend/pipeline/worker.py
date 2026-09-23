"""Per-source pipeline workers: reader -> YOLO11 -> ByteTrack -> analytics -> annotated JPEG + metrics.

One `SourceWorker` per stream, each with its own reader, tracker, analytics, zones,
heatmap and settings, all sharing a single detector (inference is serialised on the
GPU). Every configured stream is analysed at once, so the dashboard can show them
side by side and any feed can be opened for details without restarting anything.
"""
import json
import logging
import re
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from .analytics import Analytics
from .annotate import Annotator
from .detector import PersonDetector
from .reader import FrameReader
from .tracker import PersonTracker

log = logging.getLogger("pipeline")

KINDS = ("file", "rtsp", "web")
VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm")
EMPTY_ZONES = {"line": [], "queue": [], "area": [], "queue_limit": None, "area_limit": None, "hold_s": 3.0}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "stream"


class SourceWorker:
    """Owns one video source end to end. Thread-safe outputs: jpeg, raw frame, metrics."""

    def __init__(self, name: str, spec: dict, *, detector, store, root: Path, config_dir: Path,
                 max_width: int, window_s: float):
        self.name = name
        self.spec = spec
        self.label = spec.get("label") or name.replace("-", " ").title()
        self.kind = spec["kind"]
        self.detector = detector
        self.store = store
        self.root = root
        self.config_dir = config_dir
        self.max_width = max_width
        self.window_s = window_s

        self.zones = self._load_zones()
        self.settings = {"blur": False, "heatmap": False}
        self.annotator = Annotator()

        self.status = "connecting"
        self.metrics: dict = {}
        self.jpeg: bytes | None = None
        self.raw = None
        self.frame_seq = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._zones_dirty = False
        self._thread = threading.Thread(target=self._run, name=f"pipeline-{name}", daemon=True)

    # ---- control -------------------------------------------------------
    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)

    def set_zones(self, zones: dict):
        text = json.dumps(zones, indent=2)
        text = re.sub(r"\[\s+([-\d.]+),\s+([-\d.]+)\s+\]", r"[\1, \2]", text)  # keep each [x, y] on one line
        self.zones_path.write_text(text)
        self.zones = zones
        self._zones_dirty = True

    def set_settings(self, **kwargs):
        self.settings.update({k: bool(v) for k, v in kwargs.items() if k in self.settings})

    def reset_heatmap(self):
        self.annotator.reset()

    # ---- outputs -------------------------------------------------------
    def latest_jpeg(self):
        with self._lock:
            return self.jpeg, self.frame_seq

    def snapshot(self) -> bytes | None:
        with self._lock:
            raw = self.raw
        if raw is None:
            return None
        return cv2.imencode(".jpg", raw, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()

    def live(self) -> dict:
        m = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in self.metrics.items()}
        return {"name": self.name, "status": self.status, "settings": dict(self.settings), "metrics": m}

    def info(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "uri": self.spec["uri"],
            "custom": bool(self.spec.get("custom")),
            "upload": bool(self.spec.get("upload")),
            "zones": self.zones,
            "settings": dict(self.settings),
            "status": self.status,
        }

    # ---- zones (one file per source: each camera sees a different scene) --
    @property
    def zones_path(self) -> Path:
        return self.config_dir / self.spec.get("zones", f"zones-{self.name}.json")

    def _load_zones(self) -> dict:
        path = self.zones_path
        return json.loads(path.read_text()) if path.exists() else dict(EMPTY_ZONES)

    # ---- main loop -----------------------------------------------------
    @property
    def uri(self) -> str:
        if self.kind == "file":
            return str((self.root / self.spec["uri"]).resolve())
        return self.spec["uri"]

    def _resize(self, frame):
        h, w = frame.shape[:2]
        if w <= self.max_width:
            return frame
        scale = self.max_width / w
        return cv2.resize(frame, (self.max_width, int(h * scale)), interpolation=cv2.INTER_AREA)

    def _run(self):
        while not self._stop.is_set():
            reader = FrameReader(self.uri, self.kind).start()
            try:
                self._process(reader)
            except Exception:
                log.exception("pipeline crashed; restarting source %s", self.name)
                self._stop.wait(1)
            finally:
                reader.stop()

    def _process(self, reader: FrameReader):
        analytics = Analytics(self.zones, self.window_s)
        self.annotator.reset()
        tracker, epoch = None, None
        last_seq, last_write, last_t, fps = 0, None, None, 0.0
        bucket = {"people": [], "area": [], "queue": []}  # per-second averages for history

        while not self._stop.is_set():
            got = reader.read(last_seq, timeout=0.5)
            if got is None:
                self.status = reader.status if reader.status != "live" else "connecting"
                continue
            self.status = "live"
            frame, last_seq, frame_epoch = got
            if frame_epoch != epoch:  # stream (re)started: IDs restart, keep totals
                tracker = PersonTracker(reader.fps)
                analytics.reset_tracks()
                epoch = frame_epoch
            if self._zones_dirty:
                self._zones_dirty = False
                analytics.configure(self.zones)

            frame = self._resize(frame)
            ts = time.monotonic()
            detections = tracker.update(self.detector(frame), ts)
            h, w = frame.shape[:2]
            metrics, fired, member = analytics.update(detections, ts, (w, h))
            for alert in fired:
                self.store.add_event(self.name, alert["kind"], alert["message"], alert["value"])

            out = self.annotator.draw(frame, detections, member, analytics, metrics, ts, **self.settings)
            jpeg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()

            now = time.monotonic()
            if last_t is not None:
                fps = 0.9 * fps + 0.1 / max(now - last_t, 1e-3) if fps else 1 / max(now - last_t, 1e-3)
            last_t = now
            metrics["fps"] = fps

            with self._lock:
                self.jpeg, self.raw, self.metrics = jpeg, frame, metrics
                self.frame_seq += 1
            for key, values in bucket.items():
                values.append(metrics[key])
            if last_write is None:  # start the first 1 s bucket at the first frame
                last_write = now
            elif now - last_write >= 1.0:
                row = dict(metrics)
                for key, values in bucket.items():
                    row[key] = round(sum(values) / len(values), 1)
                    values.clear()
                self.store.add_metrics(self.name, row)
                last_write = now


class Pipeline:
    """All streams at once: one worker per source, one shared detector.

    Streams declared in `sources.yaml` are the built-in ones (hand-edited, never
    rewritten). Streams added from the dashboard are persisted separately in
    `config/streams.json`. Any stream can be removed from the UI: a built-in one is
    recorded there as `{"removed": true}` so it stays gone without touching the yaml,
    and an uploaded video is deleted from `data/uploads/` along with its stream.
    """

    def __init__(self, cfg: dict, config_dir: Path, store, root: Path):
        self.cfg = cfg
        self.root = root
        self.store = store
        self.config_dir = config_dir
        self.custom_path = config_dir / "streams.json"
        self.upload_dir = (root / "data" / "uploads").resolve()
        self.max_width = int(cfg.get("max_width", 1280))
        self.window_s = float(cfg.get("wait_window_s", 120))

        self.detector = PersonDetector(cfg.get("model", "auto"), cfg.get("imgsz", 640), cfg.get("conf", 0.3))
        self.detector.warmup(np.zeros((720, 1280, 3), dtype=np.uint8))

        self.workers: dict[str, SourceWorker] = {}
        self._lock = threading.Lock()
        custom = self._load_custom()
        for name, spec in cfg.get("sources", {}).items():
            if not custom.get(name, {}).get("removed"):
                self.workers[name] = self._build(name, spec)
        for name, spec in custom.items():
            if not spec.get("removed") and name not in self.workers:
                self.workers[name] = self._build(name, {**spec, "custom": True})

    # ---- lifecycle -----------------------------------------------------
    def start(self):
        for worker in self.workers.values():
            worker.start()

    def stop(self):
        for worker in list(self.workers.values()):
            worker.stop()

    def _build(self, name: str, spec: dict) -> SourceWorker:
        return SourceWorker(
            name, spec,
            detector=self.detector, store=self.store, root=self.root, config_dir=self.config_dir,
            max_width=self.max_width, window_s=self.window_s,
        )

    # ---- streams -------------------------------------------------------
    def get(self, name: str) -> SourceWorker:
        return self.workers[name]

    def all(self) -> list[SourceWorker]:
        return list(self.workers.values())

    def _load_custom(self) -> dict:
        if not self.custom_path.exists():
            return {}
        try:
            return json.loads(self.custom_path.read_text())
        except json.JSONDecodeError:
            log.warning("ignoring malformed %s", self.custom_path)
            return {}

    def _save_custom(self, streams: dict):
        self.custom_path.write_text(json.dumps(streams, indent=2))

    def add(self, label: str, kind: str, uri: str, *, upload: bool = False) -> SourceWorker:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {', '.join(KINDS)}")
        if not uri.strip():
            raise ValueError("uri is required")
        with self._lock:
            streams = self._load_custom()
            base = slugify(label)
            name, n = base, 2
            while name in self.workers or name in streams:  # `streams` also holds removed built-ins
                name, n = f"{base}-{n}", n + 1
            spec = {"label": label.strip(), "kind": kind, "uri": uri.strip(),
                    "zones": f"zones-{name}.json", "custom": True}
            if upload:
                spec["upload"] = True
            streams[name] = spec
            self._save_custom(streams)
            worker = self._build(name, spec)
            self.workers[name] = worker
        worker.start()
        return worker

    def remove(self, name: str):
        with self._lock:
            worker = self.workers.pop(name, None)
            if worker is None:
                raise KeyError(name)
            custom = bool(worker.spec.get("custom"))
            streams = self._load_custom()
            if custom:
                streams.pop(name, None)
            else:
                streams[name] = {"removed": True}
            self._save_custom(streams)
        worker.stop()
        if not custom:  # built-in: its zones file may be shared (rtsp reuses zones.json), leave it
            return
        worker.zones_path.unlink(missing_ok=True)
        if worker.spec.get("upload"):
            self._delete_upload(worker)

    def _delete_upload(self, worker: SourceWorker):
        """Delete the uploaded video, but only ever a file inside data/uploads/."""
        path = Path(worker.uri)
        if not path.resolve().is_relative_to(self.upload_dir):
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:  # still held open by the reader on Windows
            log.warning("could not delete uploaded video %s", path)

    # ---- outputs -------------------------------------------------------
    def info(self) -> dict:
        return {
            "streams": [w.info() for w in self.workers.values()],
            "model": self.detector.name,
            "device": self.detector.device,
            "kinds": list(KINDS),
        }

    def live(self) -> dict:
        return {"streams": {name: w.live() for name, w in self.workers.items()}}
