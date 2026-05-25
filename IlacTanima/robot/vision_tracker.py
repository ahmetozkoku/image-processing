"""
Kamera görüntüsünden hedef ürünü tespit eder ve konumunu hesaplar.

Mevcut IlacTanima altyapısını (YOLO + OCR + barkod + DB) kullanır.
Ek olarak robot kontrolü için piksel koordinatlarını normalize eder.
"""

import sys
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

# IlacTanima kök dizinini import path'e ekle
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

log = logging.getLogger(__name__)


@dataclass
class TargetInfo:
    found:      bool
    label:      str            # Tespit edilen ürün adı / barkod
    confidence: float          # 0.0 – 1.0
    # Merkeze göre normalize hatalar (-1.0 = tam sol, +1.0 = tam sağ)
    error_x:    float          # yatay hata
    error_y:    float          # dikey hata
    # Normalize konum (0-1 arası, sol-üst köşe referans)
    center_x:   float
    center_y:   float
    # Nesnenin görüntüdeki göreli büyüklüğü (0-1 arası)
    rel_size:   float
    # Ham piksel kutusu
    box:        Optional[tuple] = None   # (x1, y1, x2, y2)

    @classmethod
    def not_found(cls) -> "TargetInfo":
        return cls(found=False, label="", confidence=0.0,
                   error_x=0.0, error_y=0.0,
                   center_x=0.5, center_y=0.5, rel_size=0.0)


class VisionTracker:
    """
    picamera2 kamerasından görüntü alır,
    YOLO + barkod + OCR ile hedef ürünü bulur,
    robot kontrolü için konum bilgisi döner.
    """

    def __init__(self):
        from robot.config_robot import CAMERA_WIDTH, CAMERA_HEIGHT
        self._w = CAMERA_WIDTH
        self._h = CAMERA_HEIGHT

        self._cam    = None
        self._detector  = None
        self._barcode   = None
        self._ocr       = None
        self._db        = None

        self._init_camera()
        self._init_detection()

    # ── Başlatma ──────────────────────────────────────────────────────────────

    def _init_camera(self):
        try:
            from picamera2 import Picamera2
            cam = Picamera2()
            cfg = cam.create_preview_configuration(
                main={"size": (self._w, self._h), "format": "RGB888"}
            )
            cam.configure(cfg)
            cam.start()
            self._cam = cam
            log.info("Kamera başlatıldı: %dx%d", self._w, self._h)
        except Exception as exc:
            log.error("Kamera başlatılamadı: %s", exc)

    def _init_detection(self):
        try:
            import config_pi as config
            from src.detection.barcode_reader import BarcodeReader
            from src.detection.ocr_reader import OCRReader
            from src.database.drug_db import DrugDatabase

            self._barcode = BarcodeReader()
            self._ocr     = OCRReader()
            self._db      = DrugDatabase(str(config.DB_PATH))

            # YOLO — IMX500 .rpk varsa onu kullan
            model_path = config.MODEL_RPK if config.MODEL_RPK.exists() else config.MODEL_ONNX
            if model_path.exists():
                from src.detection.detector import DrugDetector
                self._detector = DrugDetector(str(model_path), config.DETECTION_CONF)
                log.info("YOLO modeli yüklendi: %s", model_path.name)
            else:
                log.warning("Model bulunamadı, sadece barkod + OCR kullanılacak.")
        except Exception as exc:
            log.error("Detection başlatma hatası: %s", exc)

    # ── Ana arayüz ────────────────────────────────────────────────────────────

    def capture_bgr(self) -> np.ndarray:
        """picamera2'den BGR frame döner."""
        if self._cam is None:
            return np.zeros((self._h, self._w, 3), dtype=np.uint8)
        frame_rgb = self._cam.capture_array()
        return cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

    def find_target(self, target_name: str) -> TargetInfo:
        """
        Frame yakalar, hedef ürünü arar.
        Önce barkod, sonra YOLO + OCR + DB eşleşmesi dener.
        """
        frame = self.capture_bgr()
        h, w  = frame.shape[:2]

        # ── 1. Barkod (en hızlı, en kesin) ───────────────────────────────────
        if self._barcode:
            barcode_val = self._barcode.scan(frame)
            if isinstance(barcode_val, str):
                drug = self._db.search_by_barcode(barcode_val) if self._db else None
                if drug and target_name.lower() in (drug.name or "").lower():
                    # Barkod bulundu ama kutu koordinatı yok → frame ortasını kullan
                    return TargetInfo(
                        found=True, label=drug.name or barcode_val,
                        confidence=1.0, error_x=0.0, error_y=0.0,
                        center_x=0.5, center_y=0.5, rel_size=0.3,
                    )

        # ── 2. YOLO kutu tespiti ──────────────────────────────────────────────
        detections = []
        if self._detector:
            try:
                detections = self._detector.detect(frame)
            except Exception:
                pass

        # ── 3. OCR ile DB eşleştir ────────────────────────────────────────────
        best_det = None
        if detections:
            # En büyük kutuya OCR uygula
            biggest = max(detections,
                          key=lambda d: (d.box[2]-d.box[0]) * (d.box[3]-d.box[1]))
            if self._ocr and self._db:
                try:
                    raw = self._ocr.read_text(biggest.crop)
                    if raw:
                        name = self._ocr.extract_drug_name(raw)
                        if name and target_name.lower() in name.lower():
                            best_det = biggest
                except Exception:
                    pass

            # OCR eşleşmedi ama YOLO'da kutu var → en iyi güveni al (ilk prototip için)
            if best_det is None and detections:
                best_det = max(detections, key=lambda d: d.confidence)

        if best_det is None:
            return TargetInfo.not_found()

        # ── Konum hesapla ─────────────────────────────────────────────────────
        x1, y1, x2, y2 = best_det.box
        cx_px = (x1 + x2) / 2
        cy_px = (y1 + y2) / 2

        center_x = cx_px / w
        center_y = cy_px / h
        error_x  = (center_x - 0.5) * 2   # -1 ... +1
        error_y  = (center_y - 0.5) * 2
        box_area = (x2 - x1) * (y2 - y1)
        rel_size = box_area / (w * h)

        return TargetInfo(
            found=True,
            label=best_det.class_name,
            confidence=best_det.confidence,
            error_x=error_x,
            error_y=error_y,
            center_x=center_x,
            center_y=center_y,
            rel_size=rel_size,
            box=best_det.box,
        )

    def annotated_frame(self, target: Optional[TargetInfo] = None) -> np.ndarray:
        """Debug için üzerine çizim yapılmış frame döner."""
        frame = self.capture_bgr()
        h, w = frame.shape[:2]

        # Merkez çizgisi
        cv2.line(frame, (w//2, 0), (w//2, h), (0, 255, 0), 1)
        cv2.line(frame, (0, h//2), (w, h//2), (0, 255, 0), 1)

        if target and target.found and target.box:
            x1, y1, x2, y2 = target.box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (72, 138, 255), 2)
            label = f"{target.label}  {target.confidence:.0%}"
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (72, 138, 255), 1, cv2.LINE_AA)
            cv2.circle(frame, (int((x1+x2)/2), int((y1+y2)/2)), 5, (0, 255, 255), -1)

        return frame

    def stop(self):
        if self._cam:
            try:
                self._cam.stop()
                self._cam.close()
            except Exception:
                pass
