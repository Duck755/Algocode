from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from algocode.config.model import SandboxConfig
from algocode.sandbox.runner import SandboxProcessRunner


def _docker_image_ready() -> bool:
    if shutil.which("docker") is None:
        return False
    result = subprocess.run(
        ("docker", "image", "inspect", "algocode-sandbox:latest"),
        capture_output=True,
        check=False,
        timeout=10,
    )
    return result.returncode == 0


@unittest.skipUnless(_docker_image_ready(), "Docker sandbox image is unavailable")
class DockerSandboxTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_workspace_is_writable(self) -> None:
        result = await SandboxProcessRunner(SandboxConfig(backend="docker")).run(
            (
                "python3",
                "-c",
                "from pathlib import Path; Path('/workspace/output.txt').write_text('ok')",
            ),
            cwd=self.workspace,
            timeout_seconds=10,
        )

        self.assertEqual(result.exit_code, 0, result.stderr.decode(errors="replace"))
        self.assertEqual((self.workspace / "output.txt").read_text("utf-8"), "ok")

    async def test_root_filesystem_is_read_only(self) -> None:
        result = await SandboxProcessRunner(SandboxConfig(backend="docker")).run(
            ("python3", "-c", "open('/outside.txt', 'w').write('x')"),
            cwd=self.workspace,
            timeout_seconds=10,
        )

        self.assertNotEqual(result.exit_code, 0)

    async def test_network_is_disabled(self) -> None:
        result = await SandboxProcessRunner(SandboxConfig(backend="docker")).run(
            (
                "python3",
                "-c",
                "import socket; socket.create_connection(('1.1.1.1', 80), 1)",
            ),
            cwd=self.workspace,
            timeout_seconds=10,
        )

        self.assertNotEqual(result.exit_code, 0)

    async def test_timeout_terminates_container(self) -> None:
        result = await SandboxProcessRunner(SandboxConfig(backend="docker")).run(
            ("python3", "-c", "import time; time.sleep(5)"),
            cwd=self.workspace,
            timeout_seconds=1,
        )

        self.assertTrue(result.timed_out)
        self.assertEqual(result.exit_code, 124)


if __name__ == "__main__":
    unittest.main()
