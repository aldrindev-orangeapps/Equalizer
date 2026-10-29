import tempfile
import unittest
from pathlib import Path

from equalizer_backend import EqualizerState, FREQUENCIES
from settings_store import SettingsStore, preset_state


class SettingsStoreTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SettingsStore(Path(directory) / "settings.json")
            state = EqualizerState(True, -3, {frequency: 2 for frequency in FREQUENCIES})
            custom = {"My sound": state}
            store.save(state, custom)
            loaded, presets = store.load()
            self.assertEqual(state, loaded)
            self.assertEqual(custom, presets)

    def test_invalid_file_falls_back_to_flat(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("not json", encoding="utf-8")
            state, presets = SettingsStore(path).load()
            self.assertEqual(EqualizerState.flat(), state)
            self.assertEqual({}, presets)

    def test_bass_preset_has_automatic_headroom(self) -> None:
        state = preset_state("Bass Boost")
        self.assertEqual(-8, state.preamp)
        self.assertEqual(6, state.gains[31])
        self.assertEqual(8, state.gains[62])

    def test_deep_bass_targets_low_bands_without_clipping(self) -> None:
        state = preset_state("Deep Bass")
        self.assertEqual(-12, state.preamp)
        self.assertEqual(12, state.gains[62])
        self.assertLessEqual(state.preamp + max(state.gains.values()), 0)


if __name__ == "__main__":
    unittest.main()
