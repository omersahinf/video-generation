import os
from pathlib import Path

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma2:2b")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
HF_TOKEN = os.getenv("HF_TOKEN", "")

TTS_VOICE = os.getenv("TTS_VOICE", "en-US-AriaNeural")

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMP_DIR = PROJECT_ROOT / ".tmp"
ASSETS_DIR = PROJECT_ROOT / "assets"

VIDEO_WIDTH = 1280
VIDEO_HEIGHT = 720
VIDEO_FPS = 24

OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
