"""Real-time crowd & queue analytics on tracked detections.

- Entrance line: in/out counts from line crossings (Supervision LineZone).
- Waiting area / queue polygons: live occupancy (Supervision PolygonZone).
- Dwell: how long each track stays inside a polygon.
- Wait time: Little's Law W = L / lambda, where L is the mean queue length and
  lambda the measured queue throughput (people leaving the queue per second).
- Alerts: fire when occupancy or queue length stays above a limit for `hold_s`.

All timing uses the `ts` passed to `update`, so the same code runs live
(wall clock) and offline (video time) for validation.
"""
from collections import deque

import numpy as np
import supervision as sv

ANCHOR = sv.Position.BOTTOM_CENTER  # a person's feet decide which zone they are in


def _px(points, w, h) -> np.ndarray:
    return np.array([[x * w, y * h] for x, y in points], dtype=np.int32)


class ZoneTimer:
    """Time each track ID spends inside a zone; records a departure when it walks out.

    A departure needs the person to be *seen outside* the zone for `grace_s`.
    Tracks that vanish while inside (occlusion, ID switch) are dropped without
    counting, so tracker glitches do not inflate throughput.
    """

    def __init__(self, grace_s: float = 0.5, lost_s: float = 3.0, min_dwell_s: float = 1.0):
        self.grace_s = grace_s
        self.lost_s = lost_s
        self.min_dwell_s = min_dwell_s
        # tid -> [entered_ts, last_inside_ts, outside_since_ts | None, last_seen_ts]
        self.active: dict[int, list] = {}
        self.departures: deque[tuple[float, float]] = deque()  # (ts, dwell_s)

    def update(self, inside_ids, visible_ids, ts: float):
        inside = set(inside_ids)
        for tid in inside:
            state = self.active.get(tid)
            if state is None:
                self.active[tid] = [ts, ts, None, ts]
            else:
                state[1], state[2], state[3] = ts, None, ts
        visible = set(visible_ids)
        for tid, state in list(self.active.items()):
            if tid in inside:
                continue
            entered, last_in, outside_since, last_seen = state
            if tid in visible:
                state[3] = ts
                if outside_since is None:
                    state[2] = ts
                elif ts - outside_since >= self.grace_s:
                    del self.active[tid]
                    if last_in - entered >= self.min_dwell_s:
                        self.departures.append((last_in, last_in - entered))
            elif ts - last_seen > self.lost_s:
                del self.active[tid]

    def elapsed(self, tid: int, ts: float) -> float | None:
        state = self.active.get(tid)
        return ts - state[0] if state else None

    def prune(self, since: float):
        while self.departures and self.departures[0][0] < since:
            self.departures.popleft()

    def avg_dwell(self) -> float | None:
        if not self.departures:
            return None
        return float(np.mean([d for _, d in self.departures]))


class ThresholdAlert:
    """Debounced threshold: must stay over the limit for hold_s to fire, under it for hold_s to clear."""

    def __init__(self, kind: str, message: str):
        self.kind = kind
        self.message = message
        self.active = False
        self._since = None

    def update(self, value: float, limit: float | None, hold_s: float, ts: float) -> bool:
        """Returns True exactly once when the alert fires."""
        over = bool(limit) and value > limit
        if over == self.active:
            self._since = None
            return False
        if self._since is None:
            self._since = ts
        if ts - self._since >= hold_s:
            self.active = over
            self._since = None
            return over
        return False


class Analytics:
    def __init__(self, zones: dict, window_s: float = 120.0):
        self.window_s = window_s
        self.zones = zones
        self._wh = None
        self.line = self.queue_zone = self.area_zone = None
        self._entries_base = self._exits_base = 0
        self.queue_timer = ZoneTimer()
        self.area_timer = ZoneTimer()
        self.queue_samples: deque[tuple[float, int]] = deque()
        self.start_ts = None
        self.alerts = [
            ThresholdAlert("queue", "Queue over limit"),
            ThresholdAlert("area", "Waiting area overcrowded"),
        ]

    # ---- configuration -------------------------------------------------
    def configure(self, zones: dict):
        self.zones = zones
        self._wh = None  # rebuild zones on the next frame

    def _build(self, w: int, h: int):
        self._bank_line_counts()
        z = self.zones
        line = z.get("line") or []
        self.line = None
        if len(line) == 2:
            (x1, y1), (x2, y2) = _px(line, w, h)
            self.line = sv.LineZone(
                start=sv.Point(int(x1), int(y1)),
                end=sv.Point(int(x2), int(y2)),
                triggering_anchors=[ANCHOR],
            )
        self.queue_zone = self._polygon(z.get("queue"), w, h)
        self.area_zone = self._polygon(z.get("area"), w, h)
        self.queue_timer.active.clear()
        self.area_timer.active.clear()
        self._wh = (w, h)

    @staticmethod
    def _polygon(points, w, h):
        if not points or len(points) < 3:
            return None
        return sv.PolygonZone(polygon=_px(points, w, h), triggering_anchors=[ANCHOR])

    def _bank_line_counts(self):
        """Keep running entry/exit totals when the LineZone has to be recreated."""
        if self.line is not None:
            self._entries_base += self.line.in_count
            self._exits_base += self.line.out_count
        self.line = None

    def reset_tracks(self):
        """Tracker IDs restarted (stream loop / reconnect): drop per-track state, keep totals."""
        self._wh = None
        self.queue_timer.active.clear()
        self.area_timer.active.clear()

    # ---- per frame -----------------------------------------------------
    def update(self, detections: sv.Detections, ts: float, frame_wh: tuple[int, int]):
        if self._wh != frame_wh:
            self._build(*frame_wh)
        if self.start_ts is None:
            self.start_ts = ts

        n = len(detections)
        tids = detections.tracker_id if detections.tracker_id is not None else np.zeros(n, dtype=int)
        in_queue = self.queue_zone.trigger(detections) if self.queue_zone else np.zeros(n, bool)
        in_area = self.area_zone.trigger(detections) if self.area_zone else np.zeros(n, bool)
        if self.line is not None and n:
            self.line.trigger(detections)

        visible = tids.tolist()
        self.queue_timer.update(tids[in_queue].tolist(), visible, ts)
        self.area_timer.update(tids[in_area].tolist(), visible, ts)

        queue_len = int(in_queue.sum())
        area_count = int(in_area.sum())
        since = ts - self.window_s
        self.queue_samples.append((ts, queue_len))
        while self.queue_samples and self.queue_samples[0][0] < since:
            self.queue_samples.popleft()
        self.queue_timer.prune(since)
        self.area_timer.prune(since)

        wait_s, L, lam = self._little(ts, queue_len)
        hold = float(self.zones.get("hold_s", 3))
        fired = []
        for alert, value, limit in (
            (self.alerts[0], queue_len, self.zones.get("queue_limit")),
            (self.alerts[1], area_count, self.zones.get("area_limit")),
        ):
            if alert.update(value, limit, hold, ts):
                fired.append({"kind": alert.kind, "message": alert.message, "value": value, "limit": limit})

        metrics = {
            "people": n,
            "entries": self._entries_base + (self.line.in_count if self.line else 0),
            "exits": self._exits_base + (self.line.out_count if self.line else 0),
            "area": area_count,
            "queue": queue_len,
            "wait_s": wait_s,
            "L": L,
            "lambda_pm": None if lam is None else lam * 60,
            "dwell_s": self.queue_timer.avg_dwell(),
            "area_stay_s": self.area_timer.avg_dwell(),
            "alerts": [{"kind": a.kind, "message": a.message} for a in self.alerts if a.active],
        }
        return metrics, fired, {"queue": in_queue, "area": in_area}

    def _little(self, ts: float, queue_len: int):
        span = min(self.window_s, ts - self.start_ts)
        if span < 15:  # not enough history yet
            return None, None, None
        L = float(np.mean([q for _, q in self.queue_samples]))
        lam = len(self.queue_timer.departures) / span  # people served per second
        if lam == 0:
            return (0.0 if L < 0.5 else None), L, 0.0
        return L / lam, L, lam
