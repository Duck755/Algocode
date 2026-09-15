from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.domain.errors import ResourceBusyError
from algocode.runtime.locks import FileResourceLock


class ResourceLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_resource_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            async with FileResourceLock(root, "benchmark:env"):
                with self.assertRaises(ResourceBusyError):
                    async with FileResourceLock(root, "benchmark:env"):
                        pass

    async def test_different_resources_can_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            async with (
                FileResourceLock(root, "benchmark:env-1"),
                FileResourceLock(root, "benchmark:env-2"),
            ):
                pass


if __name__ == "__main__":
    unittest.main()
