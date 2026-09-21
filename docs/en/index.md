# Algocode Documentation

Algocode is a verifiable algorithm optimization agent for C++ and Python. It creates candidate implementations in isolated Git worktrees and validates them with three forms of evidence: Correctness, Contract, and Benchmark. The original project is modified only after the user explicitly runs `accept` and `apply`.

Starting with `v0.1.2`, Algocode supports multi-candidate search. When a direction shows significant positive evidence but has not yet met the acceptance threshold, it refines the same candidate. Benchmarks use multi-scale inputs, a fixed harness, paired tests, and robust variation to reduce the influence of scheduling noise.

Algocode provides both a CLI and a VS Code extension, for terminal automation and editor-based workflows.

This documentation is organized around the user journey:

- [Quick Start](getting-started/quickstart.md): complete the smallest end-to-end workflow.
- [Command Guide](commands/index.md): understand what each command does.
- [Complete Workflow](user-guide/workflow.md): follow the full path from initialization to rollback.
- [Core Concepts](concepts/architecture.md): understand the architecture and evidence model.
- [Reference](reference/cli.md): look up CLI options, configuration, schemas, and project layout.
- [Development](development/code-structure.md): contribute code, run tests, and release builds.
- [v0.1.2 Changelog](changelog/v0.1.2.md): review the latest additions and fixes.
