"""
audio_capture.py
----------------
Captures system audio (loopback) from video conferencing software.

On Linux:  Select a PulseAudio/PipeWire "monitor" source.
On Windows: Select "Stereo Mix" or WASAPI loopback device.
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
            is_monitor = (
                "monitor" in name.lower()
                or "loopback" in name.lower()
                or "stereo mix" in name.lower()
                or "what u hear" in name.lower()
            )
            devices.append(
                {
                    "id": idx,
                    "name": name,
                    "channels": dev["max_input_channels"],
                    "sample_rate": int(dev["default_samplerate"]),
                    "is_monitor": is_monitor,
                }
            )
        return devices

    @staticmethod
    def preferred_device(devices: List[Dict]) -> Optional[int]:
        """
        Return the id of the best default device for meeting audio capture.
        Prefers monitor/loopback sources; falls back to first available.
        """
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
