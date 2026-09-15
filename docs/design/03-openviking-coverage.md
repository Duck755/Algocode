# OpenViking 阅读覆盖台账

> 对应设计文档：`03-openviking-design.md`  
> 分析日期：2026-09-15  
> 分析对象：`C:\Users\Administrator\Desktop\OpenViking-main\OpenViking-main`  
> 快照状态：没有 `.git`、`.venv` 或可执行测试环境

## 1. 覆盖结论

OpenViking 是一个超大型 monorepo。核心 Python、Rust、测试和外围产品的规模如下：

| 范围 | 文件数 | 行数 |
|---|---:|---:|
| `openviking` Python | 640 | 188,194 |
| `openviking_cli` Python | 51 | 12,864 |
| `crates` Rust | 149 | 105,393 |
| `src` C++ | 65 | 14,033 |
| `tests` 测试代码 | 748 | 211,810 |
| Python SDK | 21 | 6,952 |
| TypeScript SDK | 8 | 3,325 |
| Go SDK | 21 | 5,374 |
| VikingBot | 163 | 59,902 |
| Web Studio | 321 | 61,667 |
| examples | 172 | 51,404 |
| benchmark | 106 | 42,560 |
| integrations | 17 | 6,251 |

本次覆盖策略：

1. 全部顶层目录和主要模块清单已盘点和分类。
2. 核心运行链的入口、类、数据模型、服务和关键函数已逐块精读。
3. 官方架构、存储、检索、会话、事务、多租户和 ACL 文档已阅读。
4. 大规模测试没有逐行阅读，按文件、测试类、关键断言和测试主题审查。
5. Bot、Web Studio、examples、benchmark 和第三方代码只做结构审阅，不按核心设计逐行展开。

## 2. 核心 Python 模块总览

| 模块 | 文件数 | 行数 | 覆盖级别 |
|---|---:|---:|---|
| `openviking/storage` | 123 | 41,252 | 核心精读 |
| `openviking/session` | 90 | 37,731 | 核心精读 |
| `openviking/server` | 71 | 21,982 | 核心精读 |
| `openviking/parse` | 63 | 20,105 | 核心结构精读 |
| `openviking/service` | 24 | 14,029 | 核心精读 |
| `openviking/models` | 34 | 10,326 | 模型接口审阅 |
| `openviking/metrics` | 54 | 8,282 | 结构审阅 |
| `openviking/utils` | 27 | 7,007 | 关键工具审阅 |
| `openviking/retrieve` | 17 | 3,044 | 核心精读 |
| `openviking/observability` | 17 | 3,805 | 结构审阅 |
| `openviking/telemetry` | 14 | 2,711 | 结构审阅 |
| `openviking/resource` | 9 | 2,457 | 关键路径审阅 |
| `openviking/core` | 12 | 2,236 | 全文阅读 |
| `openviking/ingest` | 18 | 2,229 | 核心精读 |
| `openviking/pyagfs` | 5 | 1,567 | binding 边界审阅 |
| `openviking/crypto` | 5 | 1,502 | 安全边界审阅 |
| `openviking/privacy` | 7 | 631 | 接口审阅 |
| `openviking/message` | 3 | 375 | 核心数据模型审阅 |
| `openviking/prompts` | 2 | 311 | 提示词结构审阅 |
| `openviking/eval` | 17 | 4,222 | 外围审阅 |
| `openviking/connector` | 4 | 1,196 | 外围审阅 |
| `openviking/usage_reporter` | 7 | 941 | 结构审阅 |
| `openviking/integrations` | 13 | 155 | 外围审阅 |

## 3. 核心源码精读清单

以下文件已按完整文件或关键连续段深入阅读：

| 文件 | 行数 | 内容 |
|---|---:|---|
| `openviking/__init__.py` | 34 | 公共导出 |
| `openviking/_sdk_import.py` | 约 26 | SDK 动态导入 |
| `openviking_cli/rust_cli.py` | 113 | Rust CLI 包装器 |
| `openviking/server/app.py` | 859 | FastAPI 装配和生命周期 |
| `openviking/server/bootstrap.py` | 500 | 服务启动 |
| `openviking/service/core.py` | 715 | 核心组合根 |
| `openviking/core/context.py` | 235 | Context、Vectorize、层级 |
| `openviking/core/directories.py` | 429 | 预设目录和初始化 |
| `openviking/core/namespace.py` | 458 | 命名空间和权限路径 |
| `openviking/retrieve/hierarchical_retriever.py` | 676 | 层级检索 |
| `openviking/retrieve/intent_analyzer.py` | 190 | 意图规划 |
| `openviking/retrieve/context_assembler/pipeline.py` | 170 | Context Assembly |
| `openviking/storage/viking_fs/_base.py` | 283 | VikingFS 基础与 singleton |
| `openviking/storage/viking_fs/__init__.py` | 206 | VikingFS 组合类 |
| `openviking/storage/vikingdb_manager.py` | 551 | 向量库和队列集成 |
| `openviking/storage/collection_schemas.py` | 923 | Context collection schema |
| `openviking/storage/index_consistency.py` | 229 | 文件与索引一致性 |
| `openviking/storage/acl.py` | 573 | ACL 模型和解析 |
| `openviking/storage/queuefs/queue_manager.py` | 463 | 队列管理器 |
| `openviking/storage/queuefs/semantic_dag.py` | 1,145 | 语义 DAG |
| `sdk/python/openviking_sdk/client.py` | 3,164 | Python SDK 主客户端 |
| `sdk/python/openviking_sdk/options.py` | 206 | API options |
| `sdk/python/openviking_sdk/message.py` | 127 | 消息 Part |
| `sdk/python/openviking_sdk/actor_peer.py` | 45 | actor peer context |

## 4. 服务与 API 覆盖

已盘点路由：

- `/api/v1/fs/*`
- `/api/v1/content/*`
- `/api/v1/search/*`
- `/api/v1/sessions/*`
- `/api/v1/skills/*`
- `/api/v1/resources/*`
- `/api/v1/tasks/*`
- `/api/v1/watches/*`
- `/api/v1/snapshots/*`
- `/api/v1/pack/*`
- `/api/v1/privacy/*`
- `/api/v1/admin/*`
- `/api/v1/acl/*`
- `/api/v1/observer/*`
- `/api/v1/stats/*`
- `/api/v1/metrics`
- `/api/v1/system/*`
- WebDAV
- MCP endpoint
- Bot API proxy
- OAuth router

已确认 FastAPI app 注册的中间件、异常映射、Request ID、profile、CORS 和显式路由集合。

## 5. 存储与检索覆盖

已阅读或核对的文档：

- `docs/zh/concepts/01-architecture.md`
- `docs/zh/concepts/02-context-types.md`
- `docs/zh/concepts/03-context-layers.md`
- `docs/zh/concepts/04-viking-uri.md`
- `docs/zh/concepts/05-storage.md`
- `docs/zh/concepts/07-retrieval.md`
- `docs/zh/concepts/08-session.md`
- `docs/zh/concepts/09-transaction.md`
- `docs/zh/concepts/11-multi-tenant.md`
- `docs/zh/concepts/14-multi-write-storage.md`
- `docs/zh/concepts/15-acl.md`
- `docs/zh/concepts/16-queue-lifecycle.md`

已核对来源：

- `VikingFS` 类和 mixin 组合
- `RAGFS` 模块清单
- `VikingDBManager`
- Context collection schema
- Index consistency checker
- QueueManager 和 SemanticDagExecutor
- HierarchicalRetriever
- IntentAnalyzer
- Context assembler pipeline

## 6. Session 与 Memory 覆盖

已盘点 `session.py` 的主要生命周期函数，包含：

- Session load、exists、materialize
- add message 和 batch add
- tool result externalization
- archive Phase 1
- commit Phase 2
- resume queued commit
- memory extraction
- session context
- archive scan
- checkpoint
- working memory merge
- abstract 和 overview

已盘点 Memory V3 关键组件：

- `compressor_v3.py`
- `extract_loop.py`
- `streaming_memory_updater.py`
- `memory_updater.py`
- `dataclass.py`
- `graph_view.py`
- `schema_model_generator.py`
- `merge_op/*`
- `utils/*`

未逐行阅读全部 3 万行 session 代码，但已经覆盖核心生命周期、提取链路、合并策略、恢复和审计接口。

## 7. Parse 与 Accessor 覆盖

已盘点：

- local accessor
- HTTP accessor
- Git accessor
- web crawler
- web feed
- Feishu accessor
- Markdown parser
- PDF parser
- Directory parser
- Code repository parser
- text encoding
- image/video/audio parser
- TreeBuilder
- parser router 和 registry
- Understanding API 和 VLM

重点理解：

- Parser 不调用 LLM
- 文件解析后再进入 Semantic DAG
- Markdown 标题切分、表格保护和图片重写
- PDF 多解析路径
- Git 仓库导入
- 目录递归和增量更新

## 8. Rust、CLI 和 C++ 覆盖

Rust：

- `crates/ragfs`
- `crates/ragfs-python`
- `crates/ov_cli`

重点结构：

- `MountableFS`
- local/S3/memory backends
- path lock
- cache
- Git object/ref/index/tree
- PyO3 binding
- CLI 命令模块

C++：

- `src/store`
- `src/index`
- `src/common`
- abi3 engine backend

本次没有逐行阅读所有 Rust 和 C++，重点检查公共边界、模块结构和与 Python 的集成方式。

## 9. SDK 覆盖

### Python SDK

已阅读或盘点：

- `client.py`
- `config.py`
- `errors.py`
- `message.py`
- `options.py`
- `uploads.py`
- `actor_peer.py`
- `_utils.py`

### TypeScript SDK

已阅读或盘点：

- `client.ts`
- `transport.ts`
- `types.ts`
- `node-files.ts`
- `errors.ts`
- `index.ts`

### Go SDK

已按文件名和职责盘点：

- client、transport、types
- filesystem、retrieval、sessions
- resources、skills、pack
- watches、acl、admin
- system、upload、compile

## 10. 测试覆盖

测试统计：

```text
Python test files: 657
Python test lines: 202,649
test functions: 4,535
```

测试按以下层次盘点：

- unit
- integration
- API
- storage
- retrieval
- session
- memory
- parser
- SDK
- auth
- ACL
- encryption
- Rust RAGFS
- CLI remote

本轮没有逐行阅读 20 万行测试，也没有实际运行。覆盖方式为测试目录盘点、测试名称、测试类、参数化结构和关键断言检查。

## 11. 实际验证记录

环境：

```text
Python: 3.13.14
pytest: 未安装
cargo: 未安装
.venv: 不存在
.git: 不存在
```

已执行：

```powershell
python -m compileall -q openviking openviking_cli sdk\python\openviking_sdk
```

结果：

```text
COMPILEALL_OK
```

未执行：

- Python pytest
- Rust cargo test
- TypeScript tests
- Go tests
- 真实模型和外部服务集成测试

## 12. 外围模块

以下模块已盘点目录和规模，但没有作为核心设计逐文件精读：

- `bot/`
- `web-studio/`
- `examples/`
- `benchmark/`
- `integrations/`
- `agent-plugins/`
- `npm/`
- `deploy/`
- `docker/`
- `third_party/`
- `docs/` 中除核心概念、设计和 API 说明外的多数翻译与产品文档

## 13. 明确排除项

1. 二进制资产、图片、字体、模型和生成的 Web 构建产物。
2. `third_party` 上游实现。
3. 多语言 README 翻译全文。
4. 全部 benchmark 数据和实验结果。
5. 全部 Web Studio 前端组件和视觉资产。
6. 全部 VikingBot 渠道适配器。
7. Rust 第三方 crate 源码。
8. Windows/Linux 构建缓存和虚拟环境。

## 14. 覆盖完成度判断

对 OpenViking 的核心架构、上下文模型、存储、检索、会话、记忆、多租户、ACL、事务、队列、CLI、SDK 和 Agent 集成边界，覆盖完成。

对 30 万行以上的全部源码和 20 万行测试逐行阅读，本轮未完成。

这不是因为项目不可读，而是因为该仓库规模已经接近多个独立产品之和。设计文档以可验证的核心运行链为边界，没有把外围产品的细节伪装成已逐行审计。
