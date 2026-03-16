"""
main.py
-------
Entry point for Interview Assistant.

Wires together:
  AudioCapture  ──(raw audio)──▶  Transcriber  ──(text)──▶  GUI
"""

from __future__ import annotations

import sys
import threading
import numpy as np

from audio_capture import AudioCapture
from transcriber import Transcriber
from gui import InterviewAssistantGUI


def _check_deps() -> None:
    """Print a friendly error if required packages are missing."""
    missing = []
    try:
        import sounddevice  # noqa: F401
    except ImportError:
        missing.append("sounddevice")
    try:
        import funasr  # noqa: F401
    except ImportError:
        missing.append("funasr")
    try:
        import modelscope  # noqa: F401
    except ImportError:
        missing.append("modelscope")
    if missing:
        print(
            "\n❌  缺少依赖包，请先运行安装脚本：\n"
            "   Linux/macOS: bash setup.sh\n"
            "   Windows:     setup_windows.bat\n\n"
            f"   缺少的包: {', '.join(missing)}\n"
        )
        sys.exit(1)


class InterviewAssistant:
    """Top-level orchestrator."""

    def __init__(self) -> None:
        self._audio = AudioCapture()
        self._transcriber = Transcriber(language="zh")
        self._gui = InterviewAssistantGUI()

        # Wire GUI callbacks
        self._gui.on_start = self._start_listening
        self._gui.on_stop  = self._stop_listening

        # Populate device list
        devices = AudioCapture.list_devices()
        if not devices:
            self._gui.set_status("⚠️ 未找到音频输入设备")
        else:
            self._gui.set_devices(devices)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model_bg(self) -> None:
        """Load FunASR Paraformer in a background thread."""
        try:
            self._transcriber.load_model(
                progress_callback=self._gui.set_status
            )
        except Exception as exc:
            self._gui.set_status(f"❌ 模型加载失败: {exc}")

    # ------------------------------------------------------------------
    # Listen control
    # ------------------------------------------------------------------

    def _start_listening(self) -> None:
        if not self._transcriber.is_loaded:
            self._gui.set_status("⏳ 模型尚未加载完成，请稍候…")
            return

        # Apply current language choice
        self._transcriber.set_language(self._gui.get_language())
        self._transcriber.reset_vad()

        device_id = self._gui.get_selected_device_id()
        self._gui.set_listening(True)

        def _audio_cb(chunk: np.ndarray) -> None:
            rms = AudioCapture.rms(chunk)
            self._gui.update_volume(rms)
            self._transcriber.process_chunk(chunk, self._on_transcript)

        try:
            self._audio.start(device_id=device_id, callback=_audio_cb)
        except Exception as exc:
            self._gui.set_listening(False)
            self._gui.set_status(f"❌ 无法打开音频设备: {exc}")

    def _stop_listening(self) -> None:
        self._audio.stop()
        self._transcriber.reset_vad()
        self._gui.set_listening(False)
        self._gui.update_volume(0.0)

    # ------------------------------------------------------------------
    # Transcription callback (background thread → GUI queue)
    # ------------------------------------------------------------------

    def _on_transcript(self, text: str) -> None:
        self._gui.append_transcription(text)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self) -> None:
        # Load model in background so GUI is immediately responsive
        threading.Thread(target=self._load_model_bg, daemon=True).start()
        self._gui.run()


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _check_deps()
    app = InterviewAssistant()
    app.run()
