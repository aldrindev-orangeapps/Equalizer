"""Local preset and last-session persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path

from equalizer_backend import EqualizerState, FREQUENCIES


DEFAULT_PRESETS: dict[str, tuple[float, ...]] = {
    "Flat": (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    "Bass Boost": (6, 8, 7, 4, 1, 0, 0, 0, 0, 0),
    "Deep Bass": (9, 12, 10, 6, 2, 0, -1, -1, 0, 0),
    "Vocal": (-2, -1, 0, 1, 2, 3, 3, 2, 1, 0),
    "Gaming": (3, 2, 0, -1, 0, 2, 4, 3, 1, 0),
    "Movies": (4, 3, 1, 0, 1, 2, 3, 3, 2, 1),
    "Treble Boost": (0, 0, 0, 0, 0, 1, 3, 5, 6, 5),
}


def preset_state(name: str) -> EqualizerState:
    values = DEFAULT_PRESETS[name]
    gains = dict(zip(FREQUENCIES, values))
    return EqualizerState(True, -max(0.0, max(values)), gains)


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            path = base / "LaptopEqualizer" / "settings.json"
        self.path = Path(path)

    def load(self) -> tuple[EqualizerState, dict[str, EqualizerState]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            state = self._decode_state(payload["state"])
            custom = {name: self._decode_state(value) for name, value in payload.get("custom_presets", {}).items()}
            return state, custom
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return EqualizerState.flat(), {}

    def save(self, state: EqualizerState, custom_presets: dict[str, EqualizerState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "state": self._encode_state(state),
            "custom_presets": {name: self._encode_state(value) for name, value in custom_presets.items()},
        }
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)

    @staticmethod
    def _encode_state(state: EqualizerState) -> dict[str, object]:
        state = state.normalized()
        return {"enabled": state.enabled, "preamp": state.preamp, "gains": {str(k): v for k, v in state.gains.items()}}

    @staticmethod
    def _decode_state(payload: dict[str, object]) -> EqualizerState:
        raw_gains = payload["gains"]
        if not isinstance(raw_gains, dict):
            raise TypeError("gains must be an object")
        return EqualizerState(
            bool(payload.get("enabled", True)),
            float(payload.get("preamp", 0)),
            {frequency: float(raw_gains[str(frequency)]) for frequency in FREQUENCIES},
        ).normalized()
