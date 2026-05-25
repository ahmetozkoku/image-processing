from pathlib import Path

BASE_DIR = Path(__file__).parent

MODEL_PATH     = BASE_DIR / "best.pt"
ALT_MODEL_PATH = BASE_DIR / "models" / "best.pt"
DB_PATH        = BASE_DIR / "data" / "drugs.db"
DATASET_DIR    = BASE_DIR / "data" / "dataset"

CAMERA_INDEX      = 0
DETECTION_CONF    = 0.70
OCR_EVERY_N_FRAMES = 25
TARGET_FPS        = 30

WINDOW_TITLE = "İlaç Tanıma Sistemi  |  v2.0"
WINDOW_W     = 1280
WINDOW_H     = 720

TITCK_API_URL = "https://www.titck.gov.tr"
ILACDB_RAW    = "https://raw.githubusercontent.com/Tip-Atlasi-Projesi/ilaclardb/main/ilaclar.json"
