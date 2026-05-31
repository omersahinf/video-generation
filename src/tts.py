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
    return get_audio_duration(output_path, fallback_text=text)


def get_audio_duration(output_path: Path, fallback_text: str = "") -> float:
    """Read the generated audio duration, falling back to a word-count estimate."""
    try:
        from moviepy import AudioFileClip

        audio = AudioFileClip(str(output_path))
        try:
            return max(0.1, float(audio.duration))
        finally:
            audio.close()
    except Exception as e:
        print(f"    [tts] Audio duration probe failed: {e}")

    text = fallback_text or ""
    word_count = len(text.split())
    return max(3.0, word_count / 2.5)


async def _get_duration_async(text: str, voice: str) -> float:
    """Estimate TTS duration without saving."""
    word_count = len(text.split())
    return max(3.0, word_count / 2.5)


def estimate_duration(text: str) -> float:
    word_count = len(text.split())
    return max(3.0, word_count / 2.5)
