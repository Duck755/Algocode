"""Provider selection from resolved configuration."""

from __future__ import annotations

import os

from algocode.config import AlgocodeConfig
from algocode.providers.errors import AuthenticationError, InvalidRequestError
from algocode.providers.openai_compatible import OpenAICompatibleProvider
from algocode.providers.types import ModelRef
from algocode.security import SecretRedactor


def build_provider(
    config: AlgocodeConfig,
    *,
    provider_key: str = "default",
    model_key: str = "default",
    redactor: SecretRedactor | None = None,
) -> tuple[OpenAICompatibleProvider, ModelRef]:
    try:
        provider_config = config.providers[provider_key]
    except KeyError as exc:
        raise InvalidRequestError(f"provider {provider_key!r} is not configured") from exc
    try:
        model_config = config.models[model_key]
    except KeyError as exc:
        raise InvalidRequestError(f"model {model_key!r} is not configured") from exc
    if provider_config.type != "openai-compatible":
        raise InvalidRequestError(f"provider type {provider_config.type!r} is not supported in M6")
    if not provider_config.base_url:
        raise InvalidRequestError(f"provider {provider_key!r} has no baseUrl")
    credential_env = provider_config.api_key_env
    if credential_env is None and provider_config.credential_ref is not None:
        credential_env = provider_config.credential_ref.removeprefix("env://")
    if not credential_env:
        raise InvalidRequestError(f"provider {provider_key!r} has no credential reference")
    api_key = os.environ.get(credential_env)
    if not api_key:
        raise AuthenticationError(f"environment variable {credential_env} is not set")
    provider = OpenAICompatibleProvider(
        provider_id=provider_key,
        base_url=provider_config.base_url,
        api_key=api_key,
        model_id=model_config.model,
        redactor=redactor or SecretRedactor.from_config(config),
    )
    return provider, ModelRef(provider_id=provider_key, model_id=model_config.model)
