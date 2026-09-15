"""Content-addressed local artifact storage."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import Any

from algocode.domain.model import ArtifactRef
from algocode.security import SecretRedactor


class FileArtifactStore:
    """Store artifacts by SHA256 under a local data directory."""

    def __init__(self, root: str | Path, redactor: SecretRedactor | None = None) -> None:
        self.root = Path(root).expanduser()
        self._redactor = redactor or SecretRedactor()
        self.blobs_dir = self.root / "blobs"
        self.metadata_dir = self.root / "metadata"

    async def put(
        self,
        data: bytes | AsyncIterator[bytes],
        kind: str,
        mime_type: str,
        metadata: Mapping[str, object],
    ) -> ArtifactRef:
        if isinstance(data, bytes):
            content = data
        else:
            chunks: list[bytes] = []
            async for chunk in data:
                chunks.append(chunk)
            content = b"".join(chunks)
        content = self._redactor.redact_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        blob_path = self._blob_path(digest)
        metadata_path = self._metadata_path(digest)
        blob_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if not blob_path.exists():
            blob_path.write_bytes(content)
        metadata_path.write_text(
            json.dumps(
                {
                    "sha256": digest,
                    "kind": kind,
                    "mime_type": mime_type,
                    "size": len(content),
                    "metadata": self._redactor.redact_value(dict(metadata)),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return ArtifactRef(uri=f"artifact://sha256/{digest}", sha256=digest)

    async def open(self, ref: ArtifactRef) -> AsyncIterator[bytes]:
        path = self._blob_path(ref.sha256)
        with path.open("rb") as handle:
            while chunk := handle.read(64 * 1024):
                yield chunk

    async def delete(self, ref: ArtifactRef) -> None:
        self._blob_path(ref.sha256).unlink(missing_ok=True)
        self._metadata_path(ref.sha256).unlink(missing_ok=True)

    async def read_bytes(self, ref: ArtifactRef) -> bytes:
        return self._blob_path(ref.sha256).read_bytes()

    def description(self, ref: ArtifactRef) -> dict[str, Any]:
        path = self._metadata_path(ref.sha256)
        return json.loads(path.read_text(encoding="utf-8"))

    def _blob_path(self, digest: str) -> Path:
        _validate_digest(digest)
        return self.blobs_dir / digest[:2] / digest[2:]

    def _metadata_path(self, digest: str) -> Path:
        _validate_digest(digest)
        return self.metadata_dir / f"{digest}.json"


def _validate_digest(digest: str) -> None:
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ValueError("artifact digest must be a lowercase SHA256 hex string")
