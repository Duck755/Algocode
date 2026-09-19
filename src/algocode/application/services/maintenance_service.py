"""Local cache and artifact retention worker."""

from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from algocode.domain.model import ArtifactRef
from algocode.storage.artifacts import FileArtifactStore
from algocode.storage.sqlite.database import Database

_DIGEST_PATTERNS = (
    re.compile(r"artifact://sha256/([0-9a-f]{64})"),
    re.compile(r'"sha256"\s*:\s*"([0-9a-f]{64})"'),
)


@dataclass(frozen=True, slots=True)
class MaintenanceResult:
    removed_files: tuple[str, ...]
    removed_bytes: int
    skipped_files: tuple[str, ...]
    retention_days: int


class MaintenanceService:
    """Remove expired local artifacts, logs, and workspace remnants."""

    def __init__(
        self,
        data_dir: str | Path,
        database: Database,
        artifact_store: FileArtifactStore,
        retention_days: int,
    ) -> None:
        self._data_dir = Path(data_dir).expanduser()
        self._database = database
        self._artifact_store = artifact_store
        self._retention_days = retention_days

    async def cleanup(self, *, include_worktrees: bool = False) -> MaintenanceResult:
        cutoff = time.time() - (self._retention_days * 24 * 60 * 60)
        removed: list[str] = []
        skipped: list[str] = []
        removed_bytes = 0

        referenced = self._referenced_artifacts()
        for metadata_path in sorted(self._artifact_store.metadata_dir.glob("*.json")):
            digest = metadata_path.stem
            try:
                mtime = metadata_path.stat().st_mtime
            except OSError:
                continue
            if mtime >= cutoff or digest in referenced:
                if digest in referenced:
                    skipped.append(str(metadata_path))
                continue
            blob_path = self._artifact_store.blobs_dir / digest[:2] / digest[2:]
            try:
                blob_bytes = blob_path.stat().st_size
            except OSError:
                blob_bytes = 0
            ref = ArtifactRef(uri=f"artifact://sha256/{digest}", sha256=digest)
            await self._artifact_store.delete(ref)
            removed.append(str(metadata_path))
            removed.append(str(blob_path))
            removed_bytes += blob_bytes

        for directory_name in (
            "model-logs",
            "optimization-records",
            "repair-memory",
            "rollbacks",
        ):
            removed_bytes += self._remove_expired_tree(
                self._data_dir / directory_name,
                cutoff,
                removed,
            )

        if include_worktrees:
            worktrees_root = self._data_dir / "worktrees"
            if worktrees_root.exists():
                for worktree in sorted(worktrees_root.iterdir()):
                    try:
                        if worktree.stat().st_mtime >= cutoff:
                            continue
                        removed_bytes += _tree_bytes(worktree)
                        shutil.rmtree(worktree, ignore_errors=True)
                        removed.append(str(worktree))
                    except OSError:
                        skipped.append(str(worktree))

        return MaintenanceResult(
            removed_files=tuple(removed),
            removed_bytes=removed_bytes,
            skipped_files=tuple(skipped),
            retention_days=self._retention_days,
        )

    def _referenced_artifacts(self) -> set[str]:
        referenced: set[str] = set()
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT artifact_refs_json, payload_json FROM event_log"
            ).fetchall()
        for row in rows:
            for value in (row["artifact_refs_json"], row["payload_json"]):
                if not value:
                    continue
                for pattern in _DIGEST_PATTERNS:
                    referenced.update(pattern.findall(value))
        return referenced

    def _remove_expired_tree(
        self,
        root: Path,
        cutoff: float,
        removed: list[str],
    ) -> int:
        if not root.exists():
            return 0
        removed_bytes = 0
        for path in sorted(root.rglob("*"), reverse=True):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime >= cutoff:
                continue
            if path.is_file() or path.is_symlink():
                try:
                    removed_bytes += path.stat().st_size
                except OSError:
                    pass
                try:
                    path.unlink()
                    removed.append(str(path))
                except OSError:
                    pass
            elif path.is_dir() and not any(path.iterdir()):
                try:
                    path.rmdir()
                except OSError:
                    pass
        return removed_bytes


def _tree_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total
