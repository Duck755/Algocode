from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from algocode.cli.commands.vscode import (
    _bundled_vsix,
    _find_code_executable,
    vscode_install_command,
)


class VscodeCommandTests(unittest.TestCase):
    def test_bundled_vsix_exists(self) -> None:
        vsix = _bundled_vsix()
        self.assertTrue(vsix.name.endswith(".vsix"))
        self.assertGreater(vsix.stat().st_size, 0)

    def test_find_code_executable_uses_explicit_value(self) -> None:
        with patch("algocode.cli.commands.vscode.shutil.which", return_value="C:/Code/bin/code.cmd"):
            found = _find_code_executable("code.cmd")

        self.assertEqual(found, "C:/Code/bin/code.cmd")

    def test_install_command_invokes_code_installer(self) -> None:
        with (
            patch(
                "algocode.cli.commands.vscode._find_code_executable",
                return_value="code.cmd",
            ),
            patch(
                "algocode.cli.commands.vscode._install_with_code",
                return_value="installed",
            ) as install,
        ):
            vscode_install_command(
                code=None,
                force=True,
                json_output=False,
                no_color=False,
                quiet=False,
                verbose=False,
            )

        install.assert_called_once()
        args = install.call_args.args
        self.assertEqual(args[0], "code.cmd")
        self.assertIsInstance(args[1], Path)
        self.assertTrue(str(args[1]).endswith(".vsix"))


if __name__ == "__main__":
    unittest.main()
