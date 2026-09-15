# DeepSeek Harness 阅读覆盖台账

> 对应设计文档：`06-deepseek-harness-design.md`  
> 分析日期：2026-09-15  
> 分析对象：`C:\Users\Administrator\Desktop\deepseek-harness-master\deepseek-harness-master`  
> 快照状态：没有安装依赖，没有 `node_modules`，没有 `uv`，不能执行官方构建、测试和类型检查

## 1. 覆盖结论

DeepSeek Harness 是超大 pnpm monorepo。本次没有声称对全部源码逐行阅读。

覆盖策略：

1. 盘点顶层目录、apps、packages、Python、native、benchmarks、snapshots、scripts 和 vendor。
2. 完整阅读官方架构、Agent 生命周期、事件矩阵、Cordis Primer、工具流水线、Session、Persistence、Compaction、Sandbox、Subagent、Web 和 Tool Catalog 等核心文档。
3. 精读 CLI、Profile/Patch 组合、Agent Loop、Session、Tool Registry、LLM Service、DeepSeek Adapter、Session Persistence、Sandbox 和 Web Auth 主链。
4. 对 Web Client、Desktop、全部 UI、全部工具和外围包做结构审阅。
5. 测试文件没有逐行阅读，只做规模和主题统计。
6. 当前没有执行官方测试和构建。

## 2. 仓库规模

### 2.1 源码统计

统计范围是 `packages`、`apps`、`python` 和 `scripts` 下的 TypeScript、TSX、JavaScript、MJS 和 Python 文件，并排除构建产物。

| 范围 | 文件数 | 行数 |
|---|---:|---:|
| 非测试源码候选 | 3,704 | 790,140 |
| 测试文件 | 1,278 | 373,672 |
| 全仓文件 | 10,319 | 约 71 MB |

### 2.2 主要包规模

| 包 | 文件数 | 行数 | 覆盖级别 |
|---|---:|---:|---|
| `api/session-controller` | 79 | 21,731 | 核心接口与历史/实时流审阅 |
| `client/ui-conversation` | 92 | 19,908 | 结构审阅 |
| `experimental/inspector` | 175 | 19,563 | 外围审阅 |
| `experimental/webworker-runtime` | 117 | 18,459 | 外围审阅 |
| `client/ui-chat` | 100 | 18,019 | 结构审阅 |
| `client/ui-primitives` | 100 | 14,952 | 结构审阅 |
| `core/agent-loop` | 34 | 13,980 | 核心精读 |
| `client/ui-trajectory` | 40 | 13,155 | 结构审阅 |
| `core/tools` | 22 | 12,895 | 核心精读 |
| `subagent/subagent` | 38 | 11,476 | 核心接口精读 |
| `session/session-persistence-jsonl` | 29 | 11,468 | 核心精读 |
| `typert/generator` | 28 | 11,023 | 类型/协议结构审阅 |
| `api/gateway` | 21 | 10,722 | Web RPC 结构审阅 |
| `client/connection` | 33 | 10,385 | Web 认证与重连精读 |
| `subprocess/subprocess-local` | 31 | 10,260 | 子进程边界审阅 |

## 3. 核心源码精读清单

### 3.1 CLI、Profile 与启动

| 文件 | 行数 | 内容 |
|---|---:|---|
| `apps/cli/src/bin.ts` | 约 60 | CLI 分发入口 |
| `apps/cli/src/args.ts` | 约 300 | Launcher Flags 与内层 Args 边界 |
| `apps/cli/src/profile-boot.ts` | 约 450 | Profile 组合、Patch 和 Shutdown |
| `packages/boot/app-boot/src/index.ts` | 862 | Loader、Env、Patch、Fail Loud 和 Boot |
| `packages/boot/app-boot/src/profile.ts` | 848 | Profile、Bundle、模块回退和 Manifest |
| `packages/bundle/base/cordis.patch.yml` | 约 500 | Base 插件树 |
| `packages/bundle/web-app/cordis.patch.yml` | 约 500 | Web 插件树与 Agent Preset 接管 |
| `packages/bundle/headless/cordis.patch.yml` | 约 50 | Headless 组合 |
| `packages/bundle/sdk-app/cordis.patch.yml` | 约 40 | SDK JSON-RPC 组合 |

### 3.2 Agent 与 Session

| 文件 | 行数 | 内容 |
|---|---:|---|
| `packages/core/agent-loop/src/agent.ts` | 619 | Turn、Step、Inbox、请求冻结 |
| `packages/core/agent-loop/src/index.ts` | 930 | Agent Loop 插件和服务接线 |
| `packages/core/agent-loop/src/tool-calls.ts` | 290 | 工具调用调度 |
| `packages/core/agent/src/runtime-types.ts` | 405 | Agent 运行时事件和类型 |
| `packages/core/agent/src/index.ts` | 690 | Agent Registry、生命周期与 Ownership |
| `packages/core/session/src/index.ts` | 1,284 | Session、Surface、Fork 与 Store |
| `packages/core/session/src/types.ts` | 495 | SessionEventMap 与事件词汇 |
| `packages/core/session/src/repair.ts` | 约 100+ | 崩溃尾部和未闭合 Turn 修复 |
| `packages/core/system-prompt/src/index.ts` | 630 | Prompt Section、Tools 与 Waterfall |

### 3.3 Tool 与 LLM

| 文件 | 行数 | 内容 |
|---|---:|---|
| `packages/core/tools/src/index.ts` | 1,936 | Tool Registry 和执行流水线 |
| `packages/core/tools/src/schema.ts` | 未逐行统计 | Schema DSL |
| `packages/core/tools/src/json-schema.ts` | 未逐行统计 | JSON Schema 子集与验证 |
| `packages/core/tools/src/ptc.ts` | 未逐行统计 | PTC 代码工具桥接 |
| `packages/llm/llm/src/index.ts` | 1,147 | Adapter Registry、Prepared Call 和 Stream |
| `packages/llm/llm/src/types.ts` | 459 | StreamChunk、Message 与能力类型 |
| `packages/llm/llm/src/assistant-stream.ts` | 约 450 | 紧凑 Assistant Stream |
| `packages/llm/llm-deepseek/src/adapter.ts` | 715 | DeepSeek 协议、SSE、图片和 Files |
| `packages/llm/llm-deepseek/src/index.ts` | 未逐行统计 | DeepSeek 配置与注册 |
| `packages/llm/llm-pi-ai/src/adapter.ts` | 425 | pi-ai 多 Provider Adapter |
| `packages/llm/token-meter/src/*` | 16 文件，约 3,540 行 | Token 计量和上下文压力 |

### 3.4 持久化、压缩和 Sandbox

| 文件 | 行数 | 内容 |
|---|---:|---|
| `packages/session/session-persistence-jsonl/src/index.ts` | 1,647 | JSONL、Generation、Lease 和 Handle |
| `packages/session/session-persistence-jsonl/src/zstd.ts` | 未逐行统计 | Zstd 编码和校验 |
| `packages/session/session-persistence-jsonl/src/win32.ts` | 未逐行统计 | Windows 原子发布 |
| `packages/session/session-format-v0-to-v1/src/*` | 16 文件，约 5,072 行 | v0 到 v1 迁移 |
| `packages/session/session-format-v1-to-v2/src/*` | 10 文件，约 3,069 行 | v1 到 v2 迁移 |
| `packages/session/session-format-v2-to-v3/src/*` | 15 文件，约 2,658 行 | v2 到 v3 迁移 |
| `packages/compaction/compaction-basic/src/*` | 9 文件，约 4,855 行 | 自动压缩与恢复 |
| `packages/sandbox/sandbox/src/index.ts` | 未逐行统计 | Sandbox Seam |
| `packages/sandbox/sandbox-local/src/*` | 10 文件，约 1,919 行 | 跨平台本地 Sandbox |
| `packages/sandbox/sandbox-windows-acl/src/*` | 23 文件，约 4,233 行 | Windows ACL 后端 |
| `packages/interaction/user-approval/src/*` | 未全部统计 | Approval Seam |

### 3.5 Web、SDK 和 Subagent

| 文件 | 行数 | 内容 |
|---|---:|---|
| `packages/bundle/web-app/src/index.ts` | 未逐行统计 | Dist、信任采样和 Browser Handoff |
| `packages/bundle/web-app/src/startup.ts` | 88 | Web Flags |
| `packages/host/webserver/src/index.ts` | 未逐行统计 | HTTP 路由与 Lifecycle |
| `packages/client/connection/src/*` | 33 文件，约 10,385 行 | Browser Auth、RPC 和 Recovery |
| `packages/api/session-controller/src/*` | 79 文件，约 21,731 行 | Session History、Queue 和 Stream |
| `packages/subagent/subagent/src/*` | 38 文件，约 11,476 行 | Subagent Seam、Activation 和消息 |
| `packages/sdk/client/src/*` | 10 文件，约 2,335 行 | TypeScript SDK |
| `python/sdk/src/deepseek_harness/*` | 5 文件 | Python SDK |
| `packages/acp/acp/src/*` | 19 文件，约 4,470 行 | ACP Server |
| `apps/desktop-host/src/*` | 2 文件 | Desktop Host 与 Wire |
| `apps/desktop/src/*` | 未全部统计 | Electron Desktop |

## 4. 文档覆盖

已完整或重点阅读：

| 文档 | 内容 |
|---|---|
| `docs/architecture.zh.md` | 整体插件架构、Profile、Turn Flow、Session 和 Seam |
| `docs/agent-lifecycle.zh.md` | Turn/Step 时序图 |
| `docs/event-producer-consumer.zh.md` | 事件生产方和消费方矩阵 |
| `docs/cordis-primer.zh.md` | Cordis 五大概念与事件分派 |
| `docs/tool-execution-pipeline.zh.md` | Tool Pipeline 流程图 |
| `docs/tool-catalog.zh.md` | 全部交付 Tool Schema |
| `docs/subsystems/session.zh.md` | Session Event 和 Surface |
| `docs/subsystems/persistence.zh.md` | Session Persistence 契约 |
| `docs/subsystems/tools.zh.md` | ToolDefinition 和 Execution 类型 |
| `docs/subsystems/subagent.zh.md` | Subagent Provider、Activation 和消息 |
| `docs/subsystems/sandbox.zh.md` | Sandbox 模式和 Enforcement |
| `docs/subsystems/llm-streaming.zh.md` | LLM Stream 词汇 |
| `docs/subsystems/compaction.zh.md` | Compaction Seam |
| `docs/session-format-status.zh.md` | 当前发布格式与版本策略 |
| `docs/development.zh.md` | 开发布局和门禁 |
| `docs/testing.zh.md` | 测试策略 |
| `docs/user/guide/index.zh.md` | Web UI 使用 |
| `docs/user/guide/python-sdk.zh.md` | Python SDK |
| `docs/cookbook/adding-a-tool.zh.md` | Tool 扩展指南 |

同时阅读了各核心包的 README：

- `packages/core/agent-loop`
- `packages/core/session`
- `packages/core/tools`
- `packages/llm/llm`
- `packages/llm/llm-deepseek`
- `packages/llm/llm-pi-ai`
- `packages/session/session-persistence-jsonl`
- `packages/compaction/compaction-basic`
- `packages/subagent/subagent`
- `packages/interaction/user-approval`
- `packages/bundle/web-app`
- `packages/client/connection`
- `packages/host/webserver`
- `packages/api/session-controller`

## 5. Profile 和 Patch 覆盖

已确认：

- `dsh` CLI 只解析自身 Flags。
- 其他参数原样交给 App Plugin。
- Profile 模板：web、headless、sdk、sdk-minimal、acp。
- Bundle 通过 `package.json` 的 `dsh.bundle` 声明 Patch。
- 组合顺序：Bundle、Profile Patch、Home Patch、CLI Patch。
- Patch 替换整行 Config，不深合并。
- Live / Startup Patch Reload。
- `--dump-config` 与 `--dump-default-config`。
- 模块解析双 Anchor。
- Packaged Exe 使用 ESM Proxy。
- `.env` Bootstrap 变量保护。
- Fail Loud 启动策略。

未执行：

- 实际 Profile 初始化
- `dsh web`
- `dsh --dump-config`
- Plugin install
- Patch Live Reload
- Desktop Profile

## 6. Agent Loop 和 Session 覆盖

已确认：

- Turn 与 Step 定义
- Inbox 的 next-turn、next-step、inject、steer
- Agent Status
- `whenIdle`
- Maintenance
- `agent/pre-step`
- `agent/request`
- `agent/request-error`
- `agent/assistant-stream`
- `agent/turn-stopping`
- Request Header 和 Request Context
- System Prompt Surface Node
- Tool Call 调度
- Assistant Message 和 Assistant Attempt
- Request Series
- Frozen Request
- 取消和恢复
- Session Event 的 Lossless JSON 校验
- Surface Append 与 Replace
- `deriveMessages()`
- Fork 与 Seed
- Crash Repair

未执行：

- 长时间多 Turn 会话
- 进程崩溃恢复
- 多进程写 Lease
- Fork 子会话
- System Prompt 动态更新
- Compaction 与真实 Provider 联合测试

## 7. LLM 覆盖

已确认服务：

- `LlmRuntime`
- `LlmAdapter`
- Adapter Registry
- Configurable Provider Directory
- Model Discovery
- Exact Model Resolution
- Reasoning Effort
- Context Window
- System Prompt Update Mode
- Input Modalities
- Prepared Call
- Retry Policy
- Stream Waterfall
- Terminal Finish Chunk
- Failure Code Taxonomy
- Replay State

已确认 DeepSeek Adapter：

- Chat Completions
- SSE
- Thinking
- Reasoning Effort
- Files API
- Base64 Fallback
- 图片预算
- 图片压缩
- Prompt Cache Usage
- Request Extensions
- Request Attribution Header
- Session Header
- Retry-After
- Error Normalization
- Dynamic Settings
- Per-request Credential Resolution

已确认 pi-ai：

- 多 Provider 路由
- 认证
- 模型目录
- 动态发现
- 上下文和能力

未执行：

- 真实 DeepSeek API
- E2E Adapter
- pi-ai Provider E2E
- Files API 上传
- 图片 OCR 和视觉 Token
- Provider 故障注入

## 8. Tool 覆盖

已确认：

- `ToolDefinition`
- Input Schema
- Output Schema
- `defineTool`
- `execute`
- `finalizeContent`
- `timeoutMs`
- `isConcurrencySafe`
- `presentCall`
- `presentResult`
- Scoped Registry
- Allow / Deny Restrictions
- Tool Guards
- Pre / Execute / Post / Result Waterfall
- Tool Result Spill
- Cooperative Cancellation
- Parallel 和 Exclusive
- Unknown Tool
- Validation Failure
- Tool Output Validation

已盘点 Tool Catalog：

- `run_code`
- `ask_user_question`
- `exit_plan_mode`
- `bash`
- `present`
- `pwsh`
- `cordis_define`
- `cordis_inspect_*`
- `cordis_run`
- `cordis_stop`
- `cordis_undefine`
- `bash` Persistent
- `pwsh` Persistent
- `str_replace_editor`
- `edit`
- `read`
- `read_image`
- `write`
- `glob`
- `grep`
- Terminal 工具集
- Goal 工具集
- Schedule 工具集
- `lsp`
- `ralph`
- `skill`
- Session Query 工具集
- Subagent 工具集
- Subagent Control 工具集
- Job 工具集
- Agent Team 工具集
- `todo_write`
- `workflow`
- `web_fetch`
- `web_search`

未逐个调用每个 Tool，也未逐行阅读所有 Tool Implementation。

## 9. Sandbox 和 Approval 覆盖

已确认 Sandbox：

- `read-only`
- `workspace-write`
- `danger-full-access`
- Per-call Policy
- Workspace Root
- Session ID
- Linux bwrap
- Linux Landlock
- macOS Seatbelt
- Windows ACL Restricted Token
- `full` 与 `partial` Enforcement
- Denial Signatures
- Runner Failure Rules
- Fail Closed

已确认 Approval：

- `ask`
- `never`
- allowed-once
- denied
- cancelled
- unavailable
- `approval/request`
- `approval/asked`
- `approval/decided`
- 无 Answerer 时拒绝
- 请求必须位于未结束 Turn

未执行：

- Linux 多内核 ABI
- macOS Seatbelt
- Windows ACL
- Sandbox Escalation
- Approval UI
- 恶意命令测试

## 10. Session Persistence 和 Migration 覆盖

已确认：

- JSONL v0 到 v3
- Zstd 与 Checksum
- 原始 JSONL
- Per-session Artifact
- Atomic Materialization
- Batch Append
- Fsync
- Single Writer Lease
- Torn Tail Truncation
- Generation Selection
- Future Version Refusal
- Adjacent Migration
- Migration Publication
- Read/Write Handle
- Revision Token
- Flush Barrier
- Crash Repair

未执行：

- 真实 Lease 双进程测试
- 大规模 Session
- Zstd Corruption
- 版本迁移
- Windows Atomic Rename
- Crash Recovery E2E

## 11. Web、SDK、ACP 和 Desktop 覆盖

Web 已确认：

- `dsh web`
- 默认 Loopback
- 随机启动 Token
- 签名 Cookie
- Host 和 Origin 校验
- Cross-site 拒绝
- Remote RPC
- WebSocket Mux
- SSE 或事件流
- 断线恢复
- Session History 分页
- Queue 和 Steering
- 文件上传
- 文件媒体 Route
- Agent Presets

SDK 已确认：

- TypeScript SDK
- Python SDK
- JSON-RPC Profile
- Session 生命周期
- 版本化 Snapshot
- ACP 自动化服务

Desktop 已确认：

- Electron
- 内置 Node Host
- 私有 dsh Runtime
- Versioned Framing
- Node IPC 和 `dsh-app://`
- 不开放 Web Server
- 私有 pnpm Store

未执行：

- 浏览器 E2E
- 认证 Token 交换
- WebSocket 重连
- Python SDK
- TypeScript SDK
- ACP
- Electron 打包、签名和启动

## 12. 测试覆盖情况

测试规模：

- 约 1,278 个测试文件
- 约 373,672 行

测试类型：

- Unit
- Properties
- E2E
- Snapshot
- Expected Output
- Web Snapshot
- Stress
- Benchmark
- Migration
- JSONL Lease
- Crash Recovery
- Sandbox
- Subagent
- Loader Composition
- Documentation
- Generated Catalog
- Package Invariant

当前环境：

- Node.js `v25.2.1`
- pnpm `11.7.0`
- npm `11.6.2`
- Python `3.13.14`
- `uv` 不存在
- `node_modules` 不存在

未执行：

- `pnpm install`
- `pnpm run build`
- `pnpm run test`
- `pnpm run test:coverage`
- `pnpm run test:e2e`
- `pnpm run test:snapshot`
- `pnpm run typecheck`
- `pnpm run lint`
- `pnpm run doc-sync`
- `pnpm run website:build`

## 13. 未覆盖或未验证范围

- 全部 790,140 行非测试源码
- 全部 373,672 行测试代码
- 所有 Client UI 组件
- Desktop 完整实现
- 所有 Tool 细节
- 所有 Provider
- 所有 Native 和平台实现
- 所有 Snapshot
- Benchmark 和 Stress
- Remote、Bridge 和 Agent Team 的真实运行
- 文档网站构建
- 第三方依赖内部实现
- 真实 API、模型和图片服务

## 14. 证据可信度分级

| 级别 | 含义 | 示例 |
|---|---|---|
| A | 已读取完整源码或关键连续段 | CLI、App Boot、Agent Loop、Session、Tool、LLM、JSONL、Sandbox、Web Auth |
| B | 已审阅官方文档、接口和关键实现 | Subagent、Compaction、Web Controller、SDK、ACP |
| C | 只做结构和职责盘点 | UI、Desktop、全部 Tool、外围包 |
| D | 未执行，不能确认运行时结果 | 全部测试、E2E、Snapshot、Provider、Sandbox 和 Desktop |

## 15. 最终覆盖评价

对 DeepSeek Harness 的核心运行链，当前覆盖已经可以支持：

- 理解 Profile、Bundle 和 Patch 如何生成运行产品
- 理解 Session Event 如何成为模型历史事实源
- 理解 Turn/Step/Inbox 的完整生命周期
- 理解 LLM Adapter 与 Prepared Call
- 理解 Tool Pipeline 和 PTC
- 理解 Sandbox 与 Approval 的 Fail-closed 设计
- 理解 JSONL Session 格式、迁移和崩溃修复
- 理解 Web、Headless、SDK、ACP 和 Desktop 如何共享核心
- 提炼适合 Algocode 的 Session、Runner、Permission 和 Budget 设计

不能据此声称：

- 全仓源码已逐行阅读
- 官方测试已通过
- 所有平台 Sandbox 行为已实测
- 所有 Provider 协议已验证
- 当前主干行为与所有历史版本兼容
- 文档和实现不存在漂移

后续如果直接采用该架构，应优先验证 Session Format、Sandbox、Tool Cancellation、Provider Adapter 和 Web 认证，而不是只验证一个最简单的 Headless Prompt。
