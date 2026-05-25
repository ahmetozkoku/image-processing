"""
REST + WebSocket endpoint'leri.

GET  /api/status          → Sistem durumu (çalışıyor mu, FPS, tespit sayısı)
GET  /api/scan/latest     → Son tespit sonucu (ilaç, barkod, OCR)
GET  /api/drug/{barcode}  → Doğrudan barkod ile veritabanı araması
POST /api/config          → Güven eşiği ve diğer ayarlar
GET  /api/video/stream    → MJPEG canlı video akışı
WS   /ws/live             → WebSocket: gerçek zamanlı tespit güncellemeleri
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter()


def _pipeline(request: Request):
    """FastAPI app state'inden pipeline'ı al."""
    return request.app.state.pipeline


# ── REST endpoint'leri ────────────────────────────────────────────────────────

@router.get("/api/status")
async def get_status(request: Request):
    result = _pipeline(request).get_latest_result()
    return {
        "running":    result.get("running", False),
        "fps":        result.get("fps", 0.0),
        "detections": result.get("detections", 0),
    }


@router.get("/api/scan/latest")
async def get_latest_scan(request: Request):
    return _pipeline(request).get_latest_result()


@router.get("/api/drug/{barcode}")
async def get_drug_by_barcode(barcode: str, request: Request):
    pipeline = _pipeline(request)
    # pipeline üzerinden db'ye erişim
    found = pipeline._db.search_by_barcode(barcode)
    if not found:
        raise HTTPException(status_code=404, detail="İlaç bulunamadı")
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


class ConfigPayload(BaseModel):
    conf_threshold: Optional[float] = Field(None, ge=0.1, le=0.99)


@router.post("/api/config")
async def update_config(payload: ConfigPayload, request: Request):
    pipeline = _pipeline(request)
    if payload.conf_threshold is not None:
        pipeline.conf_threshold = payload.conf_threshold
    return {"conf_threshold": pipeline.conf_threshold}


# ── MJPEG video akışı ─────────────────────────────────────────────────────────

@router.get("/api/video/stream")
async def mjpeg_stream(request: Request):
    pipeline = _pipeline(request)

    async def generate():
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        while True:
            if await request.is_disconnected():
                break
            frame = pipeline.get_latest_jpeg()
            if frame:
                yield boundary + frame + b"\r\n"
            await asyncio.sleep(1 / 30)   # ~30 fps üst sınır

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ── WebSocket canlı tespit akışı ──────────────────────────────────────────────

@router.websocket("/ws/live")
async def ws_live(websocket: WebSocket, request: Request = None):
    pipeline = websocket.app.state.pipeline
    await websocket.accept()
    log.info("WebSocket bağlandı: %s", websocket.client)
    try:
        while True:
            result = pipeline.get_latest_result()
            await websocket.send_json(result)
            await asyncio.sleep(0.1)   # 10 Hz güncelleme (görüntü ayrı MJPEG'den geliyor)
    except WebSocketDisconnect:
        log.info("WebSocket ayrıldı: %s", websocket.client)
    except Exception as exc:
        log.warning("WebSocket hatası: %s", exc)
