"""Secret redaction for durable and model-facing boundaries."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import fields, is_dataclass, replace

REDACTED = "[REDACTED]"


class SecretRedactor:
    """Replace known credential values before persistence or prompting."""

    def __init__(self, secrets: tuple[str, ...] = ()) -> None:
        values = {secret for secret in secrets if secret}
        self._secrets = tuple(sorted(values, key=len, reverse=True))

    @classmethod
    def from_config(
        cls,
        config,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> SecretRedactor:
        source = os.environ if environ is None else environ
        names: set[str] = set()
        for provider in config.providers.values():
            if provider.api_key_env:
                names.add(provider.api_key_env)
            if provider.credential_ref and provider.credential_ref.startswith("env://"):
                names.add(provider.credential_ref.removeprefix("env://"))
        return cls(tuple(value for name in names if (value := source.get(name))))

    @property
    def has_secrets(self) -> bool:
        return bool(self._secrets)

    def redact_text(self, value: str) -> str:
        redacted = value
        for secret in self._secrets:
            redacted = redacted.replace(secret, REDACTED)
        return redacted

    def redact_bytes(self, value: bytes) -> bytes:
        redacted = value
        for secret in self._secrets:
            redacted = redacted.replace(secret.encode("utf-8"), REDACTED.encode("utf-8"))
        return redacted

    def redact_value(self, value):
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, bytes):
            return self.redact_bytes(value)
        if is_dataclass(value) and not isinstance(value, type):
            return replace(
                value,
                **{
                    field.name: self.redact_value(getattr(value, field.name))
                    for field in fields(value)
                },
            )
        if isinstance(value, Mapping):
            return {self.redact_value(key): self.redact_value(item) for key, item in value.items()}
        if isinstance(value, tuple):
            return tuple(self.redact_value(item) for item in value)
        if isinstance(value, list):
            return [self.redact_value(item) for item in value]
        if isinstance(value, set):
            return {self.redact_value(item) for item in value}
        return value
