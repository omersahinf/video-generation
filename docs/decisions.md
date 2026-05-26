# Decisions

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
