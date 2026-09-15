"""Provider adapters."""

from algocode.providers.fake import DeterministicFakeProvider, ScriptedFakeProvider
from algocode.providers.openai_compatible import OpenAICompatibleProvider
from algocode.providers.types import (
    FinishEvent,
    Message,
    ModelRef,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    ProviderErrorEvent,
    ReasoningDelta,
    TextDelta,
    ToolCall,
    ToolCallDelta,
    UsageEvent,
)

__all__ = [
    "DeterministicFakeProvider",
    "FinishEvent",
    "Message",
    "ModelRef",
    "ModelRequest",
    "ModelResponse",
    "ModelUsage",
    "OpenAICompatibleProvider",
    "ProviderErrorEvent",
    "ReasoningDelta",
    "ScriptedFakeProvider",
    "TextDelta",
    "ToolCall",
    "ToolCallDelta",
    "UsageEvent",
]
