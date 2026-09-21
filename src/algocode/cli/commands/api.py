"""Interactive provider and API-key setup."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import typer

try:
    import questionary

    from algocode.cli.tui import select as green_check_select
except ImportError:  # pragma: no cover - optional interactive TUI
    questionary = None
    green_check_select = None

from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.config import load_config
from algocode.config.global_file import read_global_config, update_global_config
from algocode.providers.errors import ProviderError
from algocode.providers.factory import build_provider
from algocode.providers.model_catalog import list_models
from algocode.providers.types import Message, ModelRequest
from algocode.security import CredentialStore


@dataclass(frozen=True, slots=True)
class ProviderPreset:
    key: str
    label: str
    provider_type: str
    base_url: str
    default_model: str
    context_window: int
    api_key_required: bool = True
    api_key_env: str | None = None


PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        key="openai",
        label="OpenAI",
        provider_type="openai-compatible",
        base_url="https://api.openai.com/v1",
        default_model="gpt-5.6",
        context_window=128_000,
        api_key_env="OPENAI_API_KEY",
    ),
    ProviderPreset(
        key="deepseek",
        label="DeepSeek",
        provider_type="openai-compatible",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-flash",
        context_window=128_000,
        api_key_env="DEEPSEEK_API_KEY",
    ),
    ProviderPreset(
        key="openrouter",
        label="OpenRouter",
        provider_type="openai-compatible",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-5.6",
        context_window=128_000,
        api_key_env="OPENROUTER_API_KEY",
    ),
    ProviderPreset(
        key="kimi",
        label="Kimi",
        provider_type="openai-compatible",
        base_url="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-128k",
        context_window=128_000,
        api_key_env="MOONSHOT_API_KEY",
    ),
    ProviderPreset(
        key="zhipu",
        label="Zhipu GLM",
        provider_type="openai-compatible",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-plus",
        context_window=128_000,
        api_key_env="ZHIPU_API_KEY",
    ),
    ProviderPreset(
        key="minimax",
        label="MiniMax",
        provider_type="openai-compatible",
        base_url="https://api.minimaxi.com/v1",
        default_model="MiniMax-Text-01",
        context_window=1_000_000,
        api_key_env="MINIMAX_API_KEY",
    ),
    ProviderPreset(
        key="claude",
        label="Anthropic Claude",
        provider_type="anthropic",
        base_url="https://api.anthropic.com",
        default_model="claude-3-7-sonnet-latest",
        context_window=200_000,
        api_key_env="ANTHROPIC_API_KEY",
    ),
    ProviderPreset(
        key="volcano",
        label="Volcano Engine Doubao",
        provider_type="openai-compatible",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        default_model="doubao-seed-1-6-250615",
        context_window=256_000,
        api_key_env="ARK_API_KEY",
    ),
    ProviderPreset(
        key="qwen",
        label="Qwen",
        provider_type="openai-compatible",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        context_window=128_000,
        api_key_env="DASHSCOPE_API_KEY",
    ),
    ProviderPreset(
        key="custom",
        label="Custom OpenAI-compatible",
        provider_type="openai-compatible",
        base_url="http://localhost:8000/v1",
        default_model="custom-model",
        context_window=128_000,
    ),
    ProviderPreset(
        key="local",
        label="Local Ollama / vLLM",
        provider_type="openai-compatible",
        base_url="http://localhost:11434/v1",
        default_model="qwen2.5-coder:7b",
        context_window=32_768,
        api_key_required=False,
    ),
)

PROTOCOL_LABELS = {
    "openai-compatible": "OpenAI-compatible",
    "anthropic": "Anthropic",
    "responses": "OpenAI Responses",
}
_MANUAL_CUSTOM = "__custom__"


@dataclass(frozen=True, slots=True)
class ProviderSelection:
    provider_key: str
    provider_type: str
    base_url: str
    model_id: str
    context_window: int
    api_key: str = ""
    api_key_env: str | None = None

    @property
    def model_key(self) -> str:
        return f"{self.provider_key}/{self.model_id}"


def api_command(
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Configure a model provider and store its API key locally."""

    selection = (
        _interactive_wizard()
        if _interactive_terminal() and questionary is not None
        else _legacy_wizard()
    )
    if selection is None:
        typer.echo("Cancelled.")
        raise typer.Exit()

    try:
        config_path = persist_provider_selection(selection)
    except (OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    connection_result = ""
    if (
        _interactive_terminal()
        and questionary is not None
        and questionary.confirm("Test the connection now?", default=True).ask()
    ):
        success, message = run_connection_check(selection)
        connection_result = message
        if success:
            typer.echo(f"Connection succeeded: {message}")
        else:
            typer.echo(f"Connection failed: {message}", err=True)
            typer.echo(
                "Provider configuration was saved. Fix the issue and run algocode test again.",
                err=True,
            )
    else:
        typer.echo("Run algocode test to verify the connection.")

    human_lines = [
        f"Provider: {selection.provider_key}",
        f"Base URL: {selection.base_url}",
        f"Model: {selection.model_id}",
        f"Config: {config_path}",
    ]
    if connection_result:
        human_lines.append(f"Connection: {connection_result}")
    emit_result(
        "api",
        data={
            "provider": selection.provider_key,
            "base_url": selection.base_url,
            "model": selection.model_id,
            "model_key": selection.model_key,
            "config_path": str(config_path),
            "connection": connection_result or None,
        },
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        human_lines=tuple(human_lines),
    )


def persist_provider_selection(
    selection: ProviderSelection,
    credential_store: CredentialStore | None = None,
) -> Path:
    """Persist a selected provider/model and return the global config path."""
    if selection.api_key:
        store = credential_store or CredentialStore()
        store.set(selection.provider_key, selection.api_key)
        credential_ref = f"local://{selection.provider_key}"
        api_key_env = None
    elif selection.api_key_env:
        credential_ref = None
        api_key_env = selection.api_key_env
    else:
        raise ValueError("API key must not be empty")

    return update_global_config(
        {
            "providers": {
                selection.provider_key: {
                    "type": selection.provider_type,
                    "base_url": selection.base_url,
                    **(
                        {"credential_ref": credential_ref}
                        if credential_ref is not None
                        else {"api_key_env": api_key_env}
                    ),
                }
            },
            "models": {
                selection.model_key: {
                    "provider": selection.provider_key,
                    "model": selection.model_id,
                    "context_window": selection.context_window,
                }
            },
            "defaults": {
                "provider": selection.provider_key,
                "model": selection.model_key,
            },
        }
    )


def run_connection_check(selection: ProviderSelection) -> tuple[bool, str]:
    """Send one tiny request to the selected provider and return success/text."""
    config = load_config(project_root=Path.cwd(), data_dir=default_data_dir())
    provider, model = build_provider(
        config,
        provider_key=selection.provider_key,
        model_key=selection.model_key,
    )
    request = ModelRequest(
        request_id=f"api_{uuid4().hex}",
        model=model,
        system=(
            f"The current model is {selection.provider_key}/{selection.model_id}. "
            "Answer the user briefly in English."
        ),
        messages=(Message(role="user", content="Hello. What model are you?"),),
        timeout_seconds=60,
    )
    try:
        response = asyncio.run(provider.complete(request))
    except ProviderError as exc:
        return False, str(exc)
    text = response.text.strip() or "[empty response]"
    return True, text


def _interactive_terminal() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def _select(message, choices, default=None):
    if green_check_select is not None:
        return green_check_select(message, choices, default)
    return questionary.select(message, choices=choices, default=default)


def _fetch_upstream_models(preset: ProviderPreset, api_key: str) -> list[str]:
    if api_key:
        return list_models(preset.provider_type, preset.base_url, api_key)
    env_value = os.environ.get(preset.api_key_env or "") if preset.api_key_env else ""
    if env_value:
        return list_models(preset.provider_type, preset.base_url, env_value)
    return []


def _interactive_wizard() -> ProviderSelection | None:
    mode = _select(
        "Choose configuration mode",
        choices=[
            questionary.Choice(title="Official provider", value="official"),
            questionary.Choice(title="Custom provider", value="custom"),
            questionary.Choice(title="Manual endpoint", value="manual"),
        ],
    ).ask()
    if mode is None:
        return None
    if mode == "custom":
        return _custom_wizard()
    if mode == "manual":
        return _manual_wizard()
    return _official_wizard()


def _official_wizard() -> ProviderSelection | None:
    config = _read_global_config_safe()
    choices = [
        questionary.Choice(
            title=f"{preset.label} ({_active_model(config, preset.key) or preset.default_model})",
            value=preset.key,
        )
        for preset in PRESETS
    ]
    provider_key = _select("Choose a model provider", choices).ask()
    if provider_key is None:
        return None
    preset = next(item for item in PRESETS if item.key == provider_key)
    if preset.key == "custom":
        return _custom_wizard()
    if preset.key == "local":
        return _local_wizard(preset)

    api_key, api_key_env = _ask_api_key(preset)
    if api_key is None and api_key_env is None:
        return None
    upstream_models = _fetch_upstream_models(preset, api_key or "")
    if not upstream_models:
        typer.echo("Could not fetch the upstream model list. Using default or configured models.")
    model_id = _ask_model(config, preset.key, preset.default_model, upstream_models)
    if model_id is None:
        return None
    return ProviderSelection(
        provider_key=preset.key,
        provider_type=preset.provider_type,
        base_url=preset.base_url,
        model_id=model_id,
        context_window=preset.context_window,
        api_key=api_key,
        api_key_env=api_key_env,
    )


def _local_wizard(preset: ProviderPreset) -> ProviderSelection | None:
    config = _read_global_config_safe()
    upstream_models = _fetch_upstream_models(preset, "local")
    if not upstream_models:
        typer.echo("Could not fetch the upstream model list. Using default or configured models.")
    model_id = _ask_model(config, preset.key, preset.default_model, upstream_models)
    if model_id is None:
        return None
    return ProviderSelection(
        provider_key=preset.key,
        provider_type=preset.provider_type,
        base_url=preset.base_url,
        model_id=model_id,
        context_window=preset.context_window,
        api_key="local",
    )


def _custom_wizard() -> ProviderSelection | None:
    name = questionary.text("Provider name", default="my-provider").ask()
    if not name or not name.strip():
        return None
    name = name.strip()
    protocol = _select(
        "Protocol",
        choices=[
            questionary.Choice(title=PROTOCOL_LABELS[key], value=key)
            for key in ("openai-compatible", "anthropic", "responses")
        ],
    ).ask()
    if protocol is None:
        return None
    default_url = (
        "http://localhost:8000/v1" if protocol == "openai-compatible" else "https://api.example.com"
    )
    base_url = questionary.text("Base URL", default=default_url).ask()
    if not base_url or not base_url.strip():
        return None
    api_key = questionary.password("API key (leave empty for local services)", default="").ask()
    if api_key is None:
        return None
    api_key = api_key.strip() or "local"
    model_id = questionary.text("Model ID").ask()
    if not model_id or not model_id.strip():
        return None
    context_window = _ask_context_window(128_000)
    if context_window is None:
        return None
    return ProviderSelection(
        provider_key=name,
        provider_type=protocol,
        base_url=base_url.strip(),
        model_id=model_id.strip(),
        context_window=context_window,
        api_key=api_key,
    )


def _manual_wizard() -> ProviderSelection | None:
    name = questionary.text("Provider name", default="manual").ask()
    if not name or not name.strip():
        return None
    base_url = questionary.text("Base URL", default="http://localhost:8000/v1").ask()
    if not base_url or not base_url.strip():
        return None
    model_id = questionary.text("Model ID").ask()
    if not model_id or not model_id.strip():
        return None
    api_key = questionary.password("API Key", default="").ask()
    if api_key is None:
        return None
    api_key = api_key.strip() or "local"
    context_window = _ask_context_window(128_000)
    if context_window is None:
        return None
    return ProviderSelection(
        provider_key=name.strip(),
        provider_type="openai-compatible",
        base_url=base_url.strip(),
        model_id=model_id.strip(),
        context_window=context_window,
        api_key=api_key,
    )


def _ask_model(
    config: dict,
    provider_key: str,
    default_model: str,
    upstream_models: list[str] | None = None,
) -> str | None:
    configured = _configured_model_ids(config, provider_key)
    models = list(dict.fromkeys([*(upstream_models or []), default_model, *configured]))
    choices = [questionary.Choice(title=model, value=model) for model in models]
    choices.append(questionary.Choice(title="Enter another model ID...", value=_MANUAL_CUSTOM))
    selected = _select("Choose a model", choices).ask()
    if selected is None:
        return None
    if selected != _MANUAL_CUSTOM:
        return selected
    model_id = questionary.text("Model ID", default=default_model).ask()
    return model_id.strip() if model_id and model_id.strip() else None


def _ask_api_key(preset: ProviderPreset) -> tuple[str | None, str | None]:
    saved = CredentialStore().get(preset.key) or ""
    env_value = os.environ.get(preset.api_key_env or "") if preset.api_key_env else ""
    hints: list[str] = []
    if saved:
        hints.append(f"Saved key: {_secret_fingerprint(saved)}")
    if preset.api_key_env:
        if env_value:
            hints.append(
                f"Environment variable ${preset.api_key_env} is set; leave empty to use it"
            )
        else:
            hints.append(f"Leave empty to use environment variable ${preset.api_key_env}")
    if saved or env_value:
        hints.append("Entering a value will replace the saved key")
    message = "Enter the API key"
    if hints:
        message += "\n" + "\n".join(hints)

    while True:
        value = questionary.password(message, default="").ask()
        if value is None:
            return None, None
        value = value.strip()
        if value:
            return value, None
        if env_value:
            return "", preset.api_key_env
        if saved:
            return saved, None
        typer.echo("API key must not be empty", err=True)


def _ask_context_window(default: int) -> int | None:
    value = questionary.text("Context window", default=str(default)).ask()
    if value is None:
        return None
    try:
        parsed = int(value.strip())
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _read_global_config_safe() -> dict:
    try:
        return read_global_config()
    except (OSError, ValueError):
        return {}


def _active_model(config: dict, provider_key: str) -> str:
    defaults = config.get("defaults") if isinstance(config.get("defaults"), dict) else {}
    if defaults.get("provider") != provider_key:
        return ""
    model_key = defaults.get("model")
    models = config.get("models") if isinstance(config.get("models"), dict) else {}
    entry = models.get(model_key)
    if isinstance(entry, dict) and entry.get("model"):
        return str(entry["model"])
    return str(model_key) if model_key else ""


def _configured_model_ids(config: dict, provider_key: str) -> list[str]:
    models = config.get("models") if isinstance(config.get("models"), dict) else {}
    result: list[str] = []
    for key, entry in models.items():
        if isinstance(entry, dict) and entry.get("provider") == provider_key:
            result.append(str(entry.get("model") or key))
    return result


def _secret_fingerprint(secret: str) -> str:
    value = secret.strip()
    if len(value) < 15:
        return "********"
    return f"{value[:6]}...{value[-4:]}"


def _legacy_wizard() -> ProviderSelection | None:
    preset = _select_preset()
    provider_key = preset.key
    if preset.key == "custom":
        provider_key = typer.prompt("Provider Key", default="custom").strip() or "custom"

    base_url = typer.prompt("Base URL", default=preset.base_url).strip()
    model_id = typer.prompt("Model ID", default=preset.default_model).strip()
    context_window = typer.prompt(
        "Context window",
        default=preset.context_window,
        type=int,
    )
    api_key = typer.prompt(
        (
            "Enter the API key"
            if preset.api_key_required
            else "Enter the API key (leave empty for local services)"
        ),
        default="",
        hide_input=True,
    ).strip()
    if preset.api_key_required and not api_key:
        typer.echo("API key must not be empty", err=True)
        raise typer.Exit(code=2)
    if not api_key:
        api_key = "local"

    if not base_url:
        typer.echo("Base URL must not be empty", err=True)
        raise typer.Exit(code=2)
    if not model_id:
        typer.echo("Model ID must not be empty", err=True)
        raise typer.Exit(code=2)

    return ProviderSelection(
        provider_key=provider_key,
        provider_type=preset.provider_type,
        base_url=base_url,
        model_id=model_id,
        context_window=context_window,
        api_key=api_key,
    )


def _select_preset() -> ProviderPreset:
    typer.echo("Choose a model provider:")
    for index, preset in enumerate(PRESETS, start=1):
        typer.echo(f"  {index}. {preset.label}")
    while True:
        try:
            selected = typer.prompt("Enter a number", type=int)
        except typer.Abort:
            raise
        if 1 <= selected <= len(PRESETS):
            return PRESETS[selected - 1]
        typer.echo(f"Enter a number between 1 and {len(PRESETS)}.", err=True)


def default_data_dir() -> Path:
    from algocode.storage.paths import default_data_dir as _default_data_dir

    return _default_data_dir()
