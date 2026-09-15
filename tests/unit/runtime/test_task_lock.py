from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.domain.errors import ResourceBusyError
from algocode.runtime.task_lock import TaskRunLock
from algocode.storage.sqlite import Database


class TaskRunLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_task_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory))
            database.initialize()
            async with TaskRunLock(database, "task_1"):
                with self.assertRaises(ResourceBusyError):
                    async with TaskRunLock(database, "task_1"):
                        pass

            async with TaskRunLock(database, "task_1"):
                pass


if __name__ == "__main__":
    unittest.main()
