# 完整工作流

Algocode 不是一个“从输入直接到输出”的单线流程。它按阶段推进，并在每个关键节点做门控和证据检查。失败时可以停在当前阶段、更换候选或基于历史记录重试。

## 1. 初始化：`algocode init`

`init` 是项目进入 Algocode 前的准备阶段，不直接优化源码。

它会：

1. 检测或初始化 Git 仓库。
2. 检测主语言：`auto`、`cpp` 或 `python`。
3. 生成 `.algocode/config.yaml`。
4. 通过模型发现 Project Contract，并生成 Contract Test。
5. 创建初始 Task。
6. 捕获 Baseline。
7. 尝试运行 Correctness 和 Baseline Benchmark。

输出包括：

```text
.algocode/config.yaml
.algocode/contract.json
.algocode/oracle/
.algocode/benchmarks/benchmark.yaml
.algocode/current-task.json
```

如果初始化已经成功，后续重复 `algocode init` 不会改变优化流程，而是重新检查项目。

## 2. Analyze：只读分析

Agent 在 Analyze 阶段只读取项目，不修改文件。

它需要形成：

- 公开 API 和入口。
- 状态变化、错误行为和边界条件。
- 可观察输出和确定性要求。
- 热点、复杂度来源和性能目标。
- 优化候选方向。

该阶段主要工具为 `list_files`、`read_file`、`read_required_files`、`search_code` 等。

## 3. Baseline：建立比较基准

Baseline 是后续所有证据的参照点。它记录：

- 基线 Git Revision。
- 源码快照 Hash。
- 环境 Hash。
- 构建产物。

Plan 和 Generate Candidate 都必须以 Baseline 为前提。若没有 Baseline，后续阶段会被 Gate 阻止。

## 4. Plan：生成优化计划

Agent 根据 Analysis 和 Baseline 提交 `OptimizationPlan`，包括：

- 优化策略。
- 目标文件。
- 风险与约束。
- 验证方式。
- 预期收益。

`algocode retry` 会在该阶段注入历史优化记录，避免重复已经失败的方向。

## 5. Generate Candidate：创建隔离候选

CLI 会从 Baseline 创建独立 Git Worktree，Agent 不会直接修改用户工作区。

VS Code 扩展则创建临时影子工作区。无论哪种入口，候选都是独立副本。

## 6. Implement：实现优化

Agent 在候选工作区中修改代码。允许工具包括：

- `apply_patch`
- `write_file`
- `edit_file`
- `run_candidate_check`
- `get_candidate_diff`

这个阶段仍可能失败。Agent 可以反复检查和修正候选，直到进入 Verify。

## 7. Verify：正确性与契约

Verify 是 Benchmark 的前置 Gate。候选必须先通过：

1. Build。
2. Correctness。
3. Contract。

只要有一项失败，候选就不会进入 Benchmark。

失败时常见路径：

- 候选被标记为 `rejected`。
- Agent 创建新的候选，重新进入 Implement。
- 任务停在 `waiting_user`，用户可通过 `algocode status` 查看原因。

## 8. Benchmark：性能测量

Correctness 和 Contract 通过后，Algocode 才运行 Benchmark。

Benchmark 会：

- 交错运行 Baseline 与 Candidate。
- 记录 Warmup、Repeats、Median、Mean、Stddev 和 Variation。
- 使用 Environment Hash 和 Comparison Key 避免错误比较。

该阶段要求至少一个完成的候选 Benchmark，且存在 Comparison Result，否则 Compare 阶段会被 Gate 阻止。

## 9. Compare：性能比较

Compare 将 Baseline 与 Candidate 的 Median 和 Improvement 汇总为 Comparison Result。

可通过以下命令查看：

```bash
algocode status
algocode review
algocode experiment show <experiment-id>
```

## 10. Decide：接受策略

接受策略根据配置判断候选是否可接受，典型条件包括：

- `requireCorrectness`。
- `minMedianImprovementPercent`。
- 峰值内存回退上限。
- 编译时间回退上限。
- 样本波动上限。

即使 Decide 阶段给出方向，最终仍需人工 Review 和 `accept`。

## 11. Review、Accept 与 Apply

```bash
algocode review
algocode diff
algocode accept <task-id> <candidate-id>
algocode apply
```

`accept` 只记录决策，不会写源码。

`apply` 才把候选 Patch 应用到用户工作区。CLI 会检查：

- Decision 是否为 `accepted`。
- 候选是否已经冻结。
- 用户工作区是否发生 stale 变化。
- 是否存在可用的 Rollback Manifest。

## 12. Rollback：回滚

Apply 后若发现问题：

```bash
algocode rollback
```

CLI 使用 Apply 时保存的 Manifest 恢复原工作区。VS Code 扩展则使用文件备份恢复。

## 13. Report：生成报告

```bash
algocode report <task-id>
```

生成：

```text
.algocode/cache/artifacts/<report-json>
.algocode/cache/artifacts/<report-md>
report.md
```

报告适合归档、分享评审和记录最终证据。

## 阶段门控

每个阶段进入前都会检查前置条件。例如：

| 阶段 | 前置条件 |
| --- | --- |
| Plan / Generate Candidate | 必须已有 Baseline。 |
| Implement / Verify / Benchmark / Compare / Decide | 必须已有 Candidate。 |
| Benchmark / Compare / Decide | Candidate Correctness 必须已通过。 |
| Compare / Decide | 必须已有 Candidate Benchmark Comparison。 |

Gate 失败时任务会停在 `waiting_user`，推荐下一步通常是 `algocode optimize` 或 `algocode status`。

## 阶段与命令对应

| 阶段 | CLI 命令 | 主要产物 |
| --- | --- | --- |
| 初始化 | `algocode init` | Contract、Task、Baseline |
| 分析 | `algocode optimize` | Analysis Report |
| 基线 | `algocode optimize` / `algocode baseline` | Baseline Snapshot |
| 计划 | `algocode optimize` / `algocode retry` | Optimization Plan |
| 候选生成 | `algocode optimize` | Candidate Worktree |
| 实现 | `algocode optimize` | Candidate Patch |
| 验证 | `algocode optimize` / `algocode correctness run` | Correctness / Contract Result |
| Benchmark | `algocode optimize` / `algocode benchmark` | Benchmark Experiment |
| 对比 | `algocode review` / `algocode status` | Comparison Result |
| 决策 | `algocode accept` | Decision |
| 应用 | `algocode apply` | Applied Workspace / Rollback Manifest |
| 回滚 | `algocode rollback` | 恢复原工作区 |
| 报告 | `algocode report` | JSON / Markdown / `report.md` |

## 失败与重试路径

### 1. 阶段 Gate 未通过

`algocode optimize` 会返回 `waiting_user` 并给出原因。此时先运行：

```bash
algocode status
```

补齐前置证据后再次运行 `algocode optimize`。

### 2. Verify 失败

候选被标记为 `rejected`。下一次 `algocode optimize` 可能创建新候选并重新实现。

### 3. Benchmark 无效

检查：

```bash
algocode benchmark <task-id> --show <benchmark-id>
algocode experiment show <experiment-id>
```

确认 Baseline 与 Candidate 的 Comparison Key 是否一致。

### 4. 收益不足或方向错误

使用历史优化记录重新规划：

```bash
algocode retry
```

### 5. Apply 失败

常见原因是候选未接受、工作区 stale 或 Patch 状态不一致。不要直接手工清理 `.algocode/cache/rollbacks/`，先查看 `algocode status` 和 `algocode review`。

## CLI 与 VS Code 的差异

- CLI 默认使用 Git Worktree 隔离候选，并在 Apply 时检查 Decision、stale 状态和 Patch。
- VS Code 扩展在临时影子工作区运行优化，Apply 使用文件备份和运行记录完成复制与回滚。
- 两者都强调先查看 Diff 和 Review，再执行 Apply。
