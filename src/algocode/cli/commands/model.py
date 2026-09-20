"""Select a configured model as the project default."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.config import load_config
from algocode.config.global_file import update_global_config
from algocode.providers.factory import resolve_api_key
from algocode.providers.model_catalog import list_models
from algocode.storage.paths import default_data_dir


@dataclass(frozen=True, slots=True)
class ModelChoice:
    model_key: str
    model_id: str
    configured: bool


def _merge_model_choices(
    models: Mapping[str, object],
    provider_key: str,
    upstream_models: Sequence[str],
    default_model_key: str,
) -> list[ModelChoice]:
    configured_by_id: dict[str, str] = {}
    configured_entries: list[tuple[str, str]] = []
    for model_key, model in models.items():
        model_provider = getattr(model, "provider", None)
        model_id = getattr(model, "model", None)
        if model_provider != provider_key or not isinstance(model_id, str):
            continue
        configured_by_id.setdefault(model_id, model_key)
        configured_entries.append((model_key, model_id))

    ordered_ids = list(
        dict.fromkeys(
            [*upstream_models, *(model_id for _, model_id in configured_entries)]
        )
    )
    default_entry = models.get(default_model_key)
    if getattr(default_entry, "provider", None) == provider_key:
        default_id = getattr(default_entry, "model", None)
        if isinstance(default_id, str) and default_id not in ordered_ids:
            ordered_ids.append(default_id)

    return [
        ModelChoice(
            model_key=configured_by_id.get(model_id, f"{provider_key}/{model_id}"),
            model_id=model_id,
            configured=model_id in configured_by_id,
        )
        for model_id in ordered_ids
    ]


def _fetch_upstream_models(provider, provider_key: str) -> tuple[list[str], str]:
    if not provider.base_url:
        return [], "provider has no baseUrl"
    try:
        api_key = resolve_api_key(provider, provider_key)
    except (OSError, RuntimeError) as exc:
        return [], str(exc)
    models = list_models(provider.type, provider.base_url, api_key)
    if not models:
        return [], "provider returned no model list"
    return models, ""


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

    upstream_models, upstream_note = _fetch_upstream_models(provider, selected_provider)
    if upstream_note:
        typer.echo(f"未能从上游获取模型列表：{upstream_note}", err=True)
    choices = _merge_model_choices(
        config.models,
        selected_provider,
        upstream_models,
        config.defaults.model,
    )

    typer.echo(f"当前 Provider: {selected_provider}")
    typer.echo("请选择模型：")
    for index, choice in enumerate(choices, start=1):
        default_marker = " (当前默认)" if choice.model_key == config.defaults.model else ""
        source_marker = "" if choice.configured else " (上游)"
        typer.echo(
            f"  {index}. {choice.model_id} [{choice.model_key}]"
            f"{source_marker}{default_marker}"
        )
    typer.echo("  0. 输入其他模型 ID")

    while True:
        selected = typer.prompt("请输入数字", type=int)
        if 0 <= selected <= len(choices):
            break
        typer.echo(f"请输入 0 到 {len(choices)} 之间的数字。", err=True)

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
        choice = choices[selected - 1]
        model_key = choice.model_key
        patch = {
            "defaults": {
                "provider": selected_provider,
                "model": model_key,
            }
        }
        if not choice.configured:
            patch["models"] = {
                model_key: {
                    "provider": selected_provider,
                    "model": choice.model_id,
                    "context_window": 128_000,
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
