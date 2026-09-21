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

如果入口程序从 stdin 读入，模型在发现契约时会同时给出一族递增规模的输入，
runtime 校验后写入 `.algocode/benchmarks/benchmark.yaml` 的 `inputs`（每个带 `id`、
`size` 和 `input`）。不足两个合法规模时不会写入；如果多规模基准跑不通，
bootstrap 会自动回退到单输入并重试，不会因此失败。

如果契约里带了 `benchmarkHarness`，runtime 会为 Python 写入
`.algocode/benchmarks/harness.py`，为单文件 C++ 项目写入并编译
`.algocode/benchmarks/harness.cpp`。随后用两次探测校准一个**固定**重复轮数
（目标约 0.5 秒），并改写 `run_command`。轮数固定而非自适应，否则每次测量做的
功不同，反而引入新的方差。没有 harness 时保持原样。

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

它还需要产出结构化的问题结构分析（`problemStructure`）和复杂度基线（`complexityBaseline`）：

- 输入模型、数据分布、查询/更新比例、单调性与约束边界。
- 操作的代数性质（可结合、可交换、幂等），这决定了能否分块、并行或预处理。
- 当前实现复杂度、该问题的已知最优复杂度、两者差距及理由。

并给出至少 3 个候选算法/数据结构（`algorithmCandidates`），每个带适用条件与预期收益。
这些字段为空时，分析报告会被判为无效并重新生成。

该阶段主要工具为 `list_files`、`read_file`、`read_required_files`、`search_code` 等。

## 3. Baseline：建立比较基准

Baseline 是后续所有证据的参照点。它记录：

- 基线 Git Revision。
- 源码快照 Hash。
- 环境 Hash。
- 构建产物。

Plan 和 Generate Candidate 都必须以 Baseline 为前提。若没有 Baseline，后续阶段会被 Gate 阻止。

## 4. Plan：生成优化计划

Agent 先做只读侦察：用 `read_file`、`search_code`、`list_files` 查看 AnalysisReport
中 profile 热点对应的真实源码，不修改任何文件。然后根据 Analysis 和 Baseline 提交
`OptimizationPlan`，包括：

- 优化策略。
- 目标文件。
- 风险与约束。
- 验证方式。
- 预期收益。

计划必须从 `problemStructure` 和 `complexityBaseline` 出发，因此额外包含：

- `algorithm`：拟采用的算法或数据结构。
- `complexityBefore` / `complexityAfter`：改动前与改动后的复杂度。
- `whyFaster`：为什么它优于当前选择。
- `structureRef`：该判断依据的问题结构字段。

`algocode retry` 会在该阶段注入历史优化记录，避免重复已经失败的方向。

## 5. Generate Candidate：创建隔离候选

CLI 会从 Baseline 创建独立 Git Worktree，Agent 不会直接修改用户工作区。

VS Code 扩展则创建临时影子工作区。无论哪种入口，候选都是独立副本。

## 6. Implement：实现优化

Agent 在候选工作区中修改代码。允许工具包括：

每个阶段只向模型暴露阶段工具白名单中的工具，并注入剩余模型轮次、剩余工具调用数和候选自检要求。实现阶段可以直接使用 `list_files`、`search_code`、`read_file` 和编辑工具，但不会看到 Benchmark、Decision 等不属于该阶段的工具。

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

Correctness 包含两类 case：

- 契约基准输出（`primary-output`）：固定期望，来自初始化时的运行结果。
- 参考实现交叉验证（`oracle-*`）：复用已校验的规模输入，现场跑
  `.algocode/oracle/reference/` 下未被修改的入口副本得到期望输出。

第二类让“换了算法”的候选必须在小规模输入上与原始实现逐字节一致，而不只是通过固定用例。
参考实现副本位于保护目录内，候选无法修改；若副本无法运行，初始化会自动回退到只有契约 case 的规格。

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
- 优先按同一 input + repeat 配对计算提升、bootstrap 置信区间和置换检验。
- 使用 MAD 鲁棒波动判定样本质量；原始标准差不再参与用户可见警告或决策。

如果 `benchmark.yaml` 的 `inputs` 为不同输入声明了 `size`，每个输入会单独统计，
整体改善取各输入改善的中位数，波动取最差的单输入波动。

该阶段要求至少一个完成的候选 Benchmark，且存在 Comparison Result，否则 Compare 阶段会被 Gate 阻止。

## 9. Compare：性能比较

Compare 将 Baseline 与 Candidate 的 Median 和 Improvement 汇总为 Comparison Result。

提升以配对相对改善的中位数表示；显著性使用配对置换检验，置信区间使用配对 bootstrap。
这能避免单次系统调度尖峰把一个整体提升数十个百分点、p 值也很小的结果错误判为无效。

当存在至少 3 个带 `size` 的输入时，还会对 `log(时间)` 与 `log(规模)` 做最小二乘
拟合，得到 `growthBaseline`、`growthCandidate`、`growthDelta` 和 `growthPoints`。
斜率下降意味着渐进复杂度下降——即使候选在最小输入上更慢，也能被识别为算法级改进。

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
- `minGrowthExponentReduction`（默认 0.5）与 `growthPointsRequired`（默认 3）：若斜率下降达到阈值，
  可豁免常数提升阈值，但仍必须通过正确性与统计显著性检查。
- 峰值内存回退上限。
- 编译时间回退上限。
- 样本波动上限。
- 配对提升置信区间不得跨过 0。

即使 Decide 阶段给出方向，最终仍需人工 Review 和 `accept`。

决策不是 `accepted` 时，会再判断一次方向是否值得继续：

- 如果这一轮有**统计显著**的改善（或拟合斜率下降），Algocode 在同一个候选上再跑一轮
  Implement → Verify → Benchmark → Compare → Decide，最多 `maxRefinements` 轮（默认 2）。
  每一轮仍然要完整通过正确性、参考实现交叉验证和基准有效性。
- 如果没有可测量的改善（退步或只有噪声），则改为创建新候选继续搜索。

也就是说：方向对了就继续挖，方向不对就换路。

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
