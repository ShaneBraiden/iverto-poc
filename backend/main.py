"""FastAPI app: per-stream MJPEG video, WebSocket live metrics for all streams, REST history/config."""
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import reporting
from pipeline.reader import can_read
from pipeline.worker import KINDS, VIDEO_EXTS, Pipeline, slugify
from storage.db import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
CFG = yaml.safe_load((BACKEND / "config" / "sources.yaml").read_text())

store = Store(ROOT / "data" / "analytics.db", CFG.get("retention_hours", 24))
pipeline = Pipeline(CFG, BACKEND / "config", store, ROOT)


@asynccontextmanager
async def lifespan(_: FastAPI):
    pipeline.start()
    yield
    pipeline.stop()


app = FastAPI(title="Crowd & Queue Analytics", lifespan=lifespan)

Point = tuple[float, float]


class Zones(BaseModel):
    line: list[Point] = Field(default_factory=list)
    queue: list[Point] = Field(default_factory=list)
    area: list[Point] = Field(default_factory=list)
    queue_limit: int | None = Field(default=None, ge=0)
    area_limit: int | None = Field(default=None, ge=0)
    hold_s: float = Field(default=3, ge=0, le=60)

    @field_validator("line", "queue", "area")
    @classmethod
    def normalized(cls, pts):
        return [(round(min(max(x, 0.0), 1.0), 4), round(min(max(y, 0.0), 1.0), 4)) for x, y in pts]

    @field_validator("line")
    @classmethod
    def two_points(cls, pts):
        if pts and len(pts) != 2:
            raise ValueError("line needs exactly 2 points")
        return pts

    @field_validator("queue", "area")
    @classmethod
    def polygon(cls, pts):
        if pts and len(pts) < 3:
            raise ValueError("polygon needs at least 3 points")
        return pts


class NewStream(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    kind: str
    uri: str = Field(min_length=1)

    @field_validator("kind")
    @classmethod
    def known_kind(cls, v):
        if v not in KINDS:
            raise ValueError(f"kind must be one of {', '.join(KINDS)}")
        return v


MAX_UPLOAD = 2 * 1024**3  # bytes


class Settings(BaseModel):
    blur: bool | None = None
    heatmap: bool | None = None


def worker(name: str):
    try:
        return pipeline.get(name)
    except KeyError:
        raise HTTPException(404, f"unknown stream {name!r}")


@app.get("/api/state")
def state():
    return pipeline.info()


@app.get("/api/streams/{name}/video")
async def video(name: str):
    src = worker(name)

    async def frames():
        seq = -1
        while True:
            jpeg, s = src.latest_jpeg()
            if jpeg is None or s == seq:
                await asyncio.sleep(0.01)
                continue
            seq = s
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"

    return StreamingResponse(
        frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/streams/{name}/thumbnail")
def thumbnail(name: str):
    """Latest annotated frame, already encoded by the worker.

    The overview grid polls this ~1x/s instead of opening one MJPEG stream per card:
    decoding every feed at full rate in the browser starves the pipeline of CPU.
    """
    jpeg, _ = worker(name).latest_jpeg()
    if jpeg is None:
        raise HTTPException(503, "no frame yet")
    return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/streams/{name}/snapshot")
def snapshot(name: str):
    jpeg = worker(name).snapshot()
    if jpeg is None:
        raise HTTPException(503, "no frame yet")
    return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.websocket("/api/ws")
async def live(ws: WebSocket):
    """Live metrics for every stream at once, so the overview stays current too."""
    await ws.accept()
    try:
        while True:
            await ws.send_json(pipeline.live())
            await asyncio.sleep(0.5)
    except (WebSocketDisconnect, RuntimeError):
        pass


@app.get("/api/streams/{name}/history")
def history(name: str, minutes: float = 10, after: float | None = None):
    worker(name)
    return store.history(name, minutes, after)


@app.get("/api/streams/{name}/events")
def events(name: str, limit: int = 20):
    worker(name)
    return store.events(name, limit)


# ---- reports ---------------------------------------------------------------
# The numbers the dashboard shows for a period, and the same numbers as CSV.
# `minutes` is capped at the retention window - anything older is already pruned.
Minutes = Query(default=60, gt=0, le=reporting.MAX_MINUTES)
CSV_DETAIL = ("summary", "samples", "events")


def csv_response(text: str, name: str):
    # utf-8-sig writes the byte-order mark Excel needs to read UTF-8 correctly.
    return Response(
        text.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )


@app.get("/api/report")
def report(minutes: float = Minutes):
    return reporting.build(store, pipeline.all(), minutes)


@app.get("/api/report.csv")
def report_csv(minutes: float = Minutes):
    data = reporting.build(store, pipeline.all(), minutes, detail=False)
    return csv_response(reporting.summary_csv(data), reporting.filename("report", "summary", data["to"]))


@app.get("/api/streams/{name}/report")
def stream_report(name: str, minutes: float = Minutes):
    return reporting.build(store, [worker(name)], minutes, name=name)


@app.get("/api/streams/{name}/report.csv")
def stream_report_csv(name: str, minutes: float = Minutes, detail: str = "samples"):
    if detail not in CSV_DETAIL:
        raise HTTPException(400, f"detail must be one of {', '.join(CSV_DETAIL)}")
    src = worker(name)
    since, until = reporting.window(minutes)
    if detail == "summary":
        text = reporting.summary_csv(reporting.build(store, [src], minutes, name=name, detail=False))
    elif detail == "events":
        text = reporting.events_csv(store.events_between(name, since, until))
    else:
        text = reporting.samples_csv(store.samples(name, since, until))
    return csv_response(text, reporting.filename(name, detail, until))


@app.put("/api/streams/{name}/zones")
def put_zones(name: str, zones: Zones):
    src = worker(name)
    src.set_zones(zones.model_dump())
    return src.zones


@app.post("/api/streams/{name}/settings")
def set_settings(name: str, body: Settings):
    src = worker(name)
    src.set_settings(**body.model_dump(exclude_none=True))
    return src.settings


@app.post("/api/streams/{name}/heatmap/reset")
def reset_heatmap(name: str):
    worker(name).reset_heatmap()
    return {"ok": True}


@app.post("/api/streams")
def add_stream(body: NewStream):
    try:
        return pipeline.add(body.label, body.kind, body.uri).info()
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/streams/upload")
async def upload_stream(request: Request, label: str = Query(min_length=1, max_length=60),
                        filename: str = Query(min_length=1, max_length=255)):
    """Add a stream from an uploaded video. The request body is the raw file, written to
    disk chunk by chunk so a large clip is never held in memory."""
    ext = Path(filename).suffix.lower()
    if ext not in VIDEO_EXTS:
        raise HTTPException(400, f"video must be one of {', '.join(VIDEO_EXTS)}")
    pipeline.upload_dir.mkdir(parents=True, exist_ok=True)
    dest = pipeline.upload_dir / f"{slugify(Path(filename).stem)}-{uuid.uuid4().hex[:8]}{ext}"
    ok = False
    try:
        size = 0
        with dest.open("wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_UPLOAD:
                    raise HTTPException(413, f"video is larger than {MAX_UPLOAD // 1024**3} GB")
                await asyncio.to_thread(f.write, chunk)
        if not await asyncio.to_thread(can_read, dest):
            raise HTTPException(400, "could not read a video from that file")
        worker = pipeline.add(label, "file", dest.relative_to(ROOT).as_posix(), upload=True)
        ok = True
        return worker.info()
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        if not ok:
            dest.unlink(missing_ok=True)


@app.delete("/api/streams/{name}")
def delete_stream(name: str):
    try:
        pipeline.remove(name)
    except KeyError:
        raise HTTPException(404, f"unknown stream {name!r}")
    return {"removed": name}


# Serve the built dashboard (frontend/dist) from the same origin when present.
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="dashboard")
