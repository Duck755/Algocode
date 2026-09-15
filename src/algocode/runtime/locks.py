"""Cross-process resource locks."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from algocode.domain.errors import ResourceBusyError


class FileResourceLock:
    """Acquire an exclusive lock for one resource key using O_EXCL."""

    def __init__(
        self,
        root: str | Path,
        key: str,
        *,
        stale_after_seconds: int = 6 * 60 * 60,
    ) -> None:
        self.root = Path(root).expanduser()
        self.key = key
        self.stale_after_seconds = stale_after_seconds
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        self.path = self.root / f"{digest}.lock"
        self._acquired = False

    async def __aenter__(self) -> FileResourceLock:
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self._create()
        except FileExistsError:
            if self._remove_if_stale():
                self._create()
            else:
                owner = self.path.read_text(encoding="utf-8", errors="replace")
                raise ResourceBusyError(f"resource {self.key} is busy: {owner.strip()}") from None
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self._acquired:
            self.path.unlink(missing_ok=True)
            self._acquired = False

    def _create(self) -> None:
        descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"pid={os.getpid()} acquired_at={time.time()}\n")
        self._acquired = True

    def _remove_if_stale(self) -> bool:
        try:
            age = time.time() - self.path.stat().st_mtime
        except FileNotFoundError:
            return True
        if age <= self.stale_after_seconds:
            return False
        self.path.unlink(missing_ok=True)
        return True
