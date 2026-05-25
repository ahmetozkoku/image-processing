#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# convert_model.sh — YOLO .pt → IMX500 .rpk dönüşüm scripti
#
# BU SCRIPT GELİŞTİRME MAKİNENİZDE ÇALIŞTIRILIR (Pi'de değil).
# Python 3.10+, CUDA opsiyonel. ~20-60 dakika sürebilir.
#
# Adımlar:
#   1. best.pt → best.onnx  (ultralytics)
#   2. best.onnx → INT8 quantize  (Sony MCT)
#   3. INT8 model → best.rpk  (imx500-tools Docker)
#   4. best.rpk → Pi'ye kopyala
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MODEL_PT="$PROJECT_DIR/best.pt"
MODEL_DIR="$PROJECT_DIR/models"
IMGSZ=320    # IMX500 için 320 veya 640 — küçük model daha hızlı

mkdir -p "$MODEL_DIR"

echo "======================================================="
echo "  YOLO → IMX500 Model Dönüşümü"
echo "  Kaynak: $MODEL_PT"
echo "  Hedef : $MODEL_DIR/best.rpk"
echo "  İmgSz : ${IMGSZ}x${IMGSZ}"
echo "======================================================="

# ── Bağımlılık kontrolleri ───────────────────────────────────────────────────
command -v python3 >/dev/null 2>&1 || { echo "HATA: python3 bulunamadı"; exit 1; }
command -v docker  >/dev/null 2>&1 || { echo "HATA: docker bulunamadı (adım 3 için gerekli)"; exit 1; }

if [ ! -f "$MODEL_PT" ]; then
    echo "HATA: best.pt bulunamadı: $MODEL_PT"
    exit 1
fi

# ── Adım 1: ONNX export ──────────────────────────────────────────────────────
echo ""
echo "[1/4] best.pt → best.onnx dönüştürülüyor..."

python3 - <<PYEOF
from ultralytics import YOLO
model = YOLO("$MODEL_PT")
model.export(
    format="onnx",
    imgsz=$IMGSZ,
    opset=11,          # IMX500 toolchain opset 11 destekler
    simplify=True,
    dynamic=False,
)
print("ONNX export tamamlandı.")
PYEOF

# ultralytics best.onnx'i best.pt ile aynı dizine yazar
ONNX_SRC="${MODEL_PT%.pt}.onnx"
ONNX_DST="$MODEL_DIR/best.onnx"
cp "$ONNX_SRC" "$ONNX_DST"
echo "  Kaydedildi: $ONNX_DST"

# ── Adım 2: Sony MCT ile INT8 quantization ───────────────────────────────────
echo ""
echo "[2/4] Sony Model Compression Toolkit ile INT8 quantization..."

pip install model-compression-toolkit onnx onnxruntime -q

python3 - <<PYEOF
import model_compression_toolkit as mct
import numpy as np
import onnxruntime as ort

ONNX_PATH = "$ONNX_DST"
OUTPUT_PATH = "$MODEL_DIR/best_int8.onnx"
IMGSZ = $IMGSZ

# Temsili kalibrasyon verisi — gerçek veriyle değiştirin
def representative_data_gen():
    for _ in range(20):
        yield [np.random.rand(1, 3, IMGSZ, IMGSZ).astype(np.float32)]

core_config = mct.core.CoreConfig(
    quantization_config=mct.core.QuantizationConfig(
        activation_n_bits=8,
        weights_n_bits=8,
    )
)

quantized_model, quantization_info = mct.ptq.keras_post_training_quantization(
    ONNX_PATH,
    representative_data_gen,
    core_config=core_config,
    target_platform_capabilities=mct.get_target_platform_capabilities("imx500"),
)

import onnx
onnx.save(quantized_model, OUTPUT_PATH)
print(f"INT8 model kaydedildi: {OUTPUT_PATH}")
PYEOF

# ── Adım 3: IMX500 .rpk compile (Docker ile) ─────────────────────────────────
echo ""
echo "[3/4] IMX500 .rpk derleniyor (Docker)..."
echo "  (Raspberry Pi imx500-tools Docker image kullanılıyor)"

docker run --rm \
    -v "$MODEL_DIR:/models" \
    ghcr.io/raspberrypi/imx500-tools:latest \
    imx500-package \
        --network /models/best_int8.onnx \
        --output /models/best.rpk

echo "  RPK dosyası hazır: $MODEL_DIR/best.rpk"

# ── Adım 4: Pi'ye kopyala ────────────────────────────────────────────────────
echo ""
echo "[4/4] Pi'ye kopyalama..."
echo ""

PI_IP="${PI_IP:-}"   # PI_IP=192.168.x.x ./convert_model.sh ile override edilebilir

if [ -n "$PI_IP" ]; then
    echo "  Pi'ye gönderiliyor: $PI_IP"
    scp "$MODEL_DIR/best.rpk" "pi@$PI_IP:/home/pi/ilac-tanima/IlacTanima/models/best.rpk"
    echo "  Transfer tamamlandı!"
else
    echo "  Otomatik transfer atlandı."
    echo "  Manuel kopyalama:"
    echo "    scp $MODEL_DIR/best.rpk pi@<PI_IP>:/home/pi/ilac-tanima/IlacTanima/models/best.rpk"
fi

echo ""
echo "======================================================="
echo "  Dönüşüm tamamlandı!"
echo "  - best.onnx (CPU fallback): $ONNX_DST"
echo "  - best.rpk  (IMX500 NPU) : $MODEL_DIR/best.rpk"
echo "======================================================="
