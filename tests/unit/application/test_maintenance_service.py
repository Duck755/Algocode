from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from algocode.application.services.maintenance_service import MaintenanceService
from algocode.bootstrap import build_context


class MaintenanceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary_directory.name) / "data"
        self.context = build_context(data_dir=self.data_dir)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_cleanup_keeps_referenced_artifacts(self) -> None:
        service = MaintenanceService(
            self.data_dir,
            self.context.database,
            self.context.artifact_store,
            retention_days=1,
        )

        referenced = self._put_artifact("referenced", b"keep")
        orphan = self._put_artifact("orphan", b"delete")
        with self.context.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO event_log(
                    id, aggregate_id, seq, type, schema_version, timestamp,
                    payload_json, artifact_refs_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "evt_reference",
                    "task_reference",
                    1,
                    "task.created",
                    1,
                    "2020-01-01T00:00:00+00:00",
                    "{}",
                    json.dumps(
                        [{"uri": referenced.uri, "sha256": referenced.sha256}],
                        sort_keys=True,
                    ),
                ),
            )

        self._make_artifact_old(referenced)
        self._make_artifact_old(orphan)
        stale_log = self.data_dir / "model-logs" / "task" / "old.md"
        stale_log.parent.mkdir(parents=True)
        stale_log.write_text("old", encoding="utf-8")
        self._make_old(stale_log)

        result = asyncio.run(service.cleanup())

        self.assertTrue(
            any(str(self._metadata_path(orphan)) == path for path in result.removed_files)
        )
        self.assertFalse(self._metadata_path(orphan).exists())
        self.assertFalse((self.data_dir / "model-logs" / "task" / "old.md").exists())
        self.assertTrue(self._blob_exists(referenced))

    def _put_artifact(self, marker: str, content: bytes):
        # Put synchronously through asyncio since FileArtifactStore.put is async.
        import asyncio

        return asyncio.run(
            self.context.artifact_store.put(
                content + marker.encode(),
                kind="test",
                mime_type="application/octet-stream",
                metadata={"marker": marker},
            )
        )

    def _make_artifact_old(self, ref) -> None:
        for path in (self._metadata_path(ref), self._blob_path(ref)):
            self._make_old(path)

    @staticmethod
    def _make_old(path) -> None:
        now = time.time() - 48 * 60 * 60
        os.utime(path, (now, now))

    def _metadata_path(self, ref) -> Path:
        return self.context.artifact_store.metadata_dir / f"{ref.sha256}.json"

    def _blob_path(self, ref) -> Path:
        return self.context.artifact_store.blobs_dir / ref.sha256[:2] / ref.sha256[2:]

    def _blob_exists(self, ref) -> bool:
        return self._blob_path(ref).exists()
