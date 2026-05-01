# TTS VoxCPM — FastAPI Service

A local text-to-speech REST API powered by [VoxCPM2](https://github.com/OpenBMB/VoxCPM). Accepts text input and returns synthesized audio in WAV, MP3, or OGG format.

---

## Requirements

- macOS / Linux
- Python 3.10–3.12 (3.13 also works with current builds)
- `ffmpeg` — required for MP3 export
- ~12 GB VRAM (GPU recommended; CPU works but is slow)
- ~16 GB RAM

---

## Installation

### 1. Clone or copy the project

```bash
git clone <your-repo-url>
cd TTS-VOXCPM
```

### 2. Install ffmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

### 3. Create a virtual environment

```bash
python3 -m venv myenv
```

### 4. Install Python dependencies

```bash
myenv/bin/pip install -r requirements.txt
```

> First run will also download the `openbmb/VoxCPM2` model weights (~several GB) from HuggingFace automatically when the server starts.

---

## Running the Server

### Option A — Docker (recommended for Windows)

Docker handles Python, ffmpeg, and CUDA dependencies inside the container — no manual setup needed.

**Prerequisites (Windows only):**
1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) with WSL2 backend enabled
2. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) for GPU passthrough
3. In Docker Desktop → Settings → Resources → WSL Integration — enable your WSL2 distro

**Start:**
```bash
docker compose up --build
```

First run downloads the VoxCPM2 model weights (~10 GB) into a named Docker volume (`hf_cache`) — this only happens once. Subsequent starts are fast:
```bash
docker compose up
```

**Stop:**
```bash
docker compose down
```

**Rebuild after code changes:**
```bash
docker compose up --build
```

**Without GPU (CPU only):** Remove the `deploy` block from `docker-compose.yml`. Inference will be significantly slower.

---

### Option B — Local (macOS / Linux, using myenv)

```bash
myenv/bin/pip install -r requirements.txt
myenv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

To run on a different port:
```bash
myenv/bin/uvicorn main:app --host 0.0.0.0 --port 9000
```

---

The server starts on `http://localhost:8000`. The VoxCPM2 model loads once at startup — wait for it to finish before sending requests.

---

## API Reference

### `POST /tts`

Synthesize speech for a multi-page story. Each page is processed independently and saved as a separate audio file named after its `page_id`.

**Query Parameters**

| Parameter | Type   | Default | Options             |
|-----------|--------|---------|---------------------|
| `format`  | string | `wav`   | `wav`, `mp3`, `ogg` |

**Request Body (JSON)**

| Field                 | Type            | Default | Description                                                                 |
|-----------------------|-----------------|---------|-----------------------------------------------------------------------------|
| `story`               | array of pages  | —       | List of pages to synthesize. Each page has `page_id` and `text`.            |
| `story[].page_id`     | string          | —       | Used as the output filename (e.g. `"3"` → `outputs/3.mp3`).                |
| `story[].text`        | string          | —       | Text to synthesize. Optionally embed a voice description at the start (see Voice Description Syntax). |
| `cfg_value`           | float           | `2.0`   | Guidance scale — controls how strictly the model follows the voice description. See details below. |
| `inference_timesteps` | int             | `10`    | Number of diffusion steps per page. See details below.                      |
| `seed`                | int or null     | `null`  | Random seed. Set the same integer (e.g. `42`) across all pages to get a consistent voice throughout the story. Without a seed each page may sound like a slightly different speaker. |
| `reference_audio_path`| string or null  | `null`  | Path to an existing audio file (WAV, MP3, or OGG) whose voice/timbre is cloned for every page. This is the most reliable way to get a consistent voice across all pages. Example: `"outputs/11.mp3"`. |

**Response**

```json
{
  "files": [
    {"page_id": "1", "file_path": "outputs/1.mp3"},
    {"page_id": "2", "file_path": "outputs/2.mp3"}
  ],
  "format": "mp3",
  "sample_rate": 48000
}
```

Generated files are saved to the `outputs/` folder inside the project directory. If two requests use the same `page_id`, the later request overwrites the earlier file.

---

## Generation Parameters

### `cfg_value` — Guidance Scale

Controls how closely the model follows the voice description you embed in the text.

| Value | Effect |
|-------|--------|
| `1.0` | Loose — model has more creative freedom, may sound more natural but less like the described voice |
| `2.0` | Balanced (default) — good match to the description with natural-sounding output |
| `3.0–4.0` | Strict — model closely matches the voice description; can sound slightly over-processed at high values |

**Recommendation for stories:** Keep at `2.0`. Only increase if the generated voice consistently ignores the style description.

### `inference_timesteps` — Diffusion Steps

Controls how many refinement steps the diffusion model runs per page. More steps = higher audio quality but slower generation.

| Value | Quality | Speed (per page, approx.) |
|-------|---------|--------------------------|
| `5`   | Acceptable for drafts | Fastest |
| `10`  | Good — default, recommended for production | Moderate |
| `20`  | Better detail and consistency | ~2× slower than 10 |
| `50`  | Diminishing returns beyond this point | Slow |

**Recommendation for stories:** Use `10` for production. Use `5` when iterating quickly on voice/text. Only go above `20` if you notice artefacts in specific pages.

---

## Examples

### Story — MP3 output
```bash
curl -X POST "http://localhost:8000/tts?format=mp3" \
  -H "Content-Type: application/json" \
  -d '{
    "cfg_value": 2.0,
    "inference_timesteps": 10,
    "seed": 42,
    "story": [
      {"page_id": "1", "text": "(A young woman, gentle and sweet voice) Once upon a time, there was a little girl named Mia."},
      {"page_id": "2", "text": "(A young woman, gentle and sweet voice) Mia put on her shiny silver space suit."},
      {"page_id": "3", "text": "(A young woman, gentle and sweet voice) Mia climbed into her tiny red rocket. Blast off!"}
    ]
  }'
```

Output files: `outputs/1.mp3`, `outputs/2.mp3`, `outputs/3.mp3`

### Story — consistent voice using a reference audio file
```bash
curl -X POST "http://localhost:8000/tts?format=mp3" \
  -H "Content-Type: application/json" \
  -d '{
    "cfg_value": 2.0,
    "inference_timesteps": 10,
    "reference_audio_path": "outputs/11.mp3",
    "story": [
      {"page_id": "1", "text": "(An old grandfather, warm storytelling voice, slow pace) Once upon a time, there was a brave young astronaut named Leo."},
      {"page_id": "2", "text": "(An old grandfather, warm storytelling voice, slow pace) Leo climbed into his rocket and blasted off into the stars."},
      {"page_id": "3", "text": "(An old grandfather, warm storytelling voice, slow pace) And so, my dear, always remember to dream big."}
    ]
  }'
```

The reference file (`outputs/11.mp3`) can be any short audio clip (3–10 seconds) of the target voice. The model clones its timbre across all pages while following the style description in the text.

### Story — WAV, higher quality
```bash
curl -X POST "http://localhost:8000/tts?format=wav" \
  -H "Content-Type: application/json" \
  -d '{
    "cfg_value": 2.0,
    "inference_timesteps": 20,
    "story": [
      {"page_id": "1", "text": "(Deep male voice, calm narrator) Chapter one. The journey begins."}
    ]
  }'
```

---

## Example Input JSONs

### 1. Minimal — defaults only
No voice description, WAV output, all defaults.

```json
{
  "story": [
    {"page_id": "1", "text": "Once upon a time, there was a little girl named Mia."},
    {"page_id": "2", "text": "Mia loved looking up at the stars every night."}
  ]
}
```

---

### 2. Grandpa narrating an astronaut story (slow pace, consistent voice via seed)
Use `seed` to lock the voice across all pages. No reference audio needed.

```json
{
  "cfg_value": 2.0,
  "inference_timesteps": 10,
  "seed": 42,
  "story": [
    {
      "page_id": "1",
      "text": "(An old grandfather, warm and storytelling voice, slow and deliberate pace) Once upon a time, there was a brave young astronaut named Leo who dreamed of touching the stars."
    },
    {
      "page_id": "2",
      "text": "(An old grandfather, warm and storytelling voice, slow and deliberate pace) One morning, Leo climbed into his shiny silver rocket and counted down. Five, four, three, two, one. Blast off!"
    },
    {
      "page_id": "3",
      "text": "(An old grandfather, warm and storytelling voice, slow and deliberate pace) Up and up Leo soared, past the clouds, past the moon, until the whole Earth looked like a tiny blue marble below him."
    },
    {
      "page_id": "4",
      "text": "(An old grandfather, warm and storytelling voice, slow and deliberate pace) Floating in the silence of space, Leo looked out his window and gasped. A million stars were winking back at him."
    },
    {
      "page_id": "5",
      "text": "(An old grandfather, warm and storytelling voice, slow and deliberate pace) And so, my dear, whenever you look up at the night sky, remember. Somewhere up there, Leo is still exploring, and one day, maybe you will too."
    }
  ]
}
```

---

### 3. Grandpa narrating — most consistent voice via reference audio
When you already have a recording of the target voice, use `reference_audio_path`. The model clones that exact timbre for every page. Combine with `seed` for maximum consistency.

```json
{
  "cfg_value": 2.0,
  "inference_timesteps": 10,
  "seed": 42,
  "reference_audio_path": "outputs/11.mp3",
  "story": [
    {
      "page_id": "1",
      "text": "(slow and deliberate pace) Once upon a time, there was a brave young astronaut named Leo who dreamed of touching the stars."
    },
    {
      "page_id": "2",
      "text": "(slow and deliberate pace) One morning, Leo climbed into his shiny silver rocket and counted down. Five, four, three, two, one. Blast off!"
    },
    {
      "page_id": "3",
      "text": "(slow and deliberate pace) Up and up Leo soared, past the clouds, until the whole Earth looked like a tiny blue marble below him."
    }
  ]
}
```

> When `reference_audio_path` is set, the voice description inside parentheses only controls **style** (pace, emotion, tone) — the actual speaker voice comes from the reference file. So you can drop the speaker description and just keep style hints.

---

### 4. Children's story — cheerful young woman voice, MP3 output
```json
{
  "cfg_value": 2.0,
  "inference_timesteps": 10,
  "seed": 7,
  "story": [
    {
      "page_id": "1",
      "text": "(A young woman, cheerful and warm voice) Mia put on her shiny silver space suit and big space boots."
    },
    {
      "page_id": "2",
      "text": "(A young woman, cheerful and warm voice) She bounced across the moon. Boing, boing, boing! The moon was quiet and shiny white."
    },
    {
      "page_id": "3",
      "text": "(A young woman, cheerful and warm voice) Then Mia met a friendly little alien named Zoop who had three big eyes and a giant smile."
    }
  ]
}
```

---

### 5. High quality render — more diffusion steps
Use `inference_timesteps: 20` when audio quality matters more than speed.

```json
{
  "cfg_value": 2.5,
  "inference_timesteps": 20,
  "seed": 42,
  "story": [
    {
      "page_id": "1",
      "text": "(Deep male voice, calm and authoritative narrator) Chapter one. The journey begins at the edge of the known universe."
    },
    {
      "page_id": "2",
      "text": "(Deep male voice, calm and authoritative narrator) No one had ever travelled this far from Earth and returned to tell the tale."
    }
  ]
}
```

---

## Interactive API Docs

Once the server is running, open in your browser:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Voice Description Syntax

Embed a natural-language description inside parentheses at the **start** of the text:

```
(A young woman, gentle and sweet voice) Your text here.
(Deep male voice, authoritative tone) Your text here.
(slightly faster, cheerful tone) Your text here.
(news broadcaster, clear and neutral) Your text here.
```

---

## Project Structure

```
TTS-VOXCPM/
├── main.py            # FastAPI app
├── text.py            # Standalone usage example
├── requirements.txt   # Python dependencies
├── README.md
├── myenv/             # Virtual environment (not committed)
└── outputs/           # Generated audio files (created at runtime)
```

---

## Troubleshooting

**Model download is slow or fails**
The model weights are downloaded from HuggingFace on first run. Ensure you have a stable internet connection and enough disk space (~10 GB).

**MP3 export fails**
`pydub` requires `ffmpeg` to be installed and available on your PATH. Verify with:
```bash
ffmpeg -version
```

**OGG export fails**
OGG support depends on `libsndfile` being compiled with Vorbis support. This is included in the `soundfile` pip package by default on most platforms. If it fails, try reinstalling soundfile:
```bash
myenv/bin/pip install --force-reinstall soundfile
```

**CUDA / GPU not detected**
Install the correct PyTorch version for your CUDA version from [pytorch.org](https://pytorch.org/get-started/locally/) before installing other dependencies:
```bash
myenv/bin/pip install torch --index-url https://download.pytorch.org/whl/cu121
myenv/bin/pip install -r requirements.txt
```

**Port already in use**
Change the port:
```bash
myenv/bin/uvicorn main:app --host 0.0.0.0 --port 9000
```
# VOXCPM-Local
