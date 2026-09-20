"""Deterministic fake provider implementations."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncIterator

from algocode.domain.model import TaskPhase
from algocode.providers.types import (
    FinishEvent,
    ModelEvent,
    ModelRequest,
    ModelResponse,
    TextDelta,
    ToolCall,
    ToolCallDelta,
    UsageEvent,
)


class ScriptedFakeProvider:
    """Return a deterministic sequence of pre-built model responses."""

    def __init__(self, responses: tuple[ModelResponse, ...]) -> None:
        self._responses = responses
        self._index = 0
        self._lock = asyncio.Lock()

    async def complete(self, request: ModelRequest) -> ModelResponse:
        async with self._lock:
            if self._index >= len(self._responses):
                return ModelResponse(text="fake provider script exhausted")
            response = self._responses[self._index]
            self._index += 1
            return response

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        response = await self.complete(request)
        if response.text:
            yield TextDelta(response.text)
        for call in response.tool_calls:
            yield ToolCallDelta(call)
        yield UsageEvent(response.usage)
        yield FinishEvent(response.finish_reason)


class DeterministicFakeProvider:
    """Run a built-in no-key script that exercises inspect and phase tools."""

    def __init__(self) -> None:
        self._counters: defaultdict[str, int] = defaultdict(int)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        phase_value = str(request.metadata.get("phase", TaskPhase.CREATE.value))
        if request.metadata.get("stage") == "analysis_summary":
            return ModelResponse(
                text=json.dumps(
                    {
                        "summary": "Fake provider analyzed the project.",
                        "language": "python",
                        "files": [{"path": "main.py", "role": "algorithm"}],
                        "problemStructure": {
                            "inputModel": "single stdin case with n values",
                            "dataDistribution": "uniform integers",
                            "operationAlgebra": "addition is associative and commutative",
                            "queryUpdateMix": "read-only queries",
                            "monotonicity": "not monotonic",
                            "constraints": ["output order preserved"],
                        },
                        "complexityBaseline": {
                            "current": "O(n^2)",
                            "knownBest": "O(n log n)",
                            "gap": "nested loop over pairs",
                            "reasoning": "the pair scan can be replaced by sorting",
                        },
                        "algorithmCandidates": [
                            {
                                "name": "sort and scan",
                                "paradigm": "sorting",
                                "complexity": "O(n log n)",
                                "applicability": "comparable keys",
                                "expectedGain": "removes the quadratic pair loop",
                            },
                            {
                                "name": "hash index",
                                "paradigm": "hashing",
                                "complexity": "O(n)",
                                "applicability": "exact key lookup",
                                "expectedGain": "constant-time membership queries",
                            },
                            {
                                "name": "two pointers",
                                "paradigm": "greedy scanning",
                                "complexity": "O(n log n)",
                                "applicability": "monotone order after sorting",
                                "expectedGain": "single pass after sorting",
                            },
                        ],
                        "optimizationCandidates": [
                            {"id": "optimize", "description": "Optimize the hot path."}
                        ],
                    }
                )
            )
        index = self._counters[phase_value]
        self._counters[phase_value] += 1
        if phase_value == TaskPhase.CREATE.value and index == 0:
            return ModelResponse(
                text="Inspecting the workspace before completing the phase.",
                tool_calls=(
                    ToolCall(
                        id="fake_list_1",
                        name="list_files",
                        arguments={"pattern": "*", "max_results": 50},
                    ),
                ),
            )
        if phase_value == TaskPhase.ANALYZE.value and index < 2:
            return ModelResponse(
                text="Reading all required files.",
                tool_calls=(
                    ToolCall(
                        id=f"fake_read_required_{index}",
                        name="read_required_files",
                        arguments={},
                    ),
                ),
            )
        if phase_value == TaskPhase.PLAN.value:
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="fake_plan",
                        name="submit_optimization_plan",
                        arguments={
                            "summary": "Optimize the hot path.",
                            "strategy": "Apply the planned optimization.",
                            "algorithm": "sort and scan",
                            "complexityBefore": "O(n^2)",
                            "complexityAfter": "O(n log n)",
                            "whyFaster": "replaces the pair scan with a sorted single pass",
                            "structureRef": "problemStructure.operationAlgebra",
                            "steps": [
                                {
                                    "id": "step-1",
                                    "description": "Modify the hot path.",
                                    "files": ["main.py"],
                                }
                            ],
                        },
                    ),
                )
            )
        if phase_value == TaskPhase.GENERATE_CANDIDATE.value and index == 0:
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="fake_candidate",
                        name="create_candidate",
                        arguments={},
                    ),
                )
            )
        return ModelResponse(
            text=f"Phase {phase_value} completed.",
            tool_calls=(
                ToolCall(
                    id=f"fake_submit_{phase_value}_{index}",
                    name="submit_phase_result",
                    arguments={
                        "phase": phase_value,
                        "status": "completed",
                        "summary": f"Completed {phase_value}",
                        "findings": [],
                        "blockers": [],
                    },
                ),
            ),
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        response = await self.complete(request)
        if response.text:
            yield TextDelta(response.text)
        for call in response.tool_calls:
            yield ToolCallDelta(call)
        yield UsageEvent(response.usage)
        yield FinishEvent(response.finish_reason)
