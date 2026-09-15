from __future__ import annotations

import unittest
from types import SimpleNamespace

from algocode.domain.model import (
    BenchmarkStatus,
    Candidate,
    CandidateStatus,
    CorrectnessStatus,
    GitRevision,
    Task,
    TaskPhase,
    new_candidate_id,
    new_project_id,
    new_task_id,
)
from algocode.runtime.gates import PhaseGate


class PhaseGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = PhaseGate()
        self.task = Task(id=new_task_id(), project_id=new_project_id(), objective="test")
        self.candidate = Candidate(
            id=new_candidate_id(),
            task_id=self.task.id,
            base_revision=GitRevision("abc"),
            base_snapshot_hash="snapshot",
            workspace_ref="workspace",
            status=CandidateStatus.FROZEN,
        )

    def test_plan_requires_baseline(self) -> None:
        decision = self.gate.evaluate(
            task=self.task,
            phase=TaskPhase.PLAN,
            has_baseline=False,
            candidates=[],
            correctness_runs=[],
            benchmark_runs=[],
        )
        self.assertFalse(decision.allowed)

    def test_implement_requires_candidate(self) -> None:
        decision = self.gate.evaluate(
            task=self.task,
            phase=TaskPhase.IMPLEMENT,
            has_baseline=True,
            candidates=[],
            correctness_runs=[],
            benchmark_runs=[],
        )
        self.assertFalse(decision.allowed)

    def test_benchmark_requires_correctness(self) -> None:
        decision = self.gate.evaluate(
            task=self.task,
            phase=TaskPhase.BENCHMARK,
            has_baseline=True,
            candidates=[self.candidate],
            correctness_runs=[],
            benchmark_runs=[],
        )
        self.assertFalse(decision.allowed)

    def test_benchmark_is_allowed_after_correctness(self) -> None:
        correctness = SimpleNamespace(
            target_kind="candidate",
            target_id=str(self.candidate.id),
            status=CorrectnessStatus.PASSED,
        )
        decision = self.gate.evaluate(
            task=self.task,
            phase=TaskPhase.BENCHMARK,
            has_baseline=True,
            candidates=[self.candidate],
            correctness_runs=[correctness],
            benchmark_runs=[],
        )
        self.assertTrue(decision.allowed)

    def test_benchmark_rejects_other_candidate_correctness(self) -> None:
        correctness = SimpleNamespace(
            target_kind="candidate",
            target_id="candidate_other",
            status=CorrectnessStatus.PASSED,
        )
        decision = self.gate.evaluate(
            task=self.task,
            phase=TaskPhase.BENCHMARK,
            has_baseline=True,
            candidates=[self.candidate],
            active_candidate_id=str(self.candidate.id),
            correctness_runs=[correctness],
            benchmark_runs=[],
        )

        self.assertFalse(decision.allowed)

    def test_compare_requires_valid_active_candidate_benchmark(self) -> None:
        correctness = SimpleNamespace(
            target_kind="candidate",
            target_id=str(self.candidate.id),
            status=CorrectnessStatus.PASSED,
        )
        invalid_benchmark = SimpleNamespace(
            target_kind="candidate",
            target_id=str(self.candidate.id),
            status=BenchmarkStatus.COMPLETED,
            comparison_ref=None,
        )
        valid_benchmark = SimpleNamespace(
            target_kind="candidate",
            target_id=str(self.candidate.id),
            status=BenchmarkStatus.COMPLETED,
            comparison_ref=object(),
        )

        denied = self.gate.evaluate(
            task=self.task,
            phase=TaskPhase.COMPARE,
            has_baseline=True,
            candidates=[self.candidate],
            active_candidate_id=str(self.candidate.id),
            correctness_runs=[correctness],
            benchmark_runs=[invalid_benchmark],
        )
        allowed = self.gate.evaluate(
            task=self.task,
            phase=TaskPhase.COMPARE,
            has_baseline=True,
            candidates=[self.candidate],
            active_candidate_id=str(self.candidate.id),
            correctness_runs=[correctness],
            benchmark_runs=[valid_benchmark],
        )

        self.assertFalse(denied.allowed)
        self.assertTrue(allowed.allowed)


if __name__ == "__main__":
    unittest.main()
