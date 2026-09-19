"""OpenAI Responses API provider."""

from __future__ import annotations

import asyncio
import json
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
    ToolProtocolError,
)
from algocode.providers.types import (
    FinishEvent,
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


class ResponsesProvider:
    """Provider for OpenAI's Responses API."""

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

    def _request_payload(self, request: ModelRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": request.model.model_id or self.model_id,
            "input": _input_payload(request),
        }
        if request.tools:
            payload["tools"] = [_tool_payload(tool) for tool in request.tools]
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice
        return payload

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
                        f"{self.base_url}/v1/responses",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
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
                    return self._parse_response(response.json(), request)
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
                    raise InvalidProviderOutputError(
                        f"invalid Responses API response: {exc}"
                    ) from exc
        raise last_error or ProviderInternalError("provider request failed")

    @staticmethod
    def _parse_response(
        payload: dict[str, Any],
        request: ModelRequest,
    ) -> ModelResponse:
        text_parts: list[str] = []
        reasoning_parts: list[str] = []
        calls: list[ToolCall] = []
        for item in payload.get("output") or []:
            item_type = item.get("type")
            if item_type == "message":
                for content in item.get("content") or []:
                    if content.get("type") in {"output_text", "text"}:
                        text_parts.append(str(content.get("text", "")))
            elif item_type == "reasoning":
                for content in item.get("content") or []:
                    if content.get("type") in {"reasoning_text", "text"}:
                        reasoning_parts.append(str(content.get("text", "")))
            elif item_type == "function_call":
                calls.append(_parse_function_call(item))
        usage = _parse_usage(payload.get("usage") or {}, str(payload.get("id", "")))
        return ModelResponse(
            text="".join(text_parts),
            tool_calls=tuple(calls),
            usage=_estimate_cost(usage, request),
            finish_reason=str(payload.get("status") or "completed"),
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
            if "insufficient" in message.lower() or "balance" in message.lower():
                return QuotaExceededError(message)
            return RateLimitError(message)
        if response.status_code == 400:
            if "context" in message.lower() and (
                "length" in message.lower() or "window" in message.lower()
            ):
                return ContextOverflowError(message)
            return InvalidRequestError(message)
        if response.status_code >= 500:
            return ProviderInternalError(message)
        return InvalidRequestError(message)


def _input_payload(request: ModelRequest) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in request.messages:
        if message.role == "tool":
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": message.tool_call_id,
                    "output": message.content,
                }
            )
            continue
        if message.role == "assistant" and message.tool_calls:
            for call in message.tool_calls:
                items.append(
                    {
                        "type": "function_call",
                        "call_id": call.id,
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    }
                )
            continue
        items.append({"role": message.role, "content": message.content})
    return items


def _tool_payload(tool: dict[str, object]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": tool["name"],
        "description": tool.get("description", ""),
        "parameters": _json_schema(tool.get("input_schema", {})),
    }


def _json_schema(input_schema: object) -> dict[str, Any]:
    if not isinstance(input_schema, dict):
        return {"type": "object", "properties": {}}
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, raw in input_schema.items():
        if not isinstance(raw, dict):
            properties[name] = {}
            continue
        properties[name] = {
            key: value
            for key, value in raw.items()
            if not (key == "required" and isinstance(value, bool))
        }
        if raw.get("required") is True:
            required.append(name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _parse_function_call(item: dict[str, Any]) -> ToolCall:
    call_id = item.get("call_id") or item.get("id")
    name = item.get("name")
    arguments = item.get("arguments") or "{}"
    if not call_id or not name:
        raise ToolProtocolError("Responses API emitted an incomplete function call")
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise ToolProtocolError(
            f"provider emitted invalid tool arguments for {name}",
            tool_name=str(name),
            call_id=str(call_id),
            raw_arguments=arguments,
            parse_error=str(exc),
        ) from exc
    if not isinstance(parsed, dict):
        raise ToolProtocolError("tool arguments must be a JSON object")
    return ToolCall(id=str(call_id), name=str(name), arguments=parsed)


def _parse_usage(payload: dict[str, Any], request_id: str) -> ModelUsage:
    input_details = payload.get("input_tokens_details") or {}
    output_details = payload.get("output_tokens_details") or {}
    return ModelUsage(
        input_tokens=int(payload.get("input_tokens", 0)),
        output_tokens=int(payload.get("output_tokens", 0)),
        reasoning_tokens=int(output_details.get("reasoning_tokens", 0)),
        cache_read_tokens=int(input_details.get("cached_tokens", 0)),
        cache_write_tokens=0,
        provider_request_id=request_id,
    )


def _estimate_cost(usage: ModelUsage, request: ModelRequest) -> ModelUsage:
    input_rate = request.provider_options.get("input_cost_per_million")
    output_rate = request.provider_options.get("output_cost_per_million")
    if not isinstance(input_rate, (int, float)) or not isinstance(output_rate, (int, float)):
        return usage
    estimated = (
        usage.input_tokens * float(input_rate) + usage.output_tokens * float(output_rate)
    ) / 1_000_000
    return ModelUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        reasoning_tokens=usage.reasoning_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        estimated_cost=estimated,
        provider_request_id=usage.provider_request_id,
        duration_ms=usage.duration_ms,
    )


def _error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error["message"])
            if isinstance(error, str):
                return error
            if payload.get("message"):
                return str(payload["message"])
    except Exception:
        pass
    return response.text or f"HTTP {response.status_code}"
