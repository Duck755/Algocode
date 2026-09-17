"""Evaluation orchestration and reporting."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from algocode.config import AlgocodeConfig, compute_config_hash
from algocode.eval.harness import EvalHarness
from algocode.eval.provider import PhaseScriptedProvider
from algocode.eval.suites import suite
from algocode.eval.types import EvalComparison, EvalRun, EvalTaskResult
from algocode.providers.factory import build_provider, resolve_model_selection
from algocode.providers.fake import DeterministicFakeProvider
from algocode.providers.types import ModelRef
from algocode.tools import build_default_registry


class EvalService:
    """Run suites, aggregate metrics, persist reports, and compare providers."""

    def __init__(self, config: AlgocodeConfig, data_dir: str | Path) -> None:
        self.config = config
        self.data_dir = Path(data_dir)
        self.report_dir = self.data_dir / "evals"

    async def run(
        self,
        suite_name: str,
        *,
        provider: str = "auto",
        provider_key: str | None = None,
        model_key: str | None = None,
        repeat_count: int = 1,
        seed: int = 0,
    ) -> EvalRun:
        tasks = suite(suite_name)
        provider_factory, provider_name, model = self._provider_factory(
            provider,
            provider_key=provider_key,
            model_key=model_key,
        )
        harness = EvalHarness(provider_factory, provider_name, model=model)
        started = time.perf_counter()
        results: list[EvalTaskResult] = []
        for _ in range(repeat_count):
            for task in tasks:
                results.append(await harness.run_task(task))
        duration = time.perf_counter() - started
        run = EvalRun(
            run_id=f"eval_{uuid4().hex}",
            suite=suite_name,
            provider=provider_name,
            model=model.model_id,
            seed=seed,
            repeat_count=repeat_count,
            config_hash=compute_config_hash(self.config),
            tool_catalog_hash=_tool_catalog_hash(),
            environment_hash=hashlib.sha256(str(Path.cwd()).encode()).hexdigest(),
            results=tuple(results),
            aggregate=_aggregate(results),
            duration_seconds=duration,
        )
        self.persist(run)
        return run

    async def compare(
        self,
        suite_name: str,
        *,
        baseline_provider: str,
        candidate_provider: str,
        repeat_count: int = 1,
    ) -> tuple[EvalRun, EvalRun, EvalComparison]:
        baseline = await self.run(
            suite_name,
            provider=baseline_provider,
            repeat_count=repeat_count,
        )
        candidate = await self.run(
            suite_name,
            provider=candidate_provider,
            repeat_count=repeat_count,
        )
        comparison = EvalComparison(
            baseline_run_id=baseline.run_id,
            candidate_run_id=candidate.run_id,
            baseline_provider=baseline.provider,
            candidate_provider=candidate.provider,
            pass_rate_delta=float(candidate.aggregate["pass_rate"])
            - float(baseline.aggregate["pass_rate"]),
            average_turns_delta=float(candidate.aggregate["average_turns"])
            - float(baseline.aggregate["average_turns"]),
            average_tool_calls_delta=float(candidate.aggregate["average_tool_calls"])
            - float(baseline.aggregate["average_tool_calls"]),
            duration_delta_seconds=candidate.duration_seconds - baseline.duration_seconds,
            improved=float(candidate.aggregate["pass_rate"])
            > float(baseline.aggregate["pass_rate"]),
        )
        return baseline, candidate, comparison

    def persist(self, run: EvalRun) -> tuple[Path, Path]:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.report_dir / f"{run.run_id}.json"
        markdown_path = self.report_dir / f"{run.run_id}.md"
        json_path.write_text(
            json.dumps(asdict(run), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        markdown_path.write_text(render_eval_markdown(run), encoding="utf-8")
        return json_path, markdown_path

    def _provider_factory(
        self,
        choice: str,
        *,
        provider_key: str | None,
        model_key: str | None,
    ):
        if choice == "fake":
            return (
                lambda task, candidate_id: DeterministicFakeProvider(),
                "fake",
                ModelRef(provider_id="fake", model_id="deterministic"),
            )
        if choice == "scripted":
            return (
                lambda task, candidate_id: PhaseScriptedProvider(task, candidate_id),
                "scripted",
                ModelRef(provider_id="scripted", model_id="deterministic"),
            )
        if choice == "real":
            selected_provider, selected_model = resolve_model_selection(
                self.config, provider_key, model_key
            )
            provider, model = build_provider(
                self.config,
                provider_key=selected_provider,
                model_key=selected_model,
            )
            return (
                lambda task, candidate_id: provider,
                f"{selected_provider}/{selected_model}",
                model,
            )
        if choice != "auto":
            raise ValueError(f"unknown eval provider: {choice}")
        return (
            lambda task, candidate_id: (
                DeterministicFakeProvider()
                if task.candidate_patch is None
                else PhaseScriptedProvider(task, candidate_id)
            ),
            "auto",
            ModelRef(provider_id="fake", model_id="deterministic"),
        )


def _aggregate(results: list[EvalTaskResult]) -> dict[str, float | int | str | None]:
    if not results:
        return {
            "pass_rate": 0.0,
            "average_turns": 0.0,
            "average_tool_calls": 0.0,
            "task_count": 0,
        }
    return {
        "pass_rate": sum(1 for result in results if result.passed) / len(results),
        "average_turns": sum(result.turns for result in results) / len(results),
        "average_tool_calls": sum(result.tool_calls for result in results) / len(results),
        "average_duration_seconds": sum(result.duration_seconds for result in results)
        / len(results),
        "task_count": len(results),
    }


def _tool_catalog_hash() -> str:
    payload = [
        {"name": definition.name, "schema": definition.input_schema, "effects": definition.effects}
        for definition in build_default_registry().definitions()
    ]
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def render_eval_markdown(run: EvalRun) -> str:
    lines = [
        f"# Algocode Eval {run.run_id}",
        "",
        f"- Suite: `{run.suite}`",
        f"- Provider: `{run.provider}`",
        f"- Repeat count: {run.repeat_count}",
        f"- Pass rate: {run.aggregate['pass_rate']}",
        f"- Average turns: {run.aggregate['average_turns']}",
        f"- Average tool calls: {run.aggregate['average_tool_calls']}",
        "",
        "## Tasks",
        "",
    ]
    for result in run.results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"- [{status}] `{result.task_id}` expected `{result.expected_behavior}`")
        if result.message:
            lines.append(f"  - {result.message}")
    return "\n".join(lines) + "\n"
