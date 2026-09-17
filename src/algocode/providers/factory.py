"""Provider selection from resolved configuration."""

from __future__ import annotations

import os

from algocode.config import AlgocodeConfig
from algocode.providers.anthropic import AnthropicProvider
from algocode.providers.errors import AuthenticationError, InvalidRequestError
from algocode.providers.openai_compatible import OpenAICompatibleProvider
from algocode.providers.types import ModelRef
from algocode.security import CredentialStore, SecretRedactor


def resolve_model_selection(
    config: AlgocodeConfig,
    provider_key: str | None = None,
    model_key: str | None = None,
) -> tuple[str, str]:
    """Resolve explicit keys or the configured default provider and model."""

    return provider_key or config.defaults.provider, model_key or config.defaults.model


def build_provider(
    config: AlgocodeConfig,
    *,
    provider_key: str | None = None,
    model_key: str | None = None,
    redactor: SecretRedactor | None = None,
) -> tuple[AnthropicProvider | OpenAICompatibleProvider, ModelRef]:
    selected_provider, selected_model = resolve_model_selection(config, provider_key, model_key)
    try:
        provider_config = config.providers[selected_provider]
    except KeyError as exc:
        raise InvalidRequestError(f"provider {selected_provider!r} is not configured") from exc
    try:
        model_config = config.models[selected_model]
    except KeyError as exc:
        raise InvalidRequestError(f"model {selected_model!r} is not configured") from exc
    if provider_config.type not in {"openai-compatible", "anthropic"}:
        raise InvalidRequestError(f"provider type {provider_config.type!r} is not supported")
    if not provider_config.base_url:
        raise InvalidRequestError(f"provider {selected_provider!r} has no baseUrl")
    api_key = _resolve_api_key(provider_config, selected_provider)
    provider_options = {
        "provider_id": selected_provider,
        "base_url": provider_config.base_url,
        "api_key": api_key,
        "model_id": model_config.model,
        "redactor": redactor or SecretRedactor.from_config(config),
    }
    provider = (
        AnthropicProvider(**provider_options)
        if provider_config.type == "anthropic"
        else OpenAICompatibleProvider(**provider_options)
    )
    return provider, ModelRef(provider_id=selected_provider, model_id=model_config.model)


def _resolve_api_key(provider_config, provider_key: str) -> str:
    if provider_config.api_key_env:
        api_key = os.environ.get(provider_config.api_key_env)
        if not api_key:
            raise AuthenticationError(
                f"environment variable {provider_config.api_key_env} is not set"
            )
        return api_key
    credential_ref = provider_config.credential_ref
    if not credential_ref:
        raise InvalidRequestError(f"provider {provider_key!r} has no credential reference")
    if credential_ref.startswith("env://"):
        name = credential_ref.removeprefix("env://")
        api_key = os.environ.get(name)
        if not api_key:
            raise AuthenticationError(f"environment variable {name} is not set")
        return api_key
    if credential_ref.startswith("local://"):
        name = credential_ref.removeprefix("local://")
        api_key = CredentialStore().get(name)
        if not api_key:
            raise AuthenticationError(
                f"local credential {name!r} is not configured; run algocode api"
            )
        return api_key
    raise InvalidRequestError(f"unsupported credential reference {credential_ref!r}")
