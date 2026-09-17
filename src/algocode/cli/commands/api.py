"""Interactive provider and API-key setup."""

from __future__ import annotations

from dataclasses import dataclass

import typer

from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result
from algocode.config.global_file import update_global_config
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


PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        key="openai",
        label="OpenAI",
        provider_type="openai-compatible",
        base_url="https://api.openai.com/v1",
        default_model="gpt- 5.6",
        context_window=128_000,
    ),
    ProviderPreset(
        key="deepseek",
        label="DeepSeek",
        provider_type="openai-compatible",
        base_url="https://api.deepseek.com/v1",
        default_model="deepseek-flash",
        context_window=128_000,
    ),
    ProviderPreset(
        key="openrouter",
        label="OpenRouter",
        provider_type="openai-compatible",
        base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-5.6",
        context_window=128_000,
    ),
    ProviderPreset(
        key="kimi",
        label="Kimi",
        provider_type="openai-compatible",
        base_url="https://api.moonshot.cn/v1",
        default_model="moonshot-v1-128k",
        context_window=128_000,
    ),
    ProviderPreset(
        key="zhipu",
        label="智谱 GLM",
        provider_type="openai-compatible",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-4-plus",
        context_window=128_000,
    ),
    ProviderPreset(
        key="minimax",
        label="MiniMax",
        provider_type="openai-compatible",
        base_url="https://api.minimaxi.com/v1",
        default_model="MiniMax-Text-01",
        context_window=1_000_000,
    ),
    ProviderPreset(
        key="claude",
        label="Anthropic Claude",
        provider_type="anthropic",
        base_url="https://api.anthropic.com",
        default_model="claude-3-7-sonnet-latest",
        context_window=200_000,
    ),
    ProviderPreset(
        key="volcano",
        label="火山引擎豆包",
        provider_type="openai-compatible",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        default_model="doubao-seed-1-6-250615",
        context_window=256_000,
    ),
    ProviderPreset(
        key="qwen",
        label="通义千问 Qwen",
        provider_type="openai-compatible",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        context_window=128_000,
    ),
    ProviderPreset(
        key="custom",
        label="自定义 OpenAI-compatible",
        provider_type="openai-compatible",
        base_url="http://localhost:8000/v1",
        default_model="custom-model",
        context_window=128_000,
    ),
    ProviderPreset(
        key="local",
        label="本地 Ollama / vLLM",
        provider_type="openai-compatible",
        base_url="http://localhost:11434/v1",
        default_model="qwen2.5-coder:7b",
        context_window=32_768,
        api_key_required=False,
    ),
)


def api_command(
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Configure a model provider and store its API key locally."""

    preset = _select_preset()
    provider_key = preset.key
    if preset.key == "custom":
        provider_key = typer.prompt("Provider Key", default="custom").strip() or "custom"

    base_url = typer.prompt("Base URL", default=preset.base_url).strip()
    model_id = typer.prompt("模型 ID", default=preset.default_model).strip()
    context_window = typer.prompt(
        "上下文窗口",
        default=preset.context_window,
        type=int,
    )
    api_key = typer.prompt(
        "请输入 API Key" if preset.api_key_required else "请输入 API Key（本地服务可留空）",
        default="",
        hide_input=True,
    ).strip()
    if preset.api_key_required and not api_key:
        typer.echo("API Key 不能为空", err=True)
        raise typer.Exit(code=2)
    if not api_key:
        api_key = "local"

    if not base_url:
        typer.echo("Base URL 不能为空", err=True)
        raise typer.Exit(code=2)
    if not model_id:
        typer.echo("模型 ID 不能为空", err=True)
        raise typer.Exit(code=2)

    model_key = f"{provider_key}/{model_id}"
    try:
        CredentialStore().set(provider_key, api_key)
        config_path = update_global_config(
            {
                "providers": {
                    provider_key: {
                        "type": preset.provider_type,
                        "base_url": base_url,
                        "credential_ref": f"local://{provider_key}",
                    }
                },
                "models": {
                    model_key: {
                        "provider": provider_key,
                        "model": model_id,
                        "context_window": context_window,
                    }
                },
                "defaults": {
                    "provider": provider_key,
                    "model": model_key,
                },
            }
        )
    except (OSError, ValueError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    emit_result(
        "api",
        data={
            "provider": provider_key,
            "base_url": base_url,
            "model": model_id,
            "model_key": model_key,
            "config_path": str(config_path),
        },
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        human_lines=(
            f"Provider: {provider_key}",
            f"Base URL: {base_url}",
            f"Model: {model_id}",
            f"Config: {config_path}",
            "API Key 已保存到本机凭证文件。",
            "运行 algocode test 验证连接。",
        ),
    )


def _select_preset() -> ProviderPreset:
    typer.echo("请选择模型厂商：")
    for index, preset in enumerate(PRESETS, start=1):
        typer.echo(f"  {index}. {preset.label}")
    while True:
        try:
            selected = typer.prompt("请输入数字", type=int)
        except typer.Abort:
            raise
        if 1 <= selected <= len(PRESETS):
            return PRESETS[selected - 1]
        typer.echo(f"请输入 1 到 {len(PRESETS)} 之间的数字。", err=True)
