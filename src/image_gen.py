"""Image generation with 3-phase progressive drawing: outline → partial → full color."""
import base64
import io
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from config import VIDEO_WIDTH, VIDEO_HEIGHT
from styles.base import StyleConfig

GEMINI_API_KEY = __import__("os").getenv("GEMINI_API_KEY", "")
HF_TOKEN = __import__("os").getenv("HF_TOKEN", "")
HF_MODEL = __import__("os").getenv("HF_MODEL", "black-forest-labs/FLUX.1-schnell")

_HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}"
_W = VIDEO_WIDTH
_H = VIDEO_HEIGHT

# 3 phases of progressive drawing
_PHASES = [
    {
        "suffix": "_phase1.png",
        "style_override": (
            "rough pencil sketch, only black outlines, no color, no shading, "
            "very early sketch stage, minimal detail, just basic shapes and text outlines, "
            "white background, thin black pen strokes"
        ),
    },
    {
        "suffix": "_phase2.png",
        "style_override": (
            "clean black and white sketch with some color highlights on key words, "
            "main shapes drawn, partial details, selective bold color accents, "
            "white background, hand-drawn whiteboard style"
        ),
    },
    {
        "suffix": "_phase3.png",
        "style_override": None,  # uses full style prompt
    },
]


def generate_illustration_phases(
    visual_description: str,
    style: StyleConfig,
    output_dir: Path,
    scene_id: int,
    key_text: str = "",
    narration: str = "",
) -> list[Path]:
    """Generate 3 progressive images for drawing animation."""
    text_instruction = ""
    if key_text:
        text_instruction = f'Include bold text "{key_text}" prominently. '
    if narration:
        short_narration = narration.split(".")[0] + "."
        text_instruction += f'Scene: {short_narration} '

    base_desc = (
        f"{text_instruction}{visual_description}, "
        f"full frame whiteboard explainer scene with cartoon characters, "
        f"speech bubbles, arrows, labels, integrated text as part of drawing"
    )

    paths = []
    for i, phase in enumerate(_PHASES):
        out_path = output_dir / f"scene_{scene_id}_phase{i+1}.png"

        if phase["style_override"]:
            prompt = f"{base_desc}, {phase['style_override']}"
        else:
            prompt = f"{base_desc}, {style.image_prompt_suffix}"

        success = _try_generate(prompt, out_path)
        if success:
            paths.append(out_path)
        else:
            # If a phase fails, duplicate the last successful one
            if paths:
                img = Image.open(paths[-1])
                img.save(out_path)
                paths.append(out_path)

    return paths


def generate_illustration(
    visual_description: str,
    style: StyleConfig,
    output_path: Path,
    key_text: str = "",
    narration: str = "",
) -> Path:
    """Single image generation (backward compatible). Used as fallback."""
    text_instruction = ""
    if key_text:
        text_instruction = f'Include bold text "{key_text}" prominently. '
    if narration:
        short_narration = narration.split(".")[0] + "."
        text_instruction += f'Scene: {short_narration} '

    prompt = (
        f"{text_instruction}{visual_description}, "
        f"full frame whiteboard explainer scene with cartoon characters, "
        f"speech bubbles, arrows, labels, integrated text as part of drawing, "
        f"{style.image_prompt_suffix}"
    )

    if _try_generate(prompt, output_path):
        return output_path
    return _placeholder(visual_description, style, output_path)


def _try_generate(prompt: str, output_path: Path) -> bool:
    """Try HuggingFace, return True if successful."""
    if HF_TOKEN:
        try:
            _hf_generate(prompt, output_path)
            return True
        except Exception as e:
            print(f"    [image] HF failed ({e})")

    if GEMINI_API_KEY:
        try:
            _gemini_generate(prompt, output_path)
            return True
        except Exception as e:
            print(f"    [image] Gemini failed ({e})")

    return False


def _hf_generate(prompt: str, output_path: Path) -> None:
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    response = requests.post(_HF_API_URL, headers=headers, json={"inputs": prompt}, timeout=90)
    response.raise_for_status()
    img = Image.open(io.BytesIO(response.content)).convert("RGB")
    img = img.resize((_W, _H), Image.LANCZOS)
    img.save(output_path)


def _gemini_generate(prompt: str, output_path: Path) -> None:
    _GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent"
    url = f"{_GEMINI_URL}?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": f"Generate an illustration: {prompt}"}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    response = requests.post(url, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "inlineData" in part:
                img_bytes = base64.b64decode(part["inlineData"]["data"])
                img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
                img = img.resize((_W, _H), Image.LANCZOS)
                img.save(output_path)
                return
    raise ValueError("No image in Gemini response")


def _placeholder(visual_description: str, style: StyleConfig, output_path: Path) -> Path:
    accent = _hex_to_rgb(style.accent_color)
    img = Image.new("RGB", (_W, _H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except Exception:
        font = ImageFont.load_default()
    draw.text((40, _H // 2), visual_description[:80], fill=accent, font=font)
    img.save(output_path)
    return output_path


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
