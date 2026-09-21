# Command Guide

This page explains Algocode commands by workflow. See the [CLI Reference](../reference/cli.md) for full options, exit codes, and JSON fields.

## Environment and Models

For a first run, use this order:

```bash
algocode doctor
algocode api
algocode test
```

| Command | Purpose | When to use |
| --- | --- | --- |
| `algocode api` | Interactively configure the provider, base URL, model, and API key. | First use or provider changes. |
| `algocode test` | Send a minimal request to verify the model connection. | Immediately after configuration. |
| `algocode doctor` | Check Python, Git, SQLite, Sandbox, C++ compiler, and data directory. | After installation or when commands fail. |
| `algocode model` | Select the default model for the current project. | Temporary or long-term model changes. |

`model` tries to refresh the available model list from the current provider's upstream API, merges it with configured models, and falls back to local configuration if the upstream is unavailable.

## Project Initialization

```bash
algocode init
algocode init --path ./demo --language python
```

| Command | Purpose | When to use |
| --- | --- | --- |
| `algocode init` | Detect the language, generate the Contract, capture a Baseline, and create the initial Task. | The first time a project is prepared for Algocode. |

A successful initialization usually prints:

```text
Next: algocode optimize <task-id> --provider default --model default
```

## Main Optimization Flow

```bash
algocode optimize
algocode retry
```

| Command | Purpose | When to use |
| --- | --- | --- |
| `algocode optimize` | Continue the phase machine from the current phase. | Start optimization after initialization or continue an unfinished task. |
| `algocode retry` | Replan from `PLAN` using historical optimization records. | The previous run failed, had insufficient gain, or followed the wrong direction. |

With default settings, `optimize` can create multiple candidates and refine candidates that show significant positive evidence but have not yet been accepted. Each phase exposes only its allowed tools, and the model receives remaining turn and tool-call budgets.

`optimize` supports `--fake-provider` for keyless integration tests and `--stop-after verify` for phase-by-phase debugging.

## Status and Evidence

```bash
algocode status
algocode review
algocode diff
```

| Command | Purpose | When to use |
| --- | --- | --- |
| `algocode status` | Show the task, current phase, candidate, evidence, and recommended next step. | When you are unsure where the workflow is. |
| `algocode review` | Summarize Correctness, Benchmark, Decision, and changed files. | Before accepting a candidate. |
| `algocode diff` | Show the candidate patch against the baseline. | To inspect exactly what changed. |

## Decision and Application

```bash
algocode accept <task-id> <candidate-id>
algocode apply
algocode rollback
```

| Command | Purpose | When to use |
| --- | --- | --- |
| `algocode accept` | Record that a candidate passed the acceptance policy. | Evidence meets the required standard. |
| `algocode apply` | Apply an accepted candidate to the user workspace. | Formalize the change after acceptance. |
| `algocode rollback` | Roll back an applied candidate. | A problem is found after apply. |

`accept` records a decision only. `apply` is the step that modifies the user workspace.

## Reports

```bash
algocode report <task-id>
algocode report <task-id> --markdown
```

| Command | Purpose | When to use |
| --- | --- | --- |
| `algocode report` | Generate task JSON, Markdown, and a root-level `report.md`. | Archive results, share reviews, or produce documentation. |

## Lower-Level Evidence Commands

```bash
algocode baseline <task-id>
algocode correctness run <task-id> --spec .algocode/oracle/correctness.yaml
algocode correctness replay <result-id>
algocode benchmark <task-id>
algocode experiment list <task-id>
algocode experiment show <experiment-id>
```

| Command | Purpose | When to use |
| --- | --- | --- |
| `algocode baseline` | Capture a task baseline independently. | Re-run a baseline manually. |
| `algocode correctness run` | Run baseline Correctness for a task. | Inspect correctness evidence manually. |
| `algocode correctness replay` | Replay stored Correctness. | Recheck historical results. |
| `algocode benchmark` | Run a baseline or candidate benchmark. | Collect or compare performance manually. |
| `algocode experiment list` | List benchmark experiments. | Query historical experiments. |
| `algocode experiment show` | Inspect one experiment, its result, and comparison. | Review a specific performance run. |

## Entity Inspection

```bash
algocode task create --objective "optimize XXX"
algocode task list
algocode task show <task-id>
algocode candidate create <task-id>
algocode candidate freeze <candidate-id>
algocode candidate list <task-id>
algocode candidate show <candidate-id>
```

| Command | Purpose | When to use |
| --- | --- | --- |
| `algocode task create` | Create a task. | Manually create an optimization task. |
| `algocode task list` | List local tasks. | Find existing tasks. |
| `algocode task show` | Inspect one task. | Check task status and phase. |
| `algocode candidate create` | Create a candidate worktree. | Create a candidate manually. |
| `algocode candidate freeze` | Freeze a candidate and record its patch hash. | Lock candidate contents. |
| `algocode candidate list` | List task candidates. | Inspect the candidate set. |
| `algocode candidate show` | Inspect one candidate. | Check status and workspace path. |

## Evaluation and Acceptance

```bash
algocode eval run smoke
algocode eval run core --provider fake
algocode gate run
```

| Command | Purpose | When to use |
| --- | --- | --- |
| `algocode eval run` | Run smoke, core, adversarial, recovery, or A/B comparisons. | Project quality regression checks. |
| `algocode gate run` | Run the P0 release acceptance gate. | Full checks before a release. |

## VS Code Extension

```bash
algocode vscode install
algocode vscode install --force
```

After installation, right-click `.py`, `.cpp`, `.cc`, or `.cxx` files in VS Code to use the `Algocode` context menu.
