# Release

## Version Number

The version comes from:

```text
src/algocode/__init__.py
```

The Python package and VS Code extension should use the same version. The current version is `0.1.2`.

## Pre-Release Checks

Run the release acceptance gate first:

```bash
algocode gate run
```

The gate checks code structure, tests, key files, and release requirements. To skip rerunning tests:

```bash
algocode gate run --skip-tests
```

Also run tests and linting:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

## Build the Python Package

```bash
.venv/bin/python -m build
```

Artifacts:

```text
dist/algocode_agent-<version>.tar.gz
dist/algocode_agent-<version>-py3-none-any.whl
```

Local install check:

```bash
.venv/bin/python -m pip install dist/algocode_agent-<version>-py3-none-any.whl
algocode doctor
```

## Publish the Python Package

GitHub Actions builds and publishes when a version tag is pushed:

```bash
git tag v0.1.2
git push origin v0.1.2
```

Users can then install:

```bash
python -m pip install algocode-agent
```

## Build the VS Code Extension

```bash
cd extensions/vscode
npm install
npm run compile
npx --yes @vscode/vsce package
```

The generated VSIX is bundled into Python package resources and can be installed with:

```bash
algocode vscode install
```

## Release Checklist

1. Update `src/algocode/__init__.py`.
2. Update `extensions/vscode/package.json`.
3. Update version references in documentation.
4. Run tests, `ruff`, and `algocode gate run`.
5. Build the Python package and VSIX.
6. Push the version tag and let CI publish.
