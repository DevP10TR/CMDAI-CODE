"""Voice recording and Speech-to-Text (local faster-whisper + optional API) for CMDAI CODE."""

from __future__ import annotations

import array
import math
import os
import tempfile
import threading
import time
import wave
from typing import Any, Dict, List, Optional

VOICE_MODEL_CATALOG: List[Dict[str, str]] = [
    {"provider": "local", "id": "small", "name": "Whisper Small (Local)", "note": "offline · ~500 MB · fast"},
    {"provider": "local", "id": "base", "name": "Whisper Base (Local)", "note": "offline · ~150 MB · lightest"},
    {"provider": "local", "id": "medium", "name": "Whisper Medium (Local)", "note": "offline · ~1.5 GB · accurate"},
    {"provider": "local", "id": "large-v3-turbo", "name": "Whisper Large v3 Turbo (Local)", "note": "offline · ~1.6 GB · best PL"},
    {"provider": "groq", "id": "whisper-large-v3-turbo", "name": "Whisper Large v3 Turbo (Groq)", "note": "free tier API"},
    {"provider": "groq", "id": "whisper-large-v3", "name": "Whisper Large v3 (Groq)", "note": "free tier API"},
    {"provider": "openai", "id": "whisper-1", "name": "Whisper-1 (OpenAI)", "note": "paid API"},
    {"provider": "openai", "id": "gpt-4o-mini-transcribe", "name": "GPT-4o Mini Transcribe (OpenAI)", "note": "paid API"},
    {"provider": "ovh", "id": "whisper-large-v3-turbo", "name": "Whisper Large v3 Turbo (OVH)", "note": "paid API"},
    {"provider": "ovh", "id": "whisper-large-v3", "name": "Whisper Large v3 (OVH)", "note": "paid API"},
]

_API_AUDIO_ENDPOINTS: Dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1/audio/transcriptions",
    "openai": "https://api.openai.com/v1/audio/transcriptions",
    "ovh": "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/audio/transcriptions",
}

_WHISPER_CACHE: Dict[str, Any] = {}
_WHISPER_LOCK = threading.Lock()


class VoiceRecorder:
    """Thread-safe 16 kHz mono WAV microphone recorder using sounddevice."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._lock = threading.Lock()
        self._stream: Any = None
        self._chunks: List[bytes] = []
        self._recording = False
        self._started_at: float = 0.0
        self._current_level: float = 0.0

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def current_level(self) -> float:
        return self._current_level

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @property
    def elapsed_seconds(self) -> float:
        if not self._recording:
            return 0.0
        return max(0.0, time.time() - self._started_at)

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "Missing 'sounddevice'. Install voice dependencies: pip install sounddevice faster-whisper"
            ) from exc

        with self._lock:
            if self._recording:
                return
            self._chunks = []

            def _callback(indata, frames, time_info, status):
                if self._recording:
                    raw = bytes(indata)
                    self._chunks.append(raw)
                    try:
                        samples = array.array("h")
                        samples.frombytes(raw)
                        if samples:
                            rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768.0
                            self._current_level = min(1.0, rms * 14.0)
                    except Exception:
                        pass

            try:
                self._stream = sd.RawInputStream(
                    samplerate=self.sample_rate,
                    channels=1,
                    dtype="int16",
                    callback=_callback,
                )
                self._stream.start()
                self._recording = True
                self._started_at = time.time()
            except Exception as exc:
                self._stream = None
                self._recording = False
                raise RuntimeError(f"Microphone error: {exc}") from exc

    def stop(self) -> str:
        with self._lock:
            self._recording = False
            self._current_level = 0.0
            stream = self._stream
            self._stream = None
            chunks = list(self._chunks)
            self._chunks = []

        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

        if not chunks:
            return ""

        return self._write_wav(chunks)

    def snapshot_wav(self) -> str:
        """Write currently buffered audio to a temp WAV without stopping recording."""
        with self._lock:
            if not self._recording or not self._chunks:
                return ""
            chunks = list(self._chunks)
        return self._write_wav(chunks)

    def _write_wav(self, chunks: List[bytes]) -> str:
        fd, wav_path = tempfile.mkstemp(prefix="cmdai_voice_", suffix=".wav")
        os.close(fd)
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b"".join(chunks))
        return wav_path

    def cancel(self) -> None:
        wav_path = self.stop()
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass


def _get_local_whisper(model_id: str) -> Any:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Missing 'faster-whisper'. Install it with: pip install faster-whisper"
        ) from exc

    with _WHISPER_LOCK:
        cached = _WHISPER_CACHE.get(model_id)
        if cached is not None:
            return cached
        download_root: Optional[str] = None
        try:
            from .model_paths import resolve_models_dir
            wdir = os.path.join(resolve_models_dir(), "whisper")
            os.makedirs(wdir, exist_ok=True)
            download_root = wdir
        except Exception:
            download_root = None
        model = WhisperModel(model_id, device="auto", compute_type="int8", download_root=download_root)
        _WHISPER_CACHE[model_id] = model
        return model


def transcribe_audio(
    wav_path: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    language: Optional[str] = None,
) -> str:
    """Transcribe a WAV file using local faster-whisper or a configured API provider."""
    if not wav_path or not os.path.isfile(wav_path):
        return ""

    from .settings import get_settings
    settings = get_settings()
    vcfg = settings.config.get("voice", {}) if isinstance(settings.config.get("voice"), dict) else {}

    prov = str(provider or vcfg.get("provider", "local") or "local").strip().lower()
    mod = str(model or vcfg.get("model", "small") or "small").strip()
    lang = str(language or vcfg.get("language", "auto") or "auto").strip().lower()
    lang_arg = None if lang in ("", "auto") else lang

    if prov == "local":
        wm = _get_local_whisper(mod)
        kwargs: Dict[str, Any] = {"beam_size": 5}
        if lang_arg:
            kwargs["language"] = lang_arg
        try:
            segments, _info = wm.transcribe(wav_path, vad_filter=True, **kwargs)
        except Exception:
            segments, _info = wm.transcribe(wav_path, **kwargs)
        parts = [str(seg.text or "").strip() for seg in segments]
        return " ".join(p for p in parts if p).strip()

    endpoint = _API_AUDIO_ENDPOINTS.get(prov)
    if not endpoint:
        raise RuntimeError(f"Unsupported voice provider: {prov}")

    api_key = settings.get_api_key(prov)
    if not api_key:
        raise RuntimeError(f"Missing API key for '{prov}'. Set it in /voicemodel (Ctrl+D).")

    import requests
    headers = {"Authorization": f"Bearer {api_key}"}
    data: Dict[str, str] = {"model": mod}
    if lang_arg:
        data["language"] = lang_arg

    with open(wav_path, "rb") as f:
        resp = requests.post(
            endpoint,
            headers=headers,
            data=data,
            files={"file": ("audio.wav", f, "audio/wav")},
            timeout=60,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"{prov} STT error ({resp.status_code}): {resp.text[:200]}")

    payload = resp.json()
    if isinstance(payload, dict):
        return str(payload.get("text") or "").strip()
    return ""
