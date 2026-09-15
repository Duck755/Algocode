from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.benchmark.spec import BenchmarkSpec
from algocode.bootstrap import build_context
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from algocode.domain.errors import DecisionError
from algocode.domain.model import CandidateStatus
from tests.support.git import init_git_repository


class ReportAcceptApplyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {"main.py": "import time\ntime.sleep(0.02)\nprint('hello')\n"},
        )
        (self.project_root / ".algocode.yaml").write_text(
            "acceptancePolicy:\n  minMedianImprovementPercent: -1000\n",
            encoding="utf-8",
        )
        self.context = build_context(
            project_root=self.project_root,
            data_dir=self.root / "data",
        )
        self.project = await self.context.project_service.register(
            self.project_root,
            write_config=True,
        )
        self.task = await self.context.task_service.create_task(
            "Apply accepted optimization",
            project_id=self.project.id,
        )
        self.baseline = await self.context.baseline_service.capture(self.task.id)
        await self.context.correctness_service.run_baseline(
            self.task.id,
            CorrectnessSpec(
                mode="cases",
                comparison="line-trim",
                cases=(CorrectnessCase(id="baseline", expected_output="hello"),),
            ),
        )

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def _accepted_candidate(self):
        candidate = await self.context.candidate_service.create(self.task.id)
        (Path(candidate.workspace_ref) / "main.py").write_text(
            "print('hi')\n",
            encoding="utf-8",
        )
        candidate = await self.context.candidate_service.freeze(candidate.id)
        correctness_spec = CorrectnessSpec(
            mode="cases",
            comparison="line-trim",
            cases=(CorrectnessCase(id="candidate", expected_output="hi"),),
        )
        correctness_run, result = await self.context.correctness_service.run_target(
            self.task.id,
            correctness_spec,
            target_kind="candidate",
            target_id=str(candidate.id),
            workspace_ref=candidate.workspace_ref,
        )
        self.assertTrue(result.passed)
        candidate = await self.context.candidate_service.get(candidate.id)
        self.assertEqual(candidate.status, CandidateStatus.VERIFIED)
        await self.context.benchmark_service.run_candidate(
            self.task.id,
            str(candidate.id),
            candidate.workspace_ref,
            correctness_run.id,
            BenchmarkSpec(warmup=0, repeats=1),
        )
        decision = await self.context.decision_service.accept(
            self.task.id,
            candidate.id,
            reason="verified in test",
        )
        self.assertEqual(candidate.status, CandidateStatus.VERIFIED)
        return candidate, decision

    async def test_report_accept_apply_and_rollback(self) -> None:
        candidate, decision = await self._accepted_candidate()
        selected = await self.context.candidate_service.get(candidate.id)
        self.assertEqual(selected.status, CandidateStatus.SELECTED)

        payload, markdown, refs = await self.context.report_service.build(self.task.id)
        self.assertEqual(payload["selectedCandidateId"], str(candidate.id))
        self.assertIn("# Algocode Report", markdown)
        self.assertTrue(refs["json_ref"]["uri"].startswith("artifact://"))
        decision_artifact = await self.context.artifact_store.read_bytes(
            next(ref for ref in decision.evidence_refs if ref.uri.startswith("artifact://"))
        )
        self.assertIsInstance(decision_artifact, bytes)

        applied = await self.context.apply_service.apply(self.task.id, candidate.id)
        self.assertTrue(applied["applied"])
        self.assertIn("print('hi')", (self.project_root / "main.py").read_text("utf-8"))
        applied_candidate = await self.context.candidate_service.get(candidate.id)
        self.assertEqual(applied_candidate.status, CandidateStatus.APPLIED)

        rolled_back = await self.context.apply_service.rollback(self.task.id, candidate.id)
        self.assertTrue(rolled_back["rolled_back"])
        self.assertIn("print('hello')", (self.project_root / "main.py").read_text("utf-8"))
        rolled_candidate = await self.context.candidate_service.get(candidate.id)
        self.assertEqual(rolled_candidate.status, CandidateStatus.ROLLED_BACK)

    async def test_apply_rejects_stale_candidate(self) -> None:
        candidate, _ = await self._accepted_candidate()
        (self.project_root / "main.py").write_text("print('user change')\n", encoding="utf-8")

        with self.assertRaisesRegex(DecisionError, "stale"):
            await self.context.apply_service.apply(self.task.id, candidate.id)

        stale = await self.context.candidate_service.get(candidate.id)
        self.assertEqual(stale.status, CandidateStatus.STALE)


if __name__ == "__main__":
    unittest.main()
