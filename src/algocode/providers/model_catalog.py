"""Fetch model catalogs from configured provider endpoints."""

from __future__ import annotations

from collections.abc import Iterable

import httpx

DEFAULT_TIMEOUT_SECONDS = 5.0


def list_models(
    provider_type: str,
    base_url: str,
    api_key: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[str]:
    """Return available model ids from a provider, or an empty list on failure."""
    if not base_url or not api_key:
        return []
    url, headers = _endpoint(provider_type, base_url, api_key)
    try:
        response = httpx.get(url, headers=headers, timeout=timeout_seconds)
    except httpx.HTTPError:
        return []
    if response.status_code != 200:
        return []
    try:
        payload = response.json()
    except ValueError:
        return []
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    models: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str) and model_id:
            models.append(model_id)
    return _dedupe(models)


def _endpoint(provider_type: str, base_url: str, api_key: str) -> tuple[str, dict[str, str]]:
    root = base_url.rstrip("/")
    if provider_type == "anthropic":
        return (
            f"{root}/v1/models",
            {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        )
    return f"{root}/models", {"Authorization": f"Bearer {api_key}"}


def _dedupe(models: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(model.strip() for model in models if model.strip()))
