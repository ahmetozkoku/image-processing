DARK_THEME = """
* {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QMainWindow, QWidget {
    background-color: #0d0d1a;
    color: #dde2f0;
}

/* ── Camera panel ── */
QLabel#camera_label {
    background-color: #000000;
    border: 2px solid #2a2a6a;
    border-radius: 10px;
}

/* ── Info card ── */
QFrame#info_card {
    background-color: #13132b;
    border: 1px solid #2a2a6a;
    border-radius: 10px;
    padding: 6px;
}

QFrame#info_card[detected="true"] {
    border: 1px solid #4466ff;
}

/* ── Status badge ── */
QLabel#status_badge {
    background-color: #1e1e40;
    color: #8888bb;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    letter-spacing: 1px;
}
QLabel#status_badge[active="true"] {
    background-color: #1a3a1a;
    color: #55ee88;
}

/* ── Drug name ── */
QLabel#drug_name {
    font-size: 22px;
    font-weight: bold;
    color: #7799ff;
}

/* ── Section headers ── */
QLabel#section_header {
    font-size: 10px;
    color: #666699;
    letter-spacing: 2px;
    text-transform: uppercase;
}

/* ── Field values ── */
QLabel#field_value {
    color: #ccd0ee;
    font-size: 13px;
}

/* ── SGK labels ── */
QLabel#sgk_yes {
    color: #44ee88;
    font-weight: bold;
    font-size: 13px;
}
QLabel#sgk_no {
    color: #ff6655;
    font-weight: bold;
    font-size: 13px;
}
QLabel#sgk_unknown {
    color: #aaaacc;
    font-size: 13px;
}

/* ── Warnings ── */
QLabel#warnings_text {
    color: #ffcc66;
    background-color: #1e1900;
    border: 1px solid #443300;
    border-radius: 6px;
    padding: 8px;
    font-size: 12px;
}

/* ── Barcode strip ── */
QLabel#barcode_label {
    color: #556688;
    font-family: 'Consolas', monospace;
    font-size: 11px;
}

/* ── Buttons ── */
QPushButton {
    background-color: #3344cc;
    color: #ffffff;
    border: none;
    border-radius: 7px;
    padding: 8px 22px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover  { background-color: #5566ee; }
QPushButton:pressed{ background-color: #2233aa; }
QPushButton:disabled { background-color: #222244; color: #666688; }

QPushButton#stop_btn {
    background-color: #882222;
}
QPushButton#stop_btn:hover  { background-color: #cc3333; }
QPushButton#stop_btn:pressed{ background-color: #661111; }

/* ── Slider ── */
QSlider::groove:horizontal {
    background: #1e1e3e;
    height: 6px;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #4455dd;
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QSlider::sub-page:horizontal { background: #4455dd; border-radius: 3px; }

/* ── Status bar ── */
QStatusBar {
    background-color: #08081a;
    color: #555577;
    border-top: 1px solid #1a1a3a;
    font-size: 11px;
}

/* ── Separator ── */
QFrame[frameShape="4"],   /* HLine */
QFrame[frameShape="5"] {  /* VLine */
    color: #1e1e3e;
}

/* ── History list ── */
QListWidget {
    background-color: #0d0d1a;
    border: 1px solid #1e1e3e;
    border-radius: 6px;
    color: #9999bb;
    font-size: 12px;
}
QListWidget::item:selected {
    background-color: #1e2050;
    color: #dde2f0;
}

/* ── Scrollbar ── */
QScrollBar:vertical {
    background: #0d0d1a;
    width: 8px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #2a2a6a;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0; }
"""
