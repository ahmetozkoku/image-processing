"""
IMX500 kamera pipeline — picamera2 + IMX500 NPU entegrasyonu.

Tek bir arka plan thread'i:
  1. picamera2 ile frame yakalar
  2. IMX500 metadata'sından YOLO sonuçlarını alır (CPU yükü yok)
  3. CPU'da barkod + OCR çalıştırır
  4. Veritabanında ilaç araması yapar
  5. Sonucu thread-safe olarak saklar → FastAPI endpoint'leri okur
"""

from __future__ import annotations

import sys
import time
import threading
import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# Proje kök dizinini sys.path'e ekle (IlacTanima/ altından import için)
_ROOT = Path(__file__).parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config_pi as config
from src.detection.barcode_reader import BarcodeReader
from src.detection.ocr_reader import OCRReader
from src.database.drug_db import DrugDatabase
from src.detection.imx500_postprocess import postprocess_yolo, annotate_frame

log = logging.getLogger(__name__)


class CameraPipeline:
    """
    Kamera + detection pipeline'ını yönetir.
    FastAPI lifespan'inde start() / stop() çağrılır.
    """

    def __init__(self) -> None:
        self._lock    = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._latest_jpeg: Optional[bytes] = None
        self._latest_result: dict = {
            "drug":       None,
            "barcode":    None,
            "ocr_text":   None,
            "detections": 0,
            "fps":        0.0,
            "running":    False,
        }

        self._barcode = BarcodeReader()
        self._ocr     = OCRReader()
        self._db      = DrugDatabase(str(config.DB_PATH))

        self._conf_threshold = config.DETECTION_CONF
        self._ocr_counter    = 0
        self._fps_count      = 0
        self._fps_time       = time.time()
        self._fps_last       = 0.0

    # ── Dışa açık arayüz ──────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="imx500-capture")
        self._thread.start()
        log.info("CameraPipeline başlatıldı.")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=8)
        log.info("CameraPipeline durduruldu.")

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def get_latest_result(self) -> dict:
        with self._lock:
            return dict(self._latest_result)

    @property
    def conf_threshold(self) -> float:
        return self._conf_threshold

    @conf_threshold.setter
    def conf_threshold(self, value: float) -> None:
        self._conf_threshold = float(max(0.1, min(0.99, value)))

    # ── İç capture döngüsü ────────────────────────────────────────────────────

    def _capture_loop(self) -> None:
        try:
            from picamera2 import Picamera2
            from picamera2.devices.imx500 import IMX500
        except ImportError:
            log.error("picamera2 bulunamadı. 'sudo apt install python3-picamera2' çalıştırın.")
            return

        rpk = str(config.MODEL_RPK)
        log.info(f"IMX500 modeli yükleniyor: {rpk}")

        imx500  = IMX500(rpk)
        picam2  = Picamera2(imx500.camera_num)

        cam_cfg = picam2.create_preview_configuration(
            main={"size": (config.CAMERA_WIDTH, config.CAMERA_HEIGHT), "format": "RGB888"},
            controls={"FrameRate": config.TARGET_FPS},
            buffer_count=12,
        )
        imx500.show_network_fw_progress_bar()   # Firmware yükleme ilerlemesini göster
        picam2.configure(cam_cfg)
        picam2.start()

        with self._lock:
            self._latest_result["running"] = True

        log.info("Kamera başlatıldı, kare akışı başlıyor.")

        try:
            while self._running:
                request    = picam2.capture_request()
                frame_rgb  = request.make_array("main")   # (H, W, 3) RGB
                metadata   = request.get_metadata()
                raw_out    = imx500.get_outputs(metadata, add_batch=True)
                request.release()

                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                h, w      = frame_bgr.shape[:2]

                # ── IMX500 YOLO post-processing ────────────────────────────
                detections = []
                if raw_out is not None:
                    detections = postprocess_yolo(
                        raw_out,
                        conf_threshold=self._conf_threshold,
                        img_w=w, img_h=h,
                        frame_bgr=frame_bgr,
                        iou_threshold=config.IOU_THRESHOLD,
                    )

                # ── Barkod — her frame (hızlı) ────────────────────────────
                barcode_str: Optional[str] = None
                barcode_raw = self._barcode.scan(frame_bgr)
                if isinstance(barcode_raw, str):
                    barcode_str = barcode_raw

                # ── OCR — her N frame'de ──────────────────────────────────
                ocr_text: Optional[str] = None
                self._ocr_counter += 1
                if self._ocr_counter >= config.OCR_EVERY_N_FRAMES:
                    self._ocr_counter = 0
                    ocr_text = self._run_ocr(frame_bgr, detections)

                # ── Veritabanı araması ────────────────────────────────────
                drug_dict = self._lookup(barcode_str, ocr_text)

                # ── FPS hesapla ───────────────────────────────────────────
                self._fps_count += 1
                elapsed = time.time() - self._fps_time
                if elapsed >= 1.0:
                    self._fps_last  = self._fps_count / elapsed
                    self._fps_count = 0
                    self._fps_time  = time.time()

                # ── Frame'i annote et + JPEG'e dönüştür ──────────────────
                annotated = annotate_frame(frame_bgr, detections, barcode_str)
                _, jpeg_buf = cv2.imencode(
                    ".jpg", annotated,
                    [cv2.IMWRITE_JPEG_QUALITY, config.JPEG_QUALITY],
                )
                jpeg_bytes = jpeg_buf.tobytes()

                # ── Thread-safe güncelleme ────────────────────────────────
                with self._lock:
                    self._latest_jpeg = jpeg_bytes
                    self._latest_result.update({
                        "drug":       drug_dict,
                        "barcode":    barcode_str,
                        "ocr_text":   ocr_text,
                        "detections": len(detections),
                        "fps":        round(self._fps_last, 1),
                        "running":    True,
                    })

        except Exception:
            log.exception("Kamera döngüsünde hata")
        finally:
            picam2.stop()
            picam2.close()
            with self._lock:
                self._latest_result["running"] = False

    # ── Yardımcı metodlar ─────────────────────────────────────────────────────

    def _run_ocr(self, frame_bgr: np.ndarray, detections: list) -> Optional[str]:
        try:
            if detections:
                biggest = max(
                    detections,
                    key=lambda d: (d.box[2] - d.box[0]) * (d.box[3] - d.box[1]),
                )
                region = biggest.crop
            else:
                h, w   = frame_bgr.shape[:2]
                region = frame_bgr[h // 4: 3 * h // 4, w // 4: 3 * w // 4]

            raw = self._ocr.read_text(region)
            return self._ocr.extract_drug_name(raw) if raw else None
        except Exception:
            return None

    def _lookup(self, barcode: Optional[str], ocr_text: Optional[str]) -> Optional[dict]:
        found = None
        if barcode:
            found = self._db.search_by_barcode(barcode)
        if not found and isinstance(ocr_text, str) and ocr_text:
            found = self._db.search_by_name(ocr_text)
        if not found:
            return None
        return {
            "name":              found.name,
            "active_ingredient": found.active_ingredient,
            "company":           found.company,
            "dosage":            found.dosage,
            "atc_code":          found.atc_code,
            "prescription_type": found.prescription_type,
            "sgk_status":        found.sgk_status,
            "barcode":           found.barcode,
            "warnings":          found.warnings,
        }
