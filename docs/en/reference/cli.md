# CLI Reference

This page documents CLI options, defaults, and JSON output details. See the [Command Guide](../commands/index.md) for everyday workflows and examples.

## Common Conventions

Most commands support:

| Option | Description |
| --- | --- |
| `--json` | Emit machine-readable JSON. |
| `--quiet` | Suppress non-essential human-readable output. |
| `--verbose` | Emit diagnostics to stderr. |
| `--no-color` | Disable ANSI color. |
| `--data-dir <path>` | Override the Algocode data directory. |
| `--progress/--no-progress` | Force live phase progress on or off. The default is TTY-dependent. |

Many commands can omit `task_id` and read `.algocode/current-task.json` instead.

```bash
algocode --version
algocode --help
algocode <command> --help
```

## Environment and Models

### `algocode api`

Interactively select a provider, base URL, model ID, context window, and API key.

```bash
algocode api
algocode api --json
```

API keys are stored in the local credential file, not project configuration.

### `algocode test`

Send a minimal model request.

```bash
algocode test
algocode test --provider openai --model openai/gpt-5-mini
```

### `algocode doctor`

Check Python, Git, SQLite, Sandbox, C++ compiler, and data directory.

```bash
algocode doctor
algocode doctor --json
```

### `algocode model`

Select the default model for the current project. The command attempts to refresh models from the provider's `/models` endpoint and merges the result with locally configured models.

```bash
algocode model
algocode model --provider openai
```

## Initialization

### `algocode init`

Detect the project, generate the Contract, capture the Baseline, and create the initial Task.

```bash
algocode init
algocode init --path ./demo --language python
algocode init --no-bootstrap --no-write-config
algocode init --yes
```

| Option | Default | Description |
| --- | --- | --- |
| `--path` | `.` | Project directory. |
| `--language` | `auto` | `auto`, `cpp`, or `python`. |
| `--objective` | empty | Initial task objective. |
| `--bootstrap/--no-bootstrap` | `bootstrap` | Create Git/config prerequisites and run the first baseline. |
| `--write-config/--no-write-config` | `write-config` | Generate `.algocode/config.yaml`. |
| `--yes` / `-y` | `false` | Skip the pre-run confirmation prompt. |
| `--progress/--no-progress` | TTY auto | Force live phase progress on or off. |

## Main Optimization Flow

### `algocode optimize`

Continue the phase machine from the current phase.

```bash
algocode optimize
algocode optimize <task-id>
algocode optimize --fake-provider
algocode optimize --max-steps 20 --max-tool-calls 40 --stop-after verify
```

| Option | Default | Description |
| --- | --- | --- |
| `--fake-provider` | off | Use the deterministic Fake Provider without an API key. |
| `--provider` | project default | Override the provider. |
| `--model` | project default | Override the model. |
| `--candidate-workspace` | empty | Candidate worktree to operate on. |
| `--candidate-id` | empty | Candidate identifier. |
| `--max-steps` | config value | Maximum model turns per phase. |
| `--max-tool-calls` | config value | Maximum tool calls per phase. |
| `--stop-after` | `report` | Stop after a named phase. |
| `--progress/--no-progress` | TTY auto | Force live progress on or off. |

In an interactive terminal, Algocode shows a single-line live progress display and then leaves a permanent line with `✔` or `✖`. Non-TTY output contains only final lines without control characters. `--json` and `--quiet` disable progress completely.

The final summary includes the task, duration, phases, candidate, Correctness, Benchmark, improvement, and Decision. Interactive terminals also offer a next-step menu.

### `algocode retry`

Replan from `PLAN` using persisted optimization records.

```bash
algocode retry
algocode retry <task-id> --fake-provider
```

The command fails if no optimization records exist.

## Status and Evidence

### `algocode status`

Show the task, current phase, candidate, Correctness, Benchmark, Decision, and recommended next command.

```bash
algocode status
algocode status --candidate-id <candidate-id> --json
```

Important JSON fields include:

```text
taskId
status
currentPhase
progress.phase / turn / toolCalls / activeTool / lastTool
candidateId
correctness.status
benchmark.valid
benchmark.improvementPercent
decision.outcome
nextCommand
```

### `algocode review`

Summarize candidate Correctness, Benchmark, Decision, and changed files.

```bash
algocode review
algocode review --candidate-id <candidate-id>
```

### `algocode diff`

Print the candidate patch. JSON mode includes `patch` and `untracked`.

```bash
algocode diff
algocode diff --json
```

## Decision and Application

### `algocode accept`

Record an accepted decision without modifying the user workspace.

```bash
algocode accept <task-id> <candidate-id> --reason "evidence verified"
```

### `algocode apply`

Apply an accepted candidate to the user workspace after checking the decision, stale state, and patch.

```bash
algocode apply
algocode apply <task-id> <candidate-id>
```

If the candidate has not been accepted, the CLI attempts to record an acceptance decision first.

### `algocode rollback`

Roll back an applied candidate.

```bash
algocode rollback
algocode rollback <task-id> <candidate-id>
```

## Reports

### `algocode report`

Generate and persist a task report.

```bash
algocode report <task-id>
algocode report <task-id> --markdown
algocode report <task-id> --json
```

`--markdown` and `--json` cannot be used together.

Outputs include:

```text
.algocode/cache/artifacts/<report-json>
.algocode/cache/artifacts/<report-md>
report.md
```

## Lower-Level Evidence Commands

### `algocode baseline`

```bash
algocode baseline <task-id>
algocode baseline <task-id> --language python --build-command "python test.py" --timeout 180
```

### `algocode correctness run`

```bash
algocode correctness run <task-id> --spec .algocode/oracle/correctness.yaml
```

Exit code is `4` on failure.

### `algocode correctness replay`

```bash
algocode correctness replay <result-id>
```

### `algocode benchmark`

```bash
algocode benchmark <task-id>
algocode benchmark <task-id> --candidate-id <candidate-id>
algocode benchmark <task-id> --show <benchmark-id>
```

### `algocode experiment list`

```bash
algocode experiment list
algocode experiment list <task-id> --status completed --limit 20
```

### `algocode experiment show`

```bash
algocode experiment show <experiment-id>
```

## Entity Inspection

### `algocode task`

```bash
algocode task create --objective "optimize XXX" --project-root .
algocode task list
algocode task show <task-id>
```

### `algocode candidate`

```bash
algocode candidate create <task-id>
algocode candidate freeze <candidate-id>
algocode candidate list <task-id>
algocode candidate show <candidate-id>
```

`candidate create` supports `--base-revision` to override the baseline revision.

## Evaluation and Acceptance

### `algocode gate run`

```bash
algocode gate run
algocode gate run --skip-tests --report-dir ./acceptance
```

### `algocode eval run`

```bash
algocode eval run smoke
algocode eval run core --provider fake --repeat 3
algocode eval run smoke --ab-baseline fake --ab-candidate scripted
```

## VS Code Extension

### `algocode vscode install`

```bash
algocode vscode install
algocode vscode install --force
algocode vscode install --code "/path/to/code"
```
