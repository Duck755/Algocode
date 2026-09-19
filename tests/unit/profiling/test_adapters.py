from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from algocode.config.model import SandboxConfig
from algocode.domain.model import Language
from algocode.profiling import collect_profile
from algocode.profiling.adapters import PythonCProfileAdapter
from algocode.sandbox.runner import SandboxProcessRunner


class ProfilerAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_python_cprofile_collects_hotspots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "main.py").write_text(
                "def hot():\n    return sum(range(100000))\n\n"
                'if __name__ == "__main__":\n    print(hot())\n',
                encoding="utf-8",
            )
            runner = SandboxProcessRunner(SandboxConfig(backend="native"))
            report = await PythonCProfileAdapter().profile(
                workspace,
                (sys.executable, str(workspace / "main.py")),
                sandbox_runner=runner,
            )

            self.assertTrue(report.available, report.error)
            self.assertEqual(report.tool, "cProfile")
            self.assertTrue(any("hot" in sample.function for sample in report.samples))
            self.assertIn("Top hotspots", report.text())

    async def test_collect_profile_python_uses_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "main.py").write_text(
                "def hot():\n    return sum(range(100000))\n\n"
                'if __name__ == "__main__":\n    print(hot())\n',
                encoding="utf-8",
            )
            runner = SandboxProcessRunner(SandboxConfig(backend="native"))
            report = await collect_profile(
                workspace=workspace,
                language=Language.PYTHON,
                commands=((sys.executable, str(workspace / "main.py")),),
                sandbox_runner=runner,
            )

            self.assertTrue(report.available, report.error)
            self.assertIn("hot", report.text())


if __name__ == "__main__":
    unittest.main()
