# Algocode

Algocode is a local-first algorithm optimization agent for C++ and Python.

The engineering design is documented in `docs/design/09-algocode-engineering-design.md`.

## Development

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python -m algocode doctor
```

On macOS or Linux, use `.venv/bin/python` instead of `.venv/Scripts/python`.

## Basic workflow

```bash
algocode init --path . --json
algocode task create --objective "Optimize the hot path" --json
algocode baseline <task-id> --json
algocode correctness run <task-id> --spec correctness.yaml --json
algocode correctness replay <correctness-result-id> --json
algocode benchmark <task-id> --spec benchmark.yaml --json
algocode benchmark <task-id> --show <benchmark-run-id>
algocode optimize <task-id> --fake-provider --json
algocode optimize <task-id> --provider default --model default --json
algocode candidate create <task-id> --json
algocode candidate freeze <candidate-id> --json
algocode accept <task-id> <candidate-id> --json
algocode report <task-id> --json
algocode apply <task-id> <candidate-id> --json
algocode rollback <task-id> <candidate-id> --json
algocode eval run smoke --provider fake --json
algocode eval run core --provider auto --json
algocode eval run smoke --ab-baseline fake --ab-candidate fake --json
algocode gate run --json
```

Baseline workspaces are created as detached Git worktrees. The user working tree is not
modified during project registration or baseline capture.
