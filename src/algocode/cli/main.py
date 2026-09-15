"""Algocode command-line entry point."""

import typer

from algocode import __version__
from algocode.cli.commands.accept import accept_command
from algocode.cli.commands.apply import apply_command, rollback_command
from algocode.cli.commands.baseline import baseline_command
from algocode.cli.commands.benchmark import benchmark_command
from algocode.cli.commands.candidate import candidate_app
from algocode.cli.commands.correctness import correctness_app
from algocode.cli.commands.doctor import doctor_command
from algocode.cli.commands.eval import eval_app
from algocode.cli.commands.experiment import experiment_app
from algocode.cli.commands.gate import gate_app
from algocode.cli.commands.init import init_command
from algocode.cli.commands.optimize import optimize_command
from algocode.cli.commands.report import report_command
from algocode.cli.commands.task import task_app

app = typer.Typer(
    name="algocode",
    help="Reproducible algorithm optimization agent for C++ and Python.",
    no_args_is_help=True,
    add_completion=False,
)
app.command("init", help="Register a local Git project.")(init_command)
app.command("doctor", help="Check the local Algocode runtime environment.")(doctor_command)
app.command("baseline", help="Capture a task baseline.")(baseline_command)
app.command("benchmark", help="Run or compare a benchmark.")(benchmark_command)
app.add_typer(correctness_app)
app.command("optimize", help="Run the agent optimization loop.")(optimize_command)
app.add_typer(task_app)
app.add_typer(candidate_app)
app.add_typer(experiment_app)
app.add_typer(gate_app)
app.command("accept", help="Accept a verified candidate.")(accept_command)
app.command("apply", help="Apply an accepted candidate.")(apply_command)
app.command("rollback", help="Roll back an applied candidate.")(rollback_command)
app.command("report", help="Generate a task report.")(report_command)
app.add_typer(eval_app)


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the Algocode version and exit.",
        is_eager=True,
    ),
) -> None:
    if version:
        typer.echo(__version__)
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


def main() -> None:
    app()
