import ctypes
import unittest

import deckmode
import display_toggle as win


class FakeApi:
    def __init__(self):
        self.seen = None

    def SetDisplayConfig(self, path_count, paths, mode_count, modes, flags):
        self.seen = (path_count, mode_count, flags, paths[0].sourceInfo.id,
                     modes[0].infoType)
        return 0


class DisplaySnapshotTests(unittest.TestCase):
    def test_round_trip_preserves_supplied_path_and_mode(self):
        path = win.PATH_INFO()
        path.sourceInfo.id = 37
        mode = win.MODE_INFO()
        mode.infoType = 2
        saved = deckmode.encode_config([path], [mode])
        self.assertEqual(len(__import__("base64").b64decode(saved["paths"])),
                         ctypes.sizeof(win.PATH_INFO))
        api = FakeApi()
        deckmode.apply_config(api, saved, deckmode.SDC_VALIDATE)
        self.assertEqual(api.seen, (1, 1, deckmode.SDC_USE_SUPPLIED_DISPLAY_CONFIG |
                                    deckmode.SDC_VALIDATE, 37, 2))


if __name__ == "__main__":
    unittest.main()
