"""Install the bundled VS Code extension."""

from __future__ import annotations

import os
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Annotated

import typer

from algocode.cli.output import JsonOption, NoColorOption, QuietOption, VerboseOption, emit_result

vscode_app = typer.Typer(
    name="vscode",
    help="Manage the Algocode VS Code extension.",
    no_args_is_help=True,
)

CodeOption = Annotated[
    str | None,
    typer.Option("--code", help="VS Code CLI executable to use."),
]
ForceOption = Annotated[
    bool,
    typer.Option("--force/--no-force", help="Reinstall the extension if it already exists."),
]


def _bundled_vsix() -> resources.abc.Traversable:
    root = resources.files("algocode.resources.vscode")
    candidates = sorted(root.glob("*.vsix"))
    if not candidates:
        raise FileNotFoundError("the Algocode VS Code extension is not bundled with this package")
    return candidates[-1]


def _find_code_executable(explicit: str | None = None) -> str:
    candidates = (
        [explicit]
        if explicit
        else ["code", "code.cmd", "code-insiders", "code-insiders.cmd", "codium", "codium.cmd"]
    )
    for candidate in candidates:
        if candidate is None:
            continue
        found = shutil.which(candidate)
        if found:
            return found
    raise FileNotFoundError(
        "VS Code CLI was not found. Pass --code with the full path to code.exe/code.cmd."
    )


def _install_with_code(code_executable: str, vsix_path: Path, *, force: bool) -> str:
    command = [code_executable, "--install-extension", str(vsix_path)]
    if force:
        command.append("--force")
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        shell=os.name == "nt" and code_executable.lower().endswith((".cmd", ".bat")),
    )
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    if completed.returncode != 0:
        raise RuntimeError(output or f"VS Code extension installation failed ({completed.returncode})")
    return output


@vscode_app.command("install")
def vscode_install_command(
    code: CodeOption = None,
    force: ForceOption = True,
    json_output: JsonOption = False,
    no_color: NoColorOption = False,
    quiet: QuietOption = False,
    verbose: VerboseOption = False,
) -> None:
    """Install the bundled extension into the local VS Code installation."""

    try:
        vsix = _bundled_vsix()
        with resources.as_file(vsix) as vsix_path:
            executable = _find_code_executable(code)
            output = _install_with_code(executable, vsix_path, force=force)
    except (FileNotFoundError, OSError, RuntimeError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc

    emit_result(
        "vscode.install",
        data={
            "installed": True,
            "extension": "acd2113.algocode-vscode",
            "vsix": str(vsix_path),
            "code": executable,
        },
        json_output=json_output,
        no_color=no_color,
        quiet=quiet,
        verbose=verbose,
        human_lines=(
            "Algocode VS Code extension installed.",
            f"VSIX: {vsix_path}",
            f"VS Code CLI: {executable}",
            *(["Output:", output] if output and verbose else []),
        ),
    )
