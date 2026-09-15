from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from algocode.config.model import SandboxConfig
from algocode.sandbox.runner import SandboxProcessRunner


class SandboxRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_environment_is_sanitized_and_extra_env_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                "os.environ",
                {"ALGOCODE_API_KEY": "secret", "PATH": __import__("os").environ.get("PATH", "")},
            ):
                result = await SandboxProcessRunner().run(
                    (
                        sys.executable,
                        "-c",
                        (
                            "import os; "
                            "print(os.environ.get('ALGOCODE_API_KEY', 'missing')); "
                            "print(os.environ.get('ALGOCODE_SEED', 'missing'))"
                        ),
                    ),
                    cwd=Path(directory),
                    timeout_seconds=5,
                    extra_env={"ALGOCODE_SEED": "123"},
                )

        self.assertNotIn("secret", result.stdout.decode())
        self.assertIn("123", result.stdout.decode())

    async def test_output_is_truncated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = await SandboxProcessRunner(SandboxConfig(max_output_bytes=5)).run(
                (sys.executable, "-c", "print('abcdef')"),
                cwd=Path(directory),
                timeout_seconds=5,
            )

        self.assertTrue(result.truncated)
        self.assertLessEqual(len(result.stdout), 5)


if __name__ == "__main__":
    unittest.main()
