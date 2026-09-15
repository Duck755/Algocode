"""Provider-neutral model and tool-call types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class ModelRef:
    provider_id: str
    model_id: str
    variant: str | None = None


@dataclass(frozen=True, slots=True)
class ModelUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    estimated_cost: float | None = None
    provider_request_id: str | None = None
    duration_ms: int = 0


@dataclass(frozen=True, slots=True)
class ModelRequest:
    request_id: str
    model: ModelRef
    system: str
    messages: tuple[Message, ...]
    tools: tuple[dict[str, object], ...] = ()
    tool_choice: str | None = None
    generation: dict[str, object] = field(default_factory=dict)
    response_format: dict[str, object] | None = None
    provider_options: dict[str, object] = field(default_factory=dict)
    timeout_seconds: int = 60
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: ModelUsage = field(default_factory=ModelUsage)
    finish_reason: str = "stop"


@dataclass(frozen=True, slots=True)
class TextDelta:
    text: str


@dataclass(frozen=True, slots=True)
class ReasoningDelta:
    text: str


@dataclass(frozen=True, slots=True)
class ToolCallDelta:
    call: ToolCall


@dataclass(frozen=True, slots=True)
class UsageEvent:
    usage: ModelUsage


@dataclass(frozen=True, slots=True)
class FinishEvent:
    reason: str


@dataclass(frozen=True, slots=True)
class ProviderErrorEvent:
    error_type: str
    message: str


ModelEvent = (
    TextDelta | ReasoningDelta | ToolCallDelta | UsageEvent | FinishEvent | ProviderErrorEvent
)
