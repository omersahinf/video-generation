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
    last_error: Exception | None = None
    for attempt in range(2):
        user_prompt = _build_prompt(prompt, num_scenes, last_error)
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": user_prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.35 if attempt else 0.5},
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
        try:
            return _parse_script(raw)
        except ValueError as e:
            last_error = e

    print(f"  [script] Ollama returned invalid JSON twice, using fallback script: {last_error}")
    return _fallback_script(prompt, num_scenes)


def _build_prompt(prompt: str, num_scenes: int, last_error: Exception | None = None) -> str:
    repair_instruction = ""
    if last_error is not None:
        repair_instruction = (
            "Your previous response was invalid JSON. Return valid JSON only. "
            "Escape all quotes inside strings and do not use curly quotes. "
        )
    return (
        repair_instruction +
        f'Create an explainer video script with exactly {num_scenes} scenes about: {prompt}. '
        'Return only a JSON object with keys "title" (string) and "scenes" (array). '
        'Each scene must have: "id" (integer), "narration" (2-4 sentences of spoken text), '
        '"visual_description" (2-3 sentences describing a specific illustration), '
        '"key_text" (max 5 words summarizing the main idea for on-screen display). '
        "Make each scene build on the previous one, so the explanation has a clear narrative arc. "
        "Write the title, narration, key_text, and any requested on-screen wording in English by default, "
        "even if the user's topic is written in another language. Only use another language when the user "
        "explicitly asks for the video output, narration, or on-screen text in that language. "
        "Use accessible high-school level language unless the topic asks for a different level. "
        "For every visual_description, specify concrete characters and objects, for example an expressive "
        "person, a laptop with eyes, a labeled server, arrows, speech bubbles, warning signs, clocks, "
        "or other props that make the idea visible. "
        "Avoid vague descriptions like 'simple diagram' or 'basic shapes'. "
        "Do not request tiny paragraphs of text inside the image; the key_text is the only prominent text."
    )


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
                key_text=s.get("key_text") or _compact_key_text(narration),
                duration=duration,
            )
        )

    if not scenes:
        raise ValueError("Script has no scenes.")

    return VideoScript(title=data.get("title", "Explainer Video"), scenes=scenes)


def _compact_key_text(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    return " ".join(words[:5]) if words else "Key Idea"


def _fallback_script(prompt: str, num_scenes: int) -> VideoScript:
    templates = [
        (
            "Start With The Question",
            "We begin with the question a viewer naturally has: how does this actually work? The scene introduces the main idea and sets up the moving parts.",
            "An expressive person looks at a laptop with a confused face. A friendly computer with eyes points toward a big question bubble and colored arrows show that a request is about to begin.",
        ),
        (
            "Find The Helper",
            "Next, the request goes to the helper system that knows where to look. It checks the right place and turns a human-friendly name into something machines can use.",
            "A laptop character sends a red arrow to a helpful server stack wearing glasses. A cloud, folders, labels, and small numbered steps show the lookup process clearly.",
        ),
        (
            "Return The Answer",
            "Finally, the answer travels back and the original request can continue. The viewer sees how the invisible lookup makes the visible result feel instant.",
            "A server sends a blue arrow back to the laptop. The laptop smiles, a web page appears on screen, and a speech bubble celebrates the answer coming back.",
        ),
    ]
    scenes = []
    for idx in range(num_scenes):
        key_text, narration, visual = templates[idx % len(templates)]
        scenes.append(
            Scene(
                id=idx + 1,
                narration=narration,
                visual_description=f"{visual} Topic context: {prompt}.",
                key_text=key_text,
                duration=max(4.0, len(narration.split()) / 2.5),
            )
        )
    return VideoScript(title=f"{prompt.title()} Explained", scenes=scenes)
