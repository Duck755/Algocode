# 代码结构

仓库同时包含 Python CLI 和 VS Code 扩展两个入口。

```text
.
├── src/algocode/          # Python 包与 CLI
├── extensions/vscode/     # VS Code 扩展
├── tests/                 # pytest 测试
├── docs/                  # MkDocs 文档
├── pyproject.toml
└── mkdocs.yml
```

## Python 包

```text
src/algocode/
├── cli/                  # Typer 命令入口与输出封装
│   └── commands/         # 各命令实现
├── application/          # 用例编排、Task/Candidate/Baseline/Benchmark/Report 等服务
├── domain/               # 实体、值对象、枚举、事件
├── runtime/              # Agent 阶段机、Tool Loop、Gates、模型调用日志
├── config/               # 配置模型、加载、全局配置
├── context/              # 上下文构建、事实账本与预算
├── tools/                # Agent 工具注册表与内置工具
├── policy/               # 策略引擎
├── approval/             # 人工审批服务
├── sandbox/              # Native / Docker / WSL2 进程执行
├── security/             # 凭证、脱敏
├── providers/            # OpenAI-compatible、Anthropic、Fake Provider
├── languages/            # Python / C++ 语言适配
├── correctness/          # Correctness 规格与执行
├── benchmark/            # Benchmark 规格、Engine、Environment
├── acceptance/           # P0 发布验收 Gate
├── eval/                 # Agent 评估套件
├── workspace/            # Git Worktree、快照、Patch
├── storage/              # SQLite Event Store、Projection、Artifact Store
├── ports/                # 端口与类型边界
├── resources/            # 内置资源与 VS Code VSIX
├── observability/        # 可观测性
└── report/               # 报告辅助
```

## 关键模块职责

### `cli`

所有命令由 Typer 注册，统一使用 `emit_result` 输出。机器可读输出优先使用 `--json`，默认输出人类可读摘要。

### `application`

应用服务负责编排跨领域操作。例如：

- `baseline_service`：捕获基线。
- `candidate_service`：创建和冻结候选。
- `correctness_service`：运行 Correctness。
- `benchmark_service`：运行 Benchmark 和读取比较结果。
- `decision_service`：接受/拒绝候选。
- `apply_service`：Apply 与 Rollback。
- `report_service`：生成报告。

### `runtime`

核心 Agent 循环位于 `runtime/agent.py`。它按阶段执行模型轮次和工具调用，并写入 Phase Gate 事件。

### `domain`

领域枚举、实体和事件是持久化的核心。状态变更通过事件写入 Event Store，再投影到 SQLite 读模型。

### `storage`

SQLite 保存 Project、Task、Candidate、Baseline、Correctness、Benchmark、Decision 等读模型。大文件使用 File Artifact Store，以内容寻址方式保存。

### `workspace`

CLI 候选在 Git Worktree 中运行。Apply 会检查 Decision、stale 状态和 Patch，并创建 Rollback Manifest。

### `sandbox`

构建、Correctness 和 Benchmark 通过 Sandbox 执行。支持 Native、Docker、WSL2，并限制超时、内存、输出、PID、网络和根目录写权限。

## VS Code 扩展

```text
extensions/vscode/
├── package.json
├── tsconfig.json
└── src/
    └── extension.ts
```

扩展提供以下命令：

- `algocode.optimizeFile`：右键优化文件。
- `algocode.diff`：打开原生 Diff。
- `algocode.review`：查看证据。
- `algocode.apply`：应用候选。
- `algocode.rollback`：回滚候选。
- `algocode.api`、`algocode.test`、`algocode.model`：配置和测试模型。
- `algocode.init`、`algocode.optimize`、`algocode.status`、`algocode.report`：调用 CLI。

文件优化流程会在临时影子工作区执行 `algocode init` 和 `algocode optimize`，再打开 Diff。Apply 时把候选文件复制回原项目，并保存原文件备份供 Rollback 使用。

## 依赖方向

整体依赖应尽量向内指向 `domain` 和 `ports`。CLI、VS Code 扩展和持久化属于外部适配层，不直接实现领域规则。
