"""Scripted provider for built-in optimization and policy evaluation."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import AsyncIterator

from algocode.domain.model import TaskPhase
from algocode.eval.types import EvalTask
from algocode.providers.types import (
    FinishEvent,
    ModelEvent,
    ModelRequest,
    ModelResponse,
    ToolCall,
    ToolCallDelta,
    UsageEvent,
)


class PhaseScriptedProvider:
    def __init__(self, task: EvalTask, candidate_id: str | None) -> None:
        self.task = task
        self.candidate_id = candidate_id
        self._counters: defaultdict[str, int] = defaultdict(int)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        if request.metadata.get("stage") == "analysis_summary":
            return ModelResponse(
                text=json.dumps(
                    {
                        "summary": "Evaluation project analyzed.",
                        "language": self.task.language,
                        "files": [{"path": next(iter(self.task.files)), "role": "entrypoint"}],
                        "problemStructure": {
                            "inputModel": "stdin case defined by the evaluation task",
                            "dataDistribution": "fixed evaluation input",
                            "operationAlgebra": "the task operations are deterministic",
                            "queryUpdateMix": "single run per case",
                            "monotonicity": "not applicable",
                            "constraints": ["output must stay byte-identical"],
                        },
                        "complexityBaseline": {
                            "current": "the task baseline",
                            "knownBest": "a faster known approach exists",
                            "gap": "constant-factor overhead in the hot path",
                            "reasoning": "the prepared patch removes redundant work",
                        },
                        "algorithmCandidates": [
                            {
                                "name": "prepared patch",
                                "paradigm": "implementation",
                                "complexity": "unchanged",
                                "applicability": "always",
                                "expectedGain": "removes redundant work",
                            },
                            {
                                "name": "memoization",
                                "paradigm": "caching",
                                "complexity": "amortized lower",
                                "applicability": "repeated subproblems",
                                "expectedGain": "avoids repeated computation",
                            },
                            {
                                "name": "branch elimination",
                                "paradigm": "control flow",
                                "complexity": "unchanged",
                                "applicability": "predictable branches",
                                "expectedGain": "fewer mispredictions",
                            },
                        ],
                        "optimizationCandidates": [
                            {
                                "id": "optimize",
                                "description": self.task.objective,
                            }
                        ],
                    }
                )
            )
        phase = str(request.metadata.get("phase", TaskPhase.CREATE.value))
        index = self._counters[phase]
        self._counters[phase] += 1
        if phase == TaskPhase.ANALYZE.value and index < 2:
            return _tool(
                f"read_required_{phase}_{index}",
                "read_required_files",
                {},
            )
        if phase == TaskPhase.PLAN.value:
            return _tool(
                f"plan_{phase}_{index}",
                "submit_optimization_plan",
                {
                    "summary": self.task.objective,
                    "strategy": "Apply the candidate patch.",
                    "algorithm": "prepared patch",
                    "complexityBefore": "the task baseline",
                    "complexityAfter": "unchanged complexity, less work",
                    "whyFaster": "redundant work is removed from the hot path",
                    "structureRef": "problemStructure.inputModel",
                    "steps": [
                        {
                            "id": "s1",
                            "description": "Apply the prepared optimization.",
                            "files": sorted(self.task.files),
                        }
                    ],
                },
            )
        if (
            phase == TaskPhase.IMPLEMENT.value
            and index == 0
            and self.task.candidate_patch is not None
        ):
            return _tool(
                f"patch_{phase}_{index}",
                "apply_patch",
                {"patch": self.task.candidate_patch},
            )
        if phase == TaskPhase.IMPLEMENT.value and self.task.candidate_patch is not None:
            return _tool(
                f"implement_result_{phase}_{index}",
                "submit_phase_result",
                {
                    "phase": "implement",
                    "status": "completed",
                    "summary": "Candidate implementation completed.",
                    "result": {"changedFiles": sorted(self.task.files)},
                },
            )
        if (
            phase == TaskPhase.VERIFY.value
            and index == 0
            and self.task.candidate_correctness_spec is not None
        ):
            return _tool(
                f"correctness_{phase}_{index}",
                "run_correctness",
                {"spec": self.task.candidate_correctness_spec},
            )
        if (
            phase == TaskPhase.BENCHMARK.value
            and index == 0
            and self.task.benchmark_spec is not None
        ):
            return _tool(
                f"benchmark_{phase}_{index}",
                "run_benchmark",
                {"spec": self.task.benchmark_spec},
            )
        return _tool(
            f"submit_{phase}_{index}",
            "submit_phase_result",
            {
                "phase": phase,
                "status": "completed",
                "summary": f"Completed {phase}",
                "findings": [],
                "blockers": [],
            },
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelEvent]:
        response = await self.complete(request)
        for call in response.tool_calls:
            yield ToolCallDelta(call)
        yield UsageEvent(response.usage)
        yield FinishEvent(response.finish_reason)


def _tool(call_id: str, name: str, arguments: dict[str, object]) -> ModelResponse:
    return ModelResponse(
        text=json.dumps({"tool": name}),
        tool_calls=(ToolCall(id=call_id, name=name, arguments=arguments),),
    )
