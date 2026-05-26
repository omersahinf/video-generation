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

## Env Vars
```
OLLAMA_MODEL=gemma2:2b       # default model
HF_TOKEN=hf_xxx              # HuggingFace token (optional, enables AI images)
TTS_VOICE=en-US-AriaNeural   # edge-tts voice
```

## Style System
Each style is a `StyleConfig` in `styles/registry.py`. Categories: `canvas` (animation-first) and `sketch` (illustration-first). Adding a new style = add a new entry to `STYLES` dict in `registry.py`.

## Rules
- Keep this file short and stable. Cache-sensitive.
- New decisions → `docs/decisions.md`
- Active status → `docs/current-state.md`
