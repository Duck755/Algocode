# Codex 阅读覆盖台账

> 对应设计文档：`08-codex-design.md`  
> 分析日期：2026-09-15  
> 分析对象：`C:\Users\Administrator\Desktop\codex-main\codex-main`  
> 许可证：Apache-2.0  
> 快照状态：未编译、未测试、未运行真实模型或 TUI

## 1. 覆盖结论

Codex 是数万文件中的大型 Rust/TypeScript/Python 仓库。本次没有声称对所有源码逐行阅读。

覆盖策略：

1. 盘点顶层目录、Rust Workspace、Crate、SDK、文档和 Bazel/Cargo 构建。
2. 精读 CLI、Core ThreadManager、CodexThread、Session、Submission Loop、TurnInput、RegularTask 和 run_turn。
3. 精读 ModelClient、Responses Request、HTTP/WebSocket、Retry 和 Error 处理主链。
4. 精读 Tool Registry、ToolRouter、Orchestrator、Parallel、Sandbox Manager 和 ExecPolicy。
5. 精读 Rollout、SQLite State DB、ThreadStore 和 LiveThread。
6. 阅读 App Server、App Server Client、App Server Protocol、Daemon 和 SDK。
7. 对 TUI、MCP、Plugins、Skills、Hooks、Memories、Realtime、Multi-Agent 和远程执行做结构或接口审阅。
8. 统计测试文件和 Snapshot 数量，但没有执行任何测试。
9. 根目录 `docs/` 多为官网跳转桩，不能作为完整架构依据。
10. `codex-rs/docs/protocol_v1.md` 明确声明代码可能不完全匹配该规范，因此文档只作为术语辅助。

## 2. 仓库规模

### 2.1 全仓统计

排除 `.git`、`target`、`node_modules` 和 vendored V8。

| 指标 | 数值 |
|---|---:|
| 文件数 | 7,811 |
| 文本行数 | 2,008,313 |
| 字节数 | 77,334,385 |
| 约合大小 | 73.75 MiB |

### 2.2 Rust Crate `src` 规模

| Crate | 文件数 | 行数 | 覆盖级别 |
|---|---:|---:|---|
| `tui` | 1,707 | 345,413 | 结构审阅 |
| `core` | 525 | 225,171 | 核心精读 + 结构审阅 |
| `app-server` | 135 | 56,859 | 核心接口审阅 |
| `core-plugins` | 83 | 45,567 | 外围审阅 |
| `exec-server` | 115 | 40,665 | 结构审阅 |
| `app-server-protocol` | 64 | 34,685 | 核心协议审阅 |
| `thread-store` | 65 | 33,341 | 核心接口审阅 |
| `protocol` | 69 | 29,598 | 核心 Schema 审阅 |
| `config` | 86 | 28,259 | 结构审阅 |
| `cli` | 67 | 28,153 | 核心入口审阅 |
| `network-proxy` | 55 | 27,803 | 核心边界审阅 |
| `rmcp-client` | 77 | 26,462 | 接口级审阅 |
| `windows-sandbox-rs` | 84 | 24,682 | 结构审阅 |
| `state` | 48 | 23,989 | 核心接口审阅 |
| `codex-mcp` | 49 | 23,374 | 接口级审阅 |
| `app-server-transport` | 34 | 18,168 | 结构审阅 |
| `rollout` | 32 | 16,039 | 核心精读 |
| `hooks` | 34 | 15,671 | 接口级审阅 |
| `sandboxing` | 23 | 9,441 | 核心精读 |
| `model-provider` | 22 | 6,145 | 核心精读 |
| `tools` | 36 | 6,819 | 核心结构审阅 |

## 3. 阅读级别

| 级别 | 含义 |
|---|---|
| A：完整精读 | 文件主体被完整阅读，并进入设计结论 |
| B：核心精读 | 阅读接口、主流程、状态机、错误和边界分支 |
| C：结构审阅 | 阅读模块目录、导出、依赖和职责 |
| D：仅盘点 | 只统计文件、测试或存在性 |

大型文件如 `turn.rs`、`session/mod.rs`、`protocol.rs`、`models.rs` 和 `client.rs` 没有对每一行逐字阅读，主要覆盖主状态、主流程、关键类型和风险。

## 4. 顶层与官方文档

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `README.md` | 81 | A | 产品定位、安装和 Codex 各 Surface |
| `AGENTS.md` | 320 | A | Rust 约定、Core 约束、Context 规则、测试和代码审查规则 |
| `codex-rs/Cargo.toml` | 629 | A | Workspace Crates 与依赖 |
| `codex-rs/docs/protocol_v1.md` | 191 | A | V1 Thread/Task/Turn 术语和事件流 |
| `codex-rs/docs/bazel.md` | 180 | A | Bazel、Cargo、Lockfile 和 CI |
| `docs/getting-started.md` | 3 | A | 官网跳转桩 |
| `docs/config.md` | 15 | A | 官网跳转桩与 Hooks 说明 |
| `docs/sandbox.md` | 3 | A | 官网跳转桩 |
| `docs/execpolicy.md` | 3 | A | 官网跳转桩 |
| `docs/authentication.md` | 3 | A | 官网跳转桩 |
| `docs/agents_md.md` | 3 | A | 官网跳转桩 |
| `docs/skills.md` | 3 | A | 官网跳转桩 |
| `docs/exec.md` | 3 | A | 官网跳转桩 |
| `docs/slash_commands.md` | 3 | A | 官网跳转桩 |

结论：仓库内用户文档主要依赖 `developers.openai.com/codex`，不能从跳转桩还原完整行为。

## 5. CLI、TUI、Exec 与 App Server

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `codex-rs/cli/src/main.rs` | 5,167 | B | 命令、Login、App Server、Sandbox、Cloud、Feature 和分发 |
| `codex-rs/tui/src/lib.rs` | 3,942 | C | TUI 启动、App Server Client、配置和主要模块 |
| `codex-rs/tui/src/app.rs` | 1,073 | B | TUI 顶层状态、事件循环和请求 |
| `codex-rs/tui/src/chatwidget.rs` | 2,118 | B | Chat、流式输出、Tool、Approval 和渲染 |
| `codex-rs/exec/src/lib.rs` | 2,337 | B | Headless Exec、Event Processor、Thread/Turn |
| `codex-rs/app-server/src/lib.rs` | 1,580 | B | JSON-RPC、连接、生命周期、Shutdown |
| `codex-rs/app-server-protocol/src/lib.rs` | 71 | A | Protocol Export 入口 |
| `codex-rs/app-server-client/src/lib.rs` | 2,131 | B | In-process/Remote Client 与 typed request |
| `codex-rs/app-server-client/README.md` | 66 | A | In-process Client 目的、Transport 和 Backpressure |
| `codex-rs/app-server-daemon/README.md` | 179 | A | Daemon、Remote Control、更新和生命周期 |
| `codex-rs/app-server-transport/src/lib.rs` | 45 | B | Transport 模块边界 |
| `codex-rs/app-server/README.md` | 226 | A | User Verification、Attachment、Plugin 和协议细节 |

未覆盖：

- 全部 TUI 组件和 Snapshot。
- 全部 App Server Handler。
- 全部 Remote Control 认证和 Pairing。
- CLI 所有参数组合。

## 6. Core Thread、Session、Turn 与 Input

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `codex-rs/core/src/lib.rs` | 219 | A | Core 导出、Crate Bloat 警告和模块边界 |
| `codex-rs/core/src/session/mod.rs` | 4,936 | B | Session、所有状态、模块与主服务 |
| `codex-rs/core/src/session/session.rs` | 1,833 | B | Session 配置、启动、状态和 Step |
| `codex-rs/core/src/session/turn.rs` | 3,039 | B | Turn、Context、模型请求、工具和 Compaction |
| `codex-rs/core/src/session/turn_input.rs` | 698 | A | Start、Steer、Admission、Settings 和 Recovery |
| `codex-rs/core/src/session/input_queue.rs` | 659 | A | Pending、Mailbox、Steer 和 Activity |
| `codex-rs/core/src/session/handlers.rs` | 676 | A | Submission Loop 和主要 Op |
| `codex-rs/core/src/session/turn_context.rs` | 1,195 | B | Turn Context、Environment、Permission 和 Settings |
| `codex-rs/core/src/tasks/mod.rs` | 986 | B | SessionTask、生命周期、Abort 和 Spawn |
| `codex-rs/core/src/tasks/regular.rs` | 98 | A | RegularTask 循环 |
| `codex-rs/core/src/tasks/compact.rs` | 76 | A | Manual Compaction Task |
| `codex-rs/core/src/codex_thread.rs` | 1,013 | A | Thread 对外 API、Submit、Resume、Fork 和 Shutdown |
| `codex-rs/core/src/thread_manager.rs` | 2,480 | B | Thread 创建、恢复、Fork、Store 和生命周期 |

已确认：

- 一个 Session 同时只有一个主 Task。
- Event 和 Submission 分层。
- Start、Steer、StartIfIdle 和 Recovery 的差异。
- Thread 与 Subagent 的 Parent/Lineage。
- ThreadManager 负责 loaded Thread Map。
- RegularTask 会在 Pending Input 存在时继续 run_turn。
- Core 明确警告不要继续增加 `codex-core`。

未完整覆盖：

- `session/mod.rs` 全部 4,936 行。
- 所有环境选择和 Workspace Root 分支。
- 所有 Goal、Memory、Realtime 和 Guardian 细节。
- 所有测试。

## 7. Model Client、Protocol 与 Provider

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `codex-rs/core/src/client.rs` | 2,689 | B | HTTP/WS、Responses Request、Auth、Retry 和 Stream |
| `codex-rs/core/src/client_common.rs` | 141 | A | Prompt 和 ResponseStream |
| `codex-rs/core/src/responses_retry.rs` | 178 | A | Stream Retry、Connection Retry 和 HTTP Fallback |
| `codex-rs/protocol/src/protocol.rs` | 6,338 | C | Op、EventMsg、Thread、Turn 和协议类型 |
| `codex-rs/protocol/src/models.rs` | 4,421 | C | ResponseItem、ContentItem 和 Model 类型 |
| `codex-rs/protocol/src/turn_input.rs` | 246 | A | Turn Input Mode 与 Type |
| `codex-rs/protocol/src/items.rs` | 828 | B | TurnItem 与展示 Item |
| `codex-rs/model-provider/src/provider.rs` | 1,306 | B | Provider Trait、Capability、Auth 和 Models |
| `codex-rs/model-provider/src/models_endpoint.rs` | 645 | B | `/models` 获取与 Auth |
| `codex-rs/model-provider-info/src/lib.rs` | 710 | A | Provider Config、Wire API、Retry 和 Base URL |
| `codex-rs/codex-api/src/lib.rs` | 121 | A | API 导出边界 |
| `codex-rs/codex-api/src/common.rs` | 406 | A | ResponsesRequest、Event 和 Text Controls |
| `codex-rs/http-client/src/lib.rs` | 65 | B | HTTP Client 与 Proxy 导出 |
| `codex-rs/websocket-client/src/lib.rs` | 241 | B | Proxy-aware WebSocket 和 TLS |

已确认：

- 当前 Wire API 只有 Responses。
- HTTP SSE 与 WebSocket 两种 Transport。
- WebSocket 可以 Turn 内复用和增量发送。
- Turn State 用于 Sticky Routing。
- HTTP Fallback 是 Session 级状态。
- Request Max Retry 默认 4。
- Stream Max Retry 默认 5。
- Stream Idle Timeout 默认 300 秒。
- WebSocket Connect Timeout 默认 15 秒。
- `store = false`。
- `parallel_tool_calls` 由 Prompt 与 Model 能力共同决定。
- Structured Output 使用 `text.format = json_schema`。

未覆盖：

- `client.rs` 全部 Auth Recovery 分支。
- 所有 Responses Lite 差异。
- 所有 Attestation。
- 所有 Realtime WebRTC。
- 真实 Provider 协议兼容测试。

## 8. Tool Registry、Router 与内置工具

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `codex-rs/core/src/tools/mod.rs` | 143 | A | Tool Mode、输出格式和 Tool 边界 |
| `codex-rs/core/src/tools/registry.rs` | 826 | A | Registry、Hooks、Telemetry、Dispatch 和 Post Hook |
| `codex-rs/core/src/tools/router.rs` | 385 | A | ToolPlan、Exposure、Tool Call 和 Dispatch |
| `codex-rs/core/src/tools/orchestrator.rs` | 556 | A | Approval、Sandbox、Escalation 和 Retry |
| `codex-rs/core/src/tools/parallel.rs` | 717 | A | Parallel Gate、Cancellation 和 Tool Timing |
| `codex-rs/core/src/tools/spec_plan.rs` | 1,553 | B | Built-ins、MCP、Plugins、Exposure 和 Namespace |
| `codex-rs/core/src/tools/handlers/shell_spec.rs` | 348 | A | `exec_command`、`write_stdin` 和权限参数 |
| `codex-rs/core/src/tools/handlers/apply_patch_spec.rs` | 32 | A | Freeform Apply Patch |
| `codex-rs/core/src/tools/handlers/unified_exec.rs` | 159 | A | Shell Resolution 和 Login Shell |
| `codex-rs/core/src/tools/handlers/view_image.rs` | 509 | A | 图片读取和模型输入 |
| `codex-rs/core/src/tools/handlers/request_user_input.rs` | 175 | A | 根 Thread 用户问题与保留回答 |
| `codex-rs/core/src/tools/handlers/multi_agents_v2.rs` | 85 | B | Multi-Agent V2 Tool Surface |
| `codex-rs/tools/src/lib.rs` | 108 | A | 外部 Tools Crate API |
| `codex-rs/tools/src/tool_spec.rs` | 193 | A | Function、Namespace、Freeform、WebSearch、ToolSearch |

已确认：

- Tool Name 有 Namespace。
- 工具可以 Direct、Deferred、Code Mode、Hidden。
- Tool Router 在每个 Step 冻结可见工具。
- 并行工具通过 RwLock 控制，非并行工具独占。
- PreToolUse 可阻止或重写 Input。
- PostToolUse 可阻止或替换模型可见结果。
- Approval 可以触发沙箱内首次执行和无沙箱重试。
- 未授权、危险或不可表达策略可能直接拒绝执行。

未覆盖：

- 全部内置 Tool Handler。
- 全部 Code Mode 细节。
- 全部 MCP 动态工具。
- Plugin 和 Extension Tool。
- 每个 Tool 的 Schema 和测试。

## 9. Sandbox、ExecPolicy 与 Network Proxy

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `codex-rs/sandboxing/src/manager.rs` | 822 | A | Sandbox Type、Transform、Platform 选择和 Backend |
| `codex-rs/sandboxing/src/seatbelt.rs` | 1,075 | B | macOS Policy、路径、Socket 与网络 |
| `codex-rs/sandboxing/src/bwrap.rs` | 195 | A | Bubblewrap Probe、WSL1 与 PATH |
| `codex-rs/sandboxing/src/landlock.rs` | 107 | A | Linux Helper 和环境代理 |
| `codex-rs/sandboxing/src/windows.rs` | 401 | B | Restricted Token、Elevated 和路径 Override |
| `codex-rs/network-proxy/src/lib.rs` | 118 | A | Proxy 公共边界 |
| `codex-rs/network-proxy/src/http_proxy.rs` | 1,917 | B | HTTP Proxy、MITM、Policy 和 Runtime |
| `codex-rs/core/src/exec_policy.rs` | 1,175 | B | ExecPolicy、Prefix、Approval 和危险命令 |
| `codex-rs/core/src/exec.rs` | 1,252 | B | Exec、Timeout、Output、Sandbox 和 Cancellation |
| `codex-rs/execpolicy/src/lib.rs` | 未统计 | B | Policy Parser、Rule、Evaluation 和 Amendment |

已确认：

- macOS、Linux、Windows 平台 Sandbox 差异。
- Sandbox 不能表达策略时会拒绝，而不是静默放宽。
- Bubblewrap 与 Landlock/Seccomp 的关系。
- WSL1 明确不支持 Bubblewrap User Namespace。
- Windows Restricted Token 与 Elevated 能力不对称。
- Network Proxy 支持域名、Socket、MITM、Credential Broker。
- ExecPolicy 支持 Allow、Prompt、Forbidden。
- Danger Command Heuristic 与 Prefix Rule 是不同层。
- `/shell` 是显式 Full Access Escape Hatch。

未覆盖：

- Sandbox 在三个平台上的全部测试。
- MITM CA 生成和安装。
- Credential Broker 全部 Provider。
- Remote Network Config Reload。
- ExecPolicy Parser 全部语法。

## 10. Rollout、SQLite 与 ThreadStore

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `codex-rs/rollout/src/recorder.rs` | 2,227 | B | JSONL Writer、List、Resume、Compression 和 Lock |
| `codex-rs/rollout/src/state_db.rs` | 744 | A | SQLite Init、Backfill、List、Repair 和 Migration |
| `codex-rs/rollout/src/lib.rs` | 167 | A | Rollout Durable API |
| `codex-rs/thread-store/src/lib.rs` | 114 | A | ThreadStore Public Interface |
| `codex-rs/thread-store/src/live_thread.rs` | 417 | B | Live Thread、Append、Flush、Read 和 History |
| `codex-rs/state/src/lib.rs` | 149 | A | State Runtime 导出和常量 |
| `codex-rs/state/src/runtime.rs` | 764 | B | SQLite Runtime、Goals、Memories 和 Threads |
| `codex-rs/state/src/sqlite.rs` | 332 | B | 多 DB Path、Pool 和配置 |
| `codex-rs/rollout/src/metadata.rs` | 489 | B | Rollout Metadata 和 Backfill |
| `codex-rs/rollout/src/compression.rs` | 未统计 | C | Rollout 压缩 |
| `codex-rs/rollout/src/list.rs` | 未统计 | C | Cursor、Sort 和 Page |
| `codex-rs/rollout/src/search.rs` | 未统计 | C | Rollout Search |

已确认：

- Rollout JSONL 是完整会话记录。
- SQLite 负责快速 Metadata Query。
- ThreadStore 将 Core 与具体存储解耦。
- Local 与 InMemory Store 两种实现。
- 支持 Cursor Pagination。
- 支持 Fork、Revert、Archive、Delete。
- 支持 Rollout Compression。
- 支持 SQLite Backfill、Read Repair 和 Corruption Recovery。
- Writer 使用后台 Task 和 Writer Lock。

未覆盖：

- 全部 Rollout Migration 和 Compression 测试。
- 所有 SQLite Query Plan 和性能。
- 大仓库与长 Session 实际表现。
- 多进程并发写同一 CODEX_HOME 的全部场景。

## 11. Compaction

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `codex-rs/core/src/compact.rs` | 828 | A | Local Compaction、Prompt、Summary 和 History Replacement |
| `codex-rs/core/src/compact_remote_v2.rs` | 1,234 | B | Remote Compaction、Retention、Image Budget 和 Fallback |
| `codex-rs/core/src/compact_token_budget.rs` | 未统计 | C | Token Budget Compaction |
| `codex-rs/core/src/compact_remote_history.rs` | 未统计 | C | Remote History Group |
| `codex-rs/core/src/compact_model_fallback.rs` | 未统计 | C | Model Fallback |
| `codex-rs/core/src/session/context_window.rs` | 未统计 | B | Context Window Status |

已确认：

- Local Compaction 保留 Summary 和最近用户消息。
- 默认用户消息保留预算约 20K Tokens。
- Remote Compaction V2 保留预算约 64K Tokens。
- 单条保留 Agent Message 上限约 10K Tokens。
- 支持图片预算。
- 支持 PreCompact/PostCompact Hook。
- 支持压缩失败后的 Retry 和终止错误。
- Compaction 替换活动模型历史，而不是删除 Rollout。

未覆盖：

- 所有 Context Window 组合。
- 所有 Remote Compaction Provider。
- 所有图片预算测试。
- 长时间多轮 Compaction 的真实质量。

## 12. MCP、Plugins、Skills、Hooks、Memories 与 Multi-Agent

| 范围 | 覆盖 | 说明 |
|---|---|---|
| MCP Runtime | 接口级审阅 | Tool、Resource、Prompt、OAuth、Elicitation、Refresh |
| `codex-mcp` | 接口级审阅 | MCP Connection Manager 与缓存 |
| `rmcp-client` | 结构审阅 | RMCP Client 与协议适配 |
| Plugins | 结构审阅 | Install、Marketplace、Capability、Tool Suggest |
| Skills | 结构审阅 | Discovery、Approval、Dependency、Invocation |
| Hooks | 接口级审阅 | Lifecycle、Pre/Post Tool、Block、Context |
| Memories | 结构审阅 | Stage 1、Global Consolidation、Job、Retention |
| Multi-Agent | 接口级审阅 | Spawn、Message、Wait、Resume、Close、Follow-up |
| Realtime | 外围审阅 | WebRTC、Sideband、Voice |
| Guardian | 外围审阅 | Review、Approval、Retention 和 Risk |

未覆盖：

- 所有扩展经过真实端到端运行。
- 所有 Plugin Marketplace 行为。
- 所有 Skill 文件格式。
- 所有 Hook Config 和信任规则。
- Memory 全生命周期一致性。
- Multi-Agent 大规模并发。

## 13. SDK 覆盖

| 文件 | 行数 | 覆盖 | 内容 |
|---|---:|---|---|
| `sdk/typescript/README.md` | 160 | A | TS SDK API、Streaming、Schema、Resume 和 Config |
| `sdk/typescript/src/codex.ts` | 39 | A | Codex Client 与 Thread 创建/恢复 |
| `sdk/typescript/src/thread.ts` | 158 | A | Input、Run、Stream、Structured Output |
| `sdk/python/README.md` | 75 | A | Python SDK API、Login 与 Quickstart |
| `sdk/python/src/openai_codex/__init__.py` | 95 | A | Python 公共导出 |
| `sdk/python/src/openai_codex/_run.py` | 135 | A | Turn Result 收集和最终回复选择 |
| `sdk/python/src/openai_codex/_message_router.py` | 389 | A | Response、Notification、Turn、Goal 路由 |

已确认：

- TypeScript SDK 包装 `codex exec` 的 JSONL。
- Python SDK 使用 App Server JSON-RPC。
- Python Router 为每个 Turn 维护独立 Cursor。
- Python 支持同步与异步。
- Python 支持 Login、Goal、Approval、Input 等更多控制面。
- Python 生成类型来自 Protocol Schema。

未覆盖：

- 全部生成类型。
- 两个 SDK 的真实端到端测试。
- npm/PyPI 发布流程。

## 14. 测试与构建覆盖

### 14.1 测试统计

| 范围 | 数量 |
|---|---:|
| Rust `*_test*.rs` | 914 |
| TypeScript SDK Test | 9 |
| Python SDK Test | 21 |
| Core Suite Rust 文件 | 162 |
| Core Suite 行数 | 151,597 |
| App Server Test 文件 | 164 |
| App Server Test 行数 | 118,776 |
| Core Snapshot | 28 |
| TUI Snapshot | 999 |

### 14.2 Core Suite 主要主题

- Approvals
- Abort
- Apply Patch
- Client / WebSocket
- Code Mode
- Compaction
- Context Annotation
- ExecPolicy
- Extension Sandbox
- Fork / Resume
- Guardian
- Hooks
- MCP
- Multi-Agent
- Network Approval
- Permissions
- Prompt Cache
- Realtime
- Rollout
- Safety
- Skills
- SQLite State
- Tool Lifecycle
- Tool Parallelism
- Unified Exec
- User Shell
- Windows Sandbox
- Worktree Trust

### 14.3 测试方法

- `test_codex` 启动真实 Core Test Instance。
- HTTP Mock 捕获 `/responses`。
- 使用 `ev_*` 构造 SSE Event。
- 测试 `ResponseMock` 中真实 Request Body。
- App Server 测试走公开 JSON-RPC。
- TUI 使用 insta Snapshot。
- 大变更使用 `just test`。
- 防止直接运行 `cargo test` 绕过 Cargo/Bazel 规则。

### 14.4 未执行

没有执行：

```bash
cargo build
cargo test
just test
just fix
bazel test
bazel build
pnpm test
uv run pytest
codex exec
codex app-server
codex sandbox
TUI
真实 Responses 请求
```

因此，本台账不能给出运行时正确性结论。

## 15. 未覆盖范围

未逐行或未完整覆盖：

1. `tui` 的全部 345K 行和 999 个 Snapshot。
2. `core` 的全部 225K 行。
3. `protocol.rs` 的 6,338 行全部类型。
4. `models.rs` 的 4,421 行全部类型。
5. `session/mod.rs` 的 4,936 行全部实现。
6. `client.rs` 的全部 Auth/WebRTC/Realtime 分支。
7. 全部 MCP、Plugin、Skill 和 Hook。
8. 全部 Windows/MXC Sandbox。
9. 全部 Network MITM 和 Credential Broker。
10. 全部 Cloud Tasks。
11. 全部 App Server Endpoint。
12. 全部 Remote Control。
13. 全部 Exec Server。
14. 全部 SDK 生成代码与测试。
15. 全部 CI、Release、安装和签名流程。
16. 真实跨平台运行行为。

## 16. 证据可信度

| 结论 | 级别 | 依据 |
|---|---|---|
| Apache-2.0 与 Rust Workspace | A | `LICENSE`、`Cargo.toml` |
| 仓库规模、文件数和测试数 | A | 本地统计 |
| Core 以 Thread/Turn/Submission 为中心 | A | `protocol_v1.md`、Core 与 CLI |
| 一个 Session 同时一个主 Task | A | Session 注释和 Task 生命周期 |
| TUI/Exec 使用 App Server Client | A | `tui/src/lib.rs`、`exec/src/lib.rs` |
| 当前 Wire API 只有 Responses | A | `model-provider-info/src/lib.rs` |
| HTTP SSE 与 WebSocket 双 Transport | A | `model_client` 与 App Server Transport |
| WebSocket 有增量请求与 HTTP Fallback | A | `client.rs` |
| Tool Router 在一个 Step 冻结工具视图 | A | `StepContext`、`ToolRouter`、`run_turn` |
| Tool 执行经过 Approval + Sandbox | A | `orchestrator.rs` |
| ExecPolicy 有 Allow/Prompt/Forbidden | A | `exec_policy.rs`、`execpolicy` |
| Network Proxy 支持 Domain/Socket Policy | A | `network-proxy` |
| Rollout JSONL 与 SQLite 双存储 | A | `rollout`、`state` |
| Compaction 分 Local 与 Remote V2 | A | `compact.rs`、`compact_remote_v2.rs` |
| Python SDK 使用 App Server | A | Python Router 与 README |
| TypeScript SDK 使用 `codex exec` JSONL | A | TS README 与 `exec.ts` |
| TUI 完整交互体验 | C | 只做结构与主状态审阅 |
| 所有高级 Feature 产品可用 | D | 很多受 Feature/账号/平台控制 |
| 测试通过、构建通过、真实模型可用 | D | 本次未执行 |

## 17. 最终覆盖声明

本次对以下主链形成 A/B 级证据：

```text
CLI / TUI / Exec
  -> App Server Client
  -> ThreadManager
  -> CodexThread / Session / Submission Loop
  -> TurnInput / RegularTask / run_turn
  -> ModelClient / Responses
  -> ToolRegistry / ToolRouter / Approval / Sandbox
  -> Rollout / SQLite / ThreadStore
  -> Compaction
  -> SDK
```

对以下范围只形成 B/C/D 级证据：

- 完整 TUI。
- 全部 Core 模块。
- 全部 MCP、Plugin、Hook、Skill 和 Memory。
- 全部 Remote Control、Exec Server 和 Cloud。
- 全部平台 Sandbox。
- 全部测试、构建和真实运行。

所以，本报告适合确认 Codex 的主要架构方向、核心状态机、安全边界和可借鉴模式；不适合作为“源码已逐行审阅、所有能力已运行验证、所有实验 Feature 已稳定”的证明。真实接续开发前，仍应按具体模块运行对应 `just test -p <crate>`、真实 CLI 和真实 Provider 测试。
