import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import deckmode


class InstallerTests(unittest.TestCase):
    def test_install_preserves_existing_sunshine_apps_and_backs_up(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            apps = root / "config" / "apps.json"
            apps.parent.mkdir()
            original = {"env": {"KEEP": "yes"}, "apps": [{"name": "Desktop"}]}
            apps.write_text(json.dumps(original), encoding="utf-8")
            art = root / "art.png"
            art.write_bytes(b"test image")
            program = root / "installed"
            plan = {"primary": "DISPLAY1", "current": (1920, 1080),
                    "active_displays": 1, "connected_displays": 1,
                    "target": (1920, 1200), "steam": Path("steam.exe"), "apps": apps}
            with (mock.patch.object(deckmode.sys, "frozen", True, create=True),
                  mock.patch.object(deckmode, "PROGRAM_DIR", program),
                  mock.patch.object(deckmode, "check", return_value=plan),
                  mock.patch.object(deckmode, "is_admin", return_value=True),
                  mock.patch.object(deckmode, "resource", return_value=art),
                  mock.patch.object(deckmode, "reload_sunshine") as reload_service):
                deckmode.install(apps)
                result = json.loads(apps.read_text(encoding="utf-8"))
                self.assertEqual(result["apps"][0], {"name": "Desktop"})
                self.assertEqual(result["apps"][1]["name"], "Moonlight Deck Mode")
                self.assertEqual(result["env"], {"KEEP": "yes"})
                backups = list(program.glob("apps.backup.*.json"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(json.loads(backups[0].read_text()), original)
                self.assertTrue((program / deckmode.EXECUTABLE_NAME).is_file())
                reload_service.assert_called_once()
                # Re-running the installer must retry the reload after a
                # previous restart failed, even if the JSON entry is current.
                deckmode.install(apps)
                self.assertEqual(reload_service.call_count, 2)
                self.assertEqual(len(list(program.glob("apps.backup.*.json"))), 1)


if __name__ == "__main__":
    unittest.main()
