"""Merge video clips with audio into final MP4."""
from pathlib import Path


def compose_video(
    scene_clips: list,  # list of (VideoClip, audio_path)
    output_path: Path,
    fps: int = 24,
) -> Path:
    from moviepy import AudioFileClip, concatenate_videoclips

    final_clips = []
    for video_clip, audio_path in scene_clips:
        if audio_path and Path(audio_path).exists():
            try:
                audio = AudioFileClip(str(audio_path))
                # Match video duration to audio duration
                duration = audio.duration
                vc = video_clip.with_duration(duration)
                vc = vc.with_audio(audio)
                final_clips.append(vc)
                continue
            except Exception as e:
                print(f"  [composer] Audio load failed: {e}, using silent clip")
        final_clips.append(video_clip)

    if not final_clips:
        raise RuntimeError("No clips to compose.")

    final = concatenate_videoclips(final_clips, method="compose")
    final.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
        preset="ultrafast",
    )
    return output_path
