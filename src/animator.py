"""Whiteboard drawing animation using contour-driven reveal masks.

Extracts actual stroke paths from the illustration, then reveals original
artwork pixels along those paths so frames stay visually consistent.
"""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from config import (
    CANNY_OTSU_HIGH_RATIO,
    CANNY_OTSU_LOW_RATIO,
    CONTOUR_MIN_LENGTH,
    DRAW_HOLD_PCT,
    FILL_DELAY_PCT,
    SHOW_PEN_CURSOR,
    STROKE_DRAW_PCT_DEFAULT,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
)
from styles.base import StyleConfig

_W, _H = VIDEO_WIDTH, VIDEO_HEIGHT


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


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

    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    otsu_thresh, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    low = max(5, int(otsu_thresh * CANNY_OTSU_LOW_RATIO))
    high = max(low + 1, int(otsu_thresh * CANNY_OTSU_HIGH_RATIO))
    edges = cv2.Canny(blurred, low, high)

    # Dilate slightly to connect broken strokes
    kernel = np.ones((2, 2), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    # CHAIN_APPROX_NONE: every pixel of the contour in path order
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)

    contours = [c for c in contours if len(c) >= CONTOUR_MIN_LENGTH]

    return contours


def _sort_contours(contours: list[np.ndarray]) -> list[np.ndarray]:
    """Sort contours by nearest-neighbor travel for a more natural pen path."""
    if not contours:
        return []

    def start_key(c: np.ndarray) -> tuple[int, int]:
        x, y, w, h = cv2.boundingRect(c)
        return (y + h // 2, x + w // 2)

    remaining = sorted(contours, key=start_key)
    sorted_contours = [remaining.pop(0)]

    while remaining:
        last_pt = sorted_contours[-1][-1][0]

        best_idx = 0
        best_distance = float("inf")
        best_reversed = False
        for idx, contour in enumerate(remaining):
            start_distance = float(np.linalg.norm(contour[0][0] - last_pt))
            end_distance = float(np.linalg.norm(contour[-1][0] - last_pt))
            if start_distance < best_distance:
                best_idx = idx
                best_distance = start_distance
                best_reversed = False
            if end_distance < best_distance:
                best_idx = idx
                best_distance = end_distance
                best_reversed = True

        next_contour = remaining.pop(best_idx)
        if best_reversed:
            next_contour = next_contour[::-1]
        sorted_contours.append(next_contour)

    return sorted_contours


def _stroke_settings(style: StyleConfig) -> tuple[int, int]:
    if style.stroke_thickness > 0:
        thickness = style.stroke_thickness
    else:
        thickness = {
            "pen": 2,
            "chalk": 3,
            "marker": 4,
            "crayon": 3,
            "none": 2,
        }.get(style.drawing_effect, 2)
    mask_thickness = max(6, thickness * 4)
    return thickness, mask_thickness


def _stroke_draw_pct(style: StyleConfig) -> float:
    if style.reveal_speed <= 0:
        return STROKE_DRAW_PCT_DEFAULT
    # Faster reveal styles spend less of the scene on outline tracing.
    return _clamp(0.25 + (1.0 - style.reveal_speed) * 0.25, 0.3, 0.55)


def _compute_cumulative_lengths(contours: list[np.ndarray]) -> tuple[np.ndarray, int]:
    """Return cumulative point count for each contour and total points."""
    lengths = np.array([len(c) for c in contours])
    cumulative = np.cumsum(lengths)
    return cumulative, int(cumulative[-1]) if len(cumulative) > 0 else 0


def _fill_reveal_schedule(
    contours: list[np.ndarray],
    cumulative: np.ndarray,
    total_points: int,
    is_foreground: np.ndarray,
    fill_candidate: np.ndarray,
    mask_thickness: int,
    stroke_draw_pct: float,
    fill_delay: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Schedule filled/color regions by nearby contour timing, avoiding alpha fades and final jumps."""
    label_count, labels = cv2.connectedComponents(fill_candidate.astype(np.uint8), connectivity=8)
    reveal_progress = np.full(label_count, np.inf, dtype=np.float32)
    if label_count <= 1:
        return labels, reveal_progress

    touched = np.zeros(label_count, dtype=bool)
    touched[0] = True

    for idx, contour in enumerate(contours):
        contour_start = int(cumulative[idx] - len(contour))
        reveal_point = contour_start + max(2, int(len(contour) * 0.45))
        contour_progress = min(1.0, reveal_point / max(1, total_points))
        scene_progress = min(1.0, contour_progress * stroke_draw_pct + fill_delay)

        contour_mask = np.zeros((_H, _W), dtype=np.uint8)
        cv2.polylines(
            contour_mask,
            [contour],
            isClosed=False,
            color=255,
            thickness=mask_thickness + 8,
        )
        hit_labels = np.unique(labels[(contour_mask > 0) & is_foreground])
        hit_labels = hit_labels[hit_labels > 0]
        if hit_labels.size:
            reveal_progress[hit_labels] = np.minimum(reveal_progress[hit_labels], scene_progress)
            touched[hit_labels] = True

    fallback_progress = min(1.0, stroke_draw_pct + fill_delay + 0.12)
    untouched = (~touched) & (np.arange(label_count) > 0)
    reveal_progress[untouched] = fallback_progress
    return labels, reveal_progress


def make_scene_clip(
    illustration_path: Path,
    style: StyleConfig,
    key_text: str,
    narration: str,
    duration: float,
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

    stroke_draw_pct = _stroke_draw_pct(style)
    fill_delay = FILL_DELAY_PCT
    draw_duration = duration * max(0.1, 1.0 - DRAW_HOLD_PCT)

    stroke_color = _hex_to_rgb(style.text_color)
    cursor_color = _hex_to_rgb(style.cursor_color or style.accent_color or style.palette[1])
    stroke_thickness, mask_thickness = _stroke_settings(style)
    cursor_radius = max(4, stroke_thickness + 3)
    bg_f = bg_array.astype(np.float32)
    illus_rgb_f = illus_rgb.astype(np.float32)
    brightness = np.mean(illus_rgb, axis=2)
    ink_pixels = brightness < 95
    fill_candidate = is_foreground & ~ink_pixels
    fill_labels, fill_reveal_progress = _fill_reveal_schedule(
        contours,
        cumulative,
        total_points,
        is_foreground,
        fill_candidate,
        mask_thickness,
        stroke_draw_pct,
        fill_delay,
    )

    def make_frame(t: float) -> np.ndarray:
        progress = min(1.0, t / max(0.1, draw_duration))

        # How many total contour points have been drawn?
        stroke_progress = min(1.0, progress / stroke_draw_pct)
        points_drawn = int(stroke_progress * total_points)

        # Draw into masks only. Frames reveal original illustration pixels;
        # no new stroke color is painted over the source artwork.
        line_mask = np.zeros((_H, _W), dtype=np.uint8)
        active_pen_pos: np.ndarray | None = None

        for i, contour in enumerate(contours):
            contour_start = cumulative[i] - len(contour)

            if points_drawn <= contour_start:
                break  # haven't reached this contour yet

            # How many points of THIS contour are drawn?
            pts_in_contour = min(len(contour), points_drawn - contour_start)

            if pts_in_contour >= 2:
                partial = contour[:pts_in_contour]
                active_pen_pos = partial[-1][0]
                cv2.polylines(line_mask, [partial], isClosed=False, color=255, thickness=mask_thickness)

        combined_mask = ((line_mask > 0) & is_foreground).astype(np.float32)
        fill_progress = max(0.0, progress - fill_delay)
        if fill_progress > 0:
            fill_visible = (
                fill_candidate & (fill_reveal_progress[fill_labels] <= progress)
            ).astype(np.float32)
            combined_mask = np.maximum(combined_mask, fill_visible)

        alpha_3 = combined_mask[:, :, np.newaxis]
        frame = (illus_rgb_f * alpha_3 + bg_f * (1.0 - alpha_3)).astype(np.uint8)

        if SHOW_PEN_CURSOR and active_pen_pos is not None and progress < 1.0:
            pen_pos = tuple(int(v) for v in active_pen_pos)
            cv2.circle(frame, pen_pos, cursor_radius, cursor_color, -1)
            cv2.circle(frame, pen_pos, cursor_radius + 1, stroke_color, 1)

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
