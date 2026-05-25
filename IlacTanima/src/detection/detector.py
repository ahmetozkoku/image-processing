import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class Detection:
    box: tuple          # (x1, y1, x2, y2)
    confidence: float
    class_name: str
    crop: np.ndarray = field(repr=False)


class DrugDetector:
    def __init__(self, model_path: str, conf_threshold: float = 0.70):
        from ultralytics import YOLO
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Model bulunamadı: {model_path}")
        self.model = YOLO(str(path))
        self.conf_threshold = conf_threshold
        self.class_names: List[str] = []

    def detect(self, frame: np.ndarray) -> List[Detection]:
        results = self.model(frame, conf=self.conf_threshold, verbose=False)
        detections: List[Detection] = []
        for r in results:
            self.class_names = list(r.names.values())
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
                crop = frame[y1:y2, x1:x2].copy()
                detections.append(Detection(
                    box=(x1, y1, x2, y2),
                    confidence=float(box.conf[0]),
                    class_name=r.names[int(box.cls[0])],
                    crop=crop,
                ))
        return detections

    def annotate(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det.box
            color = (72, 138, 255)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"{det.class_name}  {det.confidence:.0%}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(annotated, (x1, y1 - th - 10), (x1 + tw + 8, y1), color, -1)
            cv2.putText(annotated, label, (x1 + 4, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        return annotated
