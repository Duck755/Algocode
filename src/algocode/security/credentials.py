"""Local credential persistence for configured model providers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import Lock

from algocode.storage.paths import default_data_dir

CREDENTIALS_VERSION = 1


class CredentialStore:
    """Store provider API keys outside project configuration files.

    The current implementation uses a user-local JSON file protected with
    owner-only permissions where the platform supports them. Provider
    configuration only stores the non-secret reference `local://<name>`.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (default_data_dir() / "credentials.json")
        self._lock = Lock()

    def get(self, name: str) -> str | None:
        with self._lock:
            return self._read().get(name)

    def set(self, name: str, value: str) -> None:
        if not name or not value:
            raise ValueError("credential name and value must not be empty")
        with self._lock:
            credentials = self._read()
            credentials[name] = value
            self._write(credentials)

    def delete(self, name: str) -> None:
        with self._lock:
            credentials = self._read()
            if credentials.pop(name, None) is not None:
                self._write(credentials)

    def _read(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"failed to read credential store {self.path}: {exc}") from exc
        if not isinstance(document, dict):
            raise RuntimeError(f"credential store {self.path} must contain a JSON object")
        raw_credentials = document.get("credentials")
        if not isinstance(raw_credentials, dict):
            return {}
        return {
            str(name): str(value)
            for name, value in raw_credentials.items()
            if isinstance(name, str) and isinstance(value, str)
        }

    def _write(self, credentials: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {"version": CREDENTIALS_VERSION, "credentials": credentials}
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, self.path)
