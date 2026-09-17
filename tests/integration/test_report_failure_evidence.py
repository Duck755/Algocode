from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.benchmark.spec import BenchmarkSpec
from algocode.bootstrap import build_context
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from algocode.domain.errors import BenchmarkError
from algocode.domain.model import BenchmarkStatus
from tests.support.git import init_git_repository


class ReportFailureEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_report_keeps_failed_benchmark_without_result_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_root = init_git_repository(
                root / "project",
                {"main.py": "print('hello')\n"},
            )
            context = build_context(project_root=project_root, data_dir=root / "data")
            project = await context.project_service.register(project_root, write_config=True)
            task = await context.task_service.create_task(
                "Report failed benchmark evidence",
                project_id=project.id,
            )
            await context.baseline_service.capture(task.id)
            correctness_spec = CorrectnessSpec(
                mode="cases",
                comparison="line-trim",
                cases=(CorrectnessCase(id="output", expected_output="hello"),),
            )
            await context.correctness_service.run_baseline(task.id, correctness_spec)
            candidate = await context.candidate_service.create(task.id)
            correctness_run, correctness = await context.correctness_service.run_target(
                task.id,
                correctness_spec,
                target_kind="candidate",
                target_id=str(candidate.id),
                workspace_ref=candidate.workspace_ref,
            )
            self.assertTrue(correctness.passed)

            with self.assertRaises(BenchmarkError):
                await context.benchmark_service.run_candidate(
                    task.id,
                    str(candidate.id),
                    candidate.workspace_ref,
                    correctness_run.id,
                    BenchmarkSpec(
                        warmup=0,
                        repeats=1,
                        run_command=("definitely-not-a-real-command",),
                    ),
                )

            runs = await context.benchmark_service.list_for_task(task.id)
            failed = next(
                run
                for run in runs
                if run.target_kind == "candidate" and run.status is BenchmarkStatus.FAILED
            )
            self.assertIsNone(failed.result_ref)

            report, markdown, _ = await context.report_service.build(task.id)

            self.assertIn("# Algocode Report", markdown)
            self.assertIn(
                failed.id,
                {item["runId"] for item in report["benchmarkEvidence"]},
            )


if __name__ == "__main__":
    unittest.main()
