"""
transcriber.py
--------------
Real-time speech-to-text using FunASR Paraformer (local, offline).
Project: https://github.com/modelscope/FunASR

Models used
-----------
* paraformer-zh        — Chinese offline ASR (state-of-the-art accuracy)
* paraformer-en        — English offline ASR
* SenseVoiceSmall      — Multilingual (zh/en/ja/ko) auto-detect mode
* fsmn-vad             — Voice activity detection
* ct-punc              — Punctuation restoration

Strategy
--------
* Audio arrives in 100 ms chunks from AudioCapture.
* Energy-based VAD accumulates chunks into a speech segment.
* When silence >= SILENCE_SECONDS the segment is sent to FunASR.
* A hard MAX_SEGMENT_SECONDS cap prevents unbounded buffering.
* Transcription runs in a daemon thread so the audio callback is never blocked.
"""

from __future__ import annotations

import threading
import numpy as np
from typing import Callable, Optional

try:
    import torch as _torch
    _TORCH_AVAILABLE = True
except ImportError:
    _torch = None  # type: ignore
    _TORCH_AVAILABLE = False

try:
    from funasr import AutoModel
except ImportError:
    AutoModel = None  # type: ignore


def _detect_device() -> str:
    """Return 'cuda' if a CUDA GPU is available, else 'cpu'."""
    if _TORCH_AVAILABLE and _torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _gpu_info() -> str:
    """Return a human-readable GPU description, or empty string on CPU."""
    if not (_TORCH_AVAILABLE and _torch.cuda.is_available()):
        return ""
    idx = _torch.cuda.current_device()
    name = _torch.cuda.get_device_name(idx)
    total_mb = _torch.cuda.get_device_properties(idx).total_memory // (1024 ** 2)
    return f"{name} ({total_mb} MB)"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SILENCE_THRESHOLD   = 0.012   # RMS below this → silence
SILENCE_SECONDS     = 1.2     # seconds of silence → end of segment
MIN_SPEECH_SECONDS  = 0.4     # ignore segments shorter than this
MAX_SEGMENT_SECONDS = 30.0    # hard cap: force-flush after this duration
SAMPLE_RATE         = 16000   # must match AudioCapture.SAMPLE_RATE
CHUNK_SECONDS       = 0.1     # AudioCapture.CHUNK_MS / 1000

# FunASR model IDs
_MODELS = {
    "zh":   "paraformer-zh",       # Chinese — best accuracy
    "en":   "paraformer-en",       # English
    "auto": "iic/SenseVoiceSmall", # Multilingual auto-detect
}


class Transcriber:
    """
    Accumulates audio chunks and transcribes completed speech segments
    using FunASR Paraformer.

    Usage::

        t = Transcriber(language="zh")
        t.load_model(progress_callback=print)   # blocking; call in a thread
        t.process_chunk(audio_array, my_callback)
    """

    def __init__(self, language: str = "zh", device: str = "cpu"):
        if AutoModel is None:
            raise ImportError(
                "funasr is not installed. Run: pip install funasr modelscope"
            )

        self.language = language
        self._device  = device
        self._model   = None
        self._loaded  = False

        # VAD state
        self._buffer: list[float] = []
        self._silence_frames = 0
        self._speech_frames  = 0

        self._silence_threshold   = SILENCE_THRESHOLD
        self._silence_frame_limit = int(SILENCE_SECONDS    / CHUNK_SECONDS)
        self._min_speech_frames   = int(MIN_SPEECH_SECONDS  / CHUNK_SECONDS)
        self._max_segment_frames  = int(MAX_SEGMENT_SECONDS / CHUNK_SECONDS)

        # Serialise transcription jobs (one at a time, FIFO)
        self._job_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(
        self, progress_callback: Optional[Callable[[str], None]] = None
    ) -> None:
        """
        Download (first run) and load the FunASR model pipeline.
        Call this in a background thread — first run downloads ~300 MB.
        Automatically uses CUDA/GPU acceleration when available.
        """
        _cb = progress_callback or (lambda _: None)
        model_id = _MODELS.get(self.language, _MODELS["zh"])

        device = _detect_device()
        gpu_desc = _gpu_info()
        if device == "cuda":
            _cb(f"🖥️ 检测到 GPU：{gpu_desc}，将使用 CUDA 加速推理")
        else:
            _cb("💻 未检测到 CUDA GPU，使用 CPU 推理（速度较慢）")

        _cb(f"正在加载模型 FunASR [{model_id}]，首次运行需下载约 300 MB…")

        try:
            self._model = AutoModel(
                model=model_id,
                vad_model="fsmn-vad",         # built-in VAD for long audio
                punc_model="ct-punc",          # punctuation restoration
                log_level="ERROR",             # suppress verbose logs
                disable_update=True,
                device=self._device,
            )
        except Exception:
            # Fallback: load without optional models if punc/vad unavailable
            _cb("⚠️ 正在尝试精简模式加载…")
            self._model = AutoModel(
                model=model_id,
                log_level="ERROR",
                disable_update=True,
                device=self._device,
            )

        self._loaded = True
        accel = f"GPU ({gpu_desc})" if device == "cuda" else "CPU"
        _cb(f"✅ FunASR 模型加载完成 [{accel}]，可以开始监听")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ------------------------------------------------------------------
    # Streaming VAD + transcription
    # ------------------------------------------------------------------

    def process_chunk(
        self,
        chunk: np.ndarray,
        on_transcript: Callable[[str], None],
    ) -> None:
        """
        Feed one audio chunk (float32, shape=(N,)) and fire *on_transcript*
        whenever a complete speech segment has been recognised.
        """
        if not self._loaded:
            return

        rms = float(np.sqrt(np.mean(chunk ** 2) + 1e-9))
        is_speech = rms > self._silence_threshold

        if is_speech:
            self._buffer.extend(chunk.tolist())
            self._speech_frames += 1
            self._silence_frames = 0

            if self._speech_frames + self._silence_frames >= self._max_segment_frames:
                self._flush(on_transcript)
        else:
            if self._buffer:
                self._silence_frames += 1
                self._buffer.extend(chunk.tolist())

                if self._silence_frames >= self._silence_frame_limit:
                    if self._speech_frames >= self._min_speech_frames:
                        self._flush(on_transcript)
                    else:
                        self._reset()

    def _flush(self, on_transcript: Callable[[str], None]) -> None:
        audio = np.array(self._buffer, dtype=np.float32)
        self._reset()
        threading.Thread(
            target=self._transcribe,
            args=(audio, on_transcript),
            daemon=True,
        ).start()

    def _reset(self) -> None:
        self._buffer.clear()
        self._speech_frames = 0
        self._silence_frames = 0

    def _transcribe(
        self, audio: np.ndarray, on_transcript: Callable[[str], None]
    ) -> None:
        """Run FunASR inference (called from a background thread)."""
        with self._job_lock:
            try:
                # FunASR expects int16 or float32 at 16 kHz
                result = self._model.generate(
                    input=audio,
                    batch_size_s=300,
                )
                if result and result[0].get("text"):
                    text = result[0]["text"].strip()
                    if text:
                        on_transcript(text)
            except Exception as exc:
                print(f"[Transcriber] error: {exc}")

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def set_language(self, lang: str) -> None:
        """
        Change language ('zh', 'en', 'auto').
        Note: requires reload if model needs to change.
        """
        if lang != self.language:
            old_model = _MODELS.get(self.language)
            self.language = lang
            # Mark as unloaded if the underlying model changed
            if _MODELS.get(lang) != old_model:
                self._loaded = False
                self._model = None

    def set_vad_params(self, threshold: float, silence_seconds: float) -> None:
        """Update VAD sensitivity (takes effect immediately, no reload needed)."""
        self._silence_threshold   = max(0.001, float(threshold))
        self._silence_frame_limit = max(1, int(float(silence_seconds) / CHUNK_SECONDS))

    def reset_vad(self) -> None:
        """Discard accumulated audio (e.g. when user stops listening)."""
        self._reset()
