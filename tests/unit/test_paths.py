from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from algocode.storage.paths import default_data_dir


class PathTests(unittest.TestCase):
    def test_windows_path_uses_local_app_data(self) -> None:
        with (
            patch.object(sys, "platform", "win32"),
            patch.dict(
                "os.environ", {"LOCALAPPDATA": "C:/Users/example/AppData/Local"}, clear=True
            ),
        ):
            self.assertEqual(
                default_data_dir(),
                Path("C:/Users/example/AppData/Local/algocode"),
            )

    def test_linux_path_respects_xdg_data_home(self) -> None:
        with (
            patch.object(sys, "platform", "linux"),
            patch.dict("os.environ", {"XDG_DATA_HOME": "/tmp/xdg"}, clear=True),
        ):
            self.assertEqual(default_data_dir(), Path("/tmp/xdg/algocode"))


if __name__ == "__main__":
    unittest.main()
