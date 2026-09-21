# Testing

## Environment Setup

Use a virtual environment and install development dependencies:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Running Tests

```bash
.venv/bin/python -m pytest
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run a directory or file:

```bash
.venv/bin/python -m pytest tests/unit
.venv/bin/python -m pytest tests/unit/test_vscode_command.py
```

## Test Types

| Directory | Purpose |
| --- | --- |
| `tests/unit` | Unit tests for config, domain, services, commands, providers, and sandbox. |
| `tests/integration` | End-to-end flows, CLI, Report/Apply, and sandbox integration. |
| `tests/contract` | Storage and projection contract tests. |

## Common Test Strategies

### Fake Provider

Many phase tests use `DeterministicFakeProvider` to avoid real API keys. The CLI also supports:

```bash
algocode optimize --fake-provider
```

### Git Fixtures

Tests involving Baseline, Candidate, Apply, and Rollback create temporary Git repositories and worktrees to exercise real Git state changes.

### Environment Dependencies

Normal tests do not require Docker. Docker and WSL2 tests skip or degrade to environment checks when those backends are unavailable.

## Code Checks

```bash
.venv/bin/python -m ruff check .
```

Before committing, run both:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

## CI

GitHub Actions handles testing, building, and publishing. At minimum, run the targeted unit tests and `ruff` before local commits.
