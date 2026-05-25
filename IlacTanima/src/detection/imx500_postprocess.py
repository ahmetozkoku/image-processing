"""
IMX500 YOLO çıktı post-processor.

IMX500, inference sonuçlarını frame metadata'sı olarak döner.
Bu modül ham tensörleri Detection nesnelerine dönüştürür.

Desteklenen YOLO output formatları:
  Format A: (1, 4+C, N)  — ultralytics YOLOv8 ONNX default
  Format B: (1, N, 4+C)  — transposed
  Format C: (1, N, 6)    — cihazda NMS uygulanmış [x1,y1,x2,y2,conf,cls]
  Format D: (N, 6)        — batch dim yok

Koordinatlar normalize edilmiş [0,1] aralığındadır.
"""

from __future__ import annotations

import numpy as np
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.detection.detector import Detection


def postprocess_yolo(
    outputs: list,
    conf_threshold: float,
    img_w: int,
    img_h: int,
    frame_bgr: np.ndarray,
    iou_threshold: float = 0.45,
) -> List["Detection"]:
    from src.detection.detector import Detection

    if not outputs or outputs[0] is None:
        return []

    pred: np.ndarray = outputs[0].astype(np.float32)

    # Batch dim kaldır
    if pred.ndim == 3:
        pred = pred[0]

    if pred.ndim == 1:
        return []

    rows, cols = pred.shape

    # Format C/D: (N, 6) — zaten NMS uygulanmış
    if cols == 6:
        boxes_xyxy = pred[:, :4]
        confs      = pred[:, 4]
        class_ids  = pred[:, 5].astype(int)

    # Format A: (4+C, N) — sütun sayısı satır sayısından az → transpose
    elif rows < cols:
        pred = pred.T
        rows, cols = pred.shape
        boxes_cxcywh = pred[:, :4]
        class_scores  = pred[:, 4:]
        class_ids     = np.argmax(class_scores, axis=1)
        confs         = class_scores[np.arange(rows), class_ids]
        boxes_xyxy    = _cxcywh_to_xyxy(boxes_cxcywh)

    # Format B: (N, 4+C)
    else:
        boxes_cxcywh = pred[:, :4]
        class_scores  = pred[:, 4:]
        class_ids     = np.argmax(class_scores, axis=1)
        confs         = class_scores[np.arange(rows), class_ids]
        boxes_xyxy    = _cxcywh_to_xyxy(boxes_cxcywh)

    # Güven eşiği filtresi
    mask = confs >= conf_threshold
    if not np.any(mask):
        return []
    boxes_xyxy = boxes_xyxy[mask]
    confs      = confs[mask]
    class_ids  = class_ids[mask]

    # Piksel koordinatlarına çevir (normalize → pixel)
    scale = np.array([img_w, img_h, img_w, img_h], dtype=np.float32)
    boxes_px = boxes_xyxy * scale
    boxes_px = np.clip(boxes_px, [0, 0, 0, 0], [img_w, img_h, img_w, img_h])

    # NMS
    keep = _nms(boxes_px, confs, iou_threshold)

    detections: List[Detection] = []
    for i in keep:
        x1, y1, x2, y2 = map(int, boxes_px[i])
        crop = frame_bgr[y1:y2, x1:x2].copy() if frame_bgr is not None and x2 > x1 and y2 > y1 else np.array([])
        detections.append(Detection(
            box=(x1, y1, x2, y2),
            confidence=float(confs[i]),
            class_name=str(int(class_ids[i])),
            crop=crop,
        ))

    return detections


def annotate_frame(frame_bgr: np.ndarray, detections: list, barcode: Optional[str]) -> np.ndarray:
    annotated = frame_bgr.copy()
    color = (72, 138, 255)
    for det in detections:
        x1, y1, x2, y2 = det.box
        cv2_rect(annotated, (x1, y1), (x2, y2), color, 2)
        label = f"{det.confidence:.0%}"
        _put_label(annotated, label, x1, y1, color)

    if barcode:
        import cv2
        h = annotated.shape[0]
        cv2.putText(annotated, f"  {barcode[:24]}",
                    (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (80, 220, 80), 1, cv2.LINE_AA)
    return annotated


# ── İç yardımcılar ────────────────────────────────────────────────────────────

def _cxcywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    cx, cy, w, h = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    return np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> List[int]:
    order = np.argsort(scores)[::-1]
    keep: List[int] = []
    while len(order):
        i = int(order[0])
        keep.append(i)
        if len(order) == 1:
            break
        iou = _iou(boxes[i], boxes[order[1:]])
        order = order[1:][iou < iou_threshold]
    return keep


def _iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])
    inter = np.maximum(0.0, x2 - x1) * np.maximum(0.0, y2 - y1)
    area1 = (box[2] - box[0]) * (box[3] - box[1])
    area2 = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return inter / (area1 + area2 - inter + 1e-6)


def cv2_rect(img, pt1, pt2, color, thickness):
    import cv2
    cv2.rectangle(img, pt1, pt2, color, thickness)


def _put_label(img, text, x1, y1, color):
    import cv2
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    cv2.rectangle(img, (x1, y1 - th - 8), (x1 + tw + 6, y1), color, -1)
    cv2.putText(img, text, (x1 + 3, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
