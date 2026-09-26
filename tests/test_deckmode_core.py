import unittest

import deckmode_core as core


class ModeSelectionTests(unittest.TestCase):
    def test_highest_exact_16_to_10_at_or_above_800p(self):
        modes = [
            core.Mode(1920, 1080, 144),
            core.Mode(1280, 800, 60),
            core.Mode(1920, 1200, 60),
            core.Mode(2560, 1600, 60),
            core.Mode(2560, 1440, 144),
        ]
        self.assertEqual(core.choose_mode(modes, modes[0]), modes[3])

    def test_refresh_prefers_current_at_same_resolution(self):
        modes = [core.Mode(1920, 1200, 60), core.Mode(1920, 1200, 144)]
        self.assertEqual(core.choose_mode(modes, core.Mode(2560, 1440, 60)), modes[0])

    def test_no_supported_mode_fails(self):
        with self.assertRaisesRegex(ValueError, "no 16:10"):
            core.choose_mode([core.Mode(1280, 720)], core.Mode(1280, 720))

    def test_single_monitor_does_not_change_topology(self):
        self.assertFalse(core.should_change_topology(1))
        self.assertTrue(core.should_change_topology(2))


class SunshineEntryTests(unittest.TestCase):
    def test_add_preserves_other_apps(self):
        original = {"env": {"TEST": "value"}, "apps": [{"name": "Desktop"}]}
        entry = {"name": core.APP_NAME, "working-dir": r"C:\ProgramData\MoonlightDeckMode"}
        result, action = core.merge_app_list(original, entry)
        self.assertEqual(action, "added")
        self.assertEqual(result["apps"][0], {"name": "Desktop"})
        self.assertEqual(result["env"], {"TEST": "value"})
        self.assertEqual(core.merge_app_list(result, entry)[1], "unchanged")

    def test_name_collision_is_not_overwritten(self):
        original = {"apps": [{"name": core.APP_NAME, "working-dir": r"C:\Other"}]}
        with self.assertRaisesRegex(ValueError, "unrelated"):
            core.merge_app_list(original, {"name": core.APP_NAME})


if __name__ == "__main__":
    unittest.main()
