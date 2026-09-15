"""Projection write contracts."""

from __future__ import annotations

import sqlite3
from typing import Protocol

from algocode.domain.events import EventEnvelope


class Projector(Protocol):
    def apply(self, connection: sqlite3.Connection, event: EventEnvelope) -> None: ...
