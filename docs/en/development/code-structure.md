# Code Structure

The repository contains two entry points: a Python CLI and a VS Code extension.

```text
.
├── src/algocode/          # Python package and CLI
├── extensions/vscode/     # VS Code extension
├── tests/                 # pytest tests
├── docs/                  # MkDocs documentation
├── pyproject.toml
└── mkdocs.yml
```

## Python Package

```text
src/algocode/
├── cli/                  # Typer command entry points and output helpers
├── application/          # Use-case orchestration and services
├── domain/               # Entities, value objects, enums, events
├── runtime/              # Agent phase machine, tool loop, gates, model logs
├── config/               # Configuration models, loading, global config
├── context/              # Context assembly, fact ledger, budgets
├── tools/                # Tool registry and built-in tools
├── policy/               # Policy engine
├── approval/             # Human approval service
├── sandbox/              # Native / Docker / WSL2 process execution
├── security/             # Credentials and secret redaction
├── providers/            # OpenAI-compatible, Anthropic, Responses, Fake providers
├── languages/            # Python / C++ adapters
├── correctness/          # Correctness specs and execution
├── benchmark/            # Benchmark specs, engine, environment
├── acceptance/           # P0 release acceptance gate
├── eval/                 # Agent evaluation suites
├── workspace/            # Git worktrees, snapshots, patches
├── storage/              # SQLite Event Store, projections, artifact store
├── ports/                # Ports and type boundaries
├── resources/            # Built-in resources and VSIX
├── observability/        # Observability extension points
└── report/               # Report helpers
```

## Key Module Responsibilities

### `cli`

All commands are registered with Typer and emit results through `emit_result`. Machine-readable output prefers `--json`; the default output is a human-readable summary.

### `application`

Application services orchestrate cross-domain operations:

- `baseline_service`: capture baselines.
- `candidate_service`: create and freeze candidates.
- `candidate_service.reopen`: return rejected or inconclusive candidates to `editing` for refinement.
- `correctness_service`: run Correctness.
- `benchmark_service`: run benchmarks and read comparisons.
- `benchmark_service`: interleaved sampling, multi-input pairing, robust variation, confidence intervals, and growth fitting.
- `decision_service`: accept or reject candidates.
- `apply_service`: Apply and Rollback.
- `report_service`: generate reports.

### `runtime`

The core Agent loop is in `runtime/agent.py`. It runs model turns and tool calls by phase and writes Phase Gate events.

### `domain`

Domain enums, entities, and events are the persistence core. State changes are written through Event Store and projected into SQLite read models.

### `storage`

SQLite stores Project, Task, Candidate, Baseline, Correctness, Benchmark, Decision, and related read models. Large files use the content-addressed File Artifact Store.

### `workspace`

CLI candidates run in Git worktrees. Apply checks the Decision, stale state, and patch, then creates a Rollback Manifest.

### `sandbox`

Builds, Correctness, and Benchmarks run through the Sandbox. It supports Native, Docker, and WSL2 with timeout, memory, output, PID, network, and root-write controls.

## VS Code Extension

```text
extensions/vscode/
├── package.json
├── tsconfig.json
└── src/
    └── extension.ts
```

The extension provides:

- `algocode.optimizeFile`: optimize a file from the context menu.
- `algocode.diff`: open the native diff.
- `algocode.review`: view evidence.
- `algocode.apply`: apply a candidate.
- `algocode.rollback`: roll back a candidate.
- `algocode.api`, `algocode.test`, `algocode.model`: configure and test models.
- `algocode.init`, `algocode.optimize`, `algocode.status`, `algocode.report`: call the CLI.

File optimization runs `algocode init` and `algocode optimize` in a temporary shadow workspace, then opens a diff. Apply copies candidate files into the original project and saves backups for Rollback.

## Dependency Direction

Dependencies should point inward toward `domain` and `ports`. CLI, VS Code, and persistence are external adapters and should not implement domain rules directly.
