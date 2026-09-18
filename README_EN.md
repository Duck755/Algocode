<div align="center">

<img src="docs/picture/algocode_icon.png" alt="Algocode" width="120">

# Algocode

> *A verifiable algorithm optimization agent for C++ / Python: local-first, evidence-driven, and rollback-safe.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/algocode-agent.svg)](https://pypi.org/project/algocode-agent/)
[![VS Code](https://img.shields.io/badge/VS%20Code-1.90%2B-007ACC?logo=visualstudiocode)](https://code.visualstudio.com/)
[![OpenAI Compatible](https://img.shields.io/badge/API-OpenAI_Compatible-green)](https://platform.openai.com/)

**Algocode is not a black box that silently rewrites your code.**

It first builds a behavioral contract, then explores optimizations inside isolated Git worktrees, and finally decides whether a candidate is worth applying based on three kinds of evidence: Correctness, Contract, and Benchmark.

[简体中文](README.md) · [Quick Start](#quick-start) · [VS Code](#vs-code-extension) · [Workflow](#optimization-workflow) · [CLI](#cli-command-reference)

</div>

---

## What It Does

Give Algocode a runnable C++ or Python project:

```text
Input: test.py

Algocode automatically:
  1. Builds the project's behavioral contract
  2. Captures baseline output and baseline performance
  3. Analyzes algorithmic hot spots and proposes optimizations
  4. Generates candidate implementations in isolated worktrees
  5. Verifies correctness and contract compliance
  6. Compares benchmark results
  7. Generates reports and diffs, then waits for you to decide whether to apply
```

Example output:

```text
Task: task_xxxxxxxx
Status: completed
Correctness: passed
Benchmark valid: true
Baseline median: 0.7594s
Candidate median: 0.5357s
Improvement: 29.4573%
```

Algocode is designed for algorithm contest code, data structure implementations, graph algorithms, string algorithms, caches, parsers, concurrency components, and other code with deterministic behavior.

---

## Core Features

- **Contract-first**: Public APIs, inputs and outputs, configuration semantics, error behavior, and boundary cases are established before optimization, preventing changes that are faster but behaviorally wrong.
- **Evidence-driven**: Correctness, Contract, and Benchmark results are persisted. Accept and reject decisions are based on real evidence, not model self-assessment.
- **Isolated candidates**: The CLI experiments inside Git worktrees. The VS Code extension uses a temporary shadow workspace. Your project is not modified directly.
- **Human-controlled**: Diff, Review, and Apply are separate steps. Inspect the evidence first, then decide whether to apply. Applied changes can be rolled back.
- **Auditable**: Model calls, tool calls, phase results, candidate snapshots, and optimization records are stored.
- **Visible phase progress**: The VS Code terminal shows the current phase, phase index, turn, active tool, tool count, and elapsed time.
- **Retryable**: If an attempt regresses, lacks evidence, or gets blocked, Algocode can plan another direction using recorded history.
- **Multiple model providers**: OpenAI, DeepSeek, OpenRouter, Kimi, Zhipu GLM, MiniMax, Anthropic Claude, Doubao, Qwen, and arbitrary OpenAI-compatible services.
- **Local-first**: Execution is local by default. Docker and WSL2 are optional isolation backends.
- **CLI + VS Code**: Suitable for terminal automation and day-to-day editor workflows.

---

## Performance and Result Disclaimer

Algocode uses large language models to analyze source code and generate candidate optimizations. Performance may improve, remain effectively unchanged, or become worse. Results depend on source quality, project structure, model capability, input size, runtime environment, and system load.

Algocode does not guarantee positive performance gains and does not replace human code review. Use the actual Correctness, Contract, Benchmark, Diff, and Review results to decide whether a candidate should be applied.

---

## Usage Rules (Read Before Optimizing)

Algocode is intended for code with verifiable behavior. Confirm the following before starting.

### General Requirements

| Requirement | Description |
|---|---|
| Git repository | The project must be a Git repository. Algocode initializes one automatically if needed. |
| Single primary language | One project supports one primary language. If Python and C++ both exist, C++ is preferred. |
| Clear entry point | There must be an executable entry file that produces output. |
| Deterministic output | The same input must produce the same output for Correctness verification. |
| Process-level benchmark | Benchmarking measures the complete process. Function-level benchmarks are not supported. |

### Python Projects

- A `.py` file exists, or `pyproject.toml` / `setup.py` is present.
- The entry point prefers `main.py` and `test.py`, then falls back to the first non-`__init__.py` file.
- The entry program runs successfully and exits with code 0.

### C++ Projects

- A `.cpp` / `.cc` / `.cxx` file exists, or `CMakeLists.txt` / `Makefile` is present.
- `g++` or `clang++` is installed with C++17 support.
- The entry point prefers `main.cpp` and `test.cpp`, then falls back to the first source file.
- The source compiles and runs successfully with exit code 0.

### Unsupported Scenarios

- Deeply mixed Python and C++ projects, such as Python calling a C++ extension.
- Complex multi-translation-unit or large CMake projects.
- Code that depends on the network, databases, GPUs, or uncontrolled external services at runtime.
- Function-level or module-level benchmarking.

---

## Environment and Dependencies

### System Requirements

| Dependency | Minimum | Notes |
|---|---|---|
| Python (required) | 3.11+ | Runtime environment |
| Git (required) | — | Worktree isolation and versioning |
| C++ compiler | — | Required for C++ projects; supports `g++` or `clang++` |

Optional enhancements:

- **Docker / WSL2**: stronger sandbox isolation, optional.
- **VS Code**: context menu, live phase progress, Diff, Apply, and Rollback.

---

## Quick Start

### Option 1: Install from PyPI

```bash
pip install algocode-agent
```

Install the VS Code extension:

```bash
algocode vscode install
```

The command automatically searches for `code`, `code-insiders`, or `codium`.

If the VS Code CLI cannot be found:

```powershell
algocode vscode install --code "{VSCodePath}\bin\code.cmd"
```

### Option 2: Install from Source

Windows PowerShell:

```powershell
git clone https://github.com/acd2113/Algocode.git
cd Algocode
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m algocode doctor
```

macOS / Linux:

```bash
git clone https://github.com/acd2113/Algocode.git
cd Algocode
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m algocode doctor
```

### Configure a Model

```bash
algocode api
algocode test
```

`algocode api` configures the provider, Base URL, model ID, and API key. API keys are stored in the local credential file and are not written into project configuration.

Switch the default model:

```bash
algocode model
```

### Check the Environment

```bash
algocode doctor
```

Confirm that the required checks pass before running the first optimization.

### Run the First Optimization

Run in the target project directory:

```bash
algocode init
algocode optimize
```

Inspect status, evidence, and diff:

```bash
algocode status
algocode review
algocode diff
```

Apply or roll back:

```bash
algocode apply
algocode rollback
```

Retry with optimization history:

```bash
algocode retry
```

---

## VS Code Extension

### Install

Recommended:

```bash
algocode vscode install
```

Manual VSIX installation:

```powershell
code --install-extension "path\to\algocode-vscode-0.1.1.vsix" --force
```

Or use:

```text
Extensions -> ... -> Install from VSIX...
```

### Usage

Right-click a `.py`, `.cpp`, `.cc`, or `.cxx` file and choose:

```text
Algocode
    Optimize
    Rollback
    Apply
    Show Diff
    Review
```

Actions:

| Action | Description |
|---|---|
| Optimize | Start the full optimization workflow in a temporary shadow workspace. |
| Rollback | Undo the most recent candidate applied through the extension. |
| Apply | Apply the most recent candidate to the original project. |
| Show Diff | Open the native VS Code diff. |
| Review | Inspect Candidate, Correctness, Benchmark, Decision, and changed files. |

The extension opens an `Algocode` terminal and displays live progress:

```text
[algocode] analyze | 1/10 | turn 2 | running read_file (3s) | tools 4 | 18s
[algocode] implement | 5/10 | turn 8 | running run_candidate_check (7s) | tools 14 | 47s
[algocode] benchmark | 7/10 | running benchmark | 21s
```

---

## CLI Command Reference

```bash
$ algocode --help
```

| Command | Description |
|---|---|
| `algocode api` | Configure a model provider and API key. |
| `algocode test` | Verify the model connection. |
| `algocode model` | Switch the default model. |
| `algocode doctor` | Check the local environment. |
| `algocode init` | Initialize the project, build the contract, and capture the baseline. |
| `algocode optimize` | Run the full optimization workflow. |
| `algocode retry` | Re-plan using optimization history. |
| `algocode status` | Show the current task, phase, and progress. |
| `algocode review` | Show Correctness, Benchmark, and decision evidence. |
| `algocode diff` | Show candidate changes. |
| `algocode apply` | Accept and apply a candidate. |
| `algocode rollback` | Roll back an applied candidate. |
| `algocode report` | Generate a Markdown report. |
| `algocode vscode install` | Install the VS Code extension bundled with the Python package. |

Most commands support `--json`:

```bash
algocode status --json
algocode review --json
algocode optimize --json
```

---

## Usage Examples

Configure the provider and API key with `algocode api`:

![Provider configuration](docs/picture/img_1.png)

Place the files to optimize in a folder:

![Project directory](docs/picture/img.png)

Run `algocode init` to initialize the project, build the contract, and capture the baseline:

![Initialization](docs/picture/img_2.png)

Run `algocode optimize` to start optimization. `Status: completed` means the workflow completed. You can then run `review`, `diff`, `report`, `apply`, and `rollback`:

![Optimization result](docs/picture/img_3.png)

### Option 1: Full CLI Workflow

```bash
algocode init
algocode optimize
algocode status
algocode review
algocode diff
```

Apply if the result meets your requirements:

```bash
algocode apply <task-id> <candidate-id>
```

Roll back when necessary:

```bash
algocode rollback
```

### Option 2: VS Code Workflow

```text
Right-click a file
  -> Algocode
  -> Optimize
  -> watch live phases
  -> inspect Diff / Review
  -> Apply or Rollback
```

This is intended for optimization, review, and apply directly from the editor.

### Option 3: Scripts and Automation

```bash
algocode init --json
algocode optimize --json
algocode status --json
algocode review --json
```

JSON output works well with CI, batch scripts, or higher-level tools.

---

## Optimization Workflow

Gates exist between phases:

- If Contract or Correctness fails, Benchmark is not started.
- If Benchmark is invalid or has no positive gain, the candidate is not accepted.
- Apply checks whether the candidate is stale.
- Rollback undoes an applied candidate.

---

## Verification Model

Algocode separates optimization evidence into three categories:

| Type | Purpose |
|---|---|
| **Correctness** | Verify that the candidate reproduces baseline behavior. Supports cases, oracle, stress, and hybrid modes. |
| **Contract** | Protect public APIs, configuration semantics, error types, state transitions, ordering, and boundary behavior. |
| **Benchmark** | Measure warmup, repeated samples, median, variation, environment hash, and related data. |

Correctness always takes priority over speed when the two conflict.

---

## Architecture

```text
CLI / VS Code
      ↓
Application Services
      ↓
Runtime Agent
      ↓
Context / Tools / Providers
      ↓
Language Adapters
      ↓
Git Worktree / Sandbox
      ↓
Storage / Event Store / Artifacts
```

---

## Project Structure

The complete source, test, and runtime directory layout is documented in [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md).

### Source Layout

```text
src/algocode/
├── cli/                  # CLI entry points and output
├── application/          # Task, Candidate, Baseline, Benchmark services
├── domain/               # Entities, value objects, and events
├── runtime/              # Phase machine, Tool Loop, Retry, model logs
├── config/               # Configuration loading and models
├── context/              # Context builder, fact ledger, and budgets
├── tools/                # File, process, and validation tools
├── policy/               # Policy engine
├── approval/             # Approval service
├── sandbox/              # Native / Docker / WSL2 execution backends
├── security/             # Credentials and redaction
├── providers/            # Model provider adapters
├── languages/            # Python / C++ language adapters
├── correctness/          # Correctness verification
├── benchmark/            # Benchmark engine
├── workspace/            # Git worktrees, Apply, Rollback
├── storage/              # SQLite event store, projections, artifacts
└── resources/            # Resources and bundled VS Code extension
```

### `.algocode` Runtime Layout

After `algocode init`, the target project contains:

```text
.algocode/
├── config.yaml           # Project configuration
├── config.local.yaml     # Optional local overrides
├── contract.json         # Behavioral contract
├── task.txt              # Human-readable task summary
├── current-task.json     # Machine-readable task state
├── oracle/               # Correctness and contract tests
│   ├── check.py
│   ├── correctness.yaml
│   ├── contract_test.py
│   ├── contract_test.cpp
│   └── reference/
├── benchmarks/
│   └── benchmark.yaml
└── cache/
    ├── algocode.db       # Event store and projections
    ├── artifacts/
    ├── model-logs/
    ├── optimization-records/
    ├── worktrees/
    ├── repair-memory/
    └── rollbacks/
```

---

## Configuration and Data

### Providers

Supported providers:

```text
OpenAI
DeepSeek
OpenRouter
Kimi
Zhipu GLM
MiniMax
Anthropic Claude
Volcengine Doubao
Qwen
Custom OpenAI-compatible
Local Ollama / vLLM
```

### Reports

```bash
algocode report
```

This generates:

```text
report.md
```

in the project root. Internal artifacts remain under `.algocode/cache/artifacts`.

---

## Security and Data

- Algocode runs locally by default.
- API keys are stored in the local credential file and are not written into project configuration.
- Model call logs are redacted before being written under `.algocode/cache/model-logs`.
- Contract, Correctness, Benchmark, and Oracle files are protected files.
- Docker and WSL2 are optional isolation enhancements.
- Running on directories containing sensitive data, production credentials, or untrusted code is not recommended.

---

## Development

```bash
git clone https://github.com/acd2113/Algocode.git
cd Algocode
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

VS Code extension development:

```bash
cd extensions/vscode
npm install
npm run compile
```

Debugging:

```text
Press F5 -> Run Algocode Extension
```

Package the extension:

```bash
npx --yes @vscode/vsce package
```

---

## Publishing

Python package publishing is handled by GitHub Actions.

Release flow:

```bash
git tag v0.1.1
git push origin v0.1.1
```

The workflow builds and publishes:

```text
algocode_agent-0.1.1.tar.gz
algocode_agent-0.1.1-py3-none-any.whl
```

Users can install with:

```bash
python -m pip install algocode-agent
algocode vscode install
```

---

## Contributing

Issues and pull requests are welcome.

When reporting an issue, include:

- Operating system and Python version
- Algocode version
- Reproduction steps
- Expected and actual behavior
- Relevant logs or screenshots

Before submitting code:

```bash
python -m pytest
python -m ruff check .
```

---

## License

This project is licensed under the [MIT License](LICENSE).

---

<div align="center">

> **Algocode** — evidence for every optimization.

</div>
