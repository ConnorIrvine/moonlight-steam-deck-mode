import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import deckmode


class SimulatedSunshineService:
    def __init__(self):
        self.state = "RUNNING"
        self.pending_polls = 0
        self.commands = []

    def run(self, command, **_kwargs):
        action = command[1]
        self.commands.append(action)
        if action == "stop":
            self.state = "STOP_PENDING"
            self.pending_polls = 3
        elif action == "start":
            self.state = "START_PENDING"
            self.pending_polls = 3
        elif action == "query" and self.state.endswith("_PENDING"):
            self.pending_polls -= 1
            if self.pending_polls == 0:
                self.state = "STOPPED" if self.state == "STOP_PENDING" else "RUNNING"
        return SimpleNamespace(returncode=0, stdout=f"STATE : 4 {self.state}", stderr="")


class RestartTests(unittest.TestCase):
    def test_waits_through_slow_stop_and_start_and_web_readiness(self):
        service = SimulatedSunshineService()
        with tempfile.TemporaryDirectory() as temporary:
            apps = Path(temporary) / "apps.json"
            connection = mock.MagicMock()
            with (mock.patch.object(deckmode.subprocess, "run", side_effect=service.run),
                  mock.patch.object(deckmode.time, "sleep"),
                  mock.patch.object(deckmode.socket, "create_connection", return_value=connection) as connect):
                deckmode.reload_sunshine(apps)
        self.assertEqual(service.state, "RUNNING")
        self.assertEqual(service.commands.count("stop"), 1)
        self.assertEqual(service.commands.count("start"), 1)
        self.assertGreaterEqual(service.commands.count("query"), 7)
        connect.assert_called_once_with(("127.0.0.1", 47990), timeout=1)

    def test_uses_configured_web_port(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "sunshine.conf"
            config.write_text("port = 48000\n", encoding="utf-8")
            self.assertEqual(deckmode.sunshine_web_endpoint(config.with_name("apps.json")),
                             ("127.0.0.1", 48001))


if __name__ == "__main__":
    unittest.main()
