"""
FastAPI uygulama giriş noktası — Raspberry Pi 5 + IMX500 için.

Başlatmak için:
    uvicorn app.main:app --host 0.0.0.0 --port 8000

veya systemd servisi:
    sudo systemctl start ilac-tanima
"""

import sys
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# IlacTanima/ kök dizinini sys.path'e ekle
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config_pi as config

# Veritabanı yoksa otomatik oluştur
if not config.DB_PATH.exists() or config.DB_PATH.stat().st_size < 1024:
    print("Veritabanı oluşturuluyor...")
    from scripts.build_database import main as build_db
    build_db()

from app.camera.imx500_cam import CameraPipeline
from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline = CameraPipeline()
    app.state.pipeline = pipeline
    pipeline.start()
    log.info("Pipeline başlatıldı — http://%s:%d", config.API_HOST, config.API_PORT)
    yield
    pipeline.stop()
    log.info("Pipeline durduruldu.")


app = FastAPI(
    title="İlaç Tanıma API",
    version="3.0",
    description="Raspberry Pi 5 + IMX500 tabanlı ilaç tanıma sistemi",
    lifespan=lifespan,
)

app.include_router(router)

# Web dashboard static dosyaları — route'lardan sonra mount edilmeli
_WEB_DIR = Path(__file__).parent / "web"
if _WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_WEB_DIR), html=True), name="web")
