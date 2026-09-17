from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from algocode.runtime.optimization_record import OptimizationRecordStore


class OptimizationRecordStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_records_and_renders_retry_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = OptimizationRecordStore(Path(directory))
            await store.record(
                task_id="task_1",
                payload={
                    "command": "optimize",
                    "status": "completed",
                    "summary": "first attempt",
                    "improvement_percent": -1.5,
                    "plan": {
                        "summary": "old plan",
                        "strategy": "old strategy",
                        "steps": [{"id": "s1", "description": "old step"}],
                    },
                    "changed_files": ["main.py"],
                    "diff": "diff --git a/main.py b/main.py",
                },
            )
            await store.record(
                task_id="task_1",
                payload={
                    "command": "retry",
                    "status": "waiting_user",
                    "summary": "second attempt",
                    "plan": {"summary": "new plan", "strategy": "new strategy"},
                },
            )

            records = store.list_records(task_id="task_1")
            history = store.render_history(task_id="task_1")

            self.assertEqual(len(records), 2)
            self.assertIn("old plan", history)
            self.assertIn("new plan", history)
            self.assertIn("diff --git a/main.py", history)
            self.assertIn("## Global Best", history)
            self.assertIn("## Decision Cursor", history)
            self.assertIn("last_attempt: 2", history)
            self.assertIn("Global best is only a scoreboard", history)
            self.assertTrue(Path(directory, "task_1", "index.md").is_file())
            first = json.loads(
                Path(directory, "task_1", "0001-optimize.json").read_text(encoding="utf-8")
            )
            self.assertEqual(first["attempt"], 1)
            self.assertEqual(first["command"], "optimize")


if __name__ == "__main__":
    unittest.main()
