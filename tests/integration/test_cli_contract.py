from __future__ import annotations

import unittest

from typer.testing import CliRunner

from algocode.cli.main import app


class CliContractTests(unittest.TestCase):
    def test_p0_commands_expose_uniform_output_options(self) -> None:
        commands = (
            ("init", "--help"),
            ("doctor", "--help"),
            ("baseline", "--help"),
            ("optimize", "--help"),
            ("correctness", "run", "--help"),
            ("correctness", "replay", "--help"),
            ("eval", "run", "--help"),
            ("experiment", "list", "--help"),
            ("experiment", "show", "--help"),
            ("report", "--help"),
            ("accept", "--help"),
            ("apply", "--help"),
            ("rollback", "--help"),
            ("task", "create", "--help"),
            ("task", "list", "--help"),
            ("task", "show", "--help"),
            ("candidate", "create", "--help"),
            ("candidate", "freeze", "--help"),
            ("candidate", "list", "--help"),
            ("candidate", "show", "--help"),
            ("benchmark", "--help"),
            ("gate", "run", "--help"),
        )
        runner = CliRunner()
        for command in commands:
            with self.subTest(command=command):
                result = runner.invoke(app, list(command))
                self.assertEqual(result.exit_code, 0, result.output)
                for option in ("--json", "--no-color", "--quiet", "--verbose"):
                    self.assertIn(option, result.stdout)


if __name__ == "__main__":
    unittest.main()
