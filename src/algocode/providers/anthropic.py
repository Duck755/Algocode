"""Anthropic Messages API provider."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx

from algocode.providers.errors import (
    AuthenticationError,
    ContextOverflowError,
    InvalidProviderOutputError,
    InvalidRequestError,
    ProviderError,
    ProviderInternalError,
    ProviderTransportError,
    QuotaExceededError,
    RateLimitError,
)
from algocode.providers.types import (
    FinishEvent,
    Message,
    ModelEvent,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    TextDelta,
    ToolCall,
    ToolCallDelta,
    UsageEvent,
)
from algocode.security import SecretRedactor


class AnthropicProvider:
    """Provider for Anthropic's native Messages API."""

    def __init__(
        self,
        *,
        provider_id: str,
        base_url: str,
        api_key: str,
        model_id: str,
        max_retries: int = 2,
        timeout_seconds: int = 60,
        redactor: SecretRedactor | None = None,
        anthropic_version: str = "2023-06-01",
    ) -> None:
        if not api_key:
            raise AuthenticationError("provider API key is empty")
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._redactor = redactor or SecretRedactor()
        self.model_id = model_id
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.anthropic_version = anthropic_version

    async def complete(self, request: ModelRequest) -> ModelResponse:
        payload = self._request_payload(request)
        return await self._post_with_retry(payload, request)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        response = await self.complete(request)
        if response.text:
            yield TextDelta(response.text)
        for call in response.tool_calls:
            yield ToolCallDelta(call)
        yield UsageEvent(response.usage)
        yield FinishEvent(response.finish_reason)

    async def _post_with_retry(
        self,
        payload: dict[str, Any],
        request: ModelRequest,
    ) -> ModelResponse:
        last_error: ProviderError | None = None
        timeout = request.timeout_seconds or self.timeout_seconds
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.post(
                        f"{self.base_url}/v1/messages",
                        headers={
                            "x-api-key": self._api_key,
                            "anthropic-version": self.anthropic_version,
                            "content-type": "application/json",
                        },
                        json=payload,
                    )
                    if response.status_code >= 400:
                        error = self._map_http_error(response)
                        if self._retryable(error) and attempt < self.max_retries:
                            last_error = error
                            await asyncio.sleep(0.25 * (2**attempt))
                            continue
                        raise error
                    return self._parse_response(response.json())
                except ProviderError as exc:
                    if self._retryable(exc) and attempt < self.max_retries:
                        last_error = exc
                        await asyncio.sleep(0.25 * (2**attempt))
                        continue
                    raise
                except (httpx.TransportError, httpx.TimeoutException) as exc:
                    last_error = ProviderTransportError(str(exc))
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.25 * (2**attempt))
                        continue
                    raise last_error from exc
                except (ValueError, TypeError) as exc:
                    raise InvalidProviderOutputError(f"invalid Anthropic response: {exc}") from exc
        raise last_error or ProviderInternalError("provider request failed")

    def _request_payload(self, request: ModelRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model.model_id or self.model_id,
            "max_tokens": request.generation.get("max_tokens", 8192),
            "messages": _messages_payload(request.messages),
        }
        if request.system:
            payload["system"] = request.system
        if request.tools:
            payload["tools"] = [_tool_payload(tool) for tool in request.tools]
        if request.tool_choice is not None:
            payload["tool_choice"] = _tool_choice_payload(request.tool_choice)
        return payload

    def _parse_response(self, payload: dict[str, Any]) -> ModelResponse:
        content = payload.get("content")
        if not isinstance(content, list):
            raise InvalidProviderOutputError("Anthropic response has no content blocks")
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
            elif block_type == "thinking" and isinstance(block.get("thinking"), str):
                reasoning_parts.append(block["thinking"])
            elif block_type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=str(block.get("id", "")),
                        name=str(block.get("name", "")),
                        arguments=(
                            block.get("input")
                            if isinstance(block.get("input"), dict)
                            else {}
                        ),
                    )
                )
        usage_payload = payload.get("usage") or {}
        usage = ModelUsage(
            input_tokens=int(usage_payload.get("input_tokens", 0)),
            output_tokens=int(usage_payload.get("output_tokens", 0)),
            cache_read_tokens=int(usage_payload.get("cache_read_input_tokens", 0)),
            cache_write_tokens=int(usage_payload.get("cache_creation_input_tokens", 0)),
            provider_request_id=str(payload.get("id")) if payload.get("id") else None,
        )
        return ModelResponse(
            text="".join(text_parts),
            tool_calls=tuple(tool_calls),
            usage=usage,
            finish_reason=str(payload.get("stop_reason", "stop")),
            reasoning="".join(reasoning_parts),
        )

    @staticmethod
    def _retryable(error: ProviderError) -> bool:
        return isinstance(
            error,
            (
                RateLimitError,
                ProviderInternalError,
                ProviderTransportError,
                InvalidProviderOutputError,
            ),
        )

    def _map_http_error(self, response: httpx.Response) -> ProviderError:
        message = self._redactor.redact_text(_error_message(response))
        if response.status_code in {401, 403}:
            return AuthenticationError(message)
        if response.status_code == 429:
            if "quota" in message.lower() or "balance" in message.lower():
                return QuotaExceededError(message)
            return RateLimitError(message)
        if response.status_code == 400:
            if "context" in message.lower() and "length" in message.lower():
                return ContextOverflowError(message)
            return InvalidRequestError(message)
        if response.status_code >= 500:
            return ProviderInternalError(message)
        return InvalidRequestError(message)


def _messages_payload(messages: tuple[Message, ...]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "tool":
            payload.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": message.tool_call_id or "",
                            "content": message.content,
                        }
                    ],
                }
            )
            continue
        if message.role == "assistant" and (message.content or message.tool_calls):
            blocks: list[dict[str, Any]] = []
            if message.content:
                blocks.append({"type": "text", "text": message.content})
            blocks.extend(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
                for call in message.tool_calls
            )
            payload.append({"role": "assistant", "content": blocks})
            continue
        payload.append({"role": message.role, "content": message.content})
    return payload


def _tool_payload(tool: dict[str, object]) -> dict[str, Any]:
    return {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "input_schema": tool.get("input_schema", {"type": "object", "properties": {}}),
    }


def _tool_choice_payload(choice: str) -> dict[str, Any]:
    return {"type": "auto" if choice == "auto" else "any"}


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"provider returned HTTP {response.status_code}"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return f"provider returned HTTP {response.status_code}: {error['message']}"
        if payload.get("message"):
            return f"provider returned HTTP {response.status_code}: {payload['message']}"
    return f"provider returned HTTP {response.status_code}"
