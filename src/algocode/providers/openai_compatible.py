"""OpenAI-compatible Chat Completions provider over SSE."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
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


@dataclass(slots=True)
class _ToolCallAccumulator:
    index: int
    call_id: str = ""
    name: str = ""
    arguments: str = ""


class OpenAICompatibleProvider:
    """OpenAI-compatible provider with SSE, tool calls, usage, and retries."""

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
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                            "Accept": "text/event-stream",
                        },
                        json={**payload, "stream": True, "stream_options": {"include_usage": True}},
                    )
                    if response.status_code >= 400:
                        error = self._map_http_error(response)
                        if self._retryable(error) and attempt < self.max_retries:
                            last_error = error
                            await asyncio.sleep(0.25 * (2**attempt))
                            continue
                        raise error
                    return self._parse_sse(response.text, request)
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
        raise last_error or ProviderInternalError("provider request failed")

    def _request_payload(self, request: ModelRequest) -> dict[str, Any]:
        messages: list[dict[str, Any]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend(_message_payload(message) for message in request.messages)
        payload: dict[str, Any] = {
            "model": request.model.model_id or self.model_id,
            "messages": messages,
        }
        if request.tools:
            payload["tools"] = [_tool_payload(tool) for tool in request.tools]
        if request.tool_choice is not None:
            payload["tool_choice"] = request.tool_choice
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        if request.generation:
            payload.update(request.generation)
        return payload

    def _parse_sse(self, body: str, request: ModelRequest) -> ModelResponse:
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls: dict[int, _ToolCallAccumulator] = {}
        usage = ModelUsage()
        finish_reason = "stop"
        request_id: str | None = None

        for line in body.splitlines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError as exc:
                raise InvalidProviderOutputError("provider emitted invalid SSE JSON") from exc
            request_id = str(chunk.get("id", request_id or "")) or request_id
            if isinstance(chunk.get("usage"), dict):
                usage = _estimate_cost(
                    _parse_usage(chunk["usage"], request_id),
                    request,
                )
            for choice in chunk.get("choices", []):
                delta = choice.get("delta") or {}
                if isinstance(delta.get("content"), str):
                    content_parts.append(delta["content"])
                reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                if isinstance(reasoning, str):
                    reasoning_parts.append(reasoning)
                for fragment in delta.get("tool_calls") or []:
                    _accumulate_tool_call(tool_calls, fragment)
                if choice.get("finish_reason"):
                    finish_reason = str(choice["finish_reason"])
        calls = tuple(_finish_tool_call(item) for _, item in sorted(tool_calls.items()))
        return ModelResponse(
            text="".join(content_parts),
            tool_calls=calls,
            usage=usage,
            finish_reason=finish_reason,
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


def _tool_payload(tool: dict[str, object]) -> dict[str, Any]:
    function: dict[str, Any] = {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "parameters": _json_schema(tool.get("input_schema", {})),
    }
    if tool.get("strict") is True:
        function["strict"] = True
    return {"type": "function", "function": function}


def _message_payload(message: Message) -> dict[str, Any]:
    payload: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.reasoning_content:
        payload["reasoning_content"] = message.reasoning_content
    if message.tool_call_id is not None:
        payload["tool_call_id"] = message.tool_call_id
    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.name,
                    "arguments": json.dumps(call.arguments, ensure_ascii=False),
                },
            }
            for call in message.tool_calls
        ]
    return payload


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


def _accumulate_tool_call(
    calls: dict[int, _ToolCallAccumulator],
    fragment: dict[str, Any],
) -> None:
    index = int(fragment.get("index", 0))
    accumulator = calls.setdefault(index, _ToolCallAccumulator(index=index))
    if fragment.get("id"):
        accumulator.call_id = str(fragment["id"])
    function = fragment.get("function") or {}
    if function.get("name"):
        accumulator.name += str(function["name"])
    if function.get("arguments"):
        accumulator.arguments += str(function["arguments"])


def _finish_tool_call(accumulator: _ToolCallAccumulator) -> ToolCall:
    if not accumulator.call_id or not accumulator.name:
        raise ToolProtocolError("provider emitted an incomplete tool call")
    try:
        arguments = json.loads(accumulator.arguments or "{}")
    except json.JSONDecodeError as exc:
        raise ToolProtocolError(
            f"provider emitted invalid tool arguments for {accumulator.name}",
            tool_name=accumulator.name,
            call_id=accumulator.call_id,
            raw_arguments=accumulator.arguments,
            parse_error=str(exc),
        ) from exc
    if not isinstance(arguments, dict):
        raise ToolProtocolError("tool arguments must be a JSON object")
    return ToolCall(id=accumulator.call_id, name=accumulator.name, arguments=arguments)


def _parse_usage(payload: dict[str, Any], request_id: str | None) -> ModelUsage:
    return ModelUsage(
        input_tokens=int(payload.get("prompt_tokens", 0)),
        output_tokens=int(payload.get("completion_tokens", 0)),
        reasoning_tokens=int(
            (payload.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
        ),
        cache_read_tokens=int(payload.get("prompt_cache_hit_tokens", 0)),
        cache_write_tokens=int(payload.get("prompt_cache_miss_tokens", 0)),
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
    except ValueError:
        return f"provider returned HTTP {response.status_code}"
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return f"provider returned HTTP {response.status_code}: {error['message']}"
        if payload.get("message"):
            return f"provider returned HTTP {response.status_code}: {payload['message']}"
    return f"provider returned HTTP {response.status_code}"
