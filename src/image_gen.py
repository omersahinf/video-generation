"""Image generation for rich explainer scenes."""
import base64
import io
import textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from config import GEMINI_IMAGE_MODEL, VIDEO_WIDTH, VIDEO_HEIGHT
from styles.base import StyleConfig

GEMINI_API_KEY = __import__("os").getenv("GEMINI_API_KEY", "")
HF_TOKEN = __import__("os").getenv("HF_TOKEN", "")
HF_MODEL = __import__("os").getenv("HF_MODEL", "black-forest-labs/FLUX.1-schnell")

_HF_API_URL = f"https://router.huggingface.co/hf-inference/models/{HF_MODEL}"
_W = VIDEO_WIDTH
_H = VIDEO_HEIGHT


def generate_illustration(
    visual_description: str,
    style: StyleConfig,
    output_path: Path,
    key_text: str = "",
    narration: str = "",
) -> Path:
    """Generate one complete illustration for contour tracing."""
    prompt = _build_prompt(visual_description, style, key_text, narration)

    if _try_generate(prompt, output_path):
        return output_path
    return _placeholder(visual_description, style, output_path, key_text=key_text, narration=narration)


def _build_prompt(
    visual_description: str,
    style: StyleConfig,
    key_text: str = "",
    narration: str = "",
) -> str:
    key_text = " ".join(key_text.split()[:5])
    allowed_labels = _allowed_text_labels(key_text)
    palette = _palette_description(style)
    text_rule = (
        f"Readable on-image text is optional and must use only these exact labels: {allowed_labels}. "
        "Do not invent, misspell, distort, abbreviate, or add any other words, letters, numbers, or pseudo-text. "
        "If a label does not fit cleanly, omit text and use icons or blank callouts instead. "
        "Allowed labels may appear only where they belong naturally in the scene: "
        "hand-drawn signs, speech bubbles, callouts, arrows, underlines, or object labels. "
        "Never place text as a large headline across the top edge or inside a banner strip. "
        "The words must look like part of the original illustration, not a later title overlay. "
        "Keep text large, clean, correctly spelled, and limited to the key ideas. "
    )
    narration_hint = ""
    if narration:
        narration_hint = f"Scene meaning: {narration.split('.')[0].strip()}. "

    scene_line = f"{visual_description} Scene topic: {key_text}." if key_text else f"{visual_description}."
    return (
        f"{scene_line} "
        f"{narration_hint}"
        "Whiteboard explainer illustration: cartoon characters with expressive faces, "
        "specific props and objects, speech bubbles with simple labels, arrows showing flow, "
        "hand-drawn style with thick black outlines, "
        f"strategic accent colors using {palette}, "
        f"{style.image_prompt_suffix}, "
        "fill the entire 16:9 frame with rich detail, "
        "5 to 10 clear visual elements arranged in a readable scene, "
        "multiple visual elements showing the concept clearly, "
        "use the full frame naturally without reserving a separate top title banner, "
        f"{text_rule}"
        "Do not draw color palette strips, hex color codes, UI bars, headers, watermarks, logos, or detached banners. "
        "high contrast, no photorealism, no 3D render"
    )


def _allowed_text_labels(key_text: str) -> str:
    words = []
    for raw_word in key_text.replace(":", " ").replace("/", " ").split():
        word = "".join(ch for ch in raw_word if ch.isalnum())
        if len(word) >= 3 and word.lower() not in {"and", "the", "for", "with"}:
            words.append(word.title())
    labels = words[:3]

    deduped = []
    for label in labels:
        if label and label not in deduped:
            deduped.append(label)
    if not deduped:
        return "none"
    return ", ".join(f'"{label}"' for label in deduped[:4])


def _palette_description(style: StyleConfig) -> str:
    colors = {
        "#1A1A1A": "black ink",
        "#E63946": "red emphasis marks",
        "#457B9D": "blue technical details",
        "#2A9D8F": "teal signal waves",
        "#F4A261": "warm orange highlights",
        "#FFFFFF": "white background",
        "#000000": "black ink",
    }
    names = [colors.get(color.upper(), "one restrained accent color") for color in style.palette[:5]]
    deduped = []
    for name in names:
        if name not in deduped:
            deduped.append(name)
    return ", ".join(deduped)


def _overlay_key_text(output_path: Path, style: StyleConfig, key_text: str) -> None:
    """Add crisp title text locally so diffusion text artifacts do not leak into frames."""
    if not key_text:
        return
    try:
        img = Image.open(output_path).convert("RGB").resize((_W, _H), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        try:
            title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", style.title_font_size)
        except Exception:
            title_font = ImageFont.load_default()
        ink = _hex_to_rgb(style.text_color)
        accent = _hex_to_rgb(style.accent_color)
        bg = _hex_to_rgb(style.background.color)
        draw.rounded_rectangle((52, 34, 1228, 112), radius=16, fill=bg, outline=accent, width=4)
        draw.text((82, 50), " ".join(key_text.split()[:5]).upper(), fill=ink, font=title_font)
        img.save(output_path)
    except Exception as e:
        print(f"    [image] Title overlay failed ({e})")


def _try_generate(prompt: str, output_path: Path) -> bool:
    """Try configured image APIs, return True if successful."""
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

    print("    [image] No image API configured; using low-quality fallback illustration")
    return False


def _hf_generate(prompt: str, output_path: Path) -> None:
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    response = requests.post(_HF_API_URL, headers=headers, json={"inputs": prompt}, timeout=90)
    response.raise_for_status()
    img = Image.open(io.BytesIO(response.content)).convert("RGB")
    img = img.resize((_W, _H), Image.LANCZOS)
    img.save(output_path)


def _gemini_generate(prompt: str, output_path: Path) -> None:
    if GEMINI_IMAGE_MODEL.startswith("imagen-"):
        _imagen_generate(prompt, output_path)
        return

    _GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_IMAGE_MODEL}:generateContent"
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


def _imagen_generate(prompt: str, output_path: Path) -> None:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_IMAGE_MODEL}:predict"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "16:9",
        },
    }
    response = requests.post(url, headers=headers, json=payload, timeout=90)
    response.raise_for_status()
    data = response.json()
    for prediction in data.get("predictions", []):
        image_data = prediction.get("bytesBase64Encoded")
        if not image_data and isinstance(prediction.get("image"), dict):
            image_data = prediction["image"].get("bytesBase64Encoded")
        if image_data:
            img_bytes = base64.b64decode(image_data)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            img = img.resize((_W, _H), Image.LANCZOS)
            img.save(output_path)
            return
    raise ValueError("No image in Imagen response")


def _placeholder(
    visual_description: str,
    style: StyleConfig,
    output_path: Path,
    key_text: str = "",
    narration: str = "",
) -> Path:
    """Draw a deterministic rich fallback scene when external image APIs are unavailable."""
    bg = _hex_to_rgb(style.background.color)
    ink = _hex_to_rgb(style.text_color)
    accent = _hex_to_rgb(style.accent_color)
    palette = [_hex_to_rgb(c) for c in style.palette]
    blue = palette[2] if len(palette) > 2 else (69, 123, 157)
    green = palette[3] if len(palette) > 3 else (42, 157, 143)

    img = Image.new("RGB", (_W, _H), bg)
    draw = ImageDraw.Draw(img)
    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 52)
        body_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 25)
        label_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except Exception:
        title_font = body_font = label_font = ImageFont.load_default()

    _draw_texture(draw, style)
    fallback_title = key_text or _title_from_text(narration or visual_description)
    _draw_title(draw, fallback_title, title_font, ink, accent)
    _draw_person(draw, (120, 315), ink, accent, blue)
    _draw_laptop(draw, (355, 320), ink, blue, bg)
    _draw_cloud(draw, (690, 165), ink, green)
    _draw_server(draw, (905, 285), ink, blue, accent)
    _draw_arrow(draw, (520, 360), (680, 265), accent, width=6)
    _draw_arrow(draw, (805, 285), (905, 345), accent, width=6)
    _draw_speech_bubble(draw, (90, 125, 390, 195), "Question", body_font, ink, accent)
    _draw_speech_bubble(draw, (735, 505, 1125, 590), "Answer flows back", body_font, ink, blue)

    summary = narration.split(".")[0].strip() or visual_description
    wrapped = textwrap.wrap(summary, width=42)[:3]
    y = 625
    for line in wrapped:
        draw.text((105, y), line, fill=ink, font=label_font)
        y += 30

    img.save(output_path)
    return output_path


def _draw_texture(draw: ImageDraw.ImageDraw, style: StyleConfig) -> None:
    if style.background.texture == "none":
        return
    color = _hex_to_rgb(style.text_color)
    muted = tuple(max(0, min(255, int(c * 0.25))) for c in color)
    step = 34 if style.background.texture == "chalk" else 44
    for x in range(0, _W, step):
        draw.line((x, 0, x - 220, _H), fill=muted, width=1)


def _draw_title(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, ink, accent) -> None:
    text = " ".join(text.split()[:5]).upper()
    draw.rounded_rectangle((60, 40, 1220, 118), radius=18, outline=accent, width=4)
    draw.text((90, 55), text, fill=ink, font=font)


def _title_from_text(text: str) -> str:
    words = [w.strip(".,:;!?()[]{}\"'") for w in text.split()]
    words = [w for w in words if w]
    return " ".join(words[:5]) if words else "Key Idea"


def _draw_person(draw: ImageDraw.ImageDraw, anchor: tuple[int, int], ink, accent, shirt) -> None:
    x, y = anchor
    draw.ellipse((x, y - 120, x + 105, y - 15), outline=ink, width=6, fill=(255, 236, 206))
    draw.arc((x + 25, y - 82, x + 80, y - 38), 10, 170, fill=ink, width=4)
    draw.ellipse((x + 30, y - 78, x + 40, y - 68), fill=ink)
    draw.ellipse((x + 66, y - 78, x + 76, y - 68), fill=ink)
    draw.polygon([(x + 18, y), (x + 88, y), (x + 120, y + 145), (x - 18, y + 145)], outline=ink, fill=shirt)
    draw.line((x + 5, y + 35, x - 65, y + 85), fill=ink, width=6)
    draw.line((x + 100, y + 35, x + 165, y + 90), fill=ink, width=6)
    draw.ellipse((x + 150, y + 78, x + 180, y + 108), outline=ink, width=4, fill=accent)


def _draw_laptop(draw: ImageDraw.ImageDraw, anchor: tuple[int, int], ink, accent, bg) -> None:
    x, y = anchor
    draw.rounded_rectangle((x, y - 115, x + 250, y + 35), radius=14, outline=ink, width=6, fill=bg)
    draw.rectangle((x - 25, y + 35, x + 275, y + 70), outline=ink, width=5, fill=accent)
    draw.ellipse((x + 82, y - 55, x + 105, y - 32), fill=ink)
    draw.ellipse((x + 145, y - 55, x + 168, y - 32), fill=ink)
    draw.arc((x + 88, y - 26, x + 164, y + 16), 0, 180, fill=ink, width=4)
    draw.text((x + 58, y + 86), "browser", fill=ink, font=ImageFont.load_default())


def _draw_cloud(draw: ImageDraw.ImageDraw, anchor: tuple[int, int], ink, fill) -> None:
    x, y = anchor
    draw.ellipse((x, y + 45, x + 120, y + 150), outline=ink, width=5, fill=fill)
    draw.ellipse((x + 70, y, x + 210, y + 150), outline=ink, width=5, fill=fill)
    draw.ellipse((x + 155, y + 55, x + 275, y + 150), outline=ink, width=5, fill=fill)
    draw.rectangle((x + 55, y + 90, x + 230, y + 150), fill=fill)
    draw.line((x + 35, y + 150, x + 250, y + 150), fill=ink, width=5)
    draw.text((x + 90, y + 91), "DNS", fill=ink, font=ImageFont.load_default())


def _draw_server(draw: ImageDraw.ImageDraw, anchor: tuple[int, int], ink, fill, accent) -> None:
    x, y = anchor
    for i in range(3):
        top = y + i * 72
        draw.rounded_rectangle((x, top, x + 230, top + 56), radius=10, outline=ink, width=5, fill=fill)
        draw.ellipse((x + 18, top + 18, x + 35, top + 35), fill=accent)
        draw.line((x + 55, top + 22, x + 200, top + 22), fill=ink, width=4)
        draw.line((x + 55, top + 36, x + 155, top + 36), fill=ink, width=4)


def _draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color, width: int = 5) -> None:
    draw.line((*start, *end), fill=color, width=width)
    ex, ey = end
    sx, sy = start
    dx = 1 if ex >= sx else -1
    dy = 1 if ey >= sy else -1
    draw.polygon([(ex, ey), (ex - dx * 28, ey), (ex, ey - dy * 28)], fill=color)


def _draw_speech_bubble(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font: ImageFont.ImageFont,
    ink,
    accent,
) -> None:
    draw.rounded_rectangle(box, radius=20, outline=ink, width=4, fill=None)
    x1, y1, x2, y2 = box
    draw.polygon([(x1 + 55, y2), (x1 + 85, y2), (x1 + 60, y2 + 35)], outline=ink, fill=accent)
    draw.text((x1 + 24, y1 + 28), text, fill=ink, font=font)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
