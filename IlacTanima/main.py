import sys
from pathlib import Path

# PyQt5 ile DLL çakışmasını önlemek için torch önce yüklenmeli (Windows)
try:
    import torch
except Exception:
    pass

# Veritabanı yoksa otomatik oluştur
import config
if not config.DB_PATH.exists() or config.DB_PATH.stat().st_size < 1024:
    print("Veritabanı oluşturuluyor...")
    from scripts.build_database import main as build_db
    build_db()

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from src.ui.main_window import MainWindow


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps,    True)

    app = QApplication(sys.argv)
    app.setApplicationName("İlaç Tanıma Sistemi")
    app.setApplicationVersion("2.0")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
