"""Initialize and register a local project."""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import typer

from algocode.application.services.project_bootstrap_service import (
    BootstrapEvent,
    BootstrapResult,
    ProjectBootstrapService,
    bootstrap_payload,
)
from algocode.bootstrap import build_context
from algocode.cli.output import (
    JsonOption,
    NoColorOption,
    ProgressOption,
    QuietOption,
    VerboseOption,
    YesOption,
    emit_result,
    is_interactive,
)
from algocode.cli.progress import StageReporter, format_duration, render_evidence
from algocode.domain.errors import ConfigError
from algocode.domain.model import Project
from algocode.providers.errors import ProviderError
from algocode.providers.factory import build_provider
from algocode.workspace.git import GitError

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]

INIT_STAGES = ("扫描", "契约", "规格", "基线", "校验", "基准", "就绪")
_STAGE_LABELS = {
    "scan": "扫描",
    "contract": "契约",
    "specs": "规格",
    "baseline": "基线",
    "correctness": "校验",
    "benchmark": "基准",
    "persist": "就绪",
}


class _RailAdapter:
    """Translate bootstrap events into stage-rail calls."""

    def __init__(self, reporter: StageReporter) -> None:
        self._reporter = reporter
        self._active: str | None = None

    def __call__(self, event: BootstrapEvent) -> None:
        label = _STAGE_LABELS.get(event.stage)
        if label is None:
            return
        if event.kind == "start":
            self._reporter.begin(label, event.detail)
            self._active = label
        elif event.kind == "detail":
            if label == self._active:
                self._reporter.update(event.detail)
        elif event.kind == "finish":
            self._reporter.complete(label, event.detail)
            if label == self._active:
                self._active = None
        elif event.kind == "fail":
            self._reporter.fail(event.detail or f"{label} 失败")
            self._active = None
        elif event.kind == "note":
            self._reporter.note(event.detail)


def _reporter(
    progress: bool | None,
    *,
    quiet: bool,
    json_output: bool,
    no_color: bool,
) -> StageReporter:
    enabled = (not quiet and not json_output) if progress is None else progress
    return StageReporter(
        INIT_STAGES,
        title="algocode · init",
        enabled=enabled,
        color=not no_color,
    )


def _preflight_lines(context, root: Path, language: str) -> list[str]:
    detected = asyncio.run(context.language_registry.detect(root))
    resolved = context.language_registry.resolve_language(language, detected)
    try:
        build_provider(context.config)
        model_note = f"{context.config.defaults.provider}/{context.config.defaults.model}"
    except ProviderError:
        model_note = "未配置（将使用确定性回退契约）"
    git_note = "已存在" if (root / ".git").exists() else "将执行 git init"
    return [
        f"项目目录：{root}",
        f"语言：{resolved.value}",
        f"Git：{git_note}",
        f"模型：{model_note}",
        "将生成：.algocode/ 下的配置、契约、判题、基准与任务状态",
        "提示：使用 --no-bootstrap 只做注册，不生成任何产物",
    ]


def _confirm(lines: list[str]) -> bool:
    for line in lines:
        typer.echo(f"  {line}")
    typer.echo("")
    try:
        answer = typer.prompt("是否继续？[Y/n]", default="y", show_default=False)
    except (typer.Abort, EOFError):
        return False
    return answer.strip().lower() in {"", "y", "yes"}


def _short(value: object) -> str:
    text = str(value)
    return text[:8] if len(text) > 8 else text


def _evidence_rows(result: BootstrapResult, seed: int) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    contract_name = Path(result.contract_path).name if result.contract_path else "contract.json"
    if result.contract_confidence is not None:
        contract_note = f"confidence {result.contract_confidence:.2f}"
    else:
        contract_note = result.contract_source or "-"
    if result.contract_source == "deterministic-fallback":
        contract_note += " · fallback"
    rows.append(("契约", f".algocode/{contract_name}", contract_note))
    rows.append(
        (
            "基线",
            f"baseline:{_short(result.baseline.id)}",
            f"git {str(result.project.git_revision)[:7]} · seed {seed}",
        )
    )
    if result.correctness is not None:
        total = len(result.correctness.cases)
        rows.append(
            (
                "校验",
                f"correctness:{_short(result.correctness_run_id or '-')}",
                f"{result.correctness.passed_cases}/{total} passed",
            )
        )
    else:
        rows.append(("校验", "skipped", "未生成判题规格"))
    if result.benchmark_run is not None and result.benchmark_result is not None:
        summary = result.benchmark_result.summary
        samples = summary.count if summary is not None else len(result.benchmark_result.samples)
        rows.append(
            (
                "基准",
                f"benchmark:{_short(result.benchmark_run.id)}",
                f"valid · {samples} samples",
            )
        )
    else:
        rows.append(("基准", "skipped", "未生成基准规格"))
    rows.append(("任务", f"task:{_short(result.task.id)}", "ready"))
    return rows


def _failure_hint(exc: Exception) -> str:
    message = str(exc)
    if "entrypoint" in message:
        return "在项目根目录添加 test.py/main.py 或 test.cpp/main.cpp，或使用 --no-bootstrap"
    if "contract test failed" in message:
        return "查看 .algocode/oracle/ 下的契约测试，或使用 --no-bootstrap 跳过"
    if "correctness specification failed" in message:
        return "检查 .algocode/oracle/correctness.yaml 与项目实际输出"
    if "benchmark specification failed" in message:
        return "检查 .algocode/benchmarks/benchmark.yaml"
    return ""


def _offer_next_steps(result: BootstrapResult, data_dir: Path | None) -> None:
    task_id = str(result.task.id)
    options = (
        ("开始优化", f"algocode optimize {task_id}"),
        ("查看基线报告", f"algocode report {task_id} --markdown"),
        ("配置模型", "algocode api"),
    )
    typer.echo("")
    typer.echo("下一步：")
    for index, (label, command) in enumerate(options, start=1):
        typer.echo(f"  {index}) {label}  ({command})")
    try:
        answer = typer.prompt("选择 [1/2/3，回车退出]", default="", show_default=False)
    except (typer.Abort, EOFError):
        return
    choice = answer.strip()
    if choice not in {"1", "2", "3"}:
        return
    try:
        if choice == "1":
            from algocode.cli.commands.optimize import optimize_command

            optimize_command(task_id=task_id, data_dir=data_dir)
        elif choice == "2":
            from algocode.cli.commands.report import report_command

            report_command(task_id=task_id, markdown=True, data_dir=data_dir)
        else:
            from algocode.cli.commands.api import api_command

            api_command()
    except typer.Exit:
        return


def _project_payload(project: Project) -> dict[str, Any]:
    payload = asdict(project)
    payload["language"] = project.language.value
    payload["created_at"] = project.created_at.isoformat()
    payload["updated_at"] = project.updated_at.isoformat()
    return payload


def init_command(
    path: Annotated[
        Path,
        typer.Option("--path", help="Project directory inside a Git repository."),
    ] = Path("."),
    language: Annotated[
        str,
        typer.Option("--language", help="auto, cpp, or python."),
    ] = "auto",
    objective: Annotated[
        str | None,
        typer.Option("--objective", help="Optimization objective for the initial task."),
    ] = None,
    bootstrap: Annotated[
        bool,
        typer.Option(
            "--bootstrap/--no-bootstrap",
            help="Create Git/config prerequisites and run the first baseline.",
        ),
    ] = True,
    write_config: Annotated[
        bool,
        typer.Option(
            "--write-config/--no-write-config",
            help="Create .algocode/config.yaml.",
        ),
    ] = True,
    progress: ProgressOption = None,
    yes: YesOption = False,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Detect and register the project without modifying its source files."""

    interactive = is_interactive()
    reporter = _reporter(
        progress,
        quiet=quiet,
        json_output=json_output,
        no_color=no_color,
    )
    try:
        context = build_context(project_root=path, data_dir=data_dir)
        if bootstrap:
            root = Path(path).expanduser().resolve()
            if interactive and not yes and not json_output and not quiet:
                if not _confirm(_preflight_lines(context, root, language)):
                    typer.echo("已取消。")
                    raise typer.Exit(code=0)
            started_at = time.perf_counter()
            result = asyncio.run(
                ProjectBootstrapService(context).run(
                    path,
                    language=language,
                    objective=objective,
                    on_event=_RailAdapter(reporter),
                )
            )
            elapsed = time.perf_counter() - started_at
            reporter.close()
            payload = bootstrap_payload(result)
            rows = _evidence_rows(result, seed=context.config.runtime.run_seed)
            human_lines = [
                f"init 完成 · 用时 {format_duration(elapsed)}",
                *render_evidence(rows),
            ]
            emit_result(
                "init",
                data=payload,
                json_output=json_output,
                no_color=no_color,
                quiet=quiet,
                verbose=verbose,
                task_id=str(result.task.id),
                human_lines=human_lines,
            )
            if interactive and not json_output and not quiet:
                _offer_next_steps(result, data_dir)
            return

        project = asyncio.run(
            context.project_service.register(
                path,
                language=language,
                write_config=write_config,
            )
        )
    except (ConfigError, GitError, ValueError, RuntimeError) as exc:
        reporter.fail(str(exc), hint=_failure_hint(exc))
        reporter.close()
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    finally:
        reporter.close()

    payload = _project_payload(project)
    emit_result(
        "init",
        data=payload,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        human_lines=(
            f"Project: {project.id}",
            f"Root: {project.root_path}",
            f"Language: {project.language.value}",
            f"Revision: {project.git_revision}",
            f"Data directory: {context.data_dir}",
        ),
    )