"""YOLO11 person detector (COCO class 0 - no custom training needed).

One instance is shared by every stream worker: `__call__` is serialised so several
sources can run at once on a single GPU without interleaving inference.
"""
import threading
from pathlib import Path

import supervision as sv
import torch
from ultralytics import YOLO

PERSON = 0
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


class PersonDetector:
    def __init__(self, model: str = "auto", imgsz: int = 640, conf: float = 0.3):
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        if model == "auto":  # small model on GPU, nano on CPU laptops
            model = "yolo11s.pt" if self.device != "cpu" else "yolo11n.pt"
        MODELS_DIR.mkdir(exist_ok=True)
        self.name = model
        self.model = YOLO(str(MODELS_DIR / model))
        self.imgsz = imgsz
        self.conf = conf
        self.precision = 16 if self.device != "cpu" else 32
        self._lock = threading.Lock()

    def warmup(self, frame):
        self(frame)

    def __call__(self, frame) -> sv.Detections:
        with self._lock:
            result = self.model.predict(
                frame,
                classes=[PERSON],
                conf=self.conf,
                imgsz=self.imgsz,
                device=self.device,
                quantize=self.precision,
                verbose=False,
            )[0]
        return sv.Detections.from_ultralytics(result)
