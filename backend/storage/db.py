"""SQLite storage: per-second metric samples and an alert event log.

Only aggregate numbers are persisted - never frames or identities.

The live dashboard reads the newest samples; reports (`backend/reporting.py`)
aggregate these same rows over a period, so an exported number is always a
number that was measured, never a second estimate of it.
"""
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
    ts           REAL NOT NULL,
    source       TEXT NOT NULL,
    people       REAL,
    entries      INTEGER,
    exits        INTEGER,
    area         REAL,
    queue        REAL,
    wait_s       REAL,
    dwell_s      REAL,
    area_stay_s  REAL,
    fps          REAL
);
CREATE INDEX IF NOT EXISTS idx_metrics_source_ts ON metrics(source, ts);
CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts);

CREATE TABLE IF NOT EXISTS events (
    ts       REAL NOT NULL,
    source   TEXT NOT NULL,
    kind     TEXT NOT NULL,
    message  TEXT NOT NULL,
    value    REAL
);
CREATE INDEX IF NOT EXISTS idx_events_source_ts ON events(source, ts);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""

METRIC_FIELDS = ("people", "entries", "exits", "area", "queue", "wait_s", "dwell_s", "area_stay_s", "fps")
EVENT_FIELDS = ("ts", "kind", "message", "value")
PEAK_FIELDS = ("people", "area", "queue", "wait_s")

_COLS = ", ".join(METRIC_FIELDS)

# Averages over the period; peaks come from _peak(), which also reports *when*.
SUMMARY_SQL = """
SELECT COUNT(*), MIN(ts), MAX(ts),
       AVG(people), AVG(area), AVG(queue),
       AVG(wait_s), AVG(dwell_s), AVG(area_stay_s), AVG(fps)
FROM metrics WHERE source = ? AND ts BETWEEN ? AND ?
"""

# Entries/exits are running totals, so the count for a period is the sum of the
# steps between consecutive samples. Only positive steps count, so a worker
# restart (counter back to zero) subtracts nothing instead of going negative.
GAINED_SQL = """
SELECT COALESCE(SUM(MAX(step, 0)), 0) FROM (
    SELECT {col} - LAG({col}) OVER (ORDER BY ts) AS step
    FROM metrics WHERE source = ? AND ts BETWEEN ? AND ?
)
"""

# Occupancy across several feeds has to be summed per second before it is averaged,
# otherwise a "peak" is the sum of peaks that never actually coincided.
PER_SECOND_SQL = """
SELECT CAST(ts AS INTEGER) AS sec, SUM(people) AS people, SUM(area) AS area, SUM(queue) AS queue
FROM metrics WHERE source IN ({marks}) AND ts BETWEEN ? AND ?
GROUP BY sec
"""


def _round(v):
    return round(v, 2) if isinstance(v, float) else v


def _marks(values) -> str:
    return ", ".join("?" * len(values))


def _points(rows, step: float) -> list[dict]:
    return [
        {
            "ts": r[0],
            "step_s": round(step, 3),
            "people": _round(r[1]),
            "area": _round(r[2]),
            "queue": _round(r[3]),
            "queue_peak": _round(r[4]),
        }
        for r in rows
    ]


class Store:
    def __init__(self, path: Path, retention_hours: float = 24):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._migrate()
        self._lock = threading.Lock()
        self._retention_s = retention_hours * 3600
        self._last_prune = 0.0

    def _migrate(self):
        """Add metric columns introduced after an existing database was created."""
        have = {row[1] for row in self._db.execute("PRAGMA table_info(metrics)")}
        for column in METRIC_FIELDS:
            if column not in have:
                self._db.execute(f"ALTER TABLE metrics ADD COLUMN {column} REAL")
        self._db.commit()

    # ---- writes --------------------------------------------------------
    def add_metrics(self, source: str, m: dict):
        ts = time.time()
        with self._lock:
            self._db.execute(
                f"INSERT INTO metrics (ts, source, {_COLS}) VALUES (?, ?{', ?' * len(METRIC_FIELDS)})",
                (ts, source, *(_round(m.get(k)) for k in METRIC_FIELDS)),
            )
            if ts - self._last_prune > 600:
                cutoff = ts - self._retention_s
                self._db.execute("DELETE FROM metrics WHERE ts < ?", (cutoff,))
                self._db.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
                self._last_prune = ts
            self._db.commit()

    def add_event(self, source: str, kind: str, message: str, value: float | None = None):
        with self._lock:
            self._db.execute(
                "INSERT INTO events (ts, source, kind, message, value) VALUES (?, ?, ?, ?, ?)",
                (time.time(), source, kind, message, value),
            )
            self._db.commit()

    # ---- live reads ----------------------------------------------------
    def history(self, source: str, minutes: float, after: float | None = None) -> list[dict]:
        since = max(time.time() - minutes * 60, after or 0)
        with self._lock:
            rows = self._db.execute(
                f"SELECT ts, {_COLS} FROM metrics WHERE source = ? AND ts > ? ORDER BY ts",
                (source, since),
            ).fetchall()
        return [dict(zip(("ts", *METRIC_FIELDS), r)) for r in rows]

    def events(self, source: str, limit: int) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT ts, kind, message, value FROM events WHERE source = ? ORDER BY ts DESC LIMIT ?",
                (source, limit),
            ).fetchall()
        return [dict(zip(EVENT_FIELDS, r)) for r in rows]

    # ---- report reads --------------------------------------------------
    def samples(self, source: str, since: float, until: float) -> list[dict]:
        """Every stored sample in the period - the raw rows a report is built from."""
        with self._lock:
            rows = self._db.execute(
                f"SELECT ts, {_COLS} FROM metrics WHERE source = ? AND ts BETWEEN ? AND ? ORDER BY ts",
                (source, since, until),
            ).fetchall()
        return [dict(zip(("ts", *METRIC_FIELDS), r)) for r in rows]

    def events_between(self, source: str, since: float, until: float, limit: int = 500) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT ts, kind, message, value FROM events WHERE source = ? AND ts BETWEEN ? AND ? "
                "ORDER BY ts DESC LIMIT ?",
                (source, since, until, limit),
            ).fetchall()
        return [dict(zip(EVENT_FIELDS, r)) for r in rows]

    def summary(self, source: str, since: float, until: float) -> dict:
        with self._lock:
            n, first, last, people, area, queue, wait, dwell, stay, fps = self._db.execute(
                SUMMARY_SQL, (source, since, until)
            ).fetchone()
            entries = self._gained("entries", source, since, until)
            exits = self._gained("exits", source, since, until)
            peaks = {c: self._peak(c, source, since, until) for c in PEAK_FIELDS}
            by_kind = dict(
                self._db.execute(
                    "SELECT kind, COUNT(*) FROM events WHERE source = ? AND ts BETWEEN ? AND ? GROUP BY kind",
                    (source, since, until),
                ).fetchall()
            )
        span = max(until - since, 1e-9)
        return {
            "samples": n,
            "first_ts": first,
            "last_ts": last,
            # One row is written per second, so samples/seconds is the share of the
            # period this feed was actually analysed (the rest it was reconnecting).
            "coverage": round(min(n / span, 1.0), 3),
            "people_avg": _round(people),
            "people_peak": peaks["people"],
            "area_avg": _round(area),
            "area_peak": peaks["area"],
            "area_stay_avg_s": _round(stay),
            "queue_avg": _round(queue),
            "queue_peak": peaks["queue"],
            "wait_avg_s": _round(wait),
            "wait_peak_s": peaks["wait_s"],
            "dwell_avg_s": _round(dwell),
            "fps_avg": _round(fps),
            "entries": int(entries),
            "exits": int(exits),
            "alerts": sum(by_kind.values()),
            "alerts_by_kind": by_kind,
        }

    def series(self, source: str, since: float, until: float, buckets: int = 120) -> list[dict]:
        """The period downsampled to at most `buckets` points, so 24 h is still one chart."""
        step = max(1.0, (until - since) / max(buckets, 1))
        with self._lock:
            rows = self._db.execute(
                "SELECT MIN(ts), AVG(people), AVG(area), AVG(queue), MAX(queue) "
                "FROM metrics WHERE source = ? AND ts BETWEEN ? AND ? "
                "GROUP BY CAST((ts - ?) / ? AS INTEGER) ORDER BY 1",
                (source, since, until, since, step),
            ).fetchall()
        return _points(rows, step)

    # called with the lock held
    def _gained(self, column: str, source: str, since: float, until: float) -> float:
        return self._db.execute(GAINED_SQL.format(col=column), (source, since, until)).fetchone()[0]

    def _peak(self, column: str, source: str, since: float, until: float) -> dict | None:
        row = self._db.execute(
            f"SELECT ts, {column} FROM metrics "
            f"WHERE source = ? AND ts BETWEEN ? AND ? AND {column} IS NOT NULL "
            f"ORDER BY {column} DESC, ts LIMIT 1",
            (source, since, until),
        ).fetchone()
        return {"value": _round(row[1]), "ts": row[0]} if row else None

    # ---- across every feed ---------------------------------------------
    def totals(self, sources: list[str], since: float, until: float) -> dict:
        if not sources:
            return {"people_avg": None, "people_peak": None}
        with self._lock:
            avg, peak, peak_ts = self._db.execute(
                f"WITH per_second AS ({PER_SECOND_SQL.format(marks=_marks(sources))}) "
                "SELECT AVG(people), MAX(people), "
                "(SELECT sec FROM per_second ORDER BY people DESC, sec LIMIT 1) FROM per_second",
                (*sources, since, until),
            ).fetchone()
        if avg is None:
            return {"people_avg": None, "people_peak": None}
        return {"people_avg": _round(avg), "people_peak": {"value": _round(peak), "ts": peak_ts}}

    def totals_series(self, sources: list[str], since: float, until: float, buckets: int = 120) -> list[dict]:
        if not sources:
            return []
        step = max(1.0, (until - since) / max(buckets, 1))
        with self._lock:
            rows = self._db.execute(
                f"WITH per_second AS ({PER_SECOND_SQL.format(marks=_marks(sources))}) "
                "SELECT MIN(sec), AVG(people), AVG(area), AVG(queue), MAX(queue) FROM per_second "
                "GROUP BY CAST((sec - ?) / ? AS INTEGER) ORDER BY 1",
                (*sources, since, until, since, step),
            ).fetchall()
        return _points(rows, step)
