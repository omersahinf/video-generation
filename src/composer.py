"""Merge video clips with audio into final MP4."""
from pathlib import Path

from config import ENCODING_CRF, ENCODING_PRESET, TRANSITION_DURATION
from styles.base import StyleConfig


def compose_video(
    scene_clips: list,  # list of (VideoClip, audio_path)
    output_path: Path,
    fps: int = 24,
    style: StyleConfig | None = None,
) -> Path:
    from moviepy import AudioFileClip, concatenate_videoclips

    final_clips = []
    for video_clip, audio_path in scene_clips:
        if audio_path and Path(audio_path).exists():
            try:
                audio = AudioFileClip(str(audio_path))
                duration = max(0.1, float(audio.duration))
                if hasattr(audio, "subclipped"):
                    audio = audio.subclipped(0, duration)
                vc = video_clip.with_duration(duration)
                vc = vc.with_audio(audio)
                final_clips.append(vc)
                continue
            except Exception as e:
                print(f"  [composer] Audio load failed: {e}, using silent clip")
        final_clips.append(video_clip)

    if not final_clips:
        raise RuntimeError("No clips to compose.")

    final_clips = _apply_transitions(final_clips, style)
    final = concatenate_videoclips(final_clips, method="compose")
    final.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
        preset=ENCODING_PRESET,
        ffmpeg_params=["-crf", ENCODING_CRF],
    )
    return output_path


def _apply_transitions(clips: list, style: StyleConfig | None) -> list:
    if not style or len(clips) < 2 or TRANSITION_DURATION <= 0:
        return clips

    transition = style.transition
    if transition == "fade":
        return _fade_edges(clips)
    if transition in {"wipe_left", "wipe_right"}:
        side = "left" if transition == "wipe_left" else "right"
        return _slide_edges(clips, side)
    return clips


def _fade_edges(clips: list) -> list:
    from moviepy.video.fx import FadeIn, FadeOut

    transitioned = []
    for idx, clip in enumerate(clips):
        effects = []
        if idx > 0:
            effects.append(FadeIn(TRANSITION_DURATION))
        if idx < len(clips) - 1:
            effects.append(FadeOut(TRANSITION_DURATION))
        transitioned.append(clip.with_effects(effects) if effects else clip)
    return transitioned


def _slide_edges(clips: list, side: str) -> list:
    from moviepy.video.fx import SlideIn, SlideOut

    out_side = "right" if side == "left" else "left"
    transitioned = []
    for idx, clip in enumerate(clips):
        effects = []
        if idx > 0:
            effects.append(SlideIn(TRANSITION_DURATION, side))
        if idx < len(clips) - 1:
            effects.append(SlideOut(TRANSITION_DURATION, out_side))
        transitioned.append(clip.with_effects(effects) if effects else clip)
    return transitioned
