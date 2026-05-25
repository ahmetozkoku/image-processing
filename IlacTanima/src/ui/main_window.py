import time
import cv2
import sys
import numpy as np
from queue import Queue, Empty
from typing import Optional, List

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui  import QImage, QPixmap
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QSlider, QFrame, QSizePolicy,
    QStatusBar, QListWidget, QScrollArea, QApplication,
)

from src.ui.styles import DARK_THEME
from src.detection.detector    import DrugDetector, Detection
from src.detection.ocr_reader  import OCRReader
from src.detection.barcode_reader import BarcodeReader
from src.database.drug_db import DrugDatabase, Drug
import config


# ─── Camera thread: sadece yakalar, tam hızda emit eder ───────────────────────

class CameraThread(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    error       = pyqtSignal(str)

    def __init__(self, index: int = 0):
        super().__init__()
        self._index   = index
        self._running = False

    def run(self):
        cap = None
        for idx in [self._index, 1, 2, 0]:
            test = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if test.isOpened():
                ok, _ = test.read()
                if ok:
                    cap = test
                    break
                test.release()
            else:
                test.release()

        if cap is None:
            self.error.emit("Kamera açılamadı — başka uygulama kullanıyor olabilir.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, config.TARGET_FPS)

        self._running = True
        interval = 1.0 / config.TARGET_FPS
        while self._running:
            t0 = time.time()
            ok, frame = cap.read()
            if not ok:
                break
            # Flip YAPMA — OCR/barkod için yazılar düzgün yönde olmalı
            self.frame_ready.emit(frame)
            # FPS limiti — event queue'nun dolmasını önler
            elapsed = time.time() - t0
            wait = interval - elapsed
            if wait > 0:
                self.msleep(int(wait * 1000))
        cap.release()

    def stop(self):
        self._running = False
        self.wait(2000)


# ─── Detection thread: YOLO + barkod ayrı CPU thread'de ──────────────────────

class DetectionThread(QThread):
    # detections, barcode, ocr_text — hepsi bu thread'de, UI bloke olmaz
    result_ready = pyqtSignal(list, object, object)

    def __init__(self, detector: DrugDetector, barcode_reader: BarcodeReader,
                 ocr_reader: OCRReader):
        super().__init__()
        self._detector = detector
        self._barcode  = barcode_reader
        self._ocr      = ocr_reader
        self._queue: Queue = Queue(maxsize=1)
        self._running = False
        self._ocr_counter = 0

    def submit(self, frame: np.ndarray):
        try:
            self._queue.put_nowait(frame.copy())
        except Exception:
            pass

    def run(self):
        self._running = True
        while self._running:
            try:
                frame = self._queue.get(timeout=0.1)
            except Empty:
                continue

            # 1. Barkod — her seferinde dene (hızlı)
            barcode = self._barcode.scan(frame)

            # 2. YOLO — sadece NEREDE olduğunu bul, sınıf adını kullanma
            detections = []
            try:
                detections = self._detector.detect(frame)
            except Exception:
                pass

            # 3. OCR — her N iterasyonda, YOLO kutusundan veya tam frame'den
            ocr_text = None
            self._ocr_counter += 1
            if self._ocr_counter >= config.OCR_EVERY_N_FRAMES:
                self._ocr_counter = 0
                try:
                    if detections:
                        # En büyük tespit kutusunu kullan (daha fazla yazı içerir)
                        biggest = max(detections, key=lambda d:
                            (d.box[2]-d.box[0]) * (d.box[3]-d.box[1]))
                        region = biggest.crop
                    else:
                        # Kutu bulunamazsa orta bölgeyi dene
                        h, w = frame.shape[:2]
                        region = frame[h//4: 3*h//4, w//4: 3*w//4]

                    raw = self._ocr.read_text(region)
                    if raw:
                        ocr_text = self._ocr.extract_drug_name(raw)
                except Exception:
                    pass

            self.result_ready.emit(detections, barcode, ocr_text)

    def stop(self):
        self._running = False
        self.wait(3000)


# ─── Yardımcı ─────────────────────────────────────────────────────────────────

def frame_to_pixmap(frame: np.ndarray) -> QPixmap:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    # .copy() kritik — QImage buffer'ı numpy array silinmeden önce kopyalamalı
    img = QImage(rgb.tobytes(), w, h, ch * w, QImage.Format_RGB888)
    return QPixmap.fromImage(img)

def _lbl(text: str, obj_name: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName(obj_name)
    lbl.setWordWrap(True)
    return lbl


# ─── Ana pencere ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.WINDOW_TITLE)
        self.setMinimumSize(config.WINDOW_W, config.WINDOW_H)
        self.setStyleSheet(DARK_THEME)

        # Bileşenler
        model_path = config.MODEL_PATH if config.MODEL_PATH.exists() else config.ALT_MODEL_PATH
        self.detector = DrugDetector(str(model_path), config.DETECTION_CONF)
        self.ocr      = OCRReader()
        self.barcode  = BarcodeReader()
        self.db       = DrugDatabase(str(config.DB_PATH))

        # Durum
        self._fps_frames   = 0
        self._fps_time     = time.time()
        self._submit_count = 0
        self._last_detections: List[Detection] = []
        self._last_barcode: Optional[str]      = None
        self._current_drug: Optional[Drug]     = None
        self._history: list = []

        self._build_ui()
        QTimer.singleShot(300, self._start_threads)

        fps_timer = QTimer(self)
        fps_timer.timeout.connect(self._update_fps)
        fps_timer.start(1000)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)
        root.addLayout(self._build_left(),  stretch=6)
        root.addLayout(self._build_right(), stretch=4)

        sb = QStatusBar()
        self.setStatusBar(sb)
        self._fps_lbl    = QLabel("FPS: --")
        self._detect_lbl = QLabel("Tespit: 0")
        self._model_lbl  = QLabel(f"Model: {config.MODEL_PATH.name}")
        sb.addWidget(self._fps_lbl)
        sb.addWidget(QLabel(" | "))
        sb.addWidget(self._detect_lbl)
        sb.addPermanentWidget(self._model_lbl)

    def _build_left(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.addWidget(_lbl("📷  CANLI KAMERA", "section_header"))

        self.camera_label = QLabel("Kamera başlatılıyor...")
        self.camera_label.setObjectName("camera_label")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.camera_label.setMinimumSize(480, 360)
        layout.addWidget(self.camera_label, stretch=1)

        ctrl = QHBoxLayout()
        self.start_btn = QPushButton("▶  Başlat")
        self.start_btn.clicked.connect(self._start_threads)
        self.start_btn.setEnabled(False)

        self.stop_btn = QPushButton("■  Durdur")
        self.stop_btn.setObjectName("stop_btn")
        self.stop_btn.clicked.connect(self._stop_threads)

        conf_lbl = QLabel("Güven:")
        conf_lbl.setObjectName("section_header")
        self.conf_val_lbl = QLabel(f"{int(config.DETECTION_CONF * 100)}%")

        self.conf_slider = QSlider(Qt.Horizontal)
        self.conf_slider.setRange(30, 95)
        self.conf_slider.setValue(int(config.DETECTION_CONF * 100))
        self.conf_slider.setFixedWidth(110)
        self.conf_slider.valueChanged.connect(self._on_conf_change)

        ctrl.addWidget(self.start_btn)
        ctrl.addWidget(self.stop_btn)
        ctrl.addStretch()
        ctrl.addWidget(conf_lbl)
        ctrl.addWidget(self.conf_slider)
        ctrl.addWidget(self.conf_val_lbl)
        layout.addLayout(ctrl)
        return layout

    def _build_right(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(10)

        self.status_badge = _lbl("🔍  TARAMA BEKLENİYOR", "status_badge")
        self.status_badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_badge)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        card_widget = QWidget()
        card_layout = QVBoxLayout(card_widget)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)

        frame = QFrame()
        frame.setObjectName("info_card")
        fl = QVBoxLayout(frame)
        fl.setSpacing(8)

        self.drug_name_lbl  = _lbl("—", "drug_name")
        fl.addWidget(self.drug_name_lbl)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        fl.addWidget(sep)

        self.active_ing_lbl = self._field(fl, "ETKİN MADDE")
        self.company_lbl    = self._field(fl, "FİRMA")
        self.dosage_lbl     = self._field(fl, "DOZAJ")
        self.atc_lbl        = self._field(fl, "ATC KODU")
        self.rx_lbl         = self._field(fl, "REÇETE TÜRÜ")
        self.sgk_lbl        = self._sgk_field(fl)
        self.barcode_val_lbl= self._field(fl, "BARKOD")

        card_layout.addWidget(frame)

        self.warnings_lbl = QLabel("")
        self.warnings_lbl.setObjectName("warnings_text")
        self.warnings_lbl.setWordWrap(True)
        self.warnings_lbl.hide()
        card_layout.addWidget(self.warnings_lbl)

        card_layout.addWidget(_lbl("SON TESPİTLER", "section_header"))
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(120)
        card_layout.addWidget(self.history_list)
        card_layout.addStretch()

        scroll.setWidget(card_widget)
        layout.addWidget(scroll, stretch=1)
        return layout

    def _field(self, parent_layout, header: str) -> QLabel:
        parent_layout.addWidget(_lbl(header, "section_header"))
        val = _lbl("—", "field_value")
        parent_layout.addWidget(val)
        return val

    def _sgk_field(self, parent_layout) -> QLabel:
        parent_layout.addWidget(_lbl("SGK DURUMU", "section_header"))
        lbl = QLabel("—"); lbl.setObjectName("sgk_unknown")
        parent_layout.addWidget(lbl)
        return lbl

    # ── Thread kontrolü ───────────────────────────────────────────────────────

    def _start_threads(self):
        self.cam_thread = CameraThread(config.CAMERA_INDEX)
        self.cam_thread.frame_ready.connect(self._on_frame)
        self.cam_thread.error.connect(self._on_camera_error)
        self.cam_thread.start()

        self.det_thread = DetectionThread(self.detector, self.barcode, self.ocr)
        self.det_thread.result_ready.connect(self._on_detection)
        self.det_thread.start()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _stop_threads(self):
        if hasattr(self, 'cam_thread'): self.cam_thread.stop()
        if hasattr(self, 'det_thread'): self.det_thread.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.camera_label.setText("Kamera durduruldu")

    def _on_camera_error(self, msg: str):
        self.camera_label.setText(f"⚠  {msg}")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _on_conf_change(self, val: int):
        self.detector.conf_threshold = val / 100
        self.conf_val_lbl.setText(f"{val}%")

    # ── Frame işleme: sadece göster + DetectionThread'e besle ────────────────

    def _on_frame(self, frame: np.ndarray):
        self._fps_frames += 1
        self._submit_count += 1

        # Her 5 frame'de bir YOLO'ya gönder (CPU'da ~6 FPS detection, 30 FPS görüntü)
        if self._submit_count % 5 == 0:
            self.det_thread.submit(frame)

        # Detection kutularını orijinal (düz) frame üzerine çiz
        annotated = self.detector.annotate(frame, self._last_detections)
        if self._last_barcode:
            cv2.putText(annotated, f"  {self._last_barcode[:24]}",
                        (10, annotated.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 220, 80), 1, cv2.LINE_AA)

        # Ekranda ayna gibi göster (kullanıcı doğal hisseder)
        display = cv2.flip(annotated, 1)

        lw = self.camera_label.width()  or 640
        lh = self.camera_label.height() or 480
        pixmap = frame_to_pixmap(display)
        self.camera_label.setPixmap(
            pixmap.scaled(lw, lh, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    # ── Detection sonucu (DetectionThread'den gelir) ──────────────────────────

    def _on_detection(self, detections: list, barcode: object, ocr_text: object):
        self._last_detections = detections
        self._last_barcode    = barcode if isinstance(barcode, str) else None
        self._detect_lbl.setText(f"Tespit: {len(detections)} kutu")

        found: Optional[Drug] = None

        # 1. Barkod — en güvenilir
        if self._last_barcode:
            found = self.db.search_by_barcode(self._last_barcode)

        # 2. OCR metni — YOLO sınıf adını KULLANMA (o sadece 12 ilacı biliyor)
        if not found and isinstance(ocr_text, str) and ocr_text:
            found = self.db.search_by_name(ocr_text)

        if found:
            self._update_drug_card(found)

    # ── İlaç bilgi kartı ─────────────────────────────────────────────────────

    def _update_drug_card(self, drug: Drug):
        if self._current_drug and self._current_drug.name == drug.name:
            return
        self._current_drug = drug

        self.status_badge.setText("✅  İLAÇ TESPİT EDİLDİ")
        self.status_badge.setProperty("active", "true")
        self.status_badge.setStyle(self.status_badge.style())

        self.drug_name_lbl.setText(drug.name or "—")
        self.active_ing_lbl.setText(drug.active_ingredient or "—")
        self.company_lbl.setText(drug.company or "—")
        self.dosage_lbl.setText(drug.dosage or "—")
        self.atc_lbl.setText(drug.atc_code or "—")
        self.rx_lbl.setText(drug.prescription_type or "—")
        self.barcode_val_lbl.setText(drug.barcode or "—")

        sgk = drug.sgk_status or "Bilinmiyor"
        if "geri ödeni" in sgk.lower() or sgk == "Evet":
            self.sgk_lbl.setText(f"✔  {sgk}")
            self.sgk_lbl.setObjectName("sgk_yes")
        elif "ödenm" in sgk.lower() or sgk == "Hayır":
            self.sgk_lbl.setText(f"✘  {sgk}")
            self.sgk_lbl.setObjectName("sgk_no")
        else:
            self.sgk_lbl.setText(sgk)
            self.sgk_lbl.setObjectName("sgk_unknown")
        self.sgk_lbl.setStyle(self.sgk_lbl.style())

        if drug.warnings:
            self.warnings_lbl.setText(f"⚠  {drug.warnings}")
            self.warnings_lbl.show()
        else:
            self.warnings_lbl.hide()

        if drug.name not in self._history:
            self._history.insert(0, drug.name)
            self._history = self._history[:20]
            self.history_list.insertItem(0, drug.name)
            while self.history_list.count() > 20:
                self.history_list.takeItem(20)

    # ── FPS sayacı ────────────────────────────────────────────────────────────

    def _update_fps(self):
        elapsed = time.time() - self._fps_time
        fps = self._fps_frames / elapsed if elapsed > 0 else 0
        self._fps_lbl.setText(f"FPS: {fps:.0f}")
        self._fps_frames = 0
        self._fps_time   = time.time()

    # ── Kapat ────────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._stop_threads()
        event.accept()
