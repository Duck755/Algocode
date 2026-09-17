"""Shared parsing and validation for model-produced structured output."""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)

_JSON_REPAIR_SUFFIXES = (
    "}",
    '"}',
    "]}",
    '"]}',
    "}}",
    '"}}',
    "]}}",
    '"]}}',
    "}]}",
    "]}",
)


class StructuredOutputError(ValueError):
    """Model output could not be parsed or validated against its contract."""


def parse_json_object(text: str, *, label: str = "model output") -> dict[str, object]:
    """Extract and parse one JSON object with conservative repair only."""
    stripped = strip_markdown_fence(text)
    if not stripped:
        raise StructuredOutputError(f"{label} was empty")

    candidates = [stripped]
    extracted = extract_balanced_json_object(stripped)
    if extracted and extracted not in candidates:
        candidates.append(extracted)

    errors: list[str] = []
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            errors.append(str(exc))
            repaired = repair_truncated_json_object(candidate)
            if repaired is not None:
                try:
                    parsed = json.loads(repaired)
                except json.JSONDecodeError as repaired_exc:
                    errors.append(str(repaired_exc))
                    continue
            else:
                continue
        if not isinstance(parsed, dict):
            raise StructuredOutputError(f"{label} must be a JSON object")
        return parsed

    detail = errors[-1] if errors else "no JSON object found"
    raise StructuredOutputError(f"{label} was not valid JSON: {detail}")


def parse_model(
    text: str,
    model_type: type[ModelT],
    *,
    label: str = "model output",
) -> ModelT:
    """Parse one JSON object and validate it with a Pydantic model."""
    payload = parse_json_object(text, label=label)
    return validate_model(payload, model_type, label=label)


def validate_model(
    payload: object,
    model_type: type[ModelT],
    *,
    label: str = "model output",
) -> ModelT:
    """Validate an already parsed payload with a Pydantic model."""
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise StructuredOutputError(
            f"{label} failed schema validation:\n{format_validation_error(exc)}"
        ) from exc


def format_validation_error(exc: ValidationError) -> str:
    """Render concise, stable Pydantic validation details for a model retry."""
    details: list[str] = []
    for item in exc.errors(include_url=False):
        location = ".".join(str(part) for part in item.get("loc", ())) or "<root>"
        message = str(item.get("msg", "invalid value"))
        details.append(f"- {location}: {message}")
    return "\n".join(details) if details else str(exc)


def strip_markdown_fence(text: str) -> str:
    """Remove one surrounding Markdown code fence when present."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines:
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def extract_balanced_json_object(text: str) -> str | None:
    """Extract the first balanced top-level JSON object without using regex."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        character = text[index]
        if escaped:
            escaped = False
            continue
        if character == "\\" and in_string:
            escaped = True
            continue
        if character == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def repair_truncated_json_object(text: str) -> str | None:
    """Try a bounded set of closing suffixes for a truncated object."""
    stripped = text.strip()
    for suffix in _JSON_REPAIR_SUFFIXES:
        try:
            parsed = json.loads(stripped + suffix)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return stripped + suffix
    return None
