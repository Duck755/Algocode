# 项目目录

`algocode init` 会在项目根目录生成 `.algocode/`。该目录同时包含配置、契约、验证规格和缓存；`cache/` 属于运行时数据，不建议手工修改。

## 标准布局

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

为兼容早期版本，项目根目录下的 `.algocode.yaml`、`.algocode.local.yaml`、`oracle/` 和 `benchmarks/` 也会被识别。

## 文件与目录说明

| 路径 | 可读 | 可手工编辑 | 说明 |
| --- | --- | --- | --- |
| `.algocode/config.yaml` | 是 | 是 | 项目级配置。 |
| `.algocode/config.local.yaml` | 是 | 是 | 本地覆盖配置，适合保存个人环境差异。 |
| `.algocode/contract.json` | 是 | 谨慎 | 模型生成的 Project Contract，是验证依据。 |
| `.algocode/task.txt` | 是 | 不建议 | 当前任务摘要。 |
| `.algocode/current-task.json` | 是 | 不建议 | 当前任务 ID 和已完成阶段，CLI 用它解析当前任务。 |
| `.algocode/oracle/correctness.yaml` | 是 | 是 | Correctness 规格。 |
| `.algocode/oracle/check.py` | 是 | 谨慎 | Correctness 运行入口。 |
| `.algocode/oracle/contract_test.py` | 是 | 谨慎 | Python Contract Test。 |
| `.algocode/oracle/contract_test.cpp` | 是 | 谨慎 | C++ Contract Test。 |
| `.algocode/oracle/reference/` | 是 | 否 | Oracle 或参考实现。 |
| `.algocode/benchmarks/benchmark.yaml` | 是 | 是 | Benchmark 规格。 |
| `.algocode/cache/algocode.db` | 间接 | 否 | SQLite Event Store 与 Projection。 |
| `.algocode/cache/artifacts/` | 是 | 否 | Correctness、Benchmark、Patch、Report 等大体积产物。 |
| `.algocode/cache/model-logs/` | 是 | 否 | 脱敏后的模型调用日志。 |
| `.algocode/cache/optimization-records/` | 是 | 否 | `retry` 使用的历史优化记录。 |
| `.algocode/cache/worktrees/` | 是 | 否 | Git Worktree 候选工作区。 |
| `.algocode/cache/repair-memory/` | 是 | 否 | 修复记忆。 |
| `.algocode/cache/rollbacks/` | 是 | 否 | Apply/Rollback Manifest 与备份。 |

## 保护文件

以下路径默认属于 Correctness 保护文件，Agent 不应修改：

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

可以在 `.algocode/config.yaml` 的 `correctness.protectedFiles` 中扩展该列表。
