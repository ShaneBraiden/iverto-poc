"""Threaded frame reader for video files, RTSP streams and public web streams.

Keeps only the newest frame (drop-old policy) so the analytics loop never works
on stale, buffered frames. Files are paced at their native FPS and looped, so
they behave like a live camera. Web sources (e.g. a YouTube live street cam) are
resolved to a direct stream URL with yt-dlp on every connect, because those URLs
expire, and are paced too: HLS arrives in bursts of whole segments. A web page that
turns out to be a plain video (not a live stream) loops like a file. Live sources
reconnect with exponential backoff.
"""
import logging
import os
import threading
import time

import cv2

log = logging.getLogger("reader")

# Prefer TCP for RTSP: slower to start but far more robust than UDP on Wi-Fi.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")


def can_read(path) -> bool:
    """True if OpenCV can decode at least one frame from this video file."""
    cap = cv2.VideoCapture(str(path))
    try:
        return cap.isOpened() and cap.read()[0]
    finally:
        cap.release()


class FrameReader:
    def __init__(self, uri: str, kind: str):
        self.uri = uri
        self.kind = kind  # "file" | "rtsp" | "web"
        self.fps = 25.0
        self.status = "connecting"
        self.epoch = 0  # bumped on reconnect: tracker IDs must restart
        self.loop = kind == "file"  # rewind at the end; web sets this from yt-dlp's is_live

        self._frame = None
        self._seq = 0
        self._lock = threading.Lock()
        self._new = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=f"reader-{kind}", daemon=True)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        with self._new:
            self._new.notify_all()
        self._thread.join(timeout=5)

    def read(self, last_seq: int, timeout: float = 1.0):
        """Block until a frame newer than `last_seq` exists. Returns (frame, seq, epoch) or None."""
        with self._new:
            if self._seq <= last_seq:
                self._new.wait(timeout)
            if self._seq <= last_seq or self._frame is None:
                return None
            return self._frame, self._seq, self.epoch

    def _publish(self, frame):
        with self._new:
            self._frame = frame
            self._seq += 1
            self._new.notify_all()

    def _resolve_web(self) -> str | None:
        """Page URL -> direct stream URL (<= 720p video, audio not needed)."""
        import yt_dlp  # only needed for web sources

        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "js_runtimes": {"node": {}},  # YouTube needs a JS runtime; Node is already required for the frontend
            "format": "bestvideo[height<=720][vcodec^=avc1]/bestvideo[height<=720]/best[height<=720]/best",
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(self.uri, download=False)
        except Exception as e:  # offline stream, removed video, network error
            log.warning("could not resolve %s: %s", self.uri, e)
            return None
        self.loop = not info.get("is_live")  # a recorded video ends, a live stream does not
        return info.get("url")

    def _open(self):
        if self.kind in ("rtsp", "web"):
            uri = self.uri if self.kind == "rtsp" else self._resolve_web()
            if uri is None:
                return None
            timeout = 5000 if self.kind == "rtsp" else 10000
            cap = cv2.VideoCapture(
                uri,
                cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout, cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout],
            )
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            cap = cv2.VideoCapture(self.uri)
        if not cap.isOpened():
            cap.release()
            return None
        fps = cap.get(cv2.CAP_PROP_FPS)
        if 1 <= fps <= 120:
            self.fps = fps
        return cap

    def _run(self):
        backoff = 1.0
        while not self._stop.is_set():
            cap = self._open()
            if cap is None:
                self.status = "error" if self.kind == "file" else "reconnecting"
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 10.0)
                continue

            self.status = "live"
            backoff = 1.0
            if self.kind == "rtsp":
                self._pump_rtsp(cap)
            else:
                self._pump_paced(cap, loop=self.loop)
            cap.release()
            if not self._stop.is_set():
                self.epoch += 1

    def _pump_paced(self, cap, loop: bool):
        period = 1.0 / self.fps
        next_t = time.monotonic()
        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok and loop:  # end of file: rewind and keep streaming, like a camera would
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = cap.read()
            if not ok:
                self.status = "error" if self.kind == "file" else "reconnecting"
                return
            self._publish(frame)
            next_t += period
            delay = next_t - time.monotonic()
            if delay > 0:
                self._stop.wait(delay)
            elif delay < -1.0:  # fell far behind (e.g. debugger pause): resync clock
                next_t = time.monotonic()

    def _pump_rtsp(self, cap):
        while not self._stop.is_set():
            ok, frame = cap.read()
            if not ok:
                self.status = "reconnecting"
                return
            self._publish(frame)
