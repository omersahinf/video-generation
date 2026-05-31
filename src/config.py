import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(PROJECT_ROOT / ".env")
_load_dotenv(PROJECT_ROOT / ".env.local")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma2:2b")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "imagen-4.0-generate-001")
HF_TOKEN = os.getenv("HF_TOKEN", "")

TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")

OUTPUT_DIR = PROJECT_ROOT / "output"
TEMP_DIR = PROJECT_ROOT / ".tmp"
ASSETS_DIR = PROJECT_ROOT / "assets"

VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS = 24

# Animation tuning
CONTOUR_MIN_LENGTH = int(os.getenv("CONTOUR_MIN_LENGTH", "15"))
CANNY_OTSU_LOW_RATIO = float(os.getenv("CANNY_OTSU_LOW_RATIO", "0.3"))
CANNY_OTSU_HIGH_RATIO = float(os.getenv("CANNY_OTSU_HIGH_RATIO", "0.7"))
STROKE_DRAW_PCT_DEFAULT = float(os.getenv("STROKE_DRAW_PCT_DEFAULT", "0.45"))
FILL_DELAY_PCT = float(os.getenv("FILL_DELAY_PCT", "0.12"))
DRAW_HOLD_PCT = float(os.getenv("DRAW_HOLD_PCT", "0.15"))
TRANSITION_DURATION = float(os.getenv("TRANSITION_DURATION", "0.45"))
SHOW_PEN_CURSOR = os.getenv("SHOW_PEN_CURSOR", "0").lower() in {"1", "true", "yes", "on"}

# Encoding tuning
ENCODING_PRESET = os.getenv("ENCODING_PRESET", "medium")
ENCODING_CRF = os.getenv("ENCODING_CRF", "20")

OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
