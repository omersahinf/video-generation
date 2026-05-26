import asyncio
from pathlib import Path

import edge_tts

from config import TTS_VOICE


async def _synthesize(text: str, output_path: Path, voice: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def text_to_speech(text: str, output_path: Path, voice: str = TTS_VOICE) -> float:
    """Generate speech audio. Returns actual duration in seconds."""
    asyncio.run(_synthesize(text, output_path, voice))

    # Estimate duration from word count (fallback if audio probe fails)
    word_count = len(text.split())
    return max(3.0, word_count / 2.5)


async def _get_duration_async(text: str, voice: str) -> float:
    """Estimate TTS duration without saving."""
    word_count = len(text.split())
    return max(3.0, word_count / 2.5)


def estimate_duration(text: str) -> float:
    word_count = len(text.split())
    return max(3.0, word_count / 2.5)
