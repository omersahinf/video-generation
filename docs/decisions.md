# Decisions

## 2026-05-31

**On-screen text must be generated as part of the illustration.**
- Do not add detached title bars or amateur-looking text overlays after image generation.
- Short readable English words are allowed and expected when they are part of the scene: hand-drawn labels, callouts, speech bubbles, object labels, signs, arrows, and underlines.
- The image model should place text where it naturally belongs in the composition, matching the same hand-drawn style as the illustration.
- Do not expose hex color codes in image prompts because image models may render them as visible palette bars. Describe colors in words and explicitly forbid palette strips, UI bars, headers, logos, watermarks, and detached banners.

**Gemini image model is configurable.**
- `GEMINI_IMAGE_MODEL` controls the Gemini image-generation model endpoint.
- Use the configured Gemini/Nano Banana image model when the user asks for Gemini/Nano Banana output; do not accidentally route that request through HuggingFace.
- Imagen 4 uses the Gemini API `models/imagen-4.0-generate-001:predict` endpoint, not the Gemini `generateContent` image endpoint.

**Fill reveal must not jump to the full foreground.**
- Do not use a final `fill_alpha >= 1.0` branch that reveals the entire foreground in one frame.
- Black ink/contours should remain contour-driven.
- Color and light gray fill regions should reveal as scheduled components near their contour timing, at full opacity, without alpha fading or a final image pop.

**Default video output language is English.**
- All future generated videos must be in English unless the user explicitly requests a different output language.
- This applies to script titles, scene narration, `key_text`, on-screen wording, image prompt intent, and voiceover.
- Do not infer Turkish output from Turkish user prompts. A Turkish request for a video still produces English video content and English narration unless it explicitly asks for Turkish output.

**Video requests must use the real production pipeline.**
- Standard flow: Ollama script generation → HuggingFace/Gemini image generation when configured → Edge TTS voiceover → OpenCV contour-driven reveal animation → MoviePy MP4 composition.
- Standalone toy/test renders are not acceptable for normal video requests.
- Deterministic fallback illustrations exist only to keep the pipeline running and must not be treated as target-quality final output.

## 2026-05-27

**Animation render model: contour-driven reveal mask, not stroke overlay.**
- Contours are still extracted and ordered with OpenCV, but `cv2.polylines` now draws only into masks.
- Each video frame blends original illustration pixels over the style background through the current reveal mask.
- This avoids the previous "kapkara stroke" problem where newly drawn black lines were thicker/darker than the source artwork.
- The final frame no longer jumps to `illus_rgb.copy()`; the mask reaches the complete foreground through the same render path.
- Pen cursor remains as an overlay because it is a UI hint, not part of the artwork.

**Fallback illustrations are not target quality.**
- If neither `HF_TOKEN` nor `GEMINI_API_KEY` is configured, `image_gen.py` uses a deterministic Pillow fallback only to keep the pipeline from crashing.
- Golpo-like visual quality depends on AI-generated illustrations; fallback output should not be used for quality review.

## 2026-05-26

**Gemini Flash image gen ücretsiz tier'da çalışmıyor.**
- API key alındı, model listede görünüyor (`gemini-2.5-flash-image`, `gemini-3.1-flash-image-preview`)
- Ama her istekte 429 (quota exceeded) veriyor
- Free tier'da image generation quota yok veya çok kısıtlı
- Sonuç: Gemini fallback olarak kalır ama birincil değil

**Image gen birincil: HuggingFace FLUX.1 Schnell**
- Ücretsiz token ile çalışır
- Flat illustration stili iyi

**LLM**: Ollama local with gemma2:2b default.
- Reason: Free, local, no API key, good structured output.

**TTS**: edge-tts (Microsoft Edge TTS).
- Reason: Free, high quality, English + multi-language support, no API key.

**Animation engine**: MoviePy + Pillow (frame-by-frame).
- Reason: No GPU needed, works on M4 Apple Silicon, full control over render.

**FFmpeg**: via imageio-ffmpeg (bundled with moviepy).
- Reason: No separate install needed.

**Style architecture**: `StyleConfig` dataclass in `registry.py`. All styles in one file.

**Video resolution**: 1280x720 (720p).

**Python version**: 3.14.
