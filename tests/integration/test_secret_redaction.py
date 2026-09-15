"""Secret redaction boundary tests."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from algocode.bootstrap import build_context
from algocode.providers.types import Message, ModelRef, ModelRequest
from algocode.security import REDACTED, SecretRedactor
from tests.support.git import init_git_repository

SECRET_ENV = "ALGOCODE_TEST_SECRET"
SECRET_VALUE = "sk-test-super-secret-value"


class SecretRedactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_request_is_redacted(self) -> None:
        redactor = SecretRedactor((SECRET_VALUE,))
        request = ModelRequest(
            request_id="req_test",
            model=ModelRef(provider_id="test", model_id="test"),
            system=SECRET_VALUE,
            messages=(Message(role="user", content=f"use {SECRET_VALUE}"),),
        )

        redacted = redactor.redact_value(request)

        self.assertNotIn(SECRET_VALUE, redacted.system)
        self.assertNotIn(SECRET_VALUE, redacted.messages[0].content)
        self.assertIn(REDACTED, redacted.messages[0].content)

    async def test_secret_is_redacted_from_sqlite_artifacts_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_root = init_git_repository(
                root / "project",
                {"main.py": "print('hello')\n"},
            )
            (project_root / ".algocode.yaml").write_text(
                "providers:\n  default:\n    apiKeyEnv: ALGOCODE_TEST_SECRET\n",
                encoding="utf-8",
            )
            data_dir = root / "data"
            with patch.dict(os.environ, {SECRET_ENV: SECRET_VALUE}):
                context = build_context(project_root=project_root, data_dir=data_dir)
                project = await context.project_service.register(
                    project_root,
                    write_config=True,
                )
                task = await context.task_service.create_task(
                    f"Optimize with {SECRET_VALUE}",
                    project_id=project.id,
                )
                ref = await context.artifact_store.put(
                    f"artifact {SECRET_VALUE}".encode(),
                    kind="test-secret",
                    mime_type="text/plain",
                    metadata={"value": SECRET_VALUE},
                )
                artifact = (await context.artifact_store.read_bytes(ref)).decode()
                report, markdown, _ = await context.report_service.build(task.id)

            raw_secret = SECRET_VALUE.encode()
            for path in data_dir.rglob("*"):
                if path.is_file():
                    self.assertNotIn(raw_secret, path.read_bytes(), str(path))
            connection = sqlite3.connect(context.database.path)
            try:
                rows = connection.execute("SELECT payload_json FROM event_log").fetchall()
            finally:
                connection.close()
            self.assertTrue(rows)
            self.assertNotIn(SECRET_VALUE, "".join(str(row[0]) for row in rows))
            self.assertNotIn(SECRET_VALUE, artifact)
            self.assertNotIn(SECRET_VALUE, str(report))
            self.assertNotIn(SECRET_VALUE, markdown)


if __name__ == "__main__":
    unittest.main()
