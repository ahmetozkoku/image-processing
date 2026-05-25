from pathlib import Path

BASE_DIR = Path(__file__).parent

# Model paths — .rpk IMX500 native, .onnx CPU fallback
MODEL_RPK  = BASE_DIR / "models" / "best.rpk"
MODEL_ONNX = BASE_DIR / "models" / "best.onnx"
DB_PATH    = BASE_DIR / "data" / "drugs.db"
DATASET_DIR = BASE_DIR / "data" / "dataset"

# Camera
CAMERA_WIDTH      = 1280
CAMERA_HEIGHT     = 720
TARGET_FPS        = 30

# Detection
DETECTION_CONF     = 0.70
IOU_THRESHOLD      = 0.45
OCR_EVERY_N_FRAMES = 25

# Web API
API_HOST = "0.0.0.0"
API_PORT = 8000

# MJPEG stream quality (0-100)
JPEG_QUALITY = 80

TITCK_API_URL = "https://www.titck.gov.tr"
ILACDB_RAW    = "https://raw.githubusercontent.com/Tip-Atlasi-Projesi/ilaclardb/main/ilaclar.json"
