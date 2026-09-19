from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from algocode.cli.commands.optimize import (
    _candidate_correctness_state,
    _evidence_rows,
    _trim,
)
from algocode.cli.main import app
from tests.support.git import init_git_repository


class CliOptimizeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {"main.py": "print('hello')\n"},
        )
        self.data_dir = self.root / "data"
        self.runner = CliRunner()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_fake_provider_optimize(self) -> None:
        self.runner.invoke(
            app,
            [
                "init",
                "--path",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--no-bootstrap",
            ],
        )
        task_result = self.runner.invoke(
            app,
            [
                "task",
                "create",
                "--objective",
                "Optimize",
                "--project-root",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        task_id = json.loads(task_result.stdout)["data"]["id"]

        result = self.runner.invoke(
            app,
            [
                "optimize",
                task_id,
                "--fake-provider",
                "--stop-after",
                "baseline",
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.stdout)["data"]
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["completed_phases"][-1], "baseline")
        self.assertGreater(payload["tool_calls"], 0)

    def test_optimize_without_task_id_reads_current_task_file(self) -> None:
        self.runner.invoke(
            app,
            [
                "init",
                "--path",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--no-bootstrap",
            ],
        )
        task_result = self.runner.invoke(
            app,
            [
                "task",
                "create",
                "--objective",
                "Optimize",
                "--project-root",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        task_id = json.loads(task_result.stdout)["data"]["id"]
        state_dir = self.project_root / ".algocode"
        state_dir.mkdir(exist_ok=True)
        (state_dir / "current-task.json").write_text(
            json.dumps({"taskId": task_id, "dataDir": str(self.data_dir)}),
            encoding="utf-8",
        )

        previous = Path.cwd()
        try:
            os.chdir(self.project_root)
            result = self.runner.invoke(
                app,
                [
                    "optimize",
                    "--fake-provider",
                    "--stop-after",
                    "baseline",
                    "--json",
                ],
            )
        finally:
            os.chdir(previous)

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.stdout)["data"]
        self.assertEqual(payload["status"], "completed")

    def test_optimize_writes_complete_current_task_state(self) -> None:
        self.runner.invoke(
            app,
            [
                "init",
                "--path",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--no-bootstrap",
            ],
        )
        task_result = self.runner.invoke(
            app,
            [
                "task",
                "create",
                "--objective",
                "Optimize",
                "--project-root",
                str(self.project_root),
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )
        task_id = json.loads(task_result.stdout)["data"]["id"]
        stale_dir = self.root / ".algocode"
        stale_dir.mkdir(parents=True, exist_ok=True)
        (stale_dir / "current-task.json").write_text(
            json.dumps({"taskId": "task_stale", "baselineId": "base_stale"}),
            encoding="utf-8",
        )

        result = self.runner.invoke(
            app,
            [
                "optimize",
                task_id,
                "--fake-provider",
                "--stop-after",
                "baseline",
                "--data-dir",
                str(self.data_dir),
                "--json",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        state = json.loads(
            (self.project_root / ".algocode" / "current-task.json").read_text(encoding="utf-8")
        )
        self.assertEqual(state["taskId"], task_id)
        self.assertEqual(state["dataDir"], str(self.data_dir.resolve()))
        self.assertEqual(state["status"], "completed")
        self.assertNotIn("base_stale", json.dumps(state))

    def test_evidence_rows_describe_the_whole_chain(self) -> None:
        result = SimpleNamespace(
            task_id="task_9dc0f7a1b2c3",
            status="completed",
            completed_phases=("analyze", "baseline", "plan"),
            turns=14,
            tool_calls=16,
        )

        rows = _evidence_rows(
            result=result,
            candidate=SimpleNamespace(id="cand_5db12345", status="selected"),
            correctness_state={"resultId": "corr_3641234", "status": "passed"},
            benchmark=SimpleNamespace(id="bench_23123456"),
            comparison={
                "valid": True,
                "improvement_percent": 3.95,
                "baseline_median": 3.222,
                "candidate_median": 3.095,
                "p_value": 0.006,
            },
            decision=SimpleNamespace(outcome="accepted", reason="evidence passed"),
            elapsed=244.0,
        )

        self.assertEqual(
            rows,
            [
                ("任务", "task:task_9dc", "completed"),
                ("耗时", "4m04s", "14 轮推理 · 16 次工具调用"),
                ("阶段", "3 个", "分析 → 基线 → 方案"),
                ("候选", "candidate:cand_5db", "selected"),
                ("正确性", "run:corr_364", "passed"),
                ("基准", "benchmark:bench_23", "valid=True"),
                ("提升", "+3.95%", "3.222 → 3.095 · p=0.006"),
                ("决策", "accepted", "evidence passed"),
            ],
        )

    def test_evidence_rows_describe_an_empty_run(self) -> None:
        result = SimpleNamespace(
            task_id="task_1",
            status="running",
            completed_phases=(),
            turns=0,
            tool_calls=0,
        )

        rows = _evidence_rows(
            result=result,
            candidate=None,
            correctness_state=None,
            benchmark=None,
            comparison=None,
            decision=None,
            elapsed=0.24,
        )

        self.assertEqual(
            rows,
            [
                ("任务", "task:task_1", "running"),
                ("耗时", "240ms", "0 轮推理 · 0 次工具调用"),
                ("阶段", "0 个", "-"),
                ("候选", "未创建", "本次运行未产生候选"),
                ("正确性", "未运行", "缺少候选正确性结果"),
                ("基准", "未运行", "缺少候选基准结果"),
            ],
        )

    def test_trim_shortens_only_long_text(self) -> None:
        self.assertEqual(_trim("short"), "short")
        self.assertEqual(_trim("x" * 120), "x" * 95 + "…")

    def test_candidate_correctness_state_uses_matching_candidate_run(self) -> None:
        runs = [
            SimpleNamespace(
                id="corr_candidate",
                target_kind="candidate",
                target_id="cand_1",
                status=SimpleNamespace(value="failed"),
            ),
            SimpleNamespace(
                id="corr_baseline",
                target_kind="baseline",
                target_id="base_1",
                status=SimpleNamespace(value="passed"),
            ),
        ]

        state = _candidate_correctness_state("cand_1", runs)

        self.assertEqual(
            state,
            {
                "specPath": ".algocode/oracle/correctness.yaml",
                "resultId": "corr_candidate",
                "status": "failed",
            },
        )


if __name__ == "__main__":
    unittest.main()
