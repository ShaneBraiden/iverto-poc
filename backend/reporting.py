"""Period reports: per-feed aggregates, facility totals and CSV export.

The dashboard answers "what is happening now"; a report answers "what happened
between these two times". Both read the same per-second samples in SQLite, so a
report never re-estimates anything - it only aggregates what was measured.
"""
import csv
import io
import time
from datetime import datetime

BUCKETS = 120          # points in a report chart, whatever the period length
MAX_MINUTES = 24 * 60  # retention ceiling; older samples are pruned

SUMMARY_COLUMNS = (
    "Samples", "Coverage %",
    "People avg", "People peak", "People peak at",
    "Entries", "Exits", "Net",
    "Waiting avg", "Waiting peak", "Waiting avg stay s",
    "Queue avg", "Queue peak", "Queue peak at",
    "Est. wait avg s", "Est. wait peak s", "Service time avg s",
    "Alerts", "FPS avg",
)
BLANK_PER_FEED = 9  # the per-feed-only columns (Waiting avg .. Service time avg) in the totals row

SAMPLE_COLUMNS = (
    ("Time", None),
    ("Unix time", "ts"),
    ("People", "people"),
    ("Entries total", "entries"),
    ("Exits total", "exits"),
    ("Waiting", "area"),
    ("Queue", "queue"),
    ("Est. wait s", "wait_s"),
    ("Service time s", "dwell_s"),
    ("Waiting stay s", "area_stay_s"),
    ("FPS", "fps"),
)


def window(minutes: float, end: float | None = None) -> tuple[float, float]:
    minutes = max(1.0, min(float(minutes), MAX_MINUTES))
    until = time.time() if end is None else end
    return until - minutes * 60, until


def local(ts: float | None) -> str:
    return "" if ts is None else datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _peak(summary: dict, key: str):
    peak = summary.get(key)
    return peak["value"] if peak else None


def _peak_at(summary: dict, key: str) -> str:
    peak = summary.get(key)
    return local(peak["ts"]) if peak else ""


def feed(store, worker, since: float, until: float, *, series=True, events=True) -> dict:
    """One feed's report entry: who it is, its period summary, and optionally detail."""
    out = {
        "name": worker.name,
        "label": worker.label,
        "kind": worker.kind,
        "status": worker.status,
        "zones": {k: bool(worker.zones.get(k)) for k in ("line", "queue", "area")},
        "limits": {k: worker.zones.get(k) for k in ("queue_limit", "area_limit")},
        "summary": store.summary(worker.name, since, until),
    }
    if series:
        out["series"] = store.series(worker.name, since, until, BUCKETS)
    if events:
        out["events"] = store.events_between(worker.name, since, until)
    return out


def build(store, workers, minutes: float, *, name: str | None = None, detail=True) -> dict:
    """Report for every feed (or just `name`), plus facility-wide totals."""
    since, until = window(minutes)
    feeds = [feed(store, w, since, until, series=detail, events=detail) for w in workers]
    names = [w.name for w in workers]
    totals = store.totals(names, since, until)
    totals.update(
        feeds=len(feeds),
        entries=sum(f["summary"]["entries"] for f in feeds),
        exits=sum(f["summary"]["exits"] for f in feeds),
        alerts=sum(f["summary"]["alerts"] for f in feeds),
        samples=sum(f["summary"]["samples"] for f in feeds),
    )
    report = {
        "from": since,
        "to": until,
        "minutes": round((until - since) / 60, 2),
        "generated": until,
        "feeds": feeds,
        "totals": totals,
    }
    if name is not None:
        report["feed"] = name
    elif detail:
        report["series"] = store.totals_series(names, since, until, BUCKETS)
    return report


# ---- CSV ---------------------------------------------------------------
def _csv(header, rows) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue()


def summary_csv(report: dict) -> str:
    """One row per feed, then a facility total - the report as a spreadsheet."""
    header = ["Feed", "Source", "Status", "From", "To", *SUMMARY_COLUMNS]
    rows = []
    for f in report["feeds"]:
        s = f["summary"]
        rows.append(
            [
                f["label"],
                f["kind"],
                f["status"],
                local(report["from"]),
                local(report["to"]),
                s["samples"],
                round(s["coverage"] * 100, 1),
                s["people_avg"],
                _peak(s, "people_peak"),
                _peak_at(s, "people_peak"),
                s["entries"],
                s["exits"],
                s["entries"] - s["exits"],
                s["area_avg"],
                _peak(s, "area_peak"),
                s["area_stay_avg_s"],
                s["queue_avg"],
                _peak(s, "queue_peak"),
                _peak_at(s, "queue_peak"),
                s["wait_avg_s"],
                _peak(s, "wait_peak_s"),
                s["dwell_avg_s"],
                s["alerts"],
                s["fps_avg"],
            ]
        )
    t = report["totals"]
    if len(report["feeds"]) > 1:
        rows.append(
            [
                "All feeds",
                f"{t['feeds']} feeds",
                "",
                local(report["from"]),
                local(report["to"]),
                t["samples"],
                "",
                t["people_avg"],
                _peak(t, "people_peak"),
                _peak_at(t, "people_peak"),
                t["entries"],
                t["exits"],
                t["entries"] - t["exits"],
                *[""] * BLANK_PER_FEED,
                t["alerts"],
                "",
            ]
        )
    return _csv(header, rows)


def samples_csv(rows: list[dict]) -> str:
    """The per-second samples themselves, for anyone who wants to re-check the maths."""
    header = [c for c, _ in SAMPLE_COLUMNS]
    body = ([local(r["ts"]), round(r["ts"], 3), *(r[k] for _, k in SAMPLE_COLUMNS[2:])] for r in rows)
    return _csv(header, body)


def events_csv(rows: list[dict]) -> str:
    return _csv(
        ["Time", "Unix time", "Kind", "Message", "Value"],
        ([local(e["ts"]), round(e["ts"], 3), e["kind"], e["message"], e["value"]] for e in rows),
    )


def filename(prefix: str, detail: str, until: float) -> str:
    stamp = datetime.fromtimestamp(until).strftime("%Y%m%d-%H%M")
    return f"iverto-{prefix}-{detail}-{stamp}.csv"
