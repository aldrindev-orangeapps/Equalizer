import tempfile
import unittest
from pathlib import Path

from equalizer_backend import (
    APP_CONFIG_NAME,
    BEGIN_MARKER,
    EqualizerApoBackend,
    EqualizerError,
    EqualizerState,
    FREQUENCIES,
    recommended_preamp,
    render_apo_config,
)


class EqualizerConfigTests(unittest.TestCase):
    def test_flat_config_has_all_ten_bands(self) -> None:
        text = render_apo_config(EqualizerState.flat())
        self.assertIn("Preamp: 0 dB", text)
        self.assertIn("GraphicEQ: 31 0; 62 0", text)
        self.assertIn("16000 0", text)

    def test_disabled_config_has_no_active_filters(self) -> None:
        state = EqualizerState(False, 4, {frequency: 8 for frequency in FREQUENCIES})
        text = render_apo_config(state)
        self.assertNotIn("Preamp:", text)
        self.assertNotIn("GraphicEQ:", text)

    def test_values_are_clamped_to_safe_ui_ranges(self) -> None:
        state = EqualizerState(True, 99, {frequency: -99 for frequency in FREQUENCIES})
        normalized = state.normalized()
        self.assertEqual(12, normalized.preamp)
        self.assertTrue(all(value == -12 for value in normalized.gains.values()))

    def test_recommended_preamp_offsets_largest_boost(self) -> None:
        self.assertEqual(-6, recommended_preamp({31: 3, 62: 6, 125: -2}))
        self.assertEqual(0, recommended_preamp({31: -3, 62: -1}))


class BackendIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temporary.name)
        self.main = self.config_dir / "config.txt"
        self.main.write_text("Preamp: -1 dB\n# Existing user configuration\n", encoding="utf-8")
        self.backend = EqualizerApoBackend(self.config_dir)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_setup_preserves_existing_config_and_is_idempotent(self) -> None:
        self.backend.install_integration()
        first = self.main.read_text(encoding="utf-8")
        self.backend.install_integration()
        second = self.main.read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("Preamp: -1 dB\n# Existing user configuration"))
        self.assertEqual(1, first.count(BEGIN_MARKER))
        self.assertIn(f"Include: {APP_CONFIG_NAME}", first)

    def test_apply_writes_only_owned_file(self) -> None:
        self.backend.install_integration()
        main_after_setup = self.main.read_text(encoding="utf-8")
        self.backend.apply(EqualizerState.flat())
        self.assertEqual(main_after_setup, self.main.read_text(encoding="utf-8"))
        self.assertIn("GraphicEQ", (self.config_dir / APP_CONFIG_NAME).read_text(encoding="utf-8"))

    def test_apply_requires_integration(self) -> None:
        with self.assertRaises(EqualizerError):
            self.backend.apply(EqualizerState.flat())

    def test_incomplete_marker_is_rejected(self) -> None:
        self.main.write_text(f"{BEGIN_MARKER}\n", encoding="utf-8")
        with self.assertRaises(EqualizerError):
            self.backend.install_integration()


if __name__ == "__main__":
    unittest.main()
