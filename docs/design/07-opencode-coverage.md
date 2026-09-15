# OpenCode 阅读覆盖台账

> 对应设计文档：`07-opencode-design.md`  
> 分析日期：2026-09-15  
> 分析对象：`C:\Users\Administrator\Desktop\opencode-dev\opencode-dev`  
> 快照状态：未安装依赖，未执行官方测试、类型检查和构建

## 1. 覆盖结论

OpenCode 是大型 TypeScript monorepo，并且正处于 V1 到 V2 迁移期。本次没有声称对所有 6,626 个文件逐行阅读。

实际覆盖策略：

1. 盘点顶层目录、Workspace、Package 和主要 Surface。
2. 完整或重点阅读 V2 Session、Tool、Provider 和 Policy 规范。
3. 精读 V1 Session、Prompt、Processor、Compaction、Permission、Plugin、MCP、Snapshot 和 HTTP Session API 的核心代码。
4. 精读 V2 Event、Input、Projector、Context Epoch、Runner、Tool Registry 和 Tool Output Store。
5. 精读独立 LLM 包的 README、架构说明、Route、Protocol、Transport、Executor 和两个主要协议。
6. 对 SDK、Schema、Agent、Provider Catalog、TUI、Desktop、Web、UI 和其余 Package 做接口或结构审阅。
7. 测试只做数量、目录和策略盘点，没有逐测试文件执行。
8. 没有安装 `node_modules`，没有运行 `bun test`、`bun typecheck`、构建或真实 Provider 请求。

因此，本台账中的“精读”不等于对每个超长文件的每一行都完成逐字阅读；对 1,000 行以上文件，主要覆盖接口、主运行链、状态机、边界条件和风险分支。

## 2. 仓库规模

### 2.1 全仓统计

统计范围排除 `.git` 和 `node_modules`。

| 指标 | 数值 |
|---|---:|
| 文件数 | 6,626 |
| 文本行数 | 1,138,492 |
| 字节数 | 131,876,912 |
| MiB | 约 125.8 |

### 2.2 `src` 目录规模

| 包 | 文件数 | 行数 | 覆盖级别 |
|---|---:|---:|---|
| `app` | 481 | 152,345 | 结构审阅 |
| `opencode` | 408 | 83,563 | 核心精读 + 结构审阅 |
| `ui` | 1,682 | 36,893 | 外围审阅 |
| `tui` | 185 | 33,717 | 结构审阅 |
| `core` | 322 | 33,656 | 核心精读 + 结构审阅 |
| `session-ui` | 114 | 21,424 | 外围审阅 |
| `llm` | 56 | 9,533 | 核心精读 + 协议审阅 |
| `desktop` | 126 | 8,526 | 结构审阅 |
| `web` | 681 | 8,293 | 外围审阅 |
| `codemode` | 26 | 6,897 | 外围审阅 |
| `client` | 12 | 4,654 | 接口级审阅 |
| `schema` | 64 | 3,387 | 核心 Schema 审阅 |
| `effect-drizzle-sqlite` | 19 | 3,238 | 结构审阅 |
| `plugin` | 37 | 2,341 | 接口级审阅 |
| `server` | 28 | 1,682 | 结构审阅 |
| `protocol` | 22 | 1,582 | 接口级审阅 |

## 3. 阅读级别定义

| 级别 | 含义 |
|---|---|
| A：完整精读 | 文件主体被完整阅读，并纳入运行链判断 |
| B：核心精读 | 接口、状态机、关键函数和错误分支被重点阅读 |
| C：结构审阅 | 目录、导出、依赖和职责被审阅，未覆盖全部实现 |
| D：仅盘点 | 只统计存在性、规模或包关系 |

本次主要文件为 A/B/C，没有把 D 级内容包装成已精读。

## 4. V2 规范阅读清单

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `CONTEXT.md` | 225 | A | Session Runtime 词汇、Context、Tool Output、SDK 契约与 Embedded |
| `AGENTS.md` | 161 | A | 仓库编辑和开发约定 |
| `specs/v2/session.md` | 231 | A | Session、Input、Runner、Context Epoch、Compaction 与 V1 Parity |
| `specs/v2/tools.md` | 186 | A | Tool make、Registration、Scope、Stale 和 Output Bounding |
| `specs/v2/provider-model.md` | 400 | A | Provider、Model、Endpoint、Variant 和 Plugin Catalog |
| `specs/v2/provider-policy.md` | 291 | A | Provider Policy、排序、迁移和边界 |
| `packages/llm/README.md` | 131 | A | LLM 包公共 API、缓存、Provider 和 Route |
| `packages/llm/AGENTS.md` | 321 | A | LLM 架构、Route、Protocol、Tool 和录制测试规范 |

## 5. CLI、Instance 与 Surface

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `packages/opencode/src/index.ts` | 142 | A | yargs 命令与全局启动 |
| `packages/opencode/src/cli/bootstrap.ts` | 11 | A | Instance Bootstrap |
| `packages/opencode/src/cli/cmd/run.ts` | 1,016 | B | Run 三类模式、参数、SDK 调用和事件消费 |
| `packages/opencode/src/cli/cmd/run/runtime.boot.ts` | 202 | B | Keymap、Provider、Variant、Limit 和 Session 并发预取 |
| `packages/opencode/src/cli/cmd/run/runtime.lifecycle.ts` | 406 | B | SDK、Relay、Session、Prompt 和 Exit Lifecycle |
| `packages/desktop/package.json` | 未统计 | C | Electron、electron-vite、Renderer 和原生依赖 |
| `packages/tui/package.json` | 未统计 | C | OpenTUI、SolidJS 和 TUI 导出 |
| `packages/app/package.json` | 未统计 | C | Vite、SolidJS、Playwright 和共享 App |
| `README.md` | 未统计 | A | 产品定位和安装方式 |
| `CONTRIBUTING.md` | 未统计 | B | 开发目录、Server、Web、Desktop 和 API 生成说明 |

未覆盖：

- 全部 CLI 子命令实现。
- TUI 全部组件和 Keymap。
- Desktop Main、Preload、Renderer 全部实现。
- Web/App 全部页面和 E2E。
- ACP 完整实现。

## 6. V1 Session、Prompt 与 Processor

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `packages/opencode/src/session/session.ts` | 1,016 | B | Session Schema、CRUD、Fork、Message/Part 和 Event 发布 |
| `packages/opencode/src/session/message-v2.ts` | 737 | B | Model Message 转换、媒体兼容、Tool Result 和 Compaction |
| `packages/opencode/src/session/prompt.ts` | 1,631 | B | V1 Prompt Loop、Subtask、System、Tool、Compaction 和 Retry |
| `packages/opencode/src/session/processor.ts` | 732 | B | LLMEvent 到 Part 的状态转换、Doom Loop、Snapshot 和 Tool Completion |
| `packages/opencode/src/session/tools.ts` | 590 | B | AI SDK Tool 装配、Plugin Hook、MCP Resource 和 Truncate |
| `packages/opencode/src/session/compaction.ts` | 608 | A | Overflow、Prune、Turn 选择、Summary、继续和 Event |
| `packages/opencode/src/session/system.ts` | 154 | A | 模型家族 Prompt、Environment、Skills 和 MCP Instructions |
| `packages/opencode/src/session/instruction.ts` | 237 | A | Global/Project Instructions、远程 URL、缓存和附近发现 |
| `packages/opencode/src/session/llm.ts` | 404 | B | Native/AI SDK 双 Runtime、Workflow Model、Tool 和 Telemetry |
| `packages/opencode/src/session/llm/native-request.ts` | 未统计 | B | AI SDK Message 到 Canonical LLMRequest |
| `packages/opencode/src/session/llm/native-runtime.ts` | 未统计 | B | LLM Route 与 V1 Tool Dispatcher 桥接 |
| `packages/opencode/src/session/llm/ai-sdk.ts` | 未统计 | C | AI SDK Stream 到 LLMEvent |
| `packages/opencode/src/session/overflow.ts` | 未统计 | B | Context Overflow 判断 |
| `packages/opencode/src/session/retry.ts` | 未统计 | C | Session Retry |
| `packages/opencode/src/session/revert.ts` | 未统计 | C | Revert 和 Snapshot 恢复 |
| `packages/opencode/src/session/summary.ts` | 未统计 | C | Summary 和 Diff |
| `packages/opencode/src/session/todo.ts` | 未统计 | C | Todo 状态 |
| `packages/opencode/src/session/status.ts` | 未统计 | C | Session Status |

未覆盖：

- Prompt 文件 1,631 行中的全部工具细节。
- 每个 Part Schema 和每个 Provider-specific 分支。
- 全部 Retry、Snapshot、Share 和 Todo 测试。
- 真实 TUI 下的并发交互。

## 7. Agent、Permission 与 Provider

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `packages/opencode/src/agent/agent.ts` | 453 | A | 内置 Agent、用户覆盖、默认 Agent 和 Agent 生成 |
| `packages/opencode/src/permission/index.ts` | 223 | A | Ruleset、Ask、Reply、Always、Deny 和 Session Pending |
| `packages/opencode/src/permission/evaluate.ts` | 1 | A | Re-export |
| `packages/opencode/src/provider/provider.ts` | 未统计 | B | V1 Provider、Model、Auth、Language Model 和默认模型 |
| `packages/core/src/policy.ts` | 49 | A | V2 Policy 和 Last Match Wins |
| `packages/core/src/permission.ts` | 310 | A | V2 Permission、Saved Approval、Ask/Assert/Reply |
| `packages/core/src/agent.ts` | 未统计 | B | V2 Agent Registry 和 Selection |
| `packages/core/src/config.ts` | 227 | A | V2 配置发现、迁移、排序和 Policy 装载 |
| `packages/core/src/config/provider.ts` | 未统计 | B | Provider 配置 Schema |
| `packages/schema/src/provider.ts` | 72 | A | Provider ID、API 和 Info |
| `packages/schema/src/model.ts` | 106 | A | Model、Variant、Capability、Cost 和 Limit |
| `packages/schema/src/agent.ts` | 38 | A | Agent V2 Info |
| `packages/schema/src/permission.ts` | 65 | A | Permission V2 Request、Rule、Ruleset 和 Event |

未覆盖：

- 全部 Provider Plugin。
- 所有账户认证与 OAuth 细节。
- Provider Catalog 全部模型元数据。
- 模型能力协商和全部 Provider Transform。

## 8. V2 Event、Input、Projector 与 Runner

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `packages/core/src/event.ts` | 638 | A | Durable Event、Transaction、Replay、Owner、Stream 和 Projector |
| `packages/core/src/session/input.ts` | 288 | A | Admit、Project、Steer、Queue 和 Promotion |
| `packages/core/src/session/projector.ts` | 455 | A | Event 到 Session/Message/Part/Input Projection |
| `packages/core/src/session/store.ts` | 63 | A | Session、Context、Runner Context 和 Message Lookup |
| `packages/core/src/session/context-epoch.ts` | 174 | A | Baseline、Snapshot、Reconcile、Replace 和 Reset |
| `packages/core/src/session/runner/index.ts` | 28 | A | Runner Interface |
| `packages/core/src/session/runner/llm.ts` | 439 | A | Provider Turn、Tool Settlement、Overflow、Steering 和 Loop |
| `packages/core/src/session/run-coordinator.ts` | 未统计 | A | Session 串行、Wake 合并、Join 和 Interrupt |
| `packages/core/src/session/history.ts` | 未统计 | B | Durable History 装载 |
| `packages/core/src/session/message-updater.ts` | 未统计 | B | Assistant/Tool Event 更新 Message |
| `packages/core/src/session/compaction.ts` | 未统计 | B | V2 Compaction |
| `packages/core/src/session/prompt.ts` | 未统计 | C | Prompt Schema 抽象 |
| `packages/core/src/session/schema.ts` | 未统计 | B | V2 Session ID 与 Info |
| `packages/core/src/session/sql.ts` | 未统计 | C | Session、Message、Input 和 Epoch 表 |
| `packages/core/src/session/event.ts` | 未统计 | B | Session Event 定义 |
| `packages/schema/src/session-input.ts` | 23 | A | Admitted 输入 |
| `packages/schema/src/event.ts` | 125 | A | Event ID、Definition、Payload 和 Version |

已确认：

- Aggregate ID 和连续 Seq。
- Durable Event 与 Projector 同事务。
- Replay 幂等与 Divergence 检测。
- Owner Claim。
- Durable Stream 的历史回放和 Live Tail。
- Prompt Admit 与 Prompted 分离。
- Steer 与 Queue 提升规则。
- Context Epoch 初始化、协调和替换。
- V2 Provider Turn 显式调用一次 `llm.stream()`。
- 工具先持久化，再执行。
- 全部本地 Tool Settlement 完成后继续。
- Overflow Compaction 只恢复一次。

未完成或标记为后续：

- 多节点 Ownership。
- Provider Retry、Timeout 和 Watchdog。
- 完整插件请求 Hook。
- 完整 Structured Output。
- 完整 `@` mention、媒体和引用展开。
- Provider-executed Tool Result 的上下文控制。
- 流式 Delta 写入的批量合并优化。
- 全局多 Session Event Stream 设计。

## 9. V2 Tool Registry

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `packages/core/src/tool/tool.ts` | 162 | A | Opaque Tool、Codec、Single Executor、Projection |
| `packages/core/src/tool/registry.ts` | 147 | A | Application/Location Overlay、Materialize、Stale 和 Bound |
| `packages/core/src/tool-output-store.ts` | 211 | A | 行/字节限制、Preview、Managed File 和 7 天清理 |
| `packages/core/src/tool/tools.ts` | 未统计 | B | 外部注册能力 |
| `packages/core/src/tool/application-tools.ts` | 未统计 | B | 进程级 Application Tool |
| `packages/core/src/tool/builtins.ts` | 未统计 | C | 内置 Tool 注册 |
| `packages/core/src/tool/read.ts` | 未统计 | C | V2 Bounded Read |
| `packages/core/src/tool/grep.ts` | 未统计 | C | V2 Grep |
| `packages/core/src/tool/bash.ts` | 未统计 | C | V2 Bash 和外部目录 |
| `packages/core/src/tool/apply-patch.ts` | 未统计 | C | V2 Add/Update/Delete |
| `packages/opencode/src/tool/registry.ts` | 455 | B | V1 Tool Registry、Agent Filter 和 Permission Filter |

已确认并记录：

- Tool Value 没有名称。
- 注册时命名。
- Scope 关闭只移除自身。
- Location 覆盖 Application。
- 最新注册胜出。
- Materialization 捕获 Identity。
- Stale Call 拒绝。
- 输入先解码。
- 输出先编码与验证。
- Model Output 统一 Bound。
- 完整文本写入 Managed Store。
- Tool Failure、Interrupt、Defect 语义分离。

## 10. Plugin、MCP、LSP、Skill 与 Snapshot

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `packages/opencode/src/plugin/index.ts` | 318 | A | Internal/External Plugin、Hooks、Event 和 Dispose |
| `packages/opencode/src/plugin/loader.ts` | 237 | A | Plan、Resolve、Load、Compat 和 Retry |
| `packages/opencode/src/mcp/index.ts` | 1,004 | B | stdio/SSE/HTTP、OAuth、Tools、Resources、Prompts |
| `packages/opencode/src/mcp/auth.ts` | 未统计 | C | MCP Auth 持久化 |
| `packages/opencode/src/mcp/oauth-provider.ts` | 未统计 | C | OAuth Provider |
| `packages/opencode/src/mcp/oauth-callback.ts` | 未统计 | C | OAuth Callback |
| `packages/opencode/src/snapshot/index.ts` | 807 | B | Git Snapshot、Track、Patch、Restore 和 Diff |
| `packages/opencode/src/lsp/server.ts` | 1,983 | B | Server Registry、Root、Spawn 和下载 |
| `packages/opencode/src/lsp/lsp.ts` | 未统计 | C | LSP 客户端与 Diagnostics |
| `packages/opencode/src/skill` | 目录 | C | Skill Discovery、Permission 和 Loading |

未覆盖：

- 全部 MCP Server 测试。
- OAuth 真实流程。
- 全部 LSP Server。
- 每个 Skill 文档和发现规则。
- Snapshot 在超大仓库上的性能。

## 11. LLM 包

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `packages/llm/src/llm.ts` | 186 | A | Request、Generate、Stream 和 GenerateObject |
| `packages/llm/src/route/protocol.ts` | 84 | A | Protocol 四轴语义 |
| `packages/llm/src/route/client.ts` | 436 | A | Route、Compile、Prepare、Stream 和 Generate |
| `packages/llm/src/route/executor.ts` | 385 | A | HTTP Execute、Retry、Redaction 和 Error |
| `packages/llm/src/route/transport/http.ts` | 155 | A | JSON HTTP、Auth、Endpoint 和 Framing |
| `packages/llm/src/route/transport/websocket.ts` | 280 | A | WebSocket Executor 和 JSON Transport |
| `packages/llm/src/protocols/openai-responses.ts` | 1,022 | B | OpenAI Responses Body、Event 和 Tools |
| `packages/llm/src/protocols/anthropic-messages.ts` | 855 | B | Anthropic Messages Body、Event 和 Tools |
| `packages/llm/src/protocols/openai-chat.ts` | 未统计 | B | OpenAI Chat Protocol |
| `packages/llm/src/protocols/gemini.ts` | 未统计 | C | Gemini Protocol |
| `packages/llm/src/protocols/bedrock-converse.ts` | 未统计 | C | Bedrock Protocol |
| `packages/llm/src/providers/openai.ts` | 未统计 | B | OpenAI Facade |
| `packages/llm/src/providers/anthropic.ts` | 35 | B | Anthropic Facade |
| `packages/llm/src/providers/openai-compatible.ts` | 未统计 | B | OpenAI-compatible Facade |
| `packages/llm/src/cache-policy.ts` | 未统计 | B | Prompt Cache 自动断点 |
| `packages/llm/src/provider-error.ts` | 未统计 | B | Provider Error 归一化 |

已确认：

- Canonical Request/Message/Tool/Event。
- Protocol、Endpoint、Auth、Framing、Transport 分层。
- HTTP 和 WebSocket 两种 Transport。
- JSON Schema 请求 Body 验证。
- Body Overlay 拒绝覆盖协议字段。
- Status Error 分类。
- 429/503/504/529 重试和指数退避。
- Header、URL Query、Body 字段和实际 Secret 的脱敏。
- Prompt Cache 自动策略。
- 录制 Cassette 和 Replay 测试策略。

未覆盖：

- 每个 Provider Facade 的所有选项。
- 全部 Protocol Test Fixture。
- 真实 Provider Cassette Replay。
- 所有 Cache 和 Media 边界。

## 12. HTTP API、SDK 与 Schema

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `packages/opencode/src/server/routes/instance/httpapi/api.ts` | 97 | A | Root、Instance、Event 和 PTY API 组合 |
| `packages/opencode/src/server/routes/instance/httpapi/groups/session.ts` | 未统计 | A | Session Endpoint、Payload 和 OpenAPI |
| `packages/opencode/src/server/routes/instance/httpapi/handlers/session.ts` | 442 | A | Session HTTP Handler 全链 |
| `packages/opencode/src/server/routes/instance/httpapi/groups/event.ts` | 未统计 | B | Event Stream API |
| `packages/opencode/src/server/routes/instance/httpapi/handlers/event.ts` | 99 | B | Event Handler |
| `packages/opencode/src/server/routes/instance/httpapi/middleware/authorization.ts` | 未统计 | B | Root Authorization |
| `packages/opencode/src/server/routes/instance/httpapi/middleware/instance-context.ts` | 未统计 | B | Instance Context |
| `packages/opencode/src/server/routes/instance/httpapi/middleware/workspace-routing.ts` | 未统计 | B | Workspace Routing |
| `packages/sdk/js/src/client.ts` | 57 | A | Legacy SDK Client |
| `packages/sdk/js/src/server.ts` | 134 | A | Spawn Server 与 TUI |
| `packages/sdk/js/src/v2/client.ts` | 93 | A | V2 SDK Client |
| `packages/sdk/js/src/v2/server.ts` | 未统计 | B | V2 Server Helper |
| `packages/schema/src/session-input.ts` | 23 | A | Input Schema |

未覆盖：

- 所有 Instance、File、PTY、MCP、Provider、TUI 和 Workspace Handler。
- OpenAPI Generation 的全部源码。
- Promise/Effect SDK 的所有生成结果。
- Embedded OpenCode 的完整实现。

## 13. 测试覆盖

### 13.1 数量

| 范围 | `.test.ts` 数量 | 文件大小 |
|---|---:|---:|
| `packages/opencode/test` | 252 | 约 15.05 MB |
| `packages/core/test` | 144 | 约 1.32 MB |
| `packages/llm/test` | 30 | 约 0.84 MB |
| `packages/sdk/js/test` | 1 | 未单独统计 |
| 四个目录合计 | 427 | - |

### 13.2 主要测试目录

`packages/opencode/test`：

- account
- acp
- agent
- auth
- background
- cli
- config
- control-plane
- filesystem
- format
- git
- ide
- image
- installation
- lsp
- mcp
- patch
- permission
- plugin
- project
- provider
- question
- server
- session
- share
- skill
- snapshot
- storage
- tool
- v2

`packages/core/test`：

- config
- effect
- filesystem
- github-copilot
- plugin
- process
- pty
- skill
- system-context
- util

`packages/llm/test`：

- provider
- protocol
- transport

### 13.3 覆盖策略

- Provider 协议测试使用 Fixture-first。
- 普通测试使用 Scripted Response。
- 真实 Provider 测试使用 Cassette。
- 默认 Replay。
- `RECORD=true` 才重新录制。
- 录制的请求按顺序匹配。
- 匹配 Method、URL、允许 Header 和 Canonical JSON。
- 二进制响应使用 Base64。

### 13.4 未执行

没有执行：

```bash
bun install
bun test
bun typecheck
bun run lint
bun run build
```

也没有运行：

- `opencode run`
- `opencode serve`
- TUI
- Desktop
- Web
- MCP OAuth
- LSP
- 真实 Provider
- Native LLM 与 AI SDK 的运行时切换
- V2 Session Runner
- HTTP API Exercise

因此，本文只评价静态设计，不声明运行时正确性。

## 14. 未覆盖范围

未逐行或未完整覆盖：

1. `packages/app` 全部 UI、Hooks、页面和测试。
2. `packages/ui` 全部基础组件。
3. `packages/session-ui` 全部会话展示逻辑。
4. `packages/tui` 全部 OpenTUI 组件和交互。
5. `packages/desktop` Electron Main、Preload、Renderer 和打包。
6. `packages/console`、`stats`、`enterprise`、`identity`、`slack`。
7. 全部 CLI 子命令。
8. 全部内置 Tool 实现。
9. 全部 Provider Plugin、OAuth 和模型元数据。
10. 全部 MCP、LSP、Skill 和 Snapshot 测试。
11. 全部 LLM Protocol、Provider Facade 和 Cassette。
12. 全部 HTTP Endpoint 和 Handler。
13. 全部生成 SDK 和 OpenAPI 文件。
14. 全部 Playwright E2E 和性能测试。
15. 发布、安装、升级和打包流水线。

## 15. 证据可信度

| 结论 | 级别 | 依据 |
|---|---|---|
| 仓库规模、Package、Bun 和 MIT | A | 本地统计与 `package.json` |
| V1 是当前完整产品主链 | A | 规范、CLI、Server、Prompt 和代码导出 |
| V2 使用事件溯源和连续 Seq | A | `event.ts`、Schema 和 V2 规范 |
| V2 输入先 Admit 后 Prompt | A | `session/input.ts` 和 Projector |
| V2 Runner 每个 Provider Turn 调用一次 `llm.stream()` | A | `runner/llm.ts` |
| Tool 先持久化再执行 | A | `runner/llm.ts`、`tool/registry.ts` |
| Location Tool 覆盖 Application Tool | A | `tool/registry.ts` |
| Stale Tool Call 会拒绝执行 | A | Tool Materialization 和 Settle 分支 |
| Context Epoch 使用不可变 Baseline 和动态更新 | A | `context-epoch.ts` 和 `CONTEXT.md` |
| Permission 与 Policy 都是最后匹配胜出 | A | `permission.ts`、`policy.ts` |
| LLM Route 分为 Protocol/Endpoint/Auth/Framing/Transport | A | `protocol.ts`、`client.ts` 和 README |
| Prompt Cache 默认开启 | A | LLM README 和 Cache Policy |
| V2 Parity 不完整 | A | `specs/v2/session.md` 的 `partial` 和 `missing` 表 |
| TUI、Desktop、Web 完整运行行为 | C | 只做结构与 Package 审阅 |
| 全部测试通过 | D | 未运行，不能声明 |
| 所有 Provider 均可使用 Native Runtime | D | 代码明确只支持部分 Provider，不能声明 |

## 16. 最终覆盖声明

本次对 OpenCode 的核心架构链路形成了 A/B 级证据：

```text
CLI / Server / SDK
  -> V1 Session / Prompt / Processor
  -> V2 Event / Input / Projector / Context Epoch / Runner
  -> Tool / Permission / Provider
  -> LLM Protocol / Transport
  -> Plugin / MCP / LSP / Snapshot
```

对 UI、全部 Plugin、全部 Provider、全部测试和部署流程只形成 B/C/D 级证据。

因此，设计文档中的架构结论可信度较高；但任何“实际运行、测试通过、所有 Provider 可用、所有 V2 Parity 已完成”的结论都不成立。
