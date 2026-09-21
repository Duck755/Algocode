# Installation and Environment Check

## Requirements

- Python 3.11 or newer.
- Git.
- `g++` or `clang++` with C++17 support when optimizing C++ projects.
- At least one OpenAI-compatible or Anthropic provider when using a real model.
- Docker or WSL2 is optional and provides stronger isolation.

## Installation

### Install from PyPI

```bash
python -m pip install algocode-agent
algocode doctor
```

### Install from Source

```powershell
python -m venv .venv
python -m pip install -e ".[dev]"
python -m algocode doctor
```

macOS / Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m algocode doctor
```

If the `algocode` command is not available, use `python -m algocode` from the matching virtual environment.

### Install the VS Code Extension

The Python package includes a VS Code extension:

```bash
python -m algocode vscode install
```

You can also build it from the extension source directory:

```bash
cd extensions/vscode
npm install
npm run compile
npx --yes @vscode/vsce package
```

## Check the Environment

```bash
algocode doctor
```

`doctor` checks Python, Git, SQLite, the sandbox, and the optional C++ compiler.

## Configure a Model Provider

```bash
algocode api
algocode test
```

`api` selects the provider and model and stores the API key. `test` sends a minimal request to verify the connection.
