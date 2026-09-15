from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.storage.artifacts import FileArtifactStore


class FileArtifactStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_round_trip_and_deduplication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = FileArtifactStore(Path(directory))
            first = await store.put(
                b"hello",
                kind="build-output",
                mime_type="text/plain",
                metadata={"task": "1"},
            )
            second = await store.put(
                b"hello",
                kind="other",
                mime_type="application/octet-stream",
                metadata={},
            )

            self.assertEqual(first, second)
            self.assertEqual(await store.read_bytes(first), b"hello")
            self.assertEqual(store.description(first)["mime_type"], "application/octet-stream")

    async def test_missing_artifact_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = FileArtifactStore(Path(directory))
            from algocode.domain.model import ArtifactRef

            ref = ArtifactRef(uri="artifact://sha256/0" * 64, sha256="0" * 64)
            with self.assertRaises(FileNotFoundError):
                await store.read_bytes(ref)


if __name__ == "__main__":
    unittest.main()
