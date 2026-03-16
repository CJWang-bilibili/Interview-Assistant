"""
audio_capture.py
----------------
Captures system audio (loopback) from video conferencing software.

推荐方案 (Windows): VB-CABLE Virtual Audio Device
  安装: https://vb-audio.com/Cable/ (VBCABLE_Driver_Pack45.exe)
  安装后会新增两个设备：
    • CABLE Input  (虚拟扬声器) — 在会议软件中将「扬声器」设置为此设备
    • CABLE Output (虚拟麦克风) — 本工具从此设备读取音频

  ⚠️  使用 CABLE Input 作为扬声器后听不到声音的解决方法：
  控制面板 → 声音 → 录制 → CABLE Output → 属性
  → 侦听 → 勾选「侦听此设备」→ 选择你的真实耳机/扬声器 → 确定

On Linux:  Select a PulseAudio/PipeWire "monitor" source.
On macOS:  Install BlackHole (https://github.com/ExistentialAudio/BlackHole)
           then select it as the input device.
"""

import sounddevice as sd
import numpy as np
import queue
from typing import Optional, Callable, List, Dict


class AudioCapture:
    """Manages audio device listing and real-time capture."""

    SAMPLE_RATE = 16000   # Whisper expects 16 kHz
    CHUNK_MS = 100        # 100 ms per callback chunk

    def __init__(self):
        self._chunk_frames = int(self.SAMPLE_RATE * self.CHUNK_MS / 1000)
        self._stream: Optional[sd.InputStream] = None
        self.is_capturing = False
        # Raw audio queue for consumers that want to pull data themselves
        self.audio_queue: queue.Queue = queue.Queue()

    # ------------------------------------------------------------------
    # Device helpers
    # ------------------------------------------------------------------

    @staticmethod
    def list_devices() -> List[Dict]:
        """
        Return all usable input devices including system-audio monitors.

        Each entry: {id, name, channels, sample_rate, is_monitor}
        """
        devices = []
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] < 1:
                continue
            name: str = dev["name"]
            name_lower = name.lower()
            # VB-CABLE Output is the virtual mic we read from.
            # Also keep Linux monitor sources and other loopback devices.
            is_vbcable = "cable output" in name_lower
            is_monitor = (
                is_vbcable
                or "monitor" in name_lower
                or "loopback" in name_lower
                or "what u hear" in name_lower
            )
            devices.append(
                {
                    "id": idx,
                    "name": name,
                    "channels": dev["max_input_channels"],
                    "sample_rate": int(dev["default_samplerate"]),
                    "is_monitor": is_monitor,
                    "is_vbcable": is_vbcable,
                }
            )
        return devices

    @staticmethod
    def preferred_device(devices: List[Dict]) -> Optional[int]:
        """
        Return the id of the best default device for meeting audio capture.
        Priority: VB-CABLE Output > other monitors > first available.
        """
        # 1st priority: VB-CABLE Output
        for dev in devices:
            if dev.get("is_vbcable"):
                return dev["id"]
        # 2nd priority: any monitor/loopback
        for dev in devices:
            if dev["is_monitor"]:
                return dev["id"]
        return devices[0]["id"] if devices else None

    # ------------------------------------------------------------------
    # Capture control
    # ------------------------------------------------------------------

    def start(
        self,
        device_id: Optional[int] = None,
        callback: Optional[Callable[[np.ndarray], None]] = None,
    ) -> None:
        """
        Begin capturing audio.

        Args:
            device_id: sounddevice device index. None = system default.
            callback:  Called with each (chunk_frames,) float32 ndarray.
        """
        if self.is_capturing:
            return

        self.is_capturing = True

        def _sd_callback(indata, frames, time_info, status):
            if not self.is_capturing:
                return
            mono = indata[:, 0].copy().astype(np.float32)
            self.audio_queue.put(mono)
            if callback:
                callback(mono)

        self._stream = sd.InputStream(
            device=device_id,
            channels=1,
            samplerate=self.SAMPLE_RATE,
            blocksize=self._chunk_frames,
            dtype="float32",
            callback=_sd_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop capturing and release the audio stream."""
        self.is_capturing = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        # Drain the queue
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def rms(audio: np.ndarray) -> float:
        """Root-mean-square energy of an audio chunk."""
        return float(np.sqrt(np.mean(audio ** 2) + 1e-9))
