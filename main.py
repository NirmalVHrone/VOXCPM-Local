from contextlib import asynccontextmanager
from pathlib import Path
import tempfile

import numpy as np
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from voxcpm import VoxCPM

OUTPUT_DIR = Path("outputs")
_model: VoxCPM | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    OUTPUT_DIR.mkdir(exist_ok=True)
    _model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
    yield
    _model = None


app = FastAPI(title="VoxCPM TTS Service", lifespan=lifespan)


class StoryPage(BaseModel):
    page_id: str
    text: str


class TTSRequest(BaseModel):
    story: list[StoryPage]
    cfg_value: float = 2.0
    inference_timesteps: int = 10
    seed: int | None = None
    reference_audio_path: str | None = None


def _ensure_wav(audio_path: str) -> tuple[str, bool]:
    """Return a WAV path for the given audio file. If conversion is needed,
    writes a temp file and returns (path, True) so the caller can delete it."""
    p = Path(audio_path)
    if not p.exists():
        raise FileNotFoundError(f"Reference audio not found: {audio_path}")
    if p.suffix.lower() == ".wav":
        return audio_path, False
    from pydub import AudioSegment
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    AudioSegment.from_file(audio_path).export(tmp.name, format="wav")
    return tmp.name, True


def _write_audio(wav: np.ndarray, sample_rate: int, path: Path, fmt: str) -> None:
    if fmt == "wav":
        sf.write(str(path), wav, sample_rate)
    elif fmt == "ogg":
        sf.write(str(path), wav, sample_rate, format="OGG", subtype="VORBIS")
    elif fmt == "mp3":
        from pydub import AudioSegment

        pcm = (np.clip(wav, -1.0, 1.0) * 32767).astype(np.int16)
        AudioSegment(
            pcm.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,
            channels=1,
        ).export(str(path), format="mp3")


@app.post("/tts")
def synthesize(
    request: TTSRequest,
    format: str = Query(default="wav", pattern="^(wav|mp3|ogg)$"),
):
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    ref_wav_path: str | None = None
    ref_is_temp = False

    if request.reference_audio_path:
        try:
            ref_wav_path, ref_is_temp = _ensure_wav(request.reference_audio_path)
        except FileNotFoundError as e:
            raise HTTPException(status_code=400, detail=str(e))

    try:
        sample_rate: int = _model.tts_model.sample_rate
        results = []

        for page in request.story:
            if request.seed is not None:
                torch.manual_seed(request.seed)

            generate_kwargs: dict = dict(
                text=page.text,
                cfg_value=request.cfg_value,
                inference_timesteps=request.inference_timesteps,
            )
            if ref_wav_path:
                generate_kwargs["reference_wav_path"] = ref_wav_path

            wav: np.ndarray = _model.generate(**generate_kwargs)
            out_path = OUTPUT_DIR / f"{page.page_id}.{format}"
            _write_audio(wav, sample_rate, out_path, fmt=format)
            results.append({"page_id": page.page_id, "file_path": str(out_path)})

    finally:
        if ref_is_temp and ref_wav_path:
            Path(ref_wav_path).unlink(missing_ok=True)

    return {"files": results, "format": format, "sample_rate": sample_rate}
