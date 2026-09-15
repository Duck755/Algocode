"""Configuration loading, precedence, and deterministic hashing."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from algocode.config.model import AlgocodeConfig
from algocode.domain.errors import ConfigError
from algocode.storage.paths import default_data_dir

ENV_PREFIX = "ALGOCODE_"
APPEND_LIST_KEYS = {"rules", "protected_files"}
SECRET_ENV_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET")
GLOBAL_CONFIG_NAME = "config.yaml"
PROJECT_CONFIG_NAME = ".algocode.yaml"
LOCAL_CONFIG_NAME = ".algocode.local.yaml"


def _read_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"failed to read configuration file {path}: {exc}") from exc
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(f"configuration file {path} must contain a YAML mapping")
    return raw


def _deep_merge(
    base: Mapping[str, Any],
    overlay: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, list) and isinstance(value, list) and key in APPEND_LIST_KEYS:
            merged[key] = [*existing, *value]
            continue
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _parse_env_value(name: str, value: str) -> Any:
    try:
        return yaml.safe_load(value)
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML value in environment variable {name}: {exc}") from exc


def _set_nested(target: dict[str, Any], path: Sequence[str], value: Any) -> None:
    current = target
    for segment in path[:-1]:
        child = current.setdefault(segment, {})
        if not isinstance(child, dict):
            joined = "__".join(path)
            raise ConfigError(f"environment variable path {joined} conflicts with another value")
        current = child
    current[path[-1]] = value


def _env_overrides(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = os.environ if environ is None else environ
    result: dict[str, Any] = {}
    for name in sorted(source):
        if not name.startswith(ENV_PREFIX):
            continue
        suffix = name[len(ENV_PREFIX) :]
        normalized_suffix = suffix.upper()
        if normalized_suffix in {"API_KEY", "TOKEN", "SECRET"} or normalized_suffix.endswith(
            SECRET_ENV_SUFFIXES
        ):
            continue
        if not suffix:
            raise ConfigError("environment variable ALGOCODE_ has no configuration path")
        path = [segment.lower() for segment in suffix.split("__")]
        if any(not segment for segment in path):
            raise ConfigError(f"environment variable {name} has an empty path segment")
        _set_nested(result, path, _parse_env_value(name, source[name]))
    return result


def _resolve_data_dir(data_dir: str | Path | None) -> Path:
    if data_dir is None:
        return default_data_dir()
    return Path(data_dir).expanduser()


def _tag_policy_rules(document: dict[str, Any], layer: str) -> dict[str, Any]:
    tagged = dict(document)
    policy = tagged.get("policy")
    if not isinstance(policy, dict):
        return tagged
    rules = policy.get("rules")
    if not isinstance(rules, list):
        return tagged
    tagged_policy = dict(policy)
    tagged_policy["rules"] = [
        ({**rule, "layer": layer} if isinstance(rule, dict) and "layer" not in rule else rule)
        for rule in rules
    ]
    tagged["policy"] = tagged_policy
    return tagged


def load_config(
    project_root: str | Path | None = None,
    data_dir: str | Path | None = None,
    *,
    cli_overrides: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> AlgocodeConfig:
    """Load configuration using the documented precedence order.

    Precedence, from lowest to highest:
    built-in defaults, global config, project config, local project config,
    environment variables, and explicit CLI overrides.
    """

    root = Path.cwd() if project_root is None else Path(project_root).expanduser()
    runtime_data_dir = _resolve_data_dir(data_dir)
    document: dict[str, Any] = {}
    global_document = _tag_policy_rules(
        _read_document(runtime_data_dir / GLOBAL_CONFIG_NAME),
        "user",
    )
    project_document = _tag_policy_rules(
        _read_document(root / PROJECT_CONFIG_NAME),
        "project",
    )
    local_document = _tag_policy_rules(
        _read_document(root / LOCAL_CONFIG_NAME),
        "project",
    )
    document = _deep_merge(document, global_document)
    document = _deep_merge(document, project_document)
    document = _deep_merge(document, local_document)
    document = _deep_merge(document, _env_overrides(environ))
    if cli_overrides is not None:
        document = _deep_merge(document, cli_overrides)
    try:
        return AlgocodeConfig.model_validate(document)
    except ValidationError as exc:
        raise ConfigError(f"invalid Algocode configuration: {exc}") from exc


def compute_config_hash(config: AlgocodeConfig) -> str:
    """Return a stable SHA256 digest of the fully resolved configuration."""

    payload = config.model_dump(mode="json")
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
