<p align="center">
  <img src="https://raw.githubusercontent.com/acd2113/Algocode/main/docs/picture/algocode_icon.png" alt="Algocode" width="120">
</p>

<p align="center">面向 C++ / Python 的可验证算法优化 Agent</p>
<p align="center">本地优先 · 证据驱动 · 可回滚</p>

***

## 项目简介

Algocode 是一个命令行驱动的算法优化 Agent，面向已有的 C++ 或 Python 项目。它会自动分析项目结构与行为，生成行为契约，然后在隔离的 Git Worktree 中尝试算法优化，并通过 Correctness 验证、Contract 测试和 Benchmark 对比来确保优化结果的正确性与收益。

**核心特性：**

- **契约优先** — 优化前先确定公开 API、输入输出、配置语义等约束，候选实现必须通过行为契约

- **证据驱动** — Correctness、Contract、Benchmark 结果均持久化，决策基于运行时证据而非自我评价

- **隔离候选** — Agent 在独立 Worktree 中试错，用户工作区仅在执行 `apply` 时才被修改

- **人工可控** — Accept 与 Apply 分离，支持查看 Diff 和证据后再决策，Apply 后可 Rollback

- **全程可审计** — 模型调用、工具调用、阶段结果、优化记录、候选血缘均完整保存

## 使用守则（使用前必看）

待优化代码需满足以下条件：

**通用要求：**

| 条件            | 说明                                     |
| ------------- | -------------------------------------- |
| Git 仓库        | 项目需是 Git 仓库，否则 Algocode 会自动初始化一个       |
| 单主语言          | 一个项目只支持一种主语言（C++ 和 Python 同时存在时优先 C++） |
| 明确入口          | 有可执行的入口文件，运行后能输出结果                     |
| 确定性输出         | 相同输入下输出一致（用于 Correctness 验证）           |
| 进程级 Benchmark | 以整个程序运行为测量单位，不支持函数级 Benchmark          |

**Python 项目：**

- 项目中有 `.py` 文件，或存在 `pyproject.toml` / `setup.py`

- 入口文件优先匹配 `main.py` 或 `test.py`，否则取第一个非 `__init__.py` 的文件

- 入口程序能正常运行且退出码为 0

**C++ 项目：**

- 项目中有 `.cpp` / `.cc` / `.cxx` 文件，或存在 `CMakeLists.txt` / `Makefile`

- 系统需安装 `g++` 或 `clang++`（支持 C++17）

- 入口文件优先匹配 `main.cpp` 或 `test.cpp`，否则取第一个源文件

- 代码能正常编译并运行，退出码为 0

**暂不支持的场景：**

- 跨语言混合项目（如 Python 调用 C++ 扩展）

- 多翻译单元 / 复杂 CMake 项目的 Contract Harness

- 运行时依赖网络、外部文件系统等不确定因素的代码

- 函数级 / 模块级 Benchmark（仅支持进程级）

## 环境与依赖

### 系统要求

| 依赖                         | 最低版本  | 说明               |
| -------------------------- | ----- | ---------------- |
| Python                     | 3.11+ | 运行环境             |
| Git                        | —     | Worktree 隔离与版本管理 |
| C++ 编译器                    | —     | 优化 C++ 项目时需要     |
| OpenAI-compatible Provider | —     | 使用真实模型时需要        |

可选增强：

- **Docker / WSL2** — 用于更强的沙箱隔离（非强制）

### 安装

**从 PyPI 安装：**

```bash
python -m pip install algocode-agent
```

**从源码开发安装：**

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m algocode doctor
```

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m algocode doctor
```

> 若 `algocode` 命令不可用，可替换为对应虚拟环境下的 `python -m algocode`。

### 配置模型 Provider

首次使用时，通过交互式命令配置模型和 API Key：

```bash
algocode api          # 选择厂商、模型并配置 API Key
algocode test         # 验证模型连接是否正常
```

支持的 Provider 包括：OpenAI、DeepSeek、OpenRouter、Kimi、智谱 GLM、MiniMax、Anthropic Claude、火山引擎豆包、通义千问 Qwen，以及任意 OpenAI-compatible 服务（如本地 Ollama / vLLM）。

API Key 保存在用户本机凭证文件中，不会写入项目配置。

**切换默认模型：**

```bash
algocode model
```

## 使用教程

### 项目要求

待优化的代码需要满足以下条件：

**通用要求：**

| 条件            | 说明                                     |
| ------------- | -------------------------------------- |
| Git 仓库        | 项目需是 Git 仓库，否则 Algocode 会自动初始化一个       |
| 单主语言          | 一个项目只支持一种主语言（C++ 和 Python 同时存在时优先 C++） |
| 明确入口          | 有可执行的入口文件，运行后能输出结果                     |
| 确定性输出         | 相同输入下输出一致（用于 Correctness 验证）           |
| 进程级 Benchmark | 以整个程序运行为测量单位，不支持函数级 Benchmark          |

**Python 项目：**

- 项目中有 `.py` 文件，或存在 `pyproject.toml` / `setup.py`

- 入口文件优先匹配 `main.py` 或 `test.py`，否则取第一个非 `__init__.py` 的文件

- 入口程序能正常运行且退出码为 0

**C++ 项目：**

- 项目中有 `.cpp` / `.cc` / `.cxx` 文件，或存在 `CMakeLists.txt` / `Makefile`

- 系统需安装 `g++` 或 `clang++`（支持 C++17）

- 入口文件优先匹配 `main.cpp` 或 `test.cpp`，否则取第一个源文件

- 代码能正常编译并运行，退出码为 0

**暂不支持的场景：**

- 跨语言混合项目（如 Python 调用 C++ 扩展）

- 多翻译单元 / 复杂 CMake 项目的 Contract Harness

- 运行时依赖网络、外部文件系统等不确定因素的代码

- 函数级 / 模块级 Benchmark（仅支持进程级）

### 快速开始

在待优化的项目根目录下执行：

```bash
algocode init         # 初始化项目，建立基线
algocode optimize     # 运行优化流程
```

查看结果与证据：

```bash
algocode status       # 查看当前任务状态
algocode review       # 查看候选验证结果与决策证据
algocode diff         # 查看候选代码变更
```

接受并应用优化：

```bash
algocode accept <task-id> <candidate-id>
algocode apply
```

回滚已应用的优化：

```bash
algocode rollback
```

基于历史记录重新搜索优化方向：

```bash
algocode retry
```

### 核心命令

| 命令                  | 说明                      |
| ------------------- | ----------------------- |
| `algocode api`      | 配置模型 Provider 和 API Key |
| `algocode test`     | 发送最小请求验证模型连接            |
| `algocode doctor`   | 检查本地运行环境                |
| `algocode init`     | 初始化项目并建立基线（大约耗时7分钟）     |
| `algocode optimize` | 运行完整优化流程（大约耗时5分钟）       |
| `algocode retry`    | 基于历史记录重新优化（同上）          |
| `algocode status`   | 查看当前任务状态                |
| `algocode review`   | 查看当前优化结果信息              |
| `algocode diff`     | 查看候选代码变更                |
| `algocode apply`    | 将候选应用到工作区               |
| `algocode rollback` | 回滚已应用的候选                |
| `algocode report`   | 生成任务报告                  |

大多数命令支持 `--json` 输出，便于脚本集成。

### 优化工作流

```
init → 契约发现 → 基线建立 → 分析 → 规划 → 候选实现
                                    ↓
                         正确性验证 ← 候选 Worktree
                                    ↓
                              Benchmark 对比
                                    ↓
                              决策 → 审查 → 接受 → 应用
                                    ↓
                                  重试
```

各阶段之间存在 Gate：候选未通过 Correctness 时不会进入 Benchmark；没有有效对比结果时不会进入决策。

### 验证体系

Algocode 将优化结果拆为三类证据：

| 类型              | 说明                                                |
| --------------- | ------------------------------------------------- |
| **Correctness** | 验证候选实现是否复现基线行为，支持 cases、oracle、stress、hybrid 等模式  |
| **Contract**    | 保护算法之外的行为，如公开 API、配置字段、错误类型、边界行为等                 |
| **Benchmark**   | 受控的性能测量，记录 warmup、重复样本、median、variation、环境 hash 等 |

## 目录结构说明

### 项目源码结构

```
src/algocode/
├── cli/                  # 命令行入口（Typer）
├── application/          # 应用服务层（Task、Candidate、Benchmark 等）
├── domain/               # 领域层（实体、值对象、事件）
├── runtime/              # 运行时（阶段机、Tool Loop、Retry）
├── config/               # 配置加载与模型
├── context/              # 上下文构建与估算
├── tools/                # 工具注册表与内置工具
├── policy/               # 策略引擎
├── approval/             # 审批服务
├── sandbox/              # 沙箱运行器
├── security/             # 凭证与脱敏
├── providers/            # 模型 Provider 适配
├── languages/            # 语言支持（Python / C++）
├── correctness/          # 正确性验证引擎
├── benchmark/            # Benchmark 引擎
├── acceptance/           # 验收与发布门禁
├── eval/                 # 评估套件
├── workspace/            # Git Workspace 管理
├── storage/              # 持久化（Event Store、Projection、Artifact）
├── ports/                # 端口与抽象接口
├── resources/            # 资源提供方
├── observability/        # 可观察性
├── report/               # 报告生成
└── bootstrap.py          # 应用组装根
```

### 项目内 .algocode 目录

执行 `init` 后，项目根目录会生成 `.algocode/` 目录：

```
.algocode/
├── config.yaml           # 项目配置
├── config.local.yaml     # 本地覆盖（可选）
├── contract.json         # 项目行为契约
├── task.txt              # 当前任务摘要
├── current-task.json     # 当前任务完整状态
├── oracle/               # Correctness 与 Contract Test
│   ├── check.py
│   ├── correctness.yaml
│   ├── contract_test.py  # Python 项目
│   ├── contract_test.cpp # C++ 项目
│   └── reference/
├── benchmarks/
│   └── benchmark.yaml    # Benchmark 规范
└── cache/                # 运行时缓存与数据
    ├── algocode.db       # Event Store 与 Projection
    ├── artifacts/        # 产物存储
    ├── model-logs/       # 模型调用记录
    ├── optimization-records/  # 优化记录
    ├── worktrees/        # Baseline 与 Candidate Worktree
    ├── repair-memory/    # 修复上下文
    └── rollbacks/        # 回滚清单
```

## 使用示例

执行api选择
![img\_1.png](img_1.png)

将需要优化的文件放入一个文件夹中
![img.png](img.png)

执行命令algocode init
会实现初始化项目并自动生成优化提示词（共调用2次大模型）
![img\_2.png](img_2.png)

执行命令algocode optimize启动优化
![img\_3.png](img_3.png)
Status：completed即为优化成功
\
后续可执行\
algocode review查看性能提升\
algocode diff 查看代码修改
\
algocode report 生成报告
\
algocode apply 将优化后代码覆盖test.py
\
algocode rollback 回滚代码

## 常见问题

Status不是completed？答：优化流程不稳定，可以重试或者查看.algocode\cache\model-logs，看模型调用进度
algocode init出现问题？ 答：可能是待优化代码无法编译或者是不符合条件

## 联系与贡献

### 反馈问题

遇到 Bug 或有功能建议，欢迎在 [GitHub Issues](https://github.com/acd2113/Algocode/issues) 中提出。提交时尽量提供：

- 操作系统与 Python 版本

- 复现步骤

- 期望行为与实际行为

- 相关日志或截图

### 参与贡献

欢迎提交 Pull Request！开发流程：

1. Fork 本仓库

2. 创建特性分支（`git checkout -b feature/xxx`）

3. 安装开发依赖并确保测试通过：

   ```bash
   python -m venv .venv
   .venv/bin/python -m pip install -e ".[dev]"
   .venv/bin/python -m pytest
   .venv/bin/python -m ruff check .
   ```

4. 提交改动并发起 PR

### 交流讨论

- **项目主页**：[github.com/acd2113/Algocode](https://github.com/acd2113/Algocode)

- **问题反馈**：[GitHub Issues](https://github.com/acd2113/Algocode/issues)

***

## License

本项目使用 MIT License，详见 [LICENSE](LICENSE)。
