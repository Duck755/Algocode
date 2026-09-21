# Quick Start

## Fastest CLI Path

Run these commands from the root of the project you want to optimize:

```bash
algocode init
algocode optimize
```

Then inspect the status and evidence:

```bash
algocode status
algocode review
algocode diff
```

By default, `optimize` can try multiple candidates. If a direction has significant positive evidence but does not yet meet the acceptance criteria, Algocode can refine the same candidate. Every refinement must pass Correctness, Contract, and Benchmark again.

After reviewing the candidate, accept and apply it:

```bash
algocode accept <task-id> <candidate-id>
algocode apply
```

Roll back when needed:

```bash
algocode rollback
```

## Fastest VS Code Path

Install the extension:

```bash
algocode vscode install
```

Then, in VS Code:

1. Open a C++ or Python project.
2. Right-click a `.py`, `.cpp`, `.cc`, or `.cxx` file in the explorer or editor.
3. Select `Algocode -> Optimize`.
4. Inspect the native diff and review output.
5. Select `Apply All`, or use `Rollback` later if needed.

## Suggested Reading Order

1. Read the [Complete Workflow](../user-guide/workflow.md) to understand each phase.
2. Use the [Command Guide](../commands/index.md) when you need the right command.
3. Read the [Evidence Model](../concepts/evidence-model.md) to understand why Algocode is safe.
