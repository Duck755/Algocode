from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from algocode.domain.model import Language
from algocode.languages.cpp import CppLanguageAdapter
from algocode.languages.python import PythonLanguageAdapter
from algocode.languages.types import BuildProfile


class LanguageAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_python_detection_and_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("def solve():\n    return 42\n", encoding="utf-8")
            adapter = PythonLanguageAdapter()

            info = await adapter.detect(root)
            result = await adapter.build(root, BuildProfile(timeout_seconds=30))

        self.assertIsNotNone(info)
        self.assertEqual(info.languages, (Language.PYTHON,))
        self.assertTrue(result.succeeded, result.stderr.decode(errors="replace"))

    @unittest.skipUnless(
        shutil.which("g++") or shutil.which("clang++"),
        "no supported C++ compiler is available",
    )
    async def test_cpp_detection_and_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.cpp").write_text(
                "#include <iostream>\nint main() { std::cout << 42; }\n",
                encoding="utf-8",
            )
            adapter = CppLanguageAdapter()

            info = await adapter.detect(root)
            result = await adapter.build(root, BuildProfile(timeout_seconds=30))
            build_exists = (root / "build").exists()

        self.assertIsNotNone(info)
        self.assertEqual(info.languages, (Language.CPP,))
        self.assertTrue(result.succeeded, result.stderr.decode(errors="replace"))
        self.assertTrue(build_exists)


if __name__ == "__main__":
    unittest.main()
