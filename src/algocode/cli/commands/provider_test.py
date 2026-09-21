"""Simple real-provider connectivity test."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer

from algocode.bootstrap import build_context
from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.providers.errors import ProviderError
from algocode.providers.factory import build_provider, resolve_model_selection
from algocode.providers.types import Message, ModelRequest


def test_command(
    provider_key: Annotated[
        str | None,
        typer.Option("--provider", help="Configured provider key. Defaults to the selected model."),
    ] = None,
    model_key: Annotated[
        str | None,
        typer.Option("--model", help="Configured model key. Defaults to the selected model."),
    ] = None,
    data_dir: Annotated[
        Path | None,
        typer.Option("--data-dir", help="Override the data directory."),
    ] = None,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Send a minimal chat request to the selected model."""

    context = build_context(project_root=Path.cwd(), data_dir=data_dir)
    selected_provider, selected_model = resolve_model_selection(
        context.config,
        provider_key,
        model_key,
    )
    try:
        provider, model = build_provider(
            context.config,
            provider_key=selected_provider,
            model_key=selected_model,
            redactor=context.secret_redactor,
        )
        model_config = context.config.models[selected_model]
        request = ModelRequest(
            request_id=f"test_{uuid4().hex}",
            model=model,
            system=(
                f"The current model is {selected_provider}/{model_config.model}. "
                "Answer the user briefly in English."
            ),
            messages=(Message(role="user", content="Hello. What model are you?"),),
            timeout_seconds=60,
        )
        response = asyncio.run(provider.complete(request))
    except ProviderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    text = response.text.strip() or "[empty response]"
    emit_result(
        "test",
        data={
            "provider": selected_provider,
            "model": model_config.model,
            "model_key": selected_model,
            "response": text,
            "reasoning": response.reasoning,
            "usage": asdict(response.usage),
            "finish_reason": response.finish_reason,
        },
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        human_lines=(
            f"Provider: {selected_provider}",
            f"Model: {model_config.model}",
            f"Response: {text}",
        ),
    )
