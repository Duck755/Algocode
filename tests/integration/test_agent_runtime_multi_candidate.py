from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from algocode.benchmark.spec import BenchmarkSpec
from algocode.bootstrap import build_context
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from algocode.domain.events import EventType
from algocode.domain.model import TaskPhase, TaskStatus
from algocode.providers.types import ModelRequest, ModelResponse, ToolCall
from algocode.runtime.agent import AgentRuntime
from algocode.tools import build_default_registry
from tests.support.git import init_git_repository

CORRECTNESS_YAML = """schema_version: 1
mode: cases
comparison: line-trim
cases:
  - id: output
    expected_output: '42'
"""


BENCHMARK_YAML = """schema_version: 1
scope: stdin
warmup: 0
repeats: 1
timeout_seconds: 10
metric: wall_time
"""


class MultiCandidateSearchProvider:
    def __init__(self, patches: tuple[str, ...]) -> None:
        self.patches = patches
        self.generated = 0
        self.saw_archive_context = False

    async def complete(self, request: ModelRequest) -> ModelResponse:
        stage = request.metadata.get("stage")
        phase = str(request.metadata.get("phase", ""))
        message_text = "\n".join(message.content for message in request.messages)
        if "[search archive]" in message_text:
            self.saw_archive_context = True

        if stage == "analysis_summary":
            return ModelResponse(
                text=json.dumps(
                    {
                        "summary": "Project analyzed from two read passes.",
                        "language": "python",
                        "files": [{"path": "main.py", "role": "algorithm"}],
                        "problemStructure": {
                            "inputModel": "stdin",
                            "dataDistribution": "uniform",
                            "operationAlgebra": "associative",
                            "queryUpdateMix": "read-only",
                            "monotonicity": "none",
                        },
                        "complexityBaseline": {
                            "current": "O(n^2)",
                            "knownBest": "O(n log n)",
                            "gap": "pairwise scan",
                            "reasoning": "sorting removes the scan",
                        },
                        "algorithmCandidates": [
                            {
                                "name": "sort and scan",
                                "paradigm": "sorting",
                                "complexity": "O(n log n)",
                                "applicability": "comparable keys",
                            },
                            {
                                "name": "hash index",
                                "paradigm": "hashing",
                                "complexity": "O(n)",
                                "applicability": "exact keys",
                            },
                            {
                                "name": "two pointers",
                                "paradigm": "greedy",
                                "complexity": "O(n)",
                                "applicability": "sorted input",
                            },
                        ],
                        "optimizationCandidates": [
                            {
                                "id": "localize",
                                "description": "Explore timing variants for main.py.",
                            }
                        ],
                    }
                )
            )
        if phase == "create":
            return self._submit(phase)
        if phase == "analyze":
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="read_required",
                        name="read_required_files",
                        arguments={},
                    ),
                )
            )
        if phase == "plan":
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="plan_result",
                        name="submit_optimization_plan",
                        arguments={
                            "summary": "Explore print timing variants.",
                            "strategy": "Try small equivalent edits to main.py.",
                            "algorithm": "sort and scan",
                            "complexityBefore": "O(n^2)",
                            "complexityAfter": "O(n log n)",
                            "whyFaster": "removes the pairwise scan",
                            "structureRef": "problemStructure.operationAlgebra",
                            "steps": [
                                {
                                    "id": "edit-main",
                                    "description": "Patch main.py.",
                                    "files": ["main.py"],
                                }
                            ],
                        },
                    ),
                )
            )
        if phase == "generate_candidate":
            self.generated += 1
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id=f"candidate_{self.generated}",
                        name="create_candidate",
                        arguments={},
                    ),
                )
            )
        if phase == "implement":
            index = min(self.generated, len(self.patches)) - 1
            patch = self.patches[index]
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id=f"patch_{index + 1}",
                        name="apply_patch",
                        arguments={"patch": patch},
                    ),
                    ToolCall(
                        id=f"check_{index + 1}",
                        name="run_candidate_check",
                        arguments={},
                    ),
                    ToolCall(
                        id=f"submit_implement_{index + 1}",
                        name="submit_phase_result",
                        arguments={
                            "phase": "implement",
                            "status": "completed",
                            "summary": f"candidate {index + 1} implemented",
                            "result": {"changedFiles": ["main.py"]},
                        },
                    ),
                )
            )
        if phase == "verify":
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="verify_correctness",
                        name="run_correctness",
                        arguments={"spec_path": ".algocode/oracle/correctness.yaml"},
                    ),
                )
            )
        if phase == "benchmark":
            return ModelResponse(
                tool_calls=(
                    ToolCall(
                        id="run_benchmark",
                        name="run_benchmark",
                        arguments={"spec_path": ".algocode/benchmarks/benchmark.yaml"},
                    ),
                )
            )
        return self._submit(phase)

    @staticmethod
    def _submit(phase: str) -> ModelResponse:
        return ModelResponse(
            tool_calls=(
                ToolCall(
                    id=f"submit_{phase}",
                    name="submit_phase_result",
                    arguments={
                        "phase": phase,
                        "status": "completed",
                        "summary": f"completed {phase}",
                    },
                ),
            )
        )


class MultiCandidateEndToEndTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {
                "main.py": "print(42)\n",
                ".algocode/oracle/correctness.yaml": CORRECTNESS_YAML,
                ".algocode/benchmarks/benchmark.yaml": BENCHMARK_YAML,
            },
        )
        self.context = build_context(data_dir=self.root / "data")
        self.project = await self.context.project_service.register(
            self.project_root,
            write_config=True,
        )
        self.task = await self.context.task_service.create_task(
            "Optimize print timing",
            project_id=self.project.id,
        )
        await self.context.baseline_service.capture(self.task.id)
        correctness_spec = CorrectnessSpec(
            mode="cases",
            comparison="line-trim",
            cases=(CorrectnessCase(id="output", expected_output="42"),),
        )
        await self.context.correctness_service.run_baseline(
            self.task.id,
            correctness_spec,
        )
        benchmark_spec = BenchmarkSpec(
            scope="stdin",
            warmup=0,
            repeats=1,
            timeout_seconds=10,
            metric="wall_time",
        )
        await self.context.benchmark_service.run_baseline(
            self.task.id,
            benchmark_spec,
        )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _runtime(self, provider) -> AgentRuntime:
        return AgentRuntime(
            event_store=self.context.event_store,
            task_service=self.context.task_service,
            provider=provider,
            tool_registry=build_default_registry(),
            project_service=self.context.project_service,
            baseline_service=self.context.baseline_service,
            artifact_store=self.context.artifact_store,
            language_registry=self.context.language_registry,
            correctness_service=self.context.correctness_service,
            benchmark_service=self.context.benchmark_service,
            candidate_service=self.context.candidate_service,
            decision_service=self.context.decision_service,
            experiment_service=self.context.experiment_service,
            search_archive_service=self.context.search_archive_service,
            max_candidates=3,
            max_population=6,
            max_evals=50,
            max_iterations=3,
        )

    async def test_optimize_explores_multiple_candidates_and_converges(self) -> None:
        patches = (
            (
                "diff --git a/main.py b/main.py\n"
                "--- a/main.py\n"
                "+++ b/main.py\n"
                "@@ -1 +1,3 @@\n"
                " print(42)\n"
                "+import time\n"
                "+time.sleep(0.02)\n"
            ),
            (
                "diff --git a/main.py b/main.py\n"
                "--- a/main.py\n"
                "+++ b/main.py\n"
                "@@ -1 +1,2 @@\n"
                " print(42)\n"
                "+total = sum(range(10000))\n"
            ),
            (
                "diff --git a/main.py b/main.py\n"
                "--- a/main.py\n"
                "+++ b/main.py\n"
                "@@ -1 +1,2 @@\n"
                " print(42)\n"
                "+value = 42\n"
            ),
        )
        provider = MultiCandidateSearchProvider(patches)

        result = await self._runtime(provider).run(
            self.task.id,
            stop_after=TaskPhase.REPORT,
        )

        self.assertEqual(result.status, TaskStatus.COMPLETED.value)
        self.assertIn(TaskPhase.DECIDE.value, result.completed_phases)
        candidates = await self.context.candidate_service.list_for_task(self.task.id)
        self.assertGreaterEqual(len(candidates), 2)
        self.assertTrue(provider.saw_archive_context)

        events = await self.context.event_store.read(str(self.task.id))
        created_events = [
            event for event in events if event.type is EventType.CANDIDATE_CREATED
        ]
        self.assertGreaterEqual(len(created_events), 2)

        project_main = self.project_root / "main.py"
        self.assertEqual(project_main.read_text(encoding="utf-8"), "print(42)\n")
