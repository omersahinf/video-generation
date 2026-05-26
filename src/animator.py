"""Whiteboard drawing animation using real contour path tracing.

Extracts actual stroke paths from the illustration, then animates a pen
following each path sequentially — like a real hand drawing on a whiteboard.
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from config import VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS
from styles.base import StyleConfig

_W, _H = VIDEO_WIDTH, VIDEO_HEIGHT


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _make_background(style: StyleConfig) -> np.ndarray:
    bg_color = _hex_to_rgb(style.background.color)
    img = np.full((_H, _W, 3), bg_color, dtype=np.uint8)
    if style.background.texture == "chalk":
        noise = np.random.randint(-9, 9, (_H, _W, 3), dtype=np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    elif style.background.texture in ("paper", "dark_paper"):
        s = 5 if style.background.texture == "paper" else 4
        noise = np.random.randint(-s, s, (_H, _W, 3), dtype=np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return img


def _extract_contours(img_bgr: np.ndarray) -> list[np.ndarray]:
    """Extract drawing contours as ordered point sequences."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold to handle varying backgrounds
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 30, 120)

    # Dilate slightly to connect broken strokes
    kernel = np.ones((2, 2), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    # CHAIN_APPROX_NONE: every pixel of the contour in path order
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    # Filter tiny noise contours (< 30 pixels)
    contours = [c for c in contours if len(c) >= 30]

    return contours


def _sort_contours(contours: list[np.ndarray]) -> list[np.ndarray]:
    """Sort contours: top-to-bottom in bands, left-to-right within each band."""
    if not contours:
        return []

    def sort_key(c: np.ndarray) -> tuple:
        rect = cv2.boundingRect(c)
        cy = rect[1] + rect[3] // 2
        cx = rect[0] + rect[2] // 2
        band = cy // (_H // 6)  # 6 horizontal bands
        return (band, cx)

    return sorted(contours, key=sort_key)


def _compute_cumulative_lengths(contours: list[np.ndarray]) -> tuple[np.ndarray, int]:
    """Return cumulative point count for each contour and total points."""
    lengths = np.array([len(c) for c in contours])
    cumulative = np.cumsum(lengths)
    return cumulative, int(cumulative[-1]) if len(cumulative) > 0 else 0


def make_scene_clip(
    illustration_path: Path,
    style: StyleConfig,
    key_text: str,
    narration: str,
    duration: float,
    phase_paths: list[Path] | None = None,
) -> "moviepy.VideoClip":
    from moviepy import VideoClip

    bg_array = _make_background(style)

    # Load the final illustration
    try:
        illus_pil = Image.open(illustration_path).convert("RGB").resize((_W, _H), Image.LANCZOS)
        illus_rgb = np.array(illus_pil)
        illus_bgr = cv2.cvtColor(illus_rgb, cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"    [animator] Cannot load image: {e}")
        return VideoClip(lambda t: bg_array, duration=duration).with_fps(VIDEO_FPS)

    # Extract and sort contours
    contours = _extract_contours(illus_bgr)
    contours = _sort_contours(contours)
    cumulative, total_points = _compute_cumulative_lengths(contours)

    if total_points == 0:
        return VideoClip(lambda t: illus_rgb, duration=duration).with_fps(VIDEO_FPS)

    # Detect background color from corners
    corners = [illus_rgb[5, 5], illus_rgb[5, -5], illus_rgb[-5, 5], illus_rgb[-5, -5]]
    bg_detected = np.mean(corners, axis=0).astype(np.float32)
    diff_from_bg = np.sqrt(np.sum((illus_rgb.astype(np.float32) - bg_detected) ** 2, axis=2))
    is_foreground = diff_from_bg > 20

    # Build a "distance from nearest drawn contour" map will be done per-frame
    # Pre-compute: for fill reveal, which pixels are near which contour
    stroke_draw_pct = 0.65  # strokes take 65% of the time
    fill_delay = 0.20  # fills start 20% after their local strokes
    draw_duration = duration * 0.85  # last 15% holds complete image

    # Pen stroke color (from style)
    stroke_color = _hex_to_rgb(style.text_color)

    def make_frame(t: float) -> np.ndarray:
        progress = min(1.0, t / max(0.1, draw_duration))

        # How many total contour points have been drawn?
        stroke_progress = min(1.0, progress / stroke_draw_pct)
        points_drawn = int(stroke_progress * total_points)

        # Start with background
        frame = bg_array.copy()

        # --- Phase 1: Draw contour strokes ---
        # Create a mask of all pixels that have been "stroked"
        stroke_mask = np.zeros((_H, _W), dtype=np.uint8)

        points_so_far = 0
        for i, contour in enumerate(contours):
            contour_start = cumulative[i] - len(contour)
            contour_end = cumulative[i]

            if points_drawn <= contour_start:
                break  # haven't reached this contour yet

            # How many points of THIS contour are drawn?
            pts_in_contour = min(len(contour), points_drawn - contour_start)

            if pts_in_contour >= 2:
                # Draw the visible portion of this contour as a thick stroke
                partial = contour[:pts_in_contour]
                cv2.polylines(frame, [partial], isClosed=False, color=stroke_color, thickness=2)

                # Mark stroked area for fill reveal
                cv2.polylines(stroke_mask, [partial], isClosed=False, color=255, thickness=8)

        # --- Phase 2: Fill colors behind completed strokes ---
        fill_progress = max(0.0, progress - fill_delay)
        if fill_progress > 0:
            # Dilate stroke mask to create fill region
            fill_kernel = np.ones((20, 20), np.uint8)
            fill_region = cv2.dilate(stroke_mask, fill_kernel, iterations=3)

            # Global fill progress ramp
            fill_alpha_global = min(1.0, fill_progress / (1.0 - fill_delay - 0.15))

            # Only fill foreground pixels within the fill region
            fill_mask = (fill_region > 0) & is_foreground
            fill_alpha = fill_mask.astype(np.float32) * fill_alpha_global

            alpha_3 = fill_alpha[:, :, np.newaxis]
            frame = (illus_rgb.astype(np.float32) * alpha_3 + frame.astype(np.float32) * (1.0 - alpha_3)).astype(np.uint8)

            # Re-draw strokes on top so they stay crisp
            for i, contour in enumerate(contours):
                contour_start = cumulative[i] - len(contour)
                if points_drawn <= contour_start:
                    break
                pts_in_contour = min(len(contour), points_drawn - contour_start)
                if pts_in_contour >= 2:
                    partial = contour[:pts_in_contour]
                    cv2.polylines(frame, [partial], isClosed=False, color=stroke_color, thickness=2)

        # If drawing is complete, show full illustration
        if progress >= 1.0:
            frame = illus_rgb.copy()

        return frame

    return VideoClip(make_frame, duration=duration).with_fps(VIDEO_FPS)


def apply_transition(
    clip1: "moviepy.VideoClip",
    clip2: "moviepy.VideoClip",
    style: StyleConfig,
    transition_duration: float = 0.5,
) -> "moviepy.VideoClip":
    from moviepy import concatenate_videoclips
    if style.transition == "fade":
        try:
            from moviepy.video.fx import FadeOut, FadeIn
            c1 = clip1.with_effects([FadeOut(transition_duration)])
            c2 = clip2.with_effects([FadeIn(transition_duration)])
            return concatenate_videoclips([c1, c2])
        except Exception:
            pass
    return concatenate_videoclips([clip1, clip2])
