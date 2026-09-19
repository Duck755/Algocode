from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from algocode.config.model import SandboxConfig
from algocode.sandbox.runner import SandboxProcessRunner, _wsl_ready


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

    def test_auto_prefers_wsl2_before_native_on_windows(self) -> None:
        with (
            patch("algocode.sandbox.runner._docker_ready", return_value=False),
            patch("algocode.sandbox.runner._wsl_ready", return_value=True),
            patch("algocode.sandbox.runner._wsl_toolchain_ready", return_value=True),
            patch("algocode.sandbox.runner.os.name", "nt"),
        ):
            runner = SandboxProcessRunner(SandboxConfig(backend="auto"))

        self.assertEqual(runner.backend, "wsl2")

    def test_auto_falls_back_from_docker_to_wsl_when_docker_toolchain_is_missing(self) -> None:
        with (
            patch("algocode.sandbox.runner._docker_ready", return_value=True),
            patch("algocode.sandbox.runner._docker_toolchain_ready", return_value=False),
            patch("algocode.sandbox.runner._wsl_ready", return_value=True),
            patch("algocode.sandbox.runner._wsl_toolchain_ready", return_value=True),
        ):
            runner = SandboxProcessRunner(SandboxConfig(backend="auto"))

        self.assertEqual(runner.backend, "wsl2")

    def test_auto_falls_back_to_native_when_wsl_toolchain_is_missing(self) -> None:
        with (
            patch("algocode.sandbox.runner._docker_ready", return_value=False),
            patch("algocode.sandbox.runner._wsl_ready", return_value=True),
            patch("algocode.sandbox.runner._wsl_toolchain_ready", return_value=False),
            patch("algocode.sandbox.runner._native_toolchain_ready", return_value=True),
        ):
            runner = SandboxProcessRunner(SandboxConfig(backend="auto"))

        self.assertEqual(runner.backend, "native")

    def test_auto_disables_when_no_toolchain_is_available(self) -> None:
        with (
            patch("algocode.sandbox.runner._docker_ready", return_value=False),
            patch("algocode.sandbox.runner._wsl_ready", return_value=False),
            patch("algocode.sandbox.runner._native_toolchain_ready", return_value=False),
        ):
            runner = SandboxProcessRunner(SandboxConfig(backend="auto"))

        self.assertEqual(runner.backend, "disabled")
        self.assertIn("no docker/wsl/native", runner.backend_reason)

    def test_explicit_docker_does_not_degrade_to_wsl(self) -> None:
        with (
            patch("algocode.sandbox.runner._docker_ready", return_value=True),
            patch("algocode.sandbox.runner._docker_toolchain_ready", return_value=False),
            patch("algocode.sandbox.runner._wsl_ready", return_value=True),
            patch("algocode.sandbox.runner._wsl_toolchain_ready", return_value=True),
        ):
            runner = SandboxProcessRunner(SandboxConfig(backend="docker"))

        self.assertEqual(runner.backend, "docker")

    def test_wsl_backend_probe_uses_flat_argument_tuple(self) -> None:
        with (
            patch(
                "algocode.sandbox.runner.shutil.which",
                side_effect=lambda name: "wsl.exe" if name == "wsl.exe" else None,
            ),
            patch("algocode.sandbox.runner.subprocess.run") as run,
        ):
            run.return_value = SimpleNamespace(returncode=0)

            ready = _wsl_ready("Ubuntu", False)

        self.assertTrue(ready)
        command = run.call_args.args[0]
        self.assertEqual(command[0], "wsl.exe")
        self.assertTrue(all(isinstance(argument, str) for argument in command))


if __name__ == "__main__":
    unittest.main()
