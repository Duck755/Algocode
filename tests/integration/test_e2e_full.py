from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from algocode.benchmark.spec import BenchmarkSpec
from algocode.bootstrap import build_context
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from algocode.domain.events import EventType
from algocode.domain.model import CandidateStatus, TaskPhase
from algocode.providers.openai_compatible import OpenAICompatibleProvider
from algocode.providers.types import ModelRef
from algocode.runtime.agent import AgentRuntime
from tests.support.git import init_git_repository
from tests.support.mock_openai import MockOpenAIServer


class FullE2ETests(unittest.IsolatedAsyncioTestCase):
    async def test_real_provider_python_candidate_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_root = init_git_repository(
                root / "project",
                {
                    "main.py": ("import time\ntime.sleep(0.05)\nprint('hello')\n"),
                    ".algocode/oracle/correctness.yaml": (
                        "schema_version: 1\n"
                        "mode: cases\n"
                        "comparison: line-trim\n"
                        "cases:\n"
                        "  - id: candidate\n"
                        '    expected_output: "hi"\n'
                    ),
                    ".algocode/oracle/contract_test.py": "raise SystemExit(0)\n",
                },
            )
            (project_root / ".algocode.yaml").write_text(
                "acceptancePolicy:\n"
                "  minMedianImprovementPercent: -1000\n"
                "  requireStatisticallySignificant: false\n"
                "policy:\n"
                "  sandbox:\n"
                "    backend: native\n",
                encoding="utf-8",
            )
            (project_root / ".git" / "info" / "exclude").write_text(
                "__pycache__/\n*.py[cod]\n",
                encoding="utf-8",
            )
            context = build_context(project_root=project_root, data_dir=root / "data")
            project = await context.project_service.register(project_root)
            task = await context.task_service.create_task(
                "Optimize Python output",
                project_id=project.id,
            )
            await context.baseline_service.capture(task.id)
            await context.correctness_service.run_baseline(
                task.id,
                CorrectnessSpec(
                    mode="cases",
                    comparison="line-trim",
                    cases=(CorrectnessCase(id="baseline", expected_output="hello"),),
                ),
            )
            benchmark_spec = BenchmarkSpec(warmup=0, repeats=1)
            await context.benchmark_service.run_baseline(task.id, benchmark_spec)

            with MockOpenAIServer() as server:
                _enqueue_python_agent_script(server)
                provider = OpenAICompatibleProvider(
                    provider_id="mock",
                    base_url=server.base_url,
                    api_key="test-key",
                    model_id="mock-model",
                )
                runtime = AgentRuntime(
                    event_store=context.event_store,
                    task_service=context.task_service,
                    provider=provider,
                    tool_registry=context.tool_registry,
                    project_service=context.project_service,
                    baseline_service=context.baseline_service,
                    artifact_store=context.artifact_store,
                    language_registry=context.language_registry,
                    correctness_service=context.correctness_service,
                    benchmark_service=context.benchmark_service,
                    database=context.database,
                    candidate_service=context.candidate_service,
                    resource_provider=context.resource_provider,
                    redactor=context.secret_redactor,
                    model=ModelRef(provider_id="mock", model_id="mock-model"),
                )
                result = await runtime.run(task.id, stop_after=TaskPhase.REPORT)
            self.assertEqual(result.status, "completed", result)
            candidates = await context.candidate_service.list_for_task(task.id)
            self.assertEqual(len(candidates), 1)
            candidate = candidates[0]
            correctness_runs = await context.correctness_service.list_for_task(task.id)
            candidate_correctness = next(
                run for run in correctness_runs if run.target_kind == "candidate"
            )
            _, replay_result = await context.correctness_service.replay(candidate_correctness.id)
            self.assertTrue(replay_result.passed)
            self.assertEqual(candidate.status, CandidateStatus.VERIFIED)

            decision = await context.decision_service.accept(task.id, candidate.id)
            report, markdown, _ = await context.report_service.build(task.id)
            applied = await context.apply_service.apply(task.id, candidate.id)
            rolled_back = await context.apply_service.rollback(task.id, candidate.id)

            self.assertEqual(decision.outcome.value, "accepted")
            self.assertEqual(report["selectedCandidateId"], str(candidate.id))
            self.assertIn(str(candidate.id), markdown)
            self.assertTrue(applied["applied"])
            self.assertTrue(rolled_back["rolled_back"])
            self.assertIn("print('hello')", (project_root / "main.py").read_text("utf-8"))

            events = await context.event_store.read(str(task.id))
            self.assertEqual(
                [event.seq for event in events],
                list(range(1, len(events) + 1)),
            )
            event_types = {event.type for event in events}
            for expected in (
                EventType.CANDIDATE_CREATED,
                EventType.CORRECTNESS_PASSED,
                EventType.BENCHMARK_SAMPLES_CAPTURED,
                EventType.COMPARISON_PRODUCED,
                EventType.DECISION_MADE,
                EventType.REPORT_GENERATED,
                EventType.CANDIDATE_APPLIED,
                EventType.CANDIDATE_ROLLED_BACK,
                EventType.TASK_COMPLETED,
            ):
                self.assertIn(expected, event_types)

            candidate_runs = [
                run
                for run in await context.benchmark_service.list_for_task(task.id)
                if run.target_kind == "candidate"
            ]
            evidence = report["benchmarkEvidence"]
            self.assertTrue(candidate_runs)
            candidate_evidence = next(
                item for item in evidence if item["runId"] == candidate_runs[-1].id
            )
            self.assertEqual(
                candidate_evidence["comparisonRef"]["sha256"],
                candidate_runs[-1].comparison_ref.sha256,
            )

    @unittest.skipUnless(
        shutil.which("g++") or shutil.which("clang++"),
        "no supported C++ compiler is available",
    )
    async def test_cpp_candidate_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_root = init_git_repository(
                root / "project",
                {
                    "main.cpp": (
                        '#include <iostream>\nint main() {\n  std::cout << "hello\\n";\n}\n'
                    )
                },
            )
            (project_root / ".algocode.yaml").write_text(
                "acceptancePolicy:\n"
                "  minMedianImprovementPercent: -1000\n"
                "  requireStatisticallySignificant: false\n"
                "policy:\n"
                "  sandbox:\n"
                "    backend: native\n",
                encoding="utf-8",
            )
            context = build_context(project_root=project_root, data_dir=root / "data")
            project = await context.project_service.register(project_root)
            task = await context.task_service.create_task(
                "Optimize C++ output",
                project_id=project.id,
            )
            await context.baseline_service.capture(task.id)
            await context.correctness_service.run_baseline(
                task.id,
                CorrectnessSpec(
                    mode="cases",
                    comparison="line-trim",
                    cases=(CorrectnessCase(id="baseline", expected_output="hello"),),
                ),
            )
            benchmark_spec = BenchmarkSpec(warmup=0, repeats=1)
            await context.benchmark_service.run_baseline(task.id, benchmark_spec)

            candidate = await context.candidate_service.create(task.id)
            (Path(candidate.workspace_ref) / "main.cpp").write_text(
                '#include <iostream>\nint main() { std::cout << "hi\\n"; }\n',
                encoding="utf-8",
            )
            candidate = await context.candidate_service.freeze(candidate.id)
            correctness_run, correctness = await context.correctness_service.run_target(
                task.id,
                CorrectnessSpec(
                    mode="cases",
                    comparison="line-trim",
                    cases=(CorrectnessCase(id="candidate", expected_output="hi"),),
                ),
                target_kind="candidate",
                target_id=str(candidate.id),
                workspace_ref=candidate.workspace_ref,
            )
            self.assertTrue(correctness.passed)
            await context.benchmark_service.run_candidate(
                task.id,
                str(candidate.id),
                candidate.workspace_ref,
                correctness_run.id,
                benchmark_spec,
            )
            await context.decision_service.accept(task.id, candidate.id)
            await context.report_service.build(task.id)
            applied = await context.apply_service.apply(task.id, candidate.id)
            rolled_back = await context.apply_service.rollback(task.id, candidate.id)

            self.assertTrue(applied["applied"])
            self.assertTrue(rolled_back["rolled_back"])
            self.assertIn("hello", (project_root / "main.cpp").read_text("utf-8"))


def _enqueue_python_agent_script(server: MockOpenAIServer) -> None:
    for index, path in enumerate(("main.py", "main.py", ".algocode.yaml", ".algocode.yaml")):
        server.enqueue_tool_call(
            f"read_{index}",
            "read_file",
            {"path": path},
        )
    server.enqueue_text(
        json.dumps(
            {
                "summary": "The Python entrypoint is analyzed.",
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
                    {"id": "remove-sleep", "description": "Remove the sleep."}
                ],
            }
        )
    )
    server.enqueue_tool_call(
        "submit_plan",
        "submit_optimization_plan",
        {
            "summary": "Remove the fixed delay.",
            "strategy": "Replace main.py with an immediate output.",
            "algorithm": "single print",
            "complexityBefore": "O(1) with a fixed delay",
            "complexityAfter": "O(1) without the delay",
            "whyFaster": "removes the artificial sleep",
            "structureRef": "problemStructure.inputModel",
            "steps": [
                {
                    "id": "remove-sleep",
                    "description": "Replace main.py with print('hi').",
                    "files": ["main.py"],
                }
            ],
        },
    )
    server.enqueue_tool_call("create_candidate", "create_candidate", {})
    patch = (
        "diff --git a/main.py b/main.py\n"
        "--- a/main.py\n"
        "+++ b/main.py\n"
        "@@ -1,3 +1 @@\n"
        "-import time\n"
        "-time.sleep(0.05)\n"
        "-print('hello')\n"
        "+print('hi')\n"
    )
    server.enqueue_tool_call("apply_patch", "apply_patch", {"patch": patch})
    server.enqueue_tool_call("run_candidate_check", "run_candidate_check", {})
    server.enqueue_tool_call(
        "submit_implement",
        "submit_phase_result",
        {
            "phase": "implement",
            "status": "completed",
            "summary": "Implemented the planned delay removal.",
            "result": {"changedFiles": ["main.py"]},
        },
    )
    server.enqueue_tool_call(
        "run_correctness",
        "run_correctness",
        {
            "spec": {
                "mode": "cases",
                "comparison": "line-trim",
                "cases": [{"id": "candidate", "expected_output": "hi"}],
            }
        },
    )
    server.enqueue_tool_call("run_contract", "run_contract", {})
    server.enqueue_tool_call(
        "run_benchmark",
        "run_benchmark",
        {"spec": {"warmup": 0, "repeats": 1}},
    )
    for phase in ("compare", "decide", "report"):
        _enqueue_submit(server, phase)


def _enqueue_submit(server: MockOpenAIServer, phase: str) -> None:
    server.enqueue_tool_call(
        f"submit_{phase}",
        "submit_phase_result",
        {
            "phase": phase,
            "status": "completed",
            "summary": f"completed {phase}",
            "findings": [],
            "blockers": [],
        },
    )
