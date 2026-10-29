"""Equalizer APO discovery and configuration for Laptop Equalizer."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


FREQUENCIES = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
APP_CONFIG_NAME = "laptop-equalizer.txt"
BEGIN_MARKER = "# BEGIN Laptop Equalizer (managed by the app)"
END_MARKER = "# END Laptop Equalizer"


class EqualizerError(RuntimeError):
    """Raised when Equalizer APO cannot be configured safely."""


@dataclass(frozen=True)
class EqualizerState:
    enabled: bool
    preamp: float
    gains: dict[int, float]

    @classmethod
    def flat(cls) -> "EqualizerState":
        return cls(True, 0.0, {frequency: 0.0 for frequency in FREQUENCIES})

    def normalized(self) -> "EqualizerState":
        missing = set(FREQUENCIES) - set(self.gains)
        if missing:
            raise EqualizerError(f"Missing equalizer bands: {sorted(missing)}")
        return EqualizerState(
            bool(self.enabled),
            _clamp(float(self.preamp), -20.0, 12.0),
            {frequency: _clamp(float(self.gains[frequency]), -12.0, 12.0) for frequency in FREQUENCIES},
        )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def format_db(value: float) -> str:
    rounded = round(value, 1)
    return f"{rounded:.1f}".rstrip("0").rstrip(".")


def render_apo_config(state: EqualizerState) -> str:
    """Render a deterministic Equalizer APO file for the shared output profile."""
    state = state.normalized()
    lines = [
        "# Laptop Equalizer - generated file; edit settings in the app",
        f"# Enabled: {'yes' if state.enabled else 'no'}",
    ]
    if not state.enabled:
        lines.append("# The app is bypassed; no filters are active.")
        return "\n".join(lines) + "\n"
    points = "; ".join(
        f"{frequency} {format_db(state.gains[frequency])}" for frequency in FREQUENCIES
    )
    lines.extend((f"Preamp: {format_db(state.preamp)} dB", f"GraphicEQ: {points}"))
    return "\n".join(lines) + "\n"


def recommended_preamp(gains: Mapping[int, float]) -> float:
    """Return conservative headroom based on the largest positive band gain."""
    return -max(0.0, max((float(value) for value in gains.values()), default=0.0))


def discover_config_dir() -> Path | None:
    """Find the Equalizer APO config directory in the common install locations."""
    candidates: list[Path] = []
    custom = os.environ.get("EQUALIZER_APO_CONFIG")
    if custom:
        candidates.append(Path(custom).expanduser())
    for variable in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        root = os.environ.get(variable)
        if root:
            candidates.append(Path(root) / "EqualizerAPO" / "config")
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).casefold()
        if key not in seen and candidate.is_dir() and (candidate / "config.txt").is_file():
            return candidate
        seen.add(key)
    return None


class EqualizerApoBackend:
    """Safely owns one included file without replacing the user's APO configuration."""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = Path(config_dir)
        self.main_config = self.config_dir / "config.txt"
        self.app_config = self.config_dir / APP_CONFIG_NAME

    @property
    def is_integrated(self) -> bool:
        if not self.main_config.is_file():
            return False
        try:
            text = self.main_config.read_text(encoding="utf-8-sig")
        except OSError:
            return False
        return BEGIN_MARKER in text and END_MARKER in text and f"Include: {APP_CONFIG_NAME}" in text

    def install_integration(self) -> None:
        """Append a marked include block, preserving all existing user filters."""
        if not self.main_config.is_file():
            raise EqualizerError(f"Equalizer APO configuration was not found at {self.main_config}")
        try:
            original = self.main_config.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise EqualizerError(f"Could not read {self.main_config}: {exc}") from exc
        if BEGIN_MARKER in original or END_MARKER in original:
            if self.is_integrated:
                return
            raise EqualizerError("The existing Laptop Equalizer integration block is incomplete. Remove it manually and retry.")
        separator = "" if not original or original.endswith(("\n", "\r")) else "\n"
        block = f"{BEGIN_MARKER}\nInclude: {APP_CONFIG_NAME}\n{END_MARKER}\n"
        self._atomic_write(self.main_config, original + separator + block)

    def apply(self, state: EqualizerState) -> None:
        if not self.is_integrated:
            raise EqualizerError("Complete Equalizer APO setup before applying audio settings.")
        self._atomic_write(self.app_config, render_apo_config(state))

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", newline="\n", dir=path.parent,
                prefix=f".{path.name}.", suffix=".tmp", delete=False,
            ) as handle:
                temporary_name = handle.name
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except OSError as exc:
            if temporary_name:
                try:
                    Path(temporary_name).unlink(missing_ok=True)
                except OSError:
                    pass
            raise EqualizerError(
                f"Could not update {path}. Try running the app as administrator.\n\n{exc}"
            ) from exc
