"""Read and update the user-global configuration file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from algocode.storage.paths import default_data_dir


def global_config_path() -> Path:
    return default_data_dir() / "config.yaml"


def read_global_config() -> dict[str, Any]:
    path = global_config_path()
    if not path.exists():
        return {}
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"failed to read global configuration {path}: {exc}") from exc
    if document is None:
        return {}
    if not isinstance(document, dict):
        raise ValueError(f"global configuration {path} must contain a YAML mapping")
    return document


def write_global_config(document: dict[str, Any]) -> Path:
    path = global_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def update_global_config(patch: dict[str, Any]) -> Path:
    document = read_global_config()
    _merge_mapping(document, patch)
    return write_global_config(document)


def _merge_mapping(target: dict[str, Any], patch: dict[str, Any]) -> None:
    for key, value in patch.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            _merge_mapping(current, value)
        else:
            target[key] = value
