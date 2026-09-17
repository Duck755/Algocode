"""Run agent evaluation suites."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from algocode.bootstrap import build_context
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.eval.service import EvalService
from algocode.providers.errors import ProviderError

eval_app = typer.Typer(
    name="eval",
    help="Run agent evaluation suites.",
    no_args_is_help=True,
)

DataDirOption = Annotated[
    Path | None,
    typer.Option("--data-dir", help="Override the data directory."),
]


@eval_app.command("run")
def eval_run(
    suite_name: Annotated[str, typer.Argument(help="smoke, core, adversarial, or recovery.")],
    provider: Annotated[
        str,
        typer.Option("--provider", help="auto, fake, scripted, or real."),
    ] = "auto",
    repeat_count: Annotated[
        int,
        typer.Option("--repeat", min=1, help="Repeat each eval task."),
    ] = 1,
    ab_baseline: Annotated[
        str | None,
        typer.Option("--ab-baseline", help="A/B baseline provider."),
    ] = None,
    ab_candidate: Annotated[
        str | None,
        typer.Option("--ab-candidate", help="A/B candidate provider."),
    ] = None,
    provider_key: Annotated[
        str | None,
        typer.Option("--provider-key", help="Configured provider key for real provider."),
    ] = None,
    model_key: Annotated[
        str | None,
        typer.Option("--model-key", help="Configured model key for real provider."),
    ] = None,
    data_dir: DataDirOption = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Run smoke, core, adversarial, recovery, or A/B comparison."""

    context = build_context(data_dir=data_dir)
    service = EvalService(context.config, context.data_dir)
    try:
        if ab_baseline is not None or ab_candidate is not None:
            if not ab_baseline or not ab_candidate:
                typer.echo("both --ab-baseline and --ab-candidate are required", err=True)
                raise typer.Exit(code=2)
            baseline, candidate, comparison = asyncio.run(
                service.compare(
                    suite_name,
                    baseline_provider=ab_baseline,
                    candidate_provider=ab_candidate,
                    repeat_count=repeat_count,
                )
            )
            data = {
                "baseline": asdict(baseline),
                "candidate": asdict(candidate),
                "comparison": asdict(comparison),
            }
            pass_rate = float(candidate.aggregate["pass_rate"])
        else:
            run = asyncio.run(
                service.run(
                    suite_name,
                    provider=provider,
                    provider_key=provider_key,
                    model_key=model_key,
                    repeat_count=repeat_count,
                )
            )
            data = asdict(run)
            pass_rate = float(run.aggregate["pass_rate"])
    except (ProviderError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    emit_result(
        "eval.run",
        data=data,
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        human_lines=(
            f"Suite: {suite_name}",
            f"Provider: {provider}",
            f"Pass rate: {pass_rate:.3f}",
        ),
    )
    if pass_rate < 1.0:
        raise typer.Exit(code=1)
