# Algocode 项目结构说明

本文档完整描述 Algocode 仓库的源码、测试、VS Code 扩展、构建配置和运行时数据布局。

---

## 顶层目录

```text
Algocode/
├── .github/
│   └── workflows/
│       ├── publish.yml            # 主 PyPI 发布工作流
│       └── python-publish.yml     # 备用/历史 Python 发布工作流
├── docker/
│   └── sandbox.Dockerfile         # Docker 沙箱镜像定义
├── docs/
│   └── picture/
│       ├── algocode_icon.jpg      # README/文档图标 JPG
│       └── algocode_icon.png      # README/文档图标 PNG
├── extensions/
│   └── vscode/                    # VS Code 扩展源码与安装包
├── src/
│   └── algocode/                  # Python 主包
├── tests/                         # 单元、集成、契约测试
├── img.png                        # README 使用示例图片
├── img_1.png                      # README Provider 示例图片
├── img_2.png                      # README init 示例图片
├── img_3.png                      # README optimize 示例图片
├── LICENSE                        # MIT License
├── README.md                      # 项目主说明
├── PROJECT_STRUCTURE.md           # 本文档
├── pyproject.toml                 # Python 包元数据、依赖、工具配置
└── mkdocs.yml                     # 文档站点配置
```

---

## Python 包：`src/algocode`

```text
src/algocode/
├── __init__.py                    # Python 包定义与 __version__
├── __main__.py                    # python -m algocode 入口
├── bootstrap.py                   # 组装 AppContext：数据库、服务、Provider、工具
├── project_layout.py              # .algocode 目录布局定义
├── structured_output.py           # 模型 JSON 提取、Schema 解析与截断修复
├── acceptance/                    # 验收测试与发布门禁支撑
├── application/                   # 应用服务层
├── approval/                      # 审批服务
├── benchmark/                     # Benchmark 执行与比较
├── cli/                           # Typer CLI
├── config/                        # 配置模型、加载与全局配置
├── context/                       # Agent 上下文构建
├── correctness/                   # Correctness 验证
├── domain/                        # 领域模型、事件和值对象
├── eval/                          # 评测套件
├── languages/                     # Python / C++ 语言适配
├── observability/                 # 可观察性扩展点
├── policy/                        # 策略引擎
├── ports/                         # 抽象接口定义
├── providers/                     # 模型 Provider 适配
├── report/                        # 报告模块
├── resources/                     # 资源提供方与内置 VSIX
├── runtime/                       # Agent 阶段机、Tool Loop、Retry
├── sandbox/                       # Native / Docker / WSL2 执行后端
├── security/                      # API Key、凭证和脱敏
├── storage/                       # SQLite、Event Store、Artifact
├── tools/                         # Agent 工具注册与内置工具
└── workspace/                     # Git Worktree、Apply、Rollback
```

### 包根文件

```text
src/algocode/
├── __init__.py                    # __version__ = "0.1.1"
├── __main__.py                    # 调用 algocode.cli.main:main
├── bootstrap.py                   # 创建 AppContext，连接所有服务
├── project_layout.py              # config、oracle、benchmark、cache 路径
└── structured_output.py           # JSON 对象提取、Markdown fence 处理、Pydantic 校验
```

### `acceptance/`

```text
acceptance/
├── __init__.py
├── matrix.py                      # 验收矩阵与测试组合定义
├── probe.py                       # 验收探针与运行时行为检查
├── service.py                     # 验收服务编排
└── types.py                       # 验收结果类型
```

### `application/services/`

```text
application/
├── __init__.py                    # 导出应用服务
└── services/
    ├── __init__.py
    ├── apply_service.py           # Apply、Rollback、stale 检查
    ├── baseline_service.py        # 捕获基线快照与基线运行结果
    ├── benchmark_service.py       # Benchmark 运行、比较和持久化
    ├── candidate_service.py       # Candidate 创建、冻结、查询
    ├── contract_service.py        # Contract Discovery、编译、规范化和修复
    ├── correctness_service.py     # Correctness 运行、候选检查、证据保存
    ├── decision_service.py        # 根据验收策略生成 Accept/Reject 决策
    ├── project_bootstrap_service.py # init 全流程：契约、基线、初始化
    ├── project_service.py         # 项目注册与查询
    ├── project_state.py           # .algocode/current-task.json 读写
    ├── report_service.py          # report.md 与内部报告产物
    └── task_service.py            # Task 创建、查询、状态变化
```

### `approval/`

```text
approval/
├── __init__.py
├── service.py                     # 审批请求、审批结果与 Provider
└── types.py                       # Approval 类型定义
```

### `benchmark/`

```text
benchmark/
├── __init__.py
├── engine.py                      # 进程级 Benchmark 执行器
├── environment.py                 # 环境 hash 与运行环境快照
├── spec.py                        # benchmark.yaml 加载与校验
└── types.py                       # Benchmark 样本、Summary、Comparison
```

### `cli/`

```text
cli/
├── __init__.py
├── main.py                        # Typer 根命令注册
├── context.py                     # 解析 task/candidate/data-dir
├── output.py                      # 人类可读输出与 --json
└── commands/
    ├── __init__.py
    ├── accept.py                  # algocode accept
    ├── api.py                     # algocode api
    ├── apply.py                   # algocode apply / rollback
    ├── baseline.py                # algocode baseline
    ├── benchmark.py               # algocode benchmark
    ├── candidate.py               # candidate create/list/show/freeze
    ├── correctness.py             # correctness run/replay
    ├── diff.py                    # algocode diff
    ├── doctor.py                  # 环境检查
    ├── eval.py                    # eval run
    ├── experiment.py              # experiment list/show
    ├── gate.py                    # gate run
    ├── init.py                    # algocode init
    ├── model.py                   # 选择默认模型
    ├── optimize.py                # algocode optimize
    ├── provider_test.py           # algocode test
    ├── report.py                  # algocode report
    ├── retry.py                   # 基于历史重试
    ├── review.py                  # 查看 Correctness/Benchmark/Decision
    ├── status.py                  # 任务状态、阶段和细粒度进度
    ├── task.py                    # task create/list/show
    └── vscode.py                  # algocode vscode install
```

### `config/`

```text
config/
├── __init__.py
├── global_file.py                 # 全局配置写入
├── loader.py                      # 配置优先级、YAML 合并、环境变量覆盖
└── model.py                       # Provider、Model、Policy、Sandbox 配置模型
```

### `context/`

```text
context/
├── __init__.py
├── builder.py                     # 构建模型上下文与系统消息
├── estimator.py                   # token/字符预算估算
├── facts.py                       # Fact Ledger，记录已验证事实
└── types.py                       # ContextSnapshot 等类型
```

### `correctness/`

```text
correctness/
├── __init__.py
├── engine.py                      # cases/oracle/stress/hybrid 验证
├── protected.py                   # 保护文件检查
├── spec.py                        # correctness.yaml 加载
└── types.py                       # CorrectnessResult 等类型
```

### `domain/`

```text
domain/
├── __init__.py
├── commands/
│   └── __init__.py
├── errors/
│   └── __init__.py                # 领域错误
├── events/
│   ├── __init__.py                # EventEnvelope / EventType 导出
│   └── envelope.py                # 事件定义与事件类型枚举
└── model/
    ├── __init__.py
    ├── entities.py                # Project、Task、Candidate 等实体
    ├── enums.py                   # TaskStatus、TaskPhase、WorkspaceKind 等
    ├── ids.py                     # 各领域实体 ID
    └── values.py                  # 值对象和 ArtifactRef
```

### `eval/`

```text
eval/
├── __init__.py
├── harness.py                     # 评测执行器
├── provider.py                    # 评测 Provider
├── service.py                     # 评测服务
├── suites.py                      # 评测用例集
└── types.py                       # 评测结果类型
```

### `languages/`

```text
languages/
├── __init__.py
├── cpp.py                         # C++ 编译、运行、Contract Test
├── discovery.py                   # 源码文件发现
├── python.py                      # Python 执行与 Contract Test
├── registry.py                    # LanguageRegistry
├── runner.py                      # 语言运行入口
└── types.py                       # Language 相关类型
```

### `policy/` 与 `ports/`

```text
policy/
├── __init__.py
├── engine.py                      # 策略匹配与授权决策
└── types.py                       # PolicyRule、PolicyEffect、Layer

ports/
├── __init__.py
├── artifact_store.py              # ArtifactStore 接口
├── clock.py                       # Clock 接口
├── event_store.py                 # EventStore 接口
├── language.py                    # LanguageAdapter 接口
├── policy.py                      # Policy 接口
├── provider.py                    # ModelProvider 接口
├── resource.py                    # ResourceProvider 接口
└── workspace.py                   # WorkspaceManager 接口
```

### `providers/`

```text
providers/
├── __init__.py
├── anthropic.py                   # Anthropic Messages API 适配
├── errors.py                      # ProviderError
├── factory.py                     # 根据配置构建 Provider
├── fake.py                        # 测试用 FakeProvider
├── openai_compatible.py           # OpenAI-compatible API 适配
└── types.py                       # Message、ToolCall、ModelResponse
```

### `resources/`

```text
resources/
├── __init__.py
├── local.py                       # 本地资源读取
├── types.py                       # ResourceResult
└── vscode/
    ├── __init__.py
    └── algocode-vscode-0.1.1.vsix # PyPI 包内携带的 VS Code 扩展
```

### `runtime/`

```text
runtime/
├── __init__.py
├── agent.py                       # 阶段机、Tool Loop、Retry、预算与 Gate
├── analysis.py                    # AnalysisReport、文件读取覆盖、命令规范化
├── gates.py                       # 阶段 Gate 检查
├── locks.py                       # 运行时锁
├── model_log.py                   # 模型调用 Markdown 日志
├── optimization_record.py         # Retry 使用的持久化优化记录
├── planning.py                    # OptimizationPlan 类型与解析
├── repair_memory.py               # 候选修复上下文
└── task_lock.py                   # Task 级并发锁
```

### `sandbox/` 与 `security/`

```text
sandbox/
├── __init__.py
├── local.py                       # 本地进程授权与净化环境
└── runner.py                      # Native / Docker / WSL2 后端选择与执行

security/
├── __init__.py
├── credentials.py                 # 本机 API Key 凭证存储
└── redaction.py                   # 日志与请求脱敏
```

### `storage/`

```text
storage/
├── __init__.py
├── paths.py                       # 默认数据目录与项目数据目录
├── artifacts/
│   ├── __init__.py
│   └── file_artifact_store.py      # 文件型 ArtifactStore
├── events/
│   ├── __init__.py
│   └── sqlite_event_store.py       # SQLite 事件日志
└── sqlite/
    ├── __init__.py
    ├── approval_store.py           # 审批记录
    ├── database.py                 # SQLite 连接与事务
    ├── migrations.py               # 数据库迁移
    └── projections/
        ├── __init__.py
        ├── baseline_projection.py
        ├── benchmark_projection.py
        ├── candidate_projection.py
        ├── correctness_projection.py
        ├── decision_projection.py
        ├── project_projection.py
        └── task_projection.py
```

### `tools/` 与 `workspace/`

```text
tools/
├── __init__.py
├── registry.py                    # 工具注册与执行
├── types.py                       # ToolDefinition、ToolCall、ToolResult
└── builtins/
    ├── __init__.py
    ├── actions.py                  # run_correctness、run_benchmark 等动作工具
    └── filesystem.py               # read_file、edit_file、write_file、apply_patch

workspace/
├── __init__.py
├── git.py                         # GitRepository、Snapshot、Worktree、Apply、Rollback
└── types.py                       # Workspace、WorkspaceKind、ApplyResult
```

### `report/` 与 `observability/`

```text
report/
└── __init__.py                    # 报告包入口

observability/
└── __init__.py                    # 可观察性扩展点
```

---

## 测试结构

```text
tests/
├── __init__.py
├── contract/
│   ├── __init__.py
│   ├── test_artifact_store.py     # ArtifactStore 跨实现契约
│   └── test_event_store.py        # EventStore 跨实现契约
├── integration/
│   ├── __init__.py
│   ├── test_acceptance_gate.py
│   ├── test_agent_runtime.py
│   ├── test_baseline_service.py
│   ├── test_benchmark_service.py
│   ├── test_cli_api_model.py
│   ├── test_cli_benchmark.py
│   ├── test_cli_contract.py
│   ├── test_cli_doctor.py
│   ├── test_cli_eval.py
│   ├── test_cli_experiment.py
│   ├── test_cli_init_baseline.py
│   ├── test_cli_optimize.py
│   ├── test_cli_report_apply.py
│   ├── test_cli_task.py
│   ├── test_correctness_service.py
│   ├── test_docker_sandbox.py
│   ├── test_e2e_full.py
│   ├── test_eval_service.py
│   ├── test_git_workspace.py
│   ├── test_project_bootstrap.py
│   ├── test_report_apply.py
│   ├── test_report_failure_evidence.py
│   ├── test_secret_redaction.py
│   ├── test_tool_actions.py
│   └── test_tool_security.py
├── support/
│   ├── __init__.py
│   ├── git.py                     # 测试 Git 仓库初始化
│   └── mock_openai.py             # OpenAI-compatible Mock Server
└── unit/
    ├── __init__.py
    ├── acceptance/
    ├── application/
    ├── approval/
    ├── benchmark/
    ├── config/
    ├── context/
    ├── correctness/
    ├── domain/
    ├── languages/
    ├── policy/
    ├── providers/
    ├── resources/
    ├── runtime/
    ├── sandbox/
    ├── security/
    ├── tools/
    ├── test_doctor.py
    ├── test_paths.py
    ├── test_project_service.py
    ├── test_status_progress.py
    ├── test_task_service.py
    └── test_vscode_command.py
```

单元测试按功能模块继续细分：

```text
tests/unit/
├── acceptance/test_matrix.py
├── application/test_decision_policy.py
├── approval/test_service.py
├── benchmark/test_engine.py
├── benchmark/test_environment.py
├── benchmark/test_locks.py
├── benchmark/test_spec.py
├── config/test_loader.py
├── context/test_builder.py
├── correctness/test_engine.py
├── correctness/test_protected.py
├── correctness/test_spec.py
├── domain/test_ids.py
├── domain/test_models.py
├── languages/test_adapters.py
├── policy/test_engine.py
├── providers/test_anthropic.py
├── providers/test_fake.py
├── providers/test_openai_compatible.py
├── resources/test_local.py
├── runtime/test_analysis.py
├── runtime/test_contract_service.py
├── runtime/test_gates.py
├── runtime/test_model_log.py
├── runtime/test_optimization_record.py
├── runtime/test_planning.py
├── runtime/test_structured_output.py
├── runtime/test_task_lock.py
├── sandbox/test_local.py
├── sandbox/test_runner.py
├── security/test_credentials.py
└── tools/test_registry.py
```

---

## VS Code 扩展

```text
extensions/vscode/
├── .vscode/
│   ├── launch.json                # F5 调试配置
│   └── tasks.json                 # 编译任务
├── src/
│   └── extension.ts               # 扩展主逻辑
├── out/
│   ├── extension.js               # TypeScript 编译产物
│   └── extension.js.map           # Source Map
├── algocode-vscode-0.1.1.vsix     # 可安装扩展包
├── package.json                   # 命令、菜单、配置贡献
├── package-lock.json              # npm 锁文件
└── tsconfig.json                  # TypeScript 配置
```

`extension.ts` 负责：

- 右键子菜单 `Algocode`
- `优化 Optimize`
- `回滚 Rollback`
- `应用 Apply`
- `差异 Show Diff`
- `检查 Review`
- 临时影子工作区
- `Algocode` 终端与阶段进度
- 原生 Diff
- Apply 前备份和 Rollback

---

## GitHub Actions 与 Docker

```text
.github/workflows/
├── publish.yml                    # tag/release 触发 PyPI 发布
└── python-publish.yml             # 备用 Python 发布工作流

docker/
└── sandbox.Dockerfile             # 可构建的沙箱镜像
```

---

## 项目运行时 `.algocode`

在用户目标项目中执行 `algocode init` 后生成：

```text
.algocode/
├── config.yaml                    # 项目级配置
├── config.local.yaml              # 本地覆盖
├── contract.json                  # Contract Discovery 结果
├── task.txt                       # 当前任务人读摘要
├── current-task.json              # 当前任务机读状态
├── oracle/
│   ├── check.py                   # 输出比较器
│   ├── correctness.yaml           # Correctness 规范
│   ├── contract_test.py           # Python Contract Test
│   ├── contract_test.cpp          # C++ Contract Test
│   └── reference/                 # 原始参考源码副本
├── benchmarks/
│   └── benchmark.yaml             # Benchmark 规范
└── cache/
    ├── algocode.db                # SQLite Event Store 与 Projection
    ├── artifacts/                 # Patch、输出、报告等产物
    ├── model-logs/                # 每次模型调用 Markdown 日志
    ├── optimization-records/      # Retry 所需优化记录
    ├── worktrees/                 # Baseline / Candidate Git Worktree
    ├── repair-memory/             # 修复上下文
    └── rollbacks/                 # Apply 后回滚清单
```

---

## 数据流

```text
CLI / VS Code
      ↓
Application Services
      ↓
Runtime Agent
      ↓
Context / Tools / Providers
      ↓
Language Adapters
      ↓
Git Worktree / Sandbox
      ↓
Correctness / Contract / Benchmark
      ↓
Decision / Report / Apply / Rollback
```

---

## 维护规则

- `src/algocode` 中的源文件按职责分层，不按单个命令堆叠。
- CLI 只负责参数解析和结果展示，核心逻辑放在 application/runtime/service 层。
- Contract、Correctness、Benchmark 的规范文件属于保护文件。
- `.algocode/` 是运行时目录，不应提交到用户项目 Git 仓库。
- 修改阶段机、Tool Loop、Storage 或 Gate 时，应同时更新对应单元测试和集成测试。
- 修改 VS Code 扩展后，需要重新执行 TypeScript 编译并更新包内 VSIX。
