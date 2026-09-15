"""Requirement traceability matrix loading and validation."""

from __future__ import annotations

from pathlib import Path

import yaml

from algocode.acceptance.types import Requirement

DEFAULT_MATRIX = Path("docs/acceptance/p0-requirements.yaml")


def load_requirements(root: str | Path, path: str | Path | None = None) -> tuple[Requirement, ...]:
    root_path = Path(root).resolve()
    matrix_path = Path(path) if path is not None else DEFAULT_MATRIX
    if not matrix_path.is_absolute():
        matrix_path = root_path / matrix_path
    try:
        raw = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"failed to load acceptance matrix {matrix_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("acceptance matrix must be a YAML mapping")
    rows = raw.get("requirements")
    if not isinstance(rows, list) or not rows:
        raise ValueError("acceptance matrix must contain requirements")
    requirements: list[Requirement] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"acceptance requirement {index} must be a mapping")
        requirement = Requirement(
            id=str(row.get("id", "")),
            title=str(row.get("title", "")),
            implementation=_paths(row.get("implementation"), "implementation", index),
            tests=_paths(row.get("tests"), "tests", index),
            evidence=tuple(str(item) for item in row.get("evidence", ())),
        )
        if not requirement.id or not requirement.title:
            raise ValueError(f"acceptance requirement {index} requires id and title")
        if requirement.id in seen:
            raise ValueError(f"duplicate acceptance requirement: {requirement.id}")
        if not requirement.implementation or not requirement.tests or not requirement.evidence:
            raise ValueError(f"acceptance requirement {requirement.id} is incomplete")
        seen.add(requirement.id)
        requirements.append(requirement)
    return tuple(requirements)


def validate_requirement_paths(
    root: str | Path,
    requirements: tuple[Requirement, ...],
) -> tuple[Requirement, ...]:
    root_path = Path(root).resolve()
    missing: list[str] = []
    for requirement in requirements:
        for path in (*requirement.implementation, *requirement.tests):
            if not (root_path / path).exists():
                missing.append(f"{requirement.id}:{path}")
    if missing:
        raise ValueError(f"acceptance matrix references missing paths: {', '.join(missing)}")
    return requirements


def _paths(value: object, field: str, index: int) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"acceptance requirement {index} field {field} must be a list")
    return tuple(str(item) for item in value)
