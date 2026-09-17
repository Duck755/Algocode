"""Select a configured model as the project default."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.config import load_config
from algocode.config.global_file import update_global_config
from algocode.storage.paths import default_data_dir


def model_command(
    provider_key: Annotated[
        str | None,
        typer.Option("--provider", help="Only select models from this provider."),
    ] = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Interactively select the default model for the current project."""

    try:
        config = load_config(project_root=Path.cwd(), data_dir=default_data_dir())
    except Exception as exc:  # noqa: BLE001
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    selected_provider = provider_key or config.defaults.provider
    provider = config.providers.get(selected_provider)
    if provider is None:
        typer.echo(f"provider {selected_provider!r} is not configured; run algocode api", err=True)
        raise typer.Exit(code=2)

    models = [
        (key, model)
        for key, model in config.models.items()
        if model.provider == selected_provider
    ]
    if not models:
        typer.echo(
            f"provider {selected_provider!r} has no configured models; run algocode api",
            err=True,
        )
        raise typer.Exit(code=2)

    typer.echo(f"当前 Provider: {selected_provider}")
    typer.echo("请选择模型：")
    for index, (key, model) in enumerate(models, start=1):
        default_marker = " (当前默认)" if key == config.defaults.model else ""
        typer.echo(f"  {index}. {model.model} [{key}]{default_marker}")
    typer.echo("  0. 输入其他模型 ID")

    while True:
        selected = typer.prompt("请输入数字", type=int)
        if 0 <= selected <= len(models):
            break
        typer.echo(f"请输入 0 到 {len(models)} 之间的数字。", err=True)

    if selected == 0:
        model_id = typer.prompt("模型 ID").strip()
        if not model_id:
            typer.echo("模型 ID 不能为空", err=True)
            raise typer.Exit(code=2)
        model_key = f"{selected_provider}/{model_id}"
        context_window = typer.prompt("上下文窗口", default=128_000, type=int)
        patch = {
            "models": {
                model_key: {
                    "provider": selected_provider,
                    "model": model_id,
                    "context_window": context_window,
                }
            },
            "defaults": {
                "provider": selected_provider,
                "model": model_key,
            },
        }
    else:
        model_key, _ = models[selected - 1]
        patch = {
            "defaults": {
                "provider": selected_provider,
                "model": model_key,
            }
        }

    try:
        config_path = update_global_config(patch)
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    emit_result(
        "model",
        data={
            "provider": selected_provider,
            "model": model_key,
            "config_path": str(config_path),
        },
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        human_lines=(
            f"默认模型已切换为: {model_key}",
            f"Config: {config_path}",
        ),
    )
