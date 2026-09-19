"""Profile collection entrypoint."""

from __future__ import annotations

from pathlib import Path

from algocode.domain.model import Language
from algocode.profiling.adapters import CppGprofAdapter, PythonCProfileAdapter
from algocode.profiling.types import ProfileReport
from algocode.sandbox.runner import SandboxProcessRunner


async def collect_profile(
    *,
    workspace: Path,
    language: Language,
    commands: tuple[tuple[str, ...], ...] = (),
    sandbox_runner: SandboxProcessRunner | None = None,
    timeout_seconds: int = 60,
) -> ProfileReport:
    """Collect the first successful profile across candidate entrypoint commands."""

    adapter = (
        PythonCProfileAdapter()
        if language is Language.PYTHON
        else CppGprofAdapter()
        if language is Language.CPP
        else None
    )
    if adapter is None:
        return ProfileReport(
            language=language.value if isinstance(language, Language) else str(language),
            tool="unsupported",
            available=False,
            error=f"no profiler adapter for {language}",
        )
    errors: list[str] = []
    for command in commands or ((),):
        report = await adapter.profile(
            workspace,
            tuple(command),
            timeout_seconds=timeout_seconds,
            sandbox_runner=sandbox_runner,
        )
        if report.available:
            return report
        errors.append(f"{' '.join(command) or '<default>'}: {report.error}")
    return ProfileReport(
        language=adapter.language,
        tool=adapter.tool,
        available=False,
        error="; ".join(errors) or "no entrypoint commands were available",
    )
