# 命令手册

本页按使用场景解释 Algocode 命令。完整参数、退出码和 JSON 字段见 [CLI 参考](../reference/cli.md)。

## 环境与模型

首次使用建议按顺序运行：

```bash
algocode doctor
algocode api
algocode test
```

| 命令 | 作用 | 使用场景 |
| --- | --- | --- |
| `algocode api` | 交互式配置 Provider、Base URL、模型和 API Key。 | 首次使用或切换服务商。 |
| `algocode test` | 发送最小请求验证模型连接。 | 配置完成后确认可用。 |
| `algocode doctor` | 检查 Python、Git、SQLite、Sandbox、C++ 编译器和数据目录。 | 安装后或命令运行异常时。 |
| `algocode model` | 切换当前项目默认模型。 | 临时或长期调整默认模型。 |

## 项目初始化

```bash
algocode init
algocode init --path ./demo --language python
```

| 命令 | 作用 | 使用场景 |
| --- | --- | --- |
| `algocode init` | 检测语言、生成 Contract、建立 Baseline 并创建初始 Task。 | 第一次把一个项目交给 Algocode。 |

初始化成功后通常会提示：

```text
Next: algocode optimize <task-id> --provider default --model default
```

## 优化主流程

```bash
algocode optimize
algocode retry
```

| 命令 | 作用 | 使用场景 |
| --- | --- | --- |
| `algocode optimize` | 从当前阶段继续运行完整阶段机。 | 初始化完成后开始优化，或继续未完成任务。 |
| `algocode retry` | 基于历史优化记录，从 `PLAN` 阶段重新规划。 | 上一次优化失败、收益不足或方向不理想。 |

`optimize` 支持 `--fake-provider` 做无 Key 联调，也支持 `--stop-after verify` 分阶段调试。

## 查看状态与证据

```bash
algocode status
algocode review
algocode diff
```

| 命令 | 作用 | 使用场景 |
| --- | --- | --- |
| `algocode status` | 查看任务、当前阶段、候选、证据和推荐下一步。 | 不确定当前处在哪个阶段。 |
| `algocode review` | 汇总 Correctness、Benchmark、Decision 和变更文件。 | 决定是否接受候选前。 |
| `algocode diff` | 查看候选相对基线的 Patch。 | 检查候选实际改了什么。 |

## 决策与应用

```bash
algocode accept <task-id> <candidate-id>
algocode apply
algocode rollback
```

| 命令 | 作用 | 使用场景 |
| --- | --- | --- |
| `algocode accept` | 记录一个候选已通过接受策略。 | 证据满足要求，决定采用。 |
| `algocode apply` | 将已接受候选应用到用户工作区。 | 接受后正式落地代码。 |
| `algocode rollback` | 回滚已应用候选。 | 应用后发现问题。 |

`accept` 只记录决策，`apply` 才修改用户工作区。

## 报告

```bash
algocode report <task-id>
algocode report <task-id> --markdown
```

| 命令 | 作用 | 使用场景 |
| --- | --- | --- |
| `algocode report` | 生成任务 JSON、Markdown 报告和根目录 `report.md`。 | 归档结果、分享评审或生成说明。 |

## 底层证据命令

```bash
algocode baseline <task-id>
algocode correctness run <task-id> --spec .algocode/oracle/correctness.yaml
algocode correctness replay <result-id>
algocode benchmark <task-id>
algocode experiment list <task-id>
algocode experiment show <experiment-id>
```

| 命令 | 作用 | 使用场景 |
| --- | --- | --- |
| `algocode baseline` | 单独建立任务基线。 | 手动重跑基线。 |
| `algocode correctness run` | 运行任务基线 Correctness。 | 手动检查正确性证据。 |
| `algocode correctness replay` | 重放已存储 Correctness。 | 复核历史结果。 |
| `algocode benchmark` | 运行基线或候选 Benchmark。 | 手动采集或比较性能。 |
| `algocode experiment list` | 列出 Benchmark Experiment。 | 查询历史实验。 |
| `algocode experiment show` | 查看一个 Experiment 及其结果和比较。 | 检查某次性能实验。 |

## 实体查询

```bash
algocode task create --objective "优化 XXX"
algocode task list
algocode task show <task-id>
algocode candidate create <task-id>
algocode candidate freeze <candidate-id>
algocode candidate list <task-id>
algocode candidate show <candidate-id>
```

| 命令 | 作用 | 使用场景 |
| --- | --- | --- |
| `algocode task create` | 创建任务。 | 手动建立优化任务。 |
| `algocode task list` | 列出本地任务。 | 查询已有任务。 |
| `algocode task show` | 查看一个任务。 | 检查任务状态和阶段。 |
| `algocode candidate create` | 创建候选 Worktree。 | 手动创建候选。 |
| `algocode candidate freeze` | 冻结候选并记录 Patch Hash。 | 固定候选内容。 |
| `algocode candidate list` | 列出任务候选。 | 查询候选列表。 |
| `algocode candidate show` | 查看一个候选。 | 检查候选状态和路径。 |

## 评估与验收

```bash
algocode eval run smoke
algocode eval run core --provider fake
algocode gate run
```

| 命令 | 作用 | 使用场景 |
| --- | --- | --- |
| `algocode eval run` | 运行 smoke、core、adversarial、recovery 或 A/B 比较。 | 项目自身质量回归。 |
| `algocode gate run` | 运行 P0 发布验收 Gate。 | 发布前做完整检查。 |

## VS Code 扩展

```bash
algocode vscode install
algocode vscode install --force
```

安装后，在 VS Code 中右键 `.py`、`.cpp`、`.cc` 或 `.cxx` 文件即可使用 `Algocode` 上下文菜单。
