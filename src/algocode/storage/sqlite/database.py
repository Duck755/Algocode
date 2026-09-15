"""SQLite connection and transaction management."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from algocode.storage.sqlite.migrations import apply_migrations


class Database:
    """Own the SQLite database location and short-lived transactions."""

    def __init__(self, data_dir: str | Path, filename: str = "algocode.db") -> None:
        self.data_dir = Path(data_dir).expanduser()
        self.path = self.data_dir / filename

    def initialize(self) -> None:
        """Create parent directories and apply pending migrations."""

        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.transaction(immediate=True) as connection:
            apply_migrations(connection)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA journal_mode = WAL")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        """Open a transaction and roll it back on any failure."""

        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
                yield connection
                connection.execute("COMMIT")
            except BaseException:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
