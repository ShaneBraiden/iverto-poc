"""Draws tracked people, zones, the entrance line, and optional blur / heatmap."""
import dataclasses

import cv2
import numpy as np
import supervision as sv

# Overlay colours match the dashboard theme (docs/frontend-design-style.md).
NEUTRAL = sv.Color.from_hex("#d9d9d6")
AREA = sv.Color.from_hex("#3b82f6")   # blue-500
QUEUE = sv.Color.from_hex("#e91e63")  # brand magenta
LINE = sv.Color.from_hex("#10b981")   # success
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _chip(img, text, x, y, color: sv.Color, scale=0.55):
    (tw, th), base = cv2.getTextSize(text, FONT, scale, 1)
    pad = 6
    h, w = img.shape[:2]
    x = int(np.clip(x, 0, w - tw - 2 * pad))
    y = int(np.clip(y, th + 2 * pad, h))
    cv2.rectangle(img, (x, y - th - 2 * pad), (x + tw + 2 * pad, y), color.as_bgr(), -1)
    cv2.putText(img, text, (x + pad, y - pad), FONT, scale, (255, 255, 255), 1, cv2.LINE_AA)


class Heatmap:
    """Where people walk/stand: foot positions accumulated at 1/4 resolution (cheap enough to run always)."""

    SCALE = 4

    def __init__(self):
        self.acc = None

    def update(self, dets: sv.Detections, shape):
        h, w = shape[0] // self.SCALE, shape[1] // self.SCALE
        if self.acc is None or self.acc.shape != (h, w):
            self.acc = np.zeros((h, w), np.float32)
        stamp = np.zeros_like(self.acc)
        for x, y in (dets.get_anchors_coordinates(sv.Position.BOTTOM_CENTER) / self.SCALE).astype(int):
            cv2.circle(stamp, (int(x), int(y)), 6, 1.0, -1)
        self.acc += stamp

    def render(self, img):
        if self.acc is None or not self.acc.any():
            return img
        heat = cv2.GaussianBlur(self.acc, (0, 0), 4)
        heat = (255 * np.sqrt(heat / heat.max())).astype(np.uint8)  # sqrt keeps walkways visible next to hotspots
        heat = cv2.resize(heat, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_LINEAR)
        color = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
        mask = heat > 40
        np.copyto(img, cv2.addWeighted(img, 0.6, color, 0.4, 0), where=mask[..., None])
        return img


class Annotator:
    def __init__(self):
        palette = sv.ColorPalette([NEUTRAL, AREA, QUEUE])
        self.box = sv.BoxAnnotator(color=palette, thickness=2, color_lookup=sv.ColorLookup.CLASS)
        self.label = sv.LabelAnnotator(
            color=palette,
            text_color=sv.Color.BLACK,
            text_scale=0.4,
            text_padding=3,
            color_lookup=sv.ColorLookup.CLASS,
        )
        self.blur = sv.BlurAnnotator(kernel_size=41)
        self.heat = Heatmap()

    def reset(self):
        self.heat = Heatmap()

    def draw(self, frame, dets: sv.Detections, member: dict, analytics, metrics: dict, ts: float,
             blur=False, heatmap=False):
        out = frame.copy()
        self.heat.update(dets, frame.shape)
        if heatmap:
            out = self.heat.render(out)
        if blur and len(dets):
            out = self.blur.annotate(out, dets)

        self._shapes(out, analytics)
        if len(dets):
            cls = np.zeros(len(dets), dtype=int)
            cls[member["area"]] = 1
            cls[member["queue"]] = 2
            tagged = dataclasses.replace(dets, class_id=cls)
            labels = []
            for tid, q in zip(tagged.tracker_id, member["queue"]):
                waited = analytics.queue_timer.elapsed(tid, ts) if q else None
                labels.append(f"#{tid}" + (f"  {waited:.0f}s" if waited is not None else ""))
            out = self.box.annotate(out, tagged)
            out = self.label.annotate(out, tagged, labels)
        self._chips(out, analytics, metrics)
        return out

    def _shapes(self, img, analytics):
        polys = [(z, c) for z, c in ((analytics.area_zone, AREA), (analytics.queue_zone, QUEUE)) if z is not None]
        if polys:
            overlay = img.copy()
            for zone, color in polys:
                cv2.fillPoly(overlay, [zone.polygon], color.as_bgr())
            cv2.addWeighted(overlay, 0.15, img, 0.85, 0, dst=img)
            for zone, color in polys:
                cv2.polylines(img, [zone.polygon], True, color.as_bgr(), 2, cv2.LINE_AA)
        if analytics.line is not None:
            a, b = analytics.line.vector.start, analytics.line.vector.end
            cv2.line(img, (a.x, a.y), (b.x, b.y), LINE.as_bgr(), 3, cv2.LINE_AA)
            for p in ((a.x, a.y), (b.x, b.y)):
                cv2.circle(img, p, 6, LINE.as_bgr(), -1, cv2.LINE_AA)

    def _chips(self, img, analytics, metrics):
        if analytics.area_zone is not None:
            x, y = analytics.area_zone.polygon.min(axis=0)
            _chip(img, f"Waiting area  {metrics['area']}", x, y, AREA)
        if analytics.queue_zone is not None:
            x, y = analytics.queue_zone.polygon.min(axis=0)
            _chip(img, f"Queue  {metrics['queue']}", x, y, QUEUE)

        if analytics.line is not None:
            a, b = analytics.line.vector.start, analytics.line.vector.end
            # Arrow points to the "in" side of the line.
            mx, my = (a.x + b.x) / 2, (a.y + b.y) / 2
            dx, dy = b.x - a.x, b.y - a.y
            norm = max((dx * dx + dy * dy) ** 0.5, 1)
            nx, ny = dy / norm, -dx / norm  # LineZone counts "in" when moving to this side
            tip = (int(mx + nx * 40), int(my + ny * 40))
            cv2.arrowedLine(img, (int(mx), int(my)), tip, LINE.as_bgr(), 3, cv2.LINE_AA, tipLength=0.35)
            _chip(img, f"In {metrics['entries']}   Out {metrics['exits']}", mx + 12, my - 12, LINE)
