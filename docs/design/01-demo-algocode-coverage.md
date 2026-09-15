# Algocode Demo 阅读覆盖台账

> 对应设计文档：`01-demo-algocode-design.md`  
> 分析日期：2026-09-15  
> 分析对象：`C:\Users\Administrator\Desktop\algocode\demo`  
> 原则：第一方源码、配置、测试和设计文档全部纳入阅读；依赖、缓存、二进制、模型和生成语料按计划排除

## 1. 覆盖结论

| 类别 | 文件数 | 行数或数量 | 状态 |
|---|---:|---:|---|
| 当前第一方 Python 源码 | 30 | 7,826 行 | 已全文阅读 |
| 当前测试与演示 Python | 25 | 2,033 行 | 已全文阅读 |
| 当前 Markdown 设计文档 | 8 | 2,450 行 | 已全文阅读 |
| 数据管线 Python 脚本 | 3 | 约 188 行 | 已全文阅读 |
| 根级 Python 工具 | 1 | 111 行 | 已全文阅读 |
| 根级配置和启动脚本 | 7 | 约 100 行 | 已阅读 |
| Git 历史中的已删除 solver | 15 | 1,212 行删除 | 已通过 `git show HEAD` 阅读 |
| OI Wiki 原始语料 | 385 | 329 Markdown + 56 Python | 检查目录、样本和用途，不逐行阅读 |
| 算法卡片 JSON | 320 | 生成数据 | 检查结构、加载逻辑和样本 |
| 模型和向量库 | 2 类目录 | 二进制或运行时数据 | 仅检查路径、数量和可用性 |
| `.venv` | 大量第三方文件 | 第三方环境 | 排除 |

## 2. 当前源码逐文件覆盖

| 文件 | 行数 | 阅读状态 | 主要内容 |
|---|---:|---|---|
| `src/config.py` | 211 | 已全文阅读 | 环境变量、系统提示词、质量档位 |
| `src/prompts.py` | 94 | 已全文阅读 | 对话和 Worker 提示词 |
| `src/infrastructure/deepseek_client.py` | 121 | 已全文阅读 | OpenAI 客户端、模型列表、请求日志 |
| `src/agent/__init__.py` | 6 | 已全文阅读 | Agent 导出 |
| `src/agent/chat_agent.py` | 933 | 已全文阅读 | 工具循环、验证、取消、日志、文本工具兜底 |
| `src/agent/optimize_agent.py` | 85 | 已全文阅读 | 优化任务追问和上下文组装 |
| `src/agent/osa_tool.py` | 98 | 已全文阅读 | `optimize_code` LangChain 工具 |
| `src/agent/unified_agent.py` | 117 | 已全文阅读 | 旧 IntegratedChatAgent |
| `src/osa/models.py` | 112 | 已全文阅读 | OSA 数据模型和 TaskSession |
| `src/osa/prepare.py` | 103 | 已全文阅读 | 不完整 C++ 代码补齐 |
| `src/osa/orchestrator.py` | 193 | 已全文阅读 | 语言识别、路径规划、历史案例注入、去重 |
| `src/osa/worker.py` | 422 | 已全文阅读 | Worker 工具循环、代码生成、对拍重试、并行 |
| `src/osa/aggregator.py` | 135 | 已全文阅读 | 独立验证、一致性审查、最优性审查、打回 |
| `src/osa/result_builder.py` | 79 | 已全文阅读 | OSA 工具结构化结果和后台案例写入 |
| `src/osa/output_router.py` | 248 | 已全文阅读 | 复杂度、基准、排序、叙述、报告、案例写入 |
| `src/osa/cli_runner.py` | 340 | 已全文阅读 | 传统 REPL、命令处理、OSA 流程调用 |
| `src/test_case/test_oracle.py` | 315 | 已全文阅读 | 用例生成、基线、归一化、对拍、基准输入 |
| `src/tools/tools.py` | 225 | 已全文阅读 | LangChain 工具定义和输出格式化 |
| `src/tools/sandbox.py` | 320 | 已全文阅读 | C++ 编译、运行、批量测试、基准 |
| `src/tools/code_parser.py` | 125 | 已全文阅读 | tree-sitter C++ 静态分析 |
| `src/tools/compute_math.py` | 349 | 已全文阅读 | SymPy 命令和 AST 安全校验 |
| `src/chroma/knowledge_base.py` | 82 | 已全文阅读 | Chroma 客户端、embedding 单例 |
| `src/chroma/retrieve_cards.py` | 172 | 已全文阅读 | BM25、向量、RRF、rerank |
| `src/chroma/case_library.py` | 114 | 已全文阅读 | 案例模型、代码指纹、JSON 存取 |
| `src/chroma/case_store.py` | 128 | 已全文阅读 | 案例 Chroma 索引和检索 |
| `src/tui/tui_app.py` | 1971 | 已全文阅读 | Textual 主应用、双视图、后台任务和报告流 |
| `src/tui/solve_tui.py` | 317 | 已全文阅读 | 已损坏的独立解题 TUI |
| `src/tui/tui.py` | 209 | 已全文阅读 | banner、边框、REPL 输入组件 |
| `src/tui/math_text.py` | 96 | 已全文阅读 | LaTeX 到 Unicode |
| `src/tui/math_markdown.py` | 106 | 已全文阅读 | markdown-it 数学插件 |

## 3. 测试和演示逐文件覆盖

| 文件 | 行数 | 阅读状态 | 主要断言或用途 |
|---|---:|---|---|
| `tests/test_offline_boot.py` | 45 | 已全文阅读 | 核心模块离线导入、配置、质量档位 |
| `tests/test_prepare.py` | 19 | 已全文阅读 | 可运行代码判断、PreparedCode |
| `tests/test_orchestrator.py` | 88 | 已全文阅读 | 语言识别、JSON 解析、路径去重 |
| `tests/test_aggregator.py` | 54 | 已全文阅读 | 排序、全失败聚合 |
| `tests/test_worker.py` | 30 | 已全文阅读 | 代码提取、工具接线 |
| `tests/test_tools.py` | 42 | 已全文阅读 | 题目模式批量评测 |
| `tests/test_test_oracle.py` | 57 | 已全文阅读 | 归一化、用例 JSON 解析 |
| `tests/test_case_library.py` | 64 | 已全文阅读 | 指纹、关键词、案例构建 |
| `tests/test_deepseek_client.py` | 72 | 已全文阅读 | 模型列表、请求日志、包装 |
| `tests/test_retrieve_cards.py` | 22 | 已全文阅读 | 卡片加载、分词、空查询 |
| `tests/test_code_parser.py` | 59 | 已全文阅读 | 循环深度、函数、递归 |
| `tests/test_sandbox.py` | 100 | 已全文阅读 | 头文件替换、编译运行、批量测试 |
| `tests/test_compute_math.py` | 161 | 已全文阅读 | 数学命令、注入防护、工具接线 |
| `tests/test_math_text.py` | 50 | 已全文阅读 | LaTeX Unicode 转换 |
| `tests/test_math_markdown.py` | 67 | 已全文阅读 | Markdown 数学 token |
| `tests/test_chat_agent.py` | 783 | 已全文阅读 | 工具循环、取消、重试、验证、日志、TUI |
| `tests/test_solver.py` | 68 | 已全文阅读 | 已删除 solver 的残留测试 |
| `tests/test_solver_v2.py` | 28 | 已全文阅读 | 已删除 solver v2 的残留测试 |
| `tests/demos/demo_aggregate.py` | 58 | 已全文阅读 | 手工 OSA 全链路演示，接口已过期 |
| `tests/demos/demo_parallel.py` | 47 | 已全文阅读 | 手工 Worker 并行演示 |
| `tests/demos/demo_paths.py` | 14 | 已全文阅读 | 手工路径规划演示 |
| `tests/demos/demo_report.py` | 44 | 已全文阅读 | 手工报告演示，引用已不存在函数 |
| `tests/demos/demo_search.py` | 18 | 已全文阅读 | LangChain 工具调用演示 |
| `tests/demos/demo_session.py` | 12 | 已全文阅读 | TaskSession 演示 |
| `tests/demos/demo_worker.py` | 31 | 已全文阅读 | 单 Worker 演示 |

## 4. 设计文档覆盖

| 文件 | 行数 | 阅读状态 | 对当前文档的作用 |
|---|---:|---|---|
| `docs/项目设计文档.md` | 630 | 已全文阅读 | 最近的一版项目现状说明，但存在过期项 |
| `docs/architecture-current.md` | 111 | 已全文阅读 | 当前架构盘点，仍有一部分与工作区不一致 |
| `docs/agent-framework.md` | 141 | 已全文阅读 | 历史 Agent 总体框架 |
| `docs/M1-独立解题闭环设计.md` | 517 | 已全文阅读 | 已删除的单方案解题设计 |
| `docs/M1-解题闭环-v2设计.md` | 572 | 已全文阅读 | 已删除的多方案解题设计 |
| `docs/technical-landing-plan.md` | 227 | 已全文阅读 | OSA 落地规划 |
| `docs/future-enhancement-plan.md` | 119 | 已全文阅读 | 产品化和可信度路线 |
| `docs/superpowers/plans/2026-08-01-osa-framework.md` | 133 | 已全文阅读 | OSA 实现清单 |

## 5. 数据和辅助文件覆盖

| 文件或目录 | 覆盖方式 | 说明 |
|---|---|---|
| `README.md` | 已全文阅读 | 与当前工作区有多处漂移 |
| `requirements.txt` | 已全文阅读 | 记录了固定版本 |
| `pytest.ini` | 已全文阅读 | `testpaths=tests`、`pythonpath=.` |
| `algocode.cmd` | 已全文阅读 | 实际指向 `tui_app.py` |
| `algocode-solve.cmd` | 已全文阅读 | 指向当前不可导入的 `solve_tui.py` |
| `.gitignore` | 已全文阅读 | 忽略虚拟环境、日志、模型和向量库 |
| `review_thinking.py` | 已全文阅读 | 请求日志回放工具 |
| `data/build_cards.py` | 已全文阅读 | 卡片生成和入库 |
| `data/fix_category.py` | 已全文阅读 | 卡片类别修复 |
| `data/inspect_db.py` | 已全文阅读 | Chroma 记录查看脚本 |
| `data/case_library.json` | 已结构化读取 | 当前 2 条案例、16,422 字节 |
| `data/cards/*.json` | 检查结构和样本 | 当前 320 张生成卡片 |
| `data/oi-wiki/**` | 检查目录、规模和样本 | 329 Markdown、56 Python 源语料 |
| `chroma_db/` | 运行时查询 | `oi_wiki=320`、`cases=3` |
| `models/` | 检查路径 | 本地 embedding 和 reranker |
| `.env` | 检查存在和变量名 | 未在文档中泄露值 |
| `.venv/` | 排除 | 第三方依赖环境 |
| `$extract/` | 排除 | Windows DLL 抽取产物 |
| `.pytest_cache/` | 排除 | pytest 缓存 |
| `__pycache__/` | 排除 | Python 字节码 |
| `messages_log.json` | 检查用途 | 完整 messages 覆盖日志 |
| `requests_log.jsonl` | 检查用途 | 模型请求追加日志 |
| `thinking_log.md` | 检查用途 | 最近思考过程 |
| `osa_error.log` / `chat_debug.log` | 检查用途 | 运行诊断日志 |

## 6. Git 历史中已删除 solver 的覆盖

这些文件不在当前工作区，但从 `HEAD` 中读取，用于理解旧独立解题设计。

| 文件 | 历史行数 | 阅读状态 | 说明 |
|---|---:|---|---|
| `src/solver/__init__.py` | 0 | 已检查 | 空包文件 |
| `src/solver/models.py` | 37 | 已全文阅读 | ProblemSpec、SolutionPlan、SolveResult |
| `src/solver/problem_solver.py` | 374 | 已全文阅读 | 单方案独立解题流程 |
| `src/solver/v2/__init__.py` | 0 | 已检查 | 空包文件 |
| `src/solver/v2/aggregator.py` | 35 | 已全文阅读 | 正确和失败结果聚合 |
| `src/solver/v2/fallback.py` | 35 | 已全文阅读 | 兜底重规划 |
| `src/solver/v2/llm_utils.py` | 55 | 已全文阅读 | JSON、C++ 和样例提取 |
| `src/solver/v2/models.py` | 76 | 已全文阅读 | v2 数据模型 |
| `src/solver/v2/orchestrator.py` | 69 | 已全文阅读 | v2 解题编排 |
| `src/solver/v2/plan_searcher.py` | 139 | 已全文阅读 | 方案搜索和反例审查 |
| `src/solver/v2/problem_parser.py` | 56 | 已全文阅读 | 题目结构化 |
| `src/solver/v2/reference.py` | 83 | 已全文阅读 | 暴力解和参考用例 |
| `src/solver/v2/reporter.py` | 59 | 已全文阅读 | 解题报告 |
| `src/solver/v2/validator.py` | 46 | 已全文阅读 | 样例测试和差分验证 |
| `src/solver/v2/worker.py` | 148 | 已全文阅读 | v2 实现 Worker |

## 7. 实际执行记录

### 7.1 语法检查

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tests
```

结果：通过。

### 7.2 全量测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

结果：2 个收集错误。

```text
tests/test_solver.py: No module named 'src.solver'
tests/test_solver_v2.py: No module named 'src.solver'
```

### 7.3 排除残留 solver 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  --ignore=tests\test_solver.py `
  --ignore=tests\test_solver_v2.py `
  --basetemp=.pytest_tmp_demo
```

结果：

```text
2 failed, 175 passed
```

失败项：

- `test_chat_agent_set_model_rebuilds_system_prompt`
- `test_ask_writes_messages_log`

### 7.4 运行时数据查询

```text
Chroma collections:
  oi_wiki = 320
  cases = 3
```

```text
data/case_library.json:
  cases = 2
  with_best = 0
```

## 8. 明确排除项

以下内容没有逐行阅读，原因是它们不是本次“项目设计”所需要的当前第一方代码：

1. `.venv` 中所有第三方库。
2. `models` 中的模型权重、tokenizer 和缓存。
3. `chroma_db` 的底层数据库文件。
4. `data/oi-wiki` 的全部原始教程正文和图片。该目录属于输入语料，不是 Algocode 自身实现，但已检查规模、目录和代表性文件。
5. 320 张生成卡片没有逐张阅读，但已确认生成脚本、字段结构、加载链和 Chroma 数量，并抽查了卡片。
6. 二进制 DLL、图片、音视频、字体和缓存。
7. 运行日志仅检查用途和格式，没有把历史日志视为设计代码。

## 9. 覆盖完成度判断

针对“当前 Algocode Demo 的一手实现及其测试”这一范围，源码和测试覆盖完成。

针对“理解和解释项目设计”这一目标，覆盖完成。

针对“逐行阅读 OI Wiki 语料、第三方依赖和二进制模型”这一字面范围，未执行；这些内容不属于项目代码，且对设计结论没有边际价值。
