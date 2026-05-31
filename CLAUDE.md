# Explainer Video Generator

AI-powered whiteboard/explainer video generator. Prompt → MP4. No paid APIs required.

## Stack
- **LLM**: Ollama (local) — script + scene breakdown
- **TTS**: edge-tts (free) — voiceover
- **Images**: HuggingFace Inference API (free tier) → SVG/Pillow fallback
- **Animation**: MoviePy + Pillow — frame composition, progressive reveal
- **Runtime**: Python 3.14, macOS (Apple Silicon)

## Project Files
```
src/
  cli.py          — entry point: python src/cli.py "prompt" --style whiteboard
  pipeline.py     — orchestrates all stages
  script_gen.py   — Ollama → structured scene JSON
  image_gen.py    — HuggingFace API or placeholder images
  tts.py          — edge-tts async wrapper
  animator.py     — style-aware frame renderer
  composer.py     — MoviePy audio+video merge → MP4
  config.py       — env vars + constants
  styles/
    base.py       — StyleConfig dataclass
    registry.py   — all style definitions + get_style()
docs/
  current-state.md  — active work status
  decisions.md      — confirmed decisions
output/           — generated MP4s
.tmp/             — intermediate files (audio, images)
```

## Commands
```bash
python src/cli.py "Explain how DNS works" --style whiteboard
python src/cli.py "prompt" --style chalkboard_color --output my_video.mp4
python src/cli.py --list-styles
```

## Non-Negotiable Video Generation Rules
- Unless the user explicitly requests another output language, every generated video must be in English.
- English means: script title, scene narration, `key_text`, on-screen wording, image prompt intent, and voiceover.
- Do not infer the output language from the language of the user's prompt. A Turkish prompt still produces an English video unless the user explicitly asks for Turkish output.
- When asked to create a video, use the real project pipeline: Ollama script generation → HuggingFace/Gemini image generation if configured → Edge TTS voiceover → OpenCV contour reveal animation → MoviePy MP4 composition.
- Do not produce standalone toy/test videos or fallback-only quality outputs as the answer to a normal video request. Fallback illustrations are only for crash-resilience, not final review quality.
- On-screen words must be part of the generated illustration itself: hand-drawn labels, callouts, speech bubbles, object labels, signs, arrows, and underlines that match the image style.
- Do not add amateur-looking title bars or text overlays after image generation. Avoid top-banner text that looks detached from the scene.
- Do not let image prompts expose hex color codes or palette values; models may draw them. Describe colors in words and forbid palette strips, UI bars, headers, logos, watermarks, and detached banners.
- Do not reveal the full foreground in a single final animation branch. Keep ink contour-driven and reveal color/light gray fills as full-opacity scheduled components near their contour timing.

## Env Vars
```
OLLAMA_MODEL=gemma2:2b       # default model
HF_TOKEN=hf_xxx              # HuggingFace token (optional, enables AI images)
GEMINI_API_KEY=xxx           # Gemini image generation key
GEMINI_IMAGE_MODEL=imagen-4.0-generate-001
TTS_VOICE=en-US-AriaNeural   # edge-tts voice
```

## Style System
Each style is a `StyleConfig` in `styles/registry.py`. Categories: `canvas` (animation-first) and `sketch` (illustration-first). Adding a new style = add a new entry to `STYLES` dict in `registry.py`.

## Rules
- Keep this file short and stable. Cache-sensitive.
- New decisions → `docs/decisions.md`
- Active status → `docs/current-state.md`
