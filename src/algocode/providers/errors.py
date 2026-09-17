"""Typed provider errors."""

from __future__ import annotations


class ProviderError(RuntimeError):
    """Base class for provider failures."""


class ProviderTransportError(ProviderError):
    """Network or transport failure."""


class AuthenticationError(ProviderError):
    """Authentication or authorization failure."""


class RateLimitError(ProviderError):
    """Provider rate limit or temporary quota pressure."""


class QuotaExceededError(ProviderError):
    """Persistent account quota exhaustion."""


class InvalidRequestError(ProviderError):
    """Invalid request rejected by the provider."""


class ContextOverflowError(InvalidRequestError):
    """The model context window was exceeded."""


class ProviderInternalError(ProviderError):
    """Provider-side internal failure."""


class InvalidProviderOutputError(ProviderError):
    """Provider output does not match the expected protocol."""


class ToolProtocolError(ProviderError):
    """Provider emitted an invalid tool call."""

    def __init__(
        self,
        message: str,
        *,
        tool_name: str = "",
        call_id: str = "",
        raw_arguments: str = "",
        parse_error: str = "",
    ) -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.call_id = call_id
        self.raw_arguments = raw_arguments
        self.parse_error = parse_error
