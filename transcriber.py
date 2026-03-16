"""
transcriber.py
--------------
Real-time speech-to-text using faster-whisper (local, offline).
Project: https://github.com/SYSTRAN/faster-whisper

Strategy
--------
* Audio arrives in 100 ms chunks from AudioCapture.
* A simple energy-based VAD accumulates chunks into a speech segment.
* When silence >= SILENCE_SECONDS the segment is sent to Whisper.
* A hard MAX_SEGMENT_SECONDS cap prevents unbounded buffering.
* Transcription runs in a daemon thread so the audio callback is never blocked.
"""

from __future__ import annotations

import threading
import numpy as np
from typing import Callable, Optional

# Lazy import – only needed at runtime
try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None  # type: ignore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SILENCE_THRESHOLD = 0.012      # RMS below this → silence
SILENCE_SECONDS   = 1.2        # seconds of silence → end of segment
MIN_SPEECH_SECONDS = 0.4       # ignore segments shorter than this
MAX_SEGMENT_SECONDS = 30.0     # hard cap: force-flush after this duration
SAMPLE_RATE = 16000            # must match AudioCapture.SAMPLE_RATE
CHUNK_SECONDS = 0.1            # AudioCapture.CHUNK_MS / 1000


class Transcriber:
    """
    Accumulates audio chunks and transcribes completed speech segments.

    Usage::

        t = Transcriber(model_size="base", language="zh")
        t.load_model(progress_cb=print)          # blocking; call in a thread
        t.process_chunk(audio_array, my_callback)
    """

    def __init__(
        self,
        model_size: str = "base",
        language: str = "zh",
        device: str = "cpu",
    ):
        if WhisperModel is None:
            raise ImportError(
                "faster-whisper is not installed. Run: pip install faster-whisper"
            )

        self.model_size = model_size
        self.language = language          # "zh", "en", or "auto" (None)
        self.device = device

        self._model: Optional[WhisperModel] = None
        self._loaded = False

        # VAD state
        self._buffer: list[float] = []
        self._silence_frames = 0
        self._speech_frames = 0

        self._silence_frame_limit = int(SILENCE_SECONDS / CHUNK_SECONDS)
        self._min_speech_frames   = int(MIN_SPEECH_SECONDS / CHUNK_SECONDS)
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
        Download (first run) and load the Whisper model.
        Call this in a background thread; it may take a while.
        """
        _cb = progress_callback or (lambda _: None)
        _cb(f"正在加载模型 faster-whisper [{self.model_size}]，首次运行需下载…")

        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type="int8",       # int8 is fast on CPU, good enough quality
        )
        self._loaded = True
        _cb("✅ 模型加载完成，可以开始监听")

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
        is_speech = rms > SILENCE_THRESHOLD

        if is_speech:
            self._buffer.extend(chunk.tolist())
            self._speech_frames += 1
            self._silence_frames = 0

            # Hard cap – flush even if speech hasn't ended
            if self._speech_frames + self._silence_frames >= self._max_segment_frames:
                self._flush(on_transcript)
        else:
            if self._buffer:
                self._silence_frames += 1
                self._buffer.extend(chunk.tolist())  # keep a bit of trailing silence

                if self._silence_frames >= self._silence_frame_limit:
                    if self._speech_frames >= self._min_speech_frames:
                        self._flush(on_transcript)
                    else:
                        # Too short – discard silently
                        self._reset()

    def _flush(self, on_transcript: Callable[[str], None]) -> None:
        """Copy buffer and schedule transcription in a daemon thread."""
        audio = np.array(self._buffer, dtype=np.float32)
        self._reset()

        thread = threading.Thread(
            target=self._transcribe,
            args=(audio, on_transcript),
            daemon=True,
        )
        thread.start()

    def _reset(self) -> None:
        self._buffer.clear()
        self._speech_frames = 0
        self._silence_frames = 0

    def _transcribe(
        self, audio: np.ndarray, on_transcript: Callable[[str], None]
    ) -> None:
        """Run Whisper inference (called from a background thread)."""
        with self._job_lock:
            try:
                lang = self.language if self.language != "auto" else None
                segments, _info = self._model.transcribe(
                    audio,
                    language=lang,
                    beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=300),
                )
                text = " ".join(seg.text for seg in segments).strip()
                if text:
                    on_transcript(text)
            except Exception as exc:
                print(f"[Transcriber] error: {exc}")

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------

    def set_language(self, lang: str) -> None:
        """Change language on the fly ('zh', 'en', 'auto')."""
        self.language = lang

    def reset_vad(self) -> None:
        """Discard accumulated audio (e.g. when user stops listening)."""
        self._reset()
