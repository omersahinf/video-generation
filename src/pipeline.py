"""Orchestrates the full prompt → MP4 pipeline."""
import time
import uuid
from pathlib import Path

from config import TEMP_DIR, OUTPUT_DIR, VIDEO_FPS
from script_gen import generate_script
from tts import text_to_speech
from image_gen import generate_illustration
from animator import make_scene_clip
from styles.registry import get_style
from composer import compose_video


def run(
    prompt: str,
    style_name: str = "whiteboard",
    output_path: Path | None = None,
    num_scenes: int = 5,
    verbose: bool = True,
) -> Path:
    style = get_style(style_name)
    run_id = uuid.uuid4().hex[:8]
    tmp = TEMP_DIR / run_id
    tmp.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        safe_name = prompt[:40].lower().replace(" ", "_").replace("/", "")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c == "_")
        output_path = OUTPUT_DIR / f"{safe_name}_{style_name}_{run_id[:6]}.mp4"

    def log(msg: str) -> None:
        if verbose:
            print(msg)

    # ── 1. Script ──────────────────────────────────────────────────────────────
    log(f"\n🎬 Generating script with Ollama ({style.name} style)...")
    t0 = time.time()
    script = generate_script(prompt, num_scenes=num_scenes)
    log(f"  ✓ Script: '{script.title}' — {len(script.scenes)} scenes ({time.time()-t0:.1f}s)")

    # ── 2. Per-scene assets ────────────────────────────────────────────────────
    scene_clips = []
    for scene in script.scenes:
        log(f"\n  Scene {scene.id}/{len(script.scenes)}: {scene.key_text or scene.visual_description[:40]}")

        try:
            audio_path = tmp / f"scene_{scene.id}_audio.mp3"
            log(f"    → TTS...")
            scene.duration = text_to_speech(scene.narration, audio_path)
            log(f"      ✓ audio duration: {scene.duration:.2f}s")

            log(f"    → Illustration...")
            image_path = tmp / f"scene_{scene.id}.png"
            generate_illustration(
                scene.visual_description,
                style,
                image_path,
                key_text=scene.key_text,
                narration=scene.narration,
            )

            log(f"    → Rendering frames...")
            video_clip = make_scene_clip(
                illustration_path=image_path,
                style=style,
                key_text=scene.key_text,
                narration=scene.narration,
                duration=scene.duration,
            )

            scene_clips.append((video_clip, audio_path))
        except Exception as e:
            log(f"    ⚠ Scene skipped: {e}")

    # ── 3. Compose final video ─────────────────────────────────────────────────
    log(f"\n🎞  Composing final video...")
    compose_video(scene_clips, output_path, fps=VIDEO_FPS, style=style)

    log(f"\n✅ Done! Video saved to: {output_path}")
    return output_path
