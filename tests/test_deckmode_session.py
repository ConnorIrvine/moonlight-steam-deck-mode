import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import deckmode


class Proceeded(Exception):
    """Raised once start_session moves past the stale-state check."""


class StaleSessionTests(unittest.TestCase):
    def start(self, state_text, active_paths=2, width=2560, height=1440):
        with tempfile.TemporaryDirectory() as temporary:
            state_dir = Path(temporary)
            state_file = state_dir / "session.json"
            state_file.write_text(state_text, encoding="utf-8")
            primary = SimpleNamespace(DeviceName=r"\.\DISPLAY2")
            current = SimpleNamespace(dmPelsWidth=width, dmPelsHeight=height)
            with (mock.patch.object(deckmode, "STATE_DIR", state_dir),
                  mock.patch.object(deckmode.win, "windows_api"),
                  mock.patch.object(deckmode, "current_display", return_value=(primary, [1], current)),
                  mock.patch.object(deckmode, "query_config", return_value=([1] * active_paths, [])),
                  mock.patch.object(deckmode, "restore") as restore,
                  mock.patch.object(deckmode, "choose_display_mode", side_effect=Proceeded) as choose,
                  mock.patch("sys.stdout")):
                try:
                    deckmode.start_session()
                except Proceeded:
                    pass
                restore.assert_not_called()
                return choose.called, state_file.exists()

    def saved(self):
        return json.dumps({"version": deckmode.STATE_VERSION, "primary": r"\.\DISPLAY2",
                           "original": [2560, 1440, 180, 32], "target": [1920, 1200],
                           "changed_topology": True, "configuration": {}})

    def test_leftover_state_is_discarded_and_setup_detected_fresh(self):
        detected, remaining = self.start(self.saved())
        self.assertTrue(detected)
        self.assertFalse(remaining)

    def test_unreadable_state_is_discarded(self):
        detected, remaining = self.start("{not json")
        self.assertTrue(detected)
        self.assertFalse(remaining)

    def test_running_session_keeps_its_state(self):
        detected, remaining = self.start(self.saved(), active_paths=1, width=1920, height=1200)
        self.assertFalse(detected)
        self.assertTrue(remaining)


if __name__ == "__main__":
    unittest.main()
