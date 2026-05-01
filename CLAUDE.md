# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A local FastAPI service that wraps the VoxCPM2 text-to-speech model. It exposes a single `POST /tts` endpoint that accepts text and synthesis parameters, runs inference locally, saves the audio file to `outputs/`, and returns the file path.

## Commands

All commands use the local `myenv` virtualenv. Never use the system Python.

**Install dependencies:**
```bash
myenv/bin/pip install -r requirements.txt
```

**Run the server:**
```bash
myenv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

**Run with auto-reload (development):**
```bash
myenv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Test the endpoint manually:**
```bash
curl -X POST "http://localhost:8000/tts?format=mp3" \
  -H "Content-Type: application/json" \
  -d '{
    "cfg_value": 2.0,
    "inference_timesteps": 10,
    "story": [
      {"page_id": "1", "text": "(A young woman, gentle voice) Hello world."},
      {"page_id": "2", "text": "(A young woman, gentle voice) This is page two."}
    ]
  }'
```

**Standalone TTS script (no server):**
```bash
myenv/bin/python text.py
```

## Architecture

### Model lifecycle (`main.py`)
The VoxCPM2 model is loaded **once at startup** via FastAPI's `lifespan` context manager and held in the module-level `_model` global. It is never reloaded between requests. `load_denoiser=False` is intentional — the denoiser adds latency and is not needed for most use cases.

### Single endpoint: `POST /tts`
- **Body** (`TTSRequest`): `story` (list of `{page_id, text}`), `cfg_value` (float, default 2.0), `inference_timesteps` (int, default 10), `seed` (int or null, default null), `reference_audio_path` (str or null, default null)
- **Query param**: `format` — one of `wav`, `mp3`, `ogg` (default `wav`)
- **Returns**: JSON with `files` (list of `{page_id, file_path}`), `format`, `sample_rate`
- Output filenames are derived from `page_id` — e.g. page `"3"` with `?format=mp3` → `outputs/3.mp3`. Same `page_id` across requests overwrites the file.

### Audio format pipeline
`model.generate()` always returns a float32 numpy array at 48kHz. Format branching happens after inference:
- **WAV**: written directly with `soundfile`
- **OGG**: written with `soundfile` using `format="OGG", subtype="VORBIS"`
- **MP3**: clipped to `[-1, 1]`, scaled to int16 PCM, then exported via `pydub.AudioSegment` — requires `ffmpeg` on PATH

### Output files
Saved to `outputs/` (created at startup if missing) with UUID filenames. Files are never cleaned up automatically.

## Key Facts

- Model: `openbmb/VoxCPM2` from HuggingFace (~10 GB, downloaded on first run)
- Native sample rate: 48000 Hz (mono)
- Voice style is controlled via parenthetical prefix in the text: `"(deep male voice) Your text here."`
- `cfg_value`: guidance scale — higher values follow the voice description more strictly
- `inference_timesteps`: diffusion steps — more steps improve quality at the cost of speed
- MP3 export requires `ffmpeg` installed system-wide (`brew install ffmpeg` on macOS)
- Python environment: `myenv/` (Python 3.13)
