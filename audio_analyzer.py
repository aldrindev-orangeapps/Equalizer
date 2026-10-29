"""Real-time Windows playback spectrum analysis using WASAPI loopback."""

from __future__ import annotations

import threading
from dataclasses import dataclass


ANALYZER_BANDS = 48


@dataclass(frozen=True)
class AnalyzerSnapshot:
    levels: tuple[float, ...]
    peak: float
    status: str
    active: bool


class PlaybackAnalyzer:
    """Capture the default Windows output without touching microphone devices."""

    def __init__(self, band_count: int = ANALYZER_BANDS) -> None:
        self.band_count = band_count
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._snapshot = AnalyzerSnapshot((0.0,) * band_count, 0.0, "Analyzer starting...", False)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._capture_loop, name="playback-analyzer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

    def snapshot(self) -> AnalyzerSnapshot:
        with self._lock:
            return self._snapshot

    def _publish(self, levels: tuple[float, ...], peak: float, status: str, active: bool) -> None:
        with self._lock:
            self._snapshot = AnalyzerSnapshot(levels, peak, status, active)

    def _capture_loop(self) -> None:
        try:
            import numpy as np
        except ImportError:
            self._publish((0.0,) * self.band_count, 0.0, "Analyzer dependencies are not installed", False)
            return
        errors: list[str] = []
        try:
            self._capture_with_pyaudio(np)
            return
        except Exception as exc:
            errors.append(self._error_message(exc))
        if self._stop.is_set():
            return
        try:
            self._capture_with_soundcard(np)
            return
        except Exception as exc:
            errors.append(self._error_message(exc))
        detail = errors[-1] if errors else "No Windows loopback device was found"
        self._publish((0.0,) * self.band_count, 0.0, f"Analyzer unavailable: {detail}", False)

    def _capture_with_pyaudio(self, np: object) -> None:
        import pyaudiowpatch as pyaudio

        audio = pyaudio.PyAudio()
        stream = None
        try:
            device = audio.get_default_wasapi_loopback()
            sample_rate = int(device["defaultSampleRate"])
            channels = max(1, int(device["maxInputChannels"]))
            chunk = 2048
            stream = audio.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=int(device["index"]),
                frames_per_buffer=chunk,
            )
            device_name = str(device.get("name", "default output")).replace(" [Loopback]", "")

            def read_frames() -> object:
                raw = stream.read(chunk, exception_on_overflow=False)
                samples = np.frombuffer(raw, dtype=np.float32)
                return samples[: chunk * channels].reshape(-1, channels)

            self._analyze(np, read_frames, sample_rate, chunk, device_name)
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            if audio is not None:
                try:
                    audio.terminate()
                except Exception:
                    pass

    def _capture_with_soundcard(self, np: object) -> None:
        import soundcard as soundcard

        speaker = soundcard.default_speaker()
        if speaker is None:
            raise RuntimeError("No default Windows speaker was found")
        loopback = soundcard.get_microphone(speaker.name, include_loopback=True)
        if loopback is None:
            raise RuntimeError("No loopback endpoint matches the default speaker")
        sample_rate = 48000
        chunk = 2048
        with loopback.recorder(samplerate=sample_rate, blocksize=chunk) as recorder:
            self._analyze(np, lambda: recorder.record(numframes=chunk), sample_rate, chunk, speaker.name)

    def _analyze(self, np: object, read_frames: object, sample_rate: int, chunk: int, device_name: str) -> None:
        window = np.hanning(chunk).astype(np.float32)
        frequencies = np.fft.rfftfreq(chunk, 1.0 / sample_rate)
        edges = np.geomspace(30.0, min(18000.0, sample_rate * 0.48), self.band_count + 1)
        smoothed = np.zeros(self.band_count, dtype=np.float32)
        while not self._stop.is_set():
            frames = np.asarray(read_frames(), dtype=np.float32)
            if frames.size < chunk:
                continue
            mono = frames[:chunk] if frames.ndim == 1 else frames[:chunk].mean(axis=1)
            spectrum = np.abs(np.fft.rfft(mono * window)) / max(1.0, chunk * 0.5)
            levels = np.zeros(self.band_count, dtype=np.float32)
            for index in range(self.band_count):
                mask = (frequencies >= edges[index]) & (frequencies < edges[index + 1])
                magnitude = float(spectrum[mask].max()) if mask.any() else 0.0
                decibels = 20.0 * np.log10(max(magnitude, 1e-7))
                levels[index] = float(np.clip((decibels + 62.0) / 62.0, 0.0, 1.0))
            smoothed = np.where(
                levels > smoothed,
                smoothed * 0.28 + levels * 0.72,
                smoothed * 0.82 + levels * 0.18,
            )
            peak = float(np.clip(
                (20.0 * np.log10(max(float(np.max(np.abs(mono))), 1e-7)) + 60.0) / 60.0,
                0.0, 1.0,
            ))
            self._publish(tuple(float(value) for value in smoothed), peak, device_name, True)

    @staticmethod
    def _error_message(exc: Exception) -> str:
        return str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
