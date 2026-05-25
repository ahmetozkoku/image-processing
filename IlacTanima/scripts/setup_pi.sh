#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# setup_pi.sh — Raspberry Pi 5 + IMX500 kurulum scripti
#
# Kullanım:
#   chmod +x scripts/setup_pi.sh
#   ./scripts/setup_pi.sh
#
# Varsayım: script IlacTanima/ dizininden çalıştırılıyor.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/../venv"
SERVICE_NAME="ilac-tanima"

echo "============================================================"
echo "  İlaç Tanıma Sistemi — Pi 5 Kurulum Scripti"
echo "  Proje dizini: $PROJECT_DIR"
echo "============================================================"

# ── 1. Sistem paketleri ──────────────────────────────────────────────────────
echo ""
echo "[1/6] Sistem paketleri yükleniyor..."
sudo apt-get update -qq
sudo apt-get install -y \
    python3-picamera2 \
    python3-pip \
    python3-venv \
    libzbar0 \
    libzbar-dev \
    python3-opencv \
    tesseract-ocr \
    tesseract-ocr-tur \
    libcamera-apps \
    imx500-all             # IMX500 firmware + araçları

# ── 2. Python sanal ortamı ───────────────────────────────────────────────────
echo ""
echo "[2/6] Python sanal ortamı oluşturuluyor..."
# --system-site-packages: picamera2, numpy, opencv sistem paketlerinden gelir
python3 -m venv --system-site-packages "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip -q
pip install -r "$PROJECT_DIR/requirements_pi.txt" -q

echo "  Sanal ortam: $VENV_DIR"

# ── 3. models/ dizini ────────────────────────────────────────────────────────
echo ""
echo "[3/6] Dizinler kontrol ediliyor..."
mkdir -p "$PROJECT_DIR/models"
mkdir -p "$PROJECT_DIR/data"

if [ ! -f "$PROJECT_DIR/models/best.rpk" ]; then
    echo ""
    echo "  UYARI: models/best.rpk bulunamadı!"
    echo "  Modeli dönüştürmek için: scripts/convert_model.sh"
    echo "  (Önce geliştirme makinenizde çalıştırın.)"
fi

# ── 4. Veritabanı ────────────────────────────────────────────────────────────
echo ""
echo "[4/6] Veritabanı kontrol ediliyor..."
cd "$PROJECT_DIR"
if [ ! -s "data/drugs.db" ]; then
    echo "  Veritabanı oluşturuluyor (birkaç dakika sürebilir)..."
    python3 -c "from scripts.build_database import main; main()"
else
    echo "  Veritabanı mevcut, atlanıyor."
fi

# ── 5. systemd servisi ───────────────────────────────────────────────────────
echo ""
echo "[5/6] systemd servisi yapılandırılıyor..."

# Service dosyasını Pi'nin gerçek yollarına göre güncelle
SERVICE_SRC="$PROJECT_DIR/ilac-tanima.service"
SERVICE_TMP="/tmp/$SERVICE_NAME.service"

sed \
    -e "s|WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|g" \
    -e "s|ExecStart=.*uvicorn|ExecStart=$VENV_DIR/bin/uvicorn|g" \
    "$SERVICE_SRC" > "$SERVICE_TMP"

sudo cp "$SERVICE_TMP" "/etc/systemd/system/$SERVICE_NAME.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

# ── 6. Durum raporu ──────────────────────────────────────────────────────────
echo ""
echo "[6/6] Durum kontrol ediliyor..."
sleep 3
sudo systemctl status "$SERVICE_NAME" --no-pager -l || true

PI_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "============================================================"
echo "  Kurulum tamamlandı!"
echo ""
echo "  Web dashboard : http://$PI_IP:8000"
echo "  API docs      : http://$PI_IP:8000/docs"
echo "  Canlı görüntü : http://$PI_IP:8000/api/video/stream"
echo ""
echo "  Servis kontrol:"
echo "    sudo systemctl status $SERVICE_NAME"
echo "    sudo journalctl -u $SERVICE_NAME -f"
echo "============================================================"
