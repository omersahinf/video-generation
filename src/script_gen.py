import json
import re
import requests
from dataclasses import dataclass

from config import OLLAMA_URL, OLLAMA_MODEL


@dataclass
class Scene:
    id: int
    narration: str
    visual_description: str
    key_text: str
    duration: float  # seconds (estimated from narration length)


@dataclass
class VideoScript:
    title: str
    scenes: list[Scene]


def generate_script(prompt: str, num_scenes: int = 5) -> VideoScript:
    user_prompt = (
        f'Create an explainer video script with exactly {num_scenes} scenes about: {prompt}. '
        f'Return a JSON object with keys "title" (string) and "scenes" (array). '
        f'Each scene must have: "id" (integer), "narration" (2-4 sentences of spoken text), '
        f'"visual_description" (1-2 sentences describing what to illustrate), '
        f'"key_text" (max 5 words for on-screen display).'
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": user_prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.5},
    }

    try:
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=120)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to Ollama at {OLLAMA_URL}. "
            "Make sure Ollama is running: `ollama serve`"
        )

    raw = response.json().get("response", "")
    return _parse_script(raw)


def _clean_json(raw: str) -> str:
    """Normalize LLM output to valid JSON."""
    # Strip markdown code fences
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    raw = raw.strip()
    # Replace smart/curly quotes with straight quotes
    raw = raw.replace("“", '"').replace("”", '"')
    raw = raw.replace("‘", "'").replace("’", "'")
    return raw


def _parse_script(raw: str) -> VideoScript:
    cleaned = _clean_json(raw)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in Ollama response:\n{raw[:500]}")

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from Ollama: {e}\nRaw: {raw[:500]}")

    scenes = []
    for s in data.get("scenes", []):
        narration = s.get("narration", "")
        # Estimate duration: ~150 words/minute = 2.5 words/second
        word_count = len(narration.split())
        duration = max(4.0, word_count / 2.5)
        scenes.append(
            Scene(
                id=s.get("id", len(scenes) + 1),
                narration=narration,
                visual_description=s.get("visual_description", narration),
                key_text=s.get("key_text", ""),
                duration=duration,
            )
        )

    if not scenes:
        raise ValueError("Script has no scenes.")

    return VideoScript(title=data.get("title", "Explainer Video"), scenes=scenes)
