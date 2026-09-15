"""Run the repeatable P0 acceptance gate."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from algocode.acceptance import AcceptanceService
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result

gate_app = typer.Typer(
    name="gate",
    help="Run P0 acceptance and release gates.",
    no_args_is_help=True,
)


@gate_app.command("run")
def gate_run(
    root: Annotated[
        Path,
        typer.Option("--root", help="Repository root to validate."),
    ] = Path("."),
    report_dir: Annotated[
        Path | None,
        typer.Option("--report-dir", help="Acceptance report output directory."),
    ] = None,
    skip_tests: Annotated[
        bool,
        typer.Option("--skip-tests", help="Collect evidence without rerunning test suites."),
    ] = False,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Run all release gates and persist the acceptance report."""

    report = AcceptanceService(root, report_dir=report_dir).run(run_tests=not skip_tests)
    payload = report.payload()
    failed = sum(1 for check in report.checks if not check.passed)
    emit_result(
        "gate.run",
        data=payload,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        status=report.status.lower(),
        message=f"{failed} failed checks",
        human_lines=(
            f"Status: {report.status}",
            f"Requirements: {report.requirements_mapped}/{report.requirements_total}",
            f"Checks: {len(report.checks) - failed}/{len(report.checks)} passed",
            f"Report: {AcceptanceService(root, report_dir=report_dir).report_dir / 'report.json'}",
        ),
    )
    if report.status != "PASS":
        raise typer.Exit(code=1)
