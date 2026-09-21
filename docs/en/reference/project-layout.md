# Project Layout

`algocode init` creates `.algocode/` in the project root. It contains configuration, contracts, verification specifications, and cache data. `cache/` is runtime data and should not be edited manually.

## Standard Layout

```text
.algocode/
├── config.yaml
├── config.local.yaml
├── contract.json
├── task.txt
├── current-task.json
├── oracle/
│   ├── check.py
│   ├── correctness.yaml
│   ├── contract_test.py
│   ├── contract_test.cpp
│   └── reference/
├── benchmarks/
│   └── benchmark.yaml
└── cache/
    ├── algocode.db
    ├── artifacts/
    ├── model-logs/
    ├── optimization-records/
    ├── worktrees/
    ├── repair-memory/
    └── rollbacks/
```

For compatibility with older versions, `.algocode.yaml`, `.algocode.local.yaml`, `oracle/`, and `benchmarks/` in the project root are also recognized.

## Files and Directories

| Path | Readable | Editable | Description |
| --- | --- | --- | --- |
| `.algocode/config.yaml` | yes | yes | Project configuration. |
| `.algocode/config.local.yaml` | yes | yes | Local overrides for machine-specific settings. |
| `.algocode/contract.json` | yes | careful | Model-generated Project Contract used for verification. |
| `.algocode/task.txt` | yes | not recommended | Current task summary. |
| `.algocode/current-task.json` | yes | not recommended | Current task ID and completed phases. |
| `.algocode/oracle/correctness.yaml` | yes | yes | Correctness specification. |
| `.algocode/oracle/check.py` | yes | careful | Correctness entry point. |
| `.algocode/oracle/contract_test.py` | yes | careful | Python Contract Test. |
| `.algocode/oracle/contract_test.cpp` | yes | careful | C++ Contract Test. |
| `.algocode/oracle/reference/` | yes | no | Oracle or reference implementation. |
| `.algocode/benchmarks/benchmark.yaml` | yes | yes | Benchmark specification. |
| `.algocode/cache/algocode.db` | indirect | no | SQLite Event Store and projections. |
| `.algocode/cache/artifacts/` | yes | no | Correctness, Benchmark, Patch, and Report artifacts. |
| `.algocode/cache/model-logs/` | yes | no | Redacted model-call logs. |
| `.algocode/cache/optimization-records/` | yes | no | Historical records used by `retry`. |
| `.algocode/cache/worktrees/` | yes | no | Candidate Git worktrees. |
| `.algocode/cache/repair-memory/` | yes | no | Repair context. |
| `.algocode/cache/rollbacks/` | yes | no | Apply and rollback manifests. |

## Protected Files

The following paths are protected by Correctness by default:

```text
tests/
.algocode/oracle/
.algocode/benchmarks/
.algocode/config.yaml
.algocode/contract.json
oracle/
generator/
hidden-tests/
benchmarks/
.algocode.yaml
```

Extend the list with `correctness.protectedFiles` in `.algocode/config.yaml`.
