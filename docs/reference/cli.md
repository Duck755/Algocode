# CLI 参考

本页记录 CLI 参数、默认值和 JSON 输出要点。日常使用场景和示例见 [命令手册](../commands/index.md)。

## 通用约定

多数命令支持：

| 选项 | 说明 |
| --- | --- |
| `--json` | 输出机器可读 JSON。 |
| `--quiet` | 抑制非必要的人类可读输出。 |
| `--verbose` | 向 stderr 输出诊断信息。 |
| `--no-color` | 禁用 ANSI 颜色。 |
| `--data-dir <path>` | 覆盖 Algocode 数据目录。 |
| `--progress/--no-progress` | 强制开启或关闭实时阶段进度（默认仅在 TTY 下开启）。 |

需要指定当前任务时，很多命令可省略 `task_id`，默认读取 `.algocode/current-task.json`。

```bash
algocode --version
algocode --help
algocode <command> --help
```

## 环境与模型

### `algocode api`

交互式选择 Provider、Base URL、模型 ID、上下文窗口，并保存 API Key。

```bash
algocode api
algocode api --json
```

API Key 不写入项目配置，保存到本机凭证文件。

### `algocode test`

发送最小请求验证模型连接。

```bash
algocode test
algocode test --provider openai --model openai/gpt-5-mini
```

### `algocode doctor`

检查 Python、Git、SQLite、Sandbox、C++ 编译器和数据目录。

```bash
algocode doctor
algocode doctor --json
```

### `algocode model`

切换当前项目默认模型。

命令会从当前 Provider 的上游 `/models` 接口获取可用模型，并与本地已配置模型合并展示。上游不可用时自动回退到本地配置，并保留手动输入模型 ID。

```bash
algocode model
algocode model --provider openai
```

## 初始化

### `algocode init`

检测项目、生成契约、建立基线和初始 Task。

```bash
algocode init
algocode init --path ./demo --language python
algocode init --no-bootstrap --no-write-config
algocode init --yes
```

| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| `--path` | `.` | 项目目录。 |
| `--language` | `auto` | `auto`、`cpp` 或 `python`。 |
| `--objective` | 空 | 初始任务目标。 |
| `--bootstrap/--no-bootstrap` | `bootstrap` | 是否创建 Git/config 前提并执行首次基线。 |
| `--write-config/--no-write-config` | `write-config` | 是否生成 `.algocode/config.yaml`。 |
| `--yes` / `-y` | `false` | 跳过运行前的确认提示。 |
| `--progress/--no-progress` | TTY 自动 | 强制显示或隐藏实时阶段进度。 |

## 优化主流程

### `algocode optimize`

从当前阶段继续运行阶段机。

```bash
algocode optimize
algocode optimize <task-id>
algocode optimize --fake-provider
algocode optimize --max-steps 20 --max-tool-calls 40 --stop-after verify
```

| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| `--fake-provider` | 关 | 使用确定性 Fake Provider，不需要 API Key。 |
| `--provider` | 项目默认 | 覆盖 Provider。 |
| `--model` | 项目默认 | 覆盖模型。 |
| `--candidate-workspace` | 空 | 指定候选 Worktree。 |
| `--candidate-id` | 空 | 指定候选。 |
| `--max-steps` | 配置值 | 每阶段最大模型轮次。 |
| `--max-tool-calls` | 配置值 | 每阶段最大工具调用数。 |
| `--stop-after` | `report` | 在指定阶段后停止。 |
| `--progress/--no-progress` | TTY 自动 | 强制显示或隐藏实时进度日志。 |

运行体验：

- 运行中在 `stderr` 保留一行原地刷新的进度日志，动作或阶段结束时定格为永久日志行并追加 `✔` 或 `✖`。
- 阶段名与工具名使用中文，`[algocode]` 前缀便于在混合日志中筛选。
- 非 TTY 只输出定格行且不写控制字符；`--json`、`--quiet` 完全关闭进度。

```text
[algocode] 分析 | 1/10 | 第 2 轮 | 读取必需文件 成功 | 工具 1 | 12s ✔
[algocode] 分析 | 1/10 | 完成 · 2 轮推理 · 2 次工具调用 | 1m04s ✔
[algocode] 校验 | 6/10 | 第 3 轮 | 运行正确性测试 失败 | 工具 9 | 10.0s ✖
```

结束时的摘要行与证据链：

```text
optimize · completed · 耗时 4m04s
┌─ 证据链 ────────────────────────────────────────────────────────────────────────────────────────────┐
│   任务    task:task_9dc       completed                                                             │
│   耗时    4m04s               14 轮推理 · 16 次工具调用                                             │
│   阶段    10 个               分析 → 基线 → 方案 → 建候选 → 实现 → 校验 → 基准 → 对比 → 决策 → 报告 │
│   候选    candidate:cand_5db  selected                                                              │
│   正确性  run:corr_364        passed                                                                │
│   基准    benchmark:bench_23  valid=True                                                            │
│   提升    +3.95%              3.222 → 3.095 · p=0.006                                               │
│   决策    accepted            correctness and benchmark evidence passed acceptance policy           │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

当 Benchmark 使用配对样本时，证据链和 JSON 会包含配对置信区间和 MAD 鲁棒波动。原始标准差不会参与 Decision，也不会产生用户可见 warning。

交互式终端下还会输出下一步菜单（查看候选改动 / 应用候选 / 生成任务报告 / 重新规划重试）。

### `algocode retry`

基于历史优化记录，从 `PLAN` 阶段重新规划。

```bash
algocode retry
algocode retry <task-id> --fake-provider
```

没有优化记录时命令会失败。`algocode retry` 与 `algocode optimize` 共享进度日志、证据链和下一步菜单，同样支持 `--progress/--no-progress`。

## 状态与证据

### `algocode status`

查看任务、当前阶段、候选、Correctness、Benchmark、Decision 和推荐下一步。

```bash
algocode status
algocode status --candidate-id <candidate-id> --json
```

JSON 重点字段：

```text
taskId
status
currentPhase
progress.phase / turn / toolCalls / activeTool / lastTool
candidateId
correctness.status
benchmark.valid
benchmark.improvementPercent
benchmark.confidenceInterval
benchmark.qualityWarnings
decision.outcome
nextCommand
```

### `algocode review`

汇总候选的 Correctness、Benchmark、Decision 和变更文件。

```bash
algocode review
algocode review --candidate-id <candidate-id>
```

### `algocode diff`

打印候选 Patch。JSON 模式下包含 `patch` 和 `untracked`。

```bash
algocode diff
algocode diff --json
```

## 决策与应用

### `algocode accept`

记录接受决策，不修改用户工作区。

```bash
algocode accept <task-id> <candidate-id> --reason "evidence verified"
```

### `algocode apply`

将已接受候选应用到用户工作区。CLI 会检查接受决策、stale 状态和 Patch，再执行应用。

```bash
algocode apply
algocode apply <task-id> <candidate-id>
```

如果尚未 `accept`，CLI 会先尝试记录接受决策。

### `algocode rollback`

回滚已应用候选。

```bash
algocode rollback
algocode rollback <task-id> <candidate-id>
```

## 报告

### `algocode report`

生成并持久化任务报告。

```bash
algocode report <task-id>
algocode report <task-id> --markdown
algocode report <task-id> --json
```

不能同时使用 `--markdown` 和 `--json`。

报告产物包括：

```text
.algocode/cache/artifacts/<report-json>
.algocode/cache/artifacts/<report-md>
report.md
```

## 底层证据命令

### `algocode baseline`

单独捕获任务基线。

```bash
algocode baseline <task-id>
algocode baseline <task-id> --language python --build-command "python test.py" --timeout 180
```

### `algocode correctness run`

运行任务基线 Correctness。

```bash
algocode correctness run <task-id> --spec .algocode/oracle/correctness.yaml
```

退出码：失败时为 `4`。

### `algocode correctness replay`

重放已存储 Correctness。

```bash
algocode correctness replay <result-id>
```

### `algocode benchmark`

运行 Baseline、Candidate 或查看已存储 Benchmark。

```bash
algocode benchmark <task-id>
algocode benchmark <task-id> --candidate-id <candidate-id>
algocode benchmark <task-id> --show <benchmark-id>
```

### `algocode experiment list`

列出 Benchmark Experiment。

```bash
algocode experiment list
algocode experiment list <task-id> --status completed --limit 20
```

### `algocode experiment show`

查看一个 Experiment 及其结果和比较产物。

```bash
algocode experiment show <experiment-id>
```

## 实体查询

### `algocode task`

```bash
algocode task create --objective "优化 XXX" --project-root .
algocode task list
algocode task show <task-id>
```

### `algocode candidate`

```bash
algocode candidate create <task-id>
algocode candidate freeze <candidate-id>
algocode candidate list <task-id>
algocode candidate show <candidate-id>
```

`candidate create` 支持 `--base-revision` 覆盖基线修订。

## 评估与验收

### `algocode gate run`

运行 P0 发布验收 Gate。

```bash
algocode gate run
algocode gate run --skip-tests --report-dir ./acceptance
```

### `algocode eval run`

运行 smoke、core、adversarial 或 recovery 评估套件。

```bash
algocode eval run smoke
algocode eval run core --provider fake --repeat 3
algocode eval run smoke --ab-baseline fake --ab-candidate scripted
```

## VS Code 扩展

### `algocode vscode install`

安装内置 VS Code 扩展。

```bash
algocode vscode install
algocode vscode install --force
algocode vscode install --code "/path/to/code"
```
