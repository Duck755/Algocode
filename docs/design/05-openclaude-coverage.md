# OpenClaude 阅读覆盖台账

> 对应设计文档：`05-openclaude-design.md`  
> 分析日期：2026-09-15  
> 分析对象：`C:\Users\Administrator\Desktop\openclaude-main\openclaude-main`  
> 快照状态：没有安装 Bun，没有 `node_modules`，不能执行官方 build、typecheck 和 test 命令

## 1. 覆盖结论

OpenClaude 是一个超大型衍生代码仓库。本次没有声称对全部代码逐行阅读。

覆盖策略：

1. 完整盘点顶层目录、主要源码分类、测试规模和运行环境。
2. 精读 CLI 引导、入口、QueryEngine、Query Loop、Tool Contract、Tool Execution、Permission、Provider Shim、Session、MCP、Plugin、Skill、gRPC 和 SDK 主链。
3. 审阅 Provider Descriptor、Routing、Runtime Metadata、Search Provider 和 Config。
4. 对 React/Ink UI、Web 文档站、VSCode Extension、Hooks React UI 和大量外围 Feature 做结构覆盖。
5. 测试文件没有逐行阅读，只统计规模和测试主题。
6. 没有执行源码构建或测试。
7. 把 `LICENSE` 中的衍生代码声明视为最高优先级风险，而不是只按 README 的 MIT 标记理解。

## 2. 许可证覆盖

已完整阅读仓库根 `LICENSE`。关键事实：

- 仓库声明包含衍生自 Anthropic Claude Code CLI 的代码。
- 原始 Claude Code 被声明为专有软件。
- 原始源码版权归 Anthropic PBC。
- 仓库明确表示没有获得 Anthropic 分发相应专有源码的授权。
- OpenClaude 贡献者仅对“自己可合法主张的部分修改”声称 MIT。
- 仓库要求用户和贡献者自行评估法律立场。

因此覆盖台账特别区分：

| 层面 | 结论 |
|---|---|
| README 标签 | 将项目标记为 MIT |
| 根 LICENSE 正文 | 完整项目并非无争议的纯 MIT |
| 衍生代码 | 法律状态不明确 |
| 本分析用途 | 只做设计与风险分析，不构成复制许可 |

## 3. 仓库规模

### 3.1 代码统计

统计范围为 `src`、`tests`、`scripts`，并排除 `node_modules`。

| 范围 | 文件数 | 行数 |
|---|---:|---:|
| 非测试源码 | 2,521 | 611,951 |
| 测试文件 | 733 | 204,238 |
| `src` 总文件 | 3,227 | 未单独重复统计全部格式 |
| `web` | 71 | 约 700 KB |
| `vscode-extension` | 21 | 约 200 KB |
| `scripts` | 41 | 约 341 KB |

### 3.2 `src` 主要模块

| 模块 | 文件数 | 行数 | 覆盖级别 |
|---|---:|---:|---|
| `utils` | 956 | 269,896 | 核心路径精读，外围结构审阅 |
| `services` | 369 | 127,246 | API、MCP、Compact 等核心精读 |
| `components` | 482 | 103,579 | 结构审阅 |
| `tools` | 277 | 63,644 | Tool Contract 和主要工具审阅 |
| `commands` | 297 | 44,064 | 命令体系结构审阅 |
| `integrations` | 146 | 33,593 | Provider 架构精读 |
| `cli` | 57 | 24,964 | 后台与 Skill CLI 审阅 |
| `hooks` | 113 | 20,643 | 权限和 UI Hooks 结构审阅 |
| `ink` | 110 | 20,185 | 结构审阅 |
| `entrypoints` | 31 | 12,608 | 核心精读 |
| `bridge` | 37 | 12,281 | 结构审阅 |
| `query` | 15 | 5,872 | 核心精读 |
| `skills` | 23 | 4,936 | 核心结构审阅 |
| `memdir` | 17 | 4,007 | 结构审阅 |
| `tasks` | 16 | 3,933 | 结构审阅 |
| `context` | 28 | 3,193 | Repo Map 精读 |

## 4. 核心源码精读清单

### 4.1 入口和启动

| 文件 | 行数 | 内容 |
|---|---:|---|
| `bin/openclaude` | 未逐行统计 | Node 启动器、Heap 与编译缓存 |
| `bin/node-compile-cache.mjs` | 未逐行统计 | Node 编译缓存 |
| `bin/heap-limit.mjs` | 未逐行统计 | Heap 配置 |
| `src/entrypoints/cli.tsx` | 823 | CLI Bootstrap 和快速路径 |
| `src/main.tsx` | 4,482 | 完整 CLI 装配 |
| `src/entrypoints/init.ts` | 226 | 配置、网络、插件和清理初始化 |
| `src/entrypoints/mcp.ts` | 267 | OpenClaude MCP Server |
| `src/entrypoints/sdk/v2.ts` | 839 | SDK V2 Session |
| `scripts/start-grpc.ts` | 未逐行统计 | gRPC 启动 |
| `src/grpc/server.ts` | 321 | gRPC 双向流服务 |
| `src/daemon/main.ts` | 11 | Daemon Stub 或入口 |
| `Dockerfile` | 约 60 | Build 与 Runtime 镜像 |

### 4.2 Query 核心

| 文件 | 行数 | 内容 |
|---|---:|---|
| `src/QueryEngine.ts` | 1,555 | Conversation 级 Query 生命周期 |
| `src/query.ts` | 3,204 | Agent Loop、恢复和继续状态机 |
| `src/context.ts` | 299 | Git、Repo Map、User Context |
| `src/query/config.ts` | 未逐行统计 | Query 配置快照 |
| `src/query/deps.ts` | 未逐行统计 | Query 依赖注入 |
| `src/query/tokenBudget.ts` | 未逐行统计 | Token Budget |
| `src/query/stopHooks.ts` | 588 | Stop Hook 流程 |
| `src/query/agentStepLimit.ts` | 未逐行统计 | Agent Step Limit |
| `src/query/toolFailureLoopGuard.ts` | 未逐行统计 | 工具失败循环保护 |

### 4.3 Tool 和权限

| 文件 | 行数 | 内容 |
|---|---:|---|
| `src/Tool.ts` | 827 | Tool 接口和默认值 |
| `src/tools.ts` | 388 | Tool 池组装 |
| `src/services/tools/toolOrchestration.ts` | 199 | 工具并发 Batch |
| `src/services/tools/StreamingToolExecutor.ts` | 616 | 流式工具执行器 |
| `src/services/tools/toolExecution.ts` | 1,981 | 校验、Hook、权限、执行和结果 |
| `src/services/tools/toolHooks.ts` | 未逐行统计 | Pre/Post/Failure Hook |
| `src/utils/permissions/permissions.ts` | 1,898 | 权限决策引擎 |
| `src/types/permissions.ts` | 约 300 | Permission 类型 |
| `src/utils/permissions/PermissionMode.ts` | 约 180 | Permission Mode |
| `src/utils/permissions/PermissionResult.ts` | 约 50 | Permission Result |
| `src/tools/BashTool/bashSecurity.ts` | 未逐行统计 | Bash 安全校验 |
| `src/tools/BashTool/shouldUseSandbox.ts` | 未逐行统计 | Sandbox 决策 |
| `src/tools/BashTool/bashPermissions.ts` | 未逐行统计 | Bash 权限规则 |

### 4.4 Provider 和模型

| 文件 | 行数 | 内容 |
|---|---:|---|
| `src/services/api/claude.ts` | 3,979 | Anthropic 请求构造、流式、缓存和恢复 |
| `src/services/api/openaiShim.ts` | 586 | OpenAI-compatible Shim 门面 |
| `src/services/api/openaiShim/requestExecutor.ts` | 1,121 | OpenAI 请求执行 |
| `src/services/api/openaiShim/requestPreparation.ts` | 390 | 请求规划 |
| `src/services/api/openaiShim/streamConversion.ts` | 1,094 | OpenAI Stream 转 Anthropic Stream |
| `src/services/api/openaiShim/messageConversion.ts` | 279 | 消息格式适配 |
| `src/services/api/openaiShim/toolConversion.ts` | 未逐行统计 | Tool Schema 适配 |
| `src/services/api/openaiShim/ollamaAdapter.ts` | 244 | Ollama 原生 Chat |
| `src/services/api/codexShim.ts` | 1,378 | Codex 协议适配 |
| `src/services/api/providerConfig.ts` | 1,399 | Provider 请求解析 |
| `src/services/api/withRetry.ts` | 1,000 | Retry、529 和 Fallback |
| `src/services/api/errors.ts` | 1,511 | Provider 错误分类 |
| `src/services/api/smartRouting/index.ts` | 264 | Smart Routing |
| `src/services/api/agentRouting.ts` | 337 | Agent Routing |
| `src/integrations/index.ts` | 约 120 | Provider Registry Loader |
| `src/integrations/runtimeMetadata.ts` | 约 400+ | Runtime Provider Metadata |
| `src/integrations/registry.ts` | 约 500+ | Descriptor Registry |
| `src/integrations/artifactGenerator.ts` | 约 400+ | Provider 生成器 |

### 4.5 Session、Compact 和上下文

| 文件 | 行数 | 内容 |
|---|---:|---|
| `src/utils/sessionStorage.ts` | 6,196 | JSONL、Chain、Resume、Fork 和 Metadata |
| `src/utils/sessionStoragePortable.ts` | 789 | SDK 可移植读取 |
| `src/services/compact/compact.ts` | 1,854 | 完整 Compact |
| `src/services/compact/autoCompact.ts` | 621 | Auto Compact 阈值和熔断 |
| `src/services/compact/microCompact.ts` | 552 | Microcompact |
| `src/utils/attachments.ts` | 4,454 | Context Attachment |
| `src/context/repoMap/index.ts` | 217 | Repo Map 入口 |
| `src/context/repoMap/*` | 未全部统计 | Tree-sitter、PageRank、Cache 和 Render |

### 4.6 MCP、Plugin、Skill 和 Hook

| 文件 | 行数 | 内容 |
|---|---:|---|
| `src/services/mcp/client.ts` | 3,667 | MCP Client、工具、资源、认证 |
| `src/utils/plugins/pluginLoader.ts` | 3,585 | Plugin 安装和加载 |
| `src/utils/hooks.ts` | 5,281 | Hook 生命周期 |
| `src/utils/hooks/postSamplingHooks.ts` | 70 | Post Sampling Hook |
| `src/cli/handlers/skills.ts` | 未逐行统计 | Skill CLI |
| `src/cli/handlers/skillsInstall.ts` | 未逐行统计 | Skill 安装 |
| `src/cli/handlers/skillsVerify.ts` | 未逐行统计 | Skill 验证 |
| `src/tools/SkillTool/*` | 未全部统计 | Skill Tool |
| `src/tools/AgentTool/*` | 未全部统计 | Agent、路由和内置 Agent |

## 5. CLI 覆盖

已阅读或核对：

- `--version` 快速路径
- Background Session 快速路径
- Provider Env File
- Provider Flag
- 早期输入捕获
- Commander 主命令
- 交互模式
- `--print`
- `--output-format text|json|stream-json`
- `--input-format text|stream-json`
- `--resume`
- `--continue`
- `--fork-session`
- `--session-id`
- `--model`
- `--provider`
- `--fallback-model`
- `--permission-mode`
- `--allowed-tools`
- `--disallowed-tools`
- `--tools`
- `--add-dir`
- `--mcp-config`
- `--plugin-dir`
- `--settings`
- `--system-prompt`
- `--append-system-prompt`
- `--json-schema`
- `--max-turns`
- `--max-budget-usd`
- `--bare`
- `--worktree`
- `--remote`
- `--remote-control`
- `--teleport`
- `--bg`

未逐项执行所有帮助输出和边界参数组合。

## 6. QueryEngine 和 Query Loop 覆盖

已确认：

- QueryEngine 配置
- Conversation 状态
- `submitMessage`
- System Prompt 组装
- User / System Context
- Slash Command 处理
- SDK Message 映射
- Query Loop State
- 工具结果预算
- Snip
- Microcompact
- Context Collapse
- Auto Compact
- Prompt Cache 相关路径
- Smart Routing
- Agent Step Limit
- Model Fallback
- Provider Fallback
- Max Output Token 恢复
- Context Overflow 恢复
- Stop Hook
- Token Budget Continuation
- Continuation Nudge
- Max Turns 终止
- Abort 分类
- Tool Failure Loop Guard
- Tombstone 和 Streaming Fallback
- Usage 累计

没有逐行阅读 `query.ts` 的每一个分支，但已覆盖主状态机和所有主要终止、恢复和继续路径。

## 7. Tool 和权限覆盖

已确认 Tool 接口：

- inputSchema
- outputSchema
- prompt
- description
- validateInput
- checkPermissions
- isEnabled
- isConcurrencySafe
- isReadOnly
- isDestructive
- interruptBehavior
- maxResultSizeChars
- result mapper
- UI renderer
- progress renderer
- error renderer
- context modifier

已确认执行顺序：

```text
Schema 校验
  -> validateInput
  -> PreToolUse Hook
  -> Permission
  -> Tool call
  -> PostToolUse Hook
  -> Result Storage
  -> Tool Result
```

已确认并发：

- 安全工具并行
- 非安全工具串行
- Streaming Tool Executor
- Bash Sibling Cancel
- 最大并发环境变量

已确认权限：

- default
- plan
- acceptEdits
- bypassPermissions
- fullAccess
- dontAsk
- auto
- bubble
- Allow / Ask / Deny Rules
- User、Project、Local、Policy、CLI、Session Source
- Hook Decision
- Classifier
- Headless Auto Deny
- SDK 默认 Deny

未执行：

- 真机 Permission Dialog
- Bash Sandbox 攻击测试
- PowerShell 安全测试
- Auto Mode Classifier 实测
- OS 级网络和文件沙箱验证

## 8. Provider 覆盖

已盘点：

- Vendors
- Gateways
- Models
- Brands
- Anthropic Proxies
- Generated Artifacts
- Registry
- Route Metadata
- Runtime Metadata
- Compatibility Layer
- Discovery Cache
- Discovery Service
- Credential Pool

已核对 Transport：

- Anthropic Native
- Anthropic Proxy
- OpenAI Chat Completions
- OpenAI Responses
- Codex
- Gemini
- Ollama
- Bedrock
- Vertex
- Foundry
- Azure OpenAI

已核对特殊适配：

- DeepSeek `reasoning_content`
- Moonshot/Kimi
- GLM / Z.AI
- MiniMax Usage
- Xiaomi MiMo
- GitHub Copilot
- GitHub Models
- OpenCode
- OpenRouter
- Bankr Header
- Azure API Key
- Native Web Search Gate

未逐项调用真实 Provider。

## 9. Session、Compact 和 Context 覆盖

已确认：

- JSONL Transcript
- UUID / Parent UUID Chain
- Compact Boundary
- Preserved Segment
- Sidechain
- Agent Metadata
- Remote Agent Metadata
- Resume
- Fork
- File History Snapshot
- Attribution Snapshot
- Content Replacement
- Session Search
- Session Metadata
- Custom Title
- AI Title
- Tag
- PR Link
- Cleanup 和脱敏

已确认 Compact：

- Tool Result Budget
- Snip
- Microcompact
- Context Collapse
- Auto Compact
- Reactive Compact
- Context Overflow Recovery
- Compact Failure Cooldown
- Circuit Breaker

未执行：

- 长时间会话压缩压力测试
- 数 GB Transcript 恢复
- 多种 Provider 的 Thinking Signature 恢复
- 并发 Session CWD 隔离真实测试
- Fork 与 Worktree 交互测试

## 10. MCP、Plugin、Skill 和 Hook 覆盖

MCP 已确认：

- stdio、SSE、HTTP、WS、SDK、IDE 和 Proxy Transport
- Tool、Resource、Prompt
- Auth Cache
- URL Elicitation
- Blob 持久化
- MCP Result 转换
- Server-scoped Permission
- OpenClaude 作为 MCP Server
- MCP Tool 重暴露

Plugin 已确认：

- NPM
- Git
- GitHub
- Git Subdirectory
- Local
- Marketplace
- Versioned Cache
- Manifest
- Component Path 校验
- Hook 合并
- Settings 合并
- Session-only Plugin

Skill 已确认：

- SKILL.md
- 项目与用户目录
- Registry
- sha256
- Revocation
- URL 安装
- Local 安装
- Validate
- Remove
- Verify
- 与 Eyebrow Lockfile 的配合

Hook 已确认：

- Session Start
- PreToolUse
- PostToolUse
- Permission
- Stop
- Failure
- Hook Chain
- Cooldown
- Dedup
- Max Depth
- Fallback Agent
- Notify Team
- Warm Remote Capacity

未执行：

- 真实 MCP OAuth
- 多 MCP Server 并发故障
- 第三方 Plugin 安装
- Hook 外部命令执行
- Skill 供应链攻击测试

## 11. SDK、gRPC 和远程覆盖

SDK V2 已确认：

- `SDKSession`
- Create
- Resume
- Send Message
- Interrupt
- Close
- Permission Request
- `respondToPermission`
- MCP Tool Injection
- Agent Injection
- Transcript 恢复
- Secure-by-default Deny

gRPC 已确认：

- Proto 定义
- 双向流
- Text Chunk
- Tool Start
- Tool Result
- Action Required
- Final Response
- Session Map
- Insecure Credentials
- Cancel

远程与后台已确认：

- `--bg`
- `ps`
- `logs`
- `attach`
- `kill`
- Remote Session
- Bridge
- SSH
- Direct Connect
- Teleport
- Coordinator Mode

未执行：

- SDK Typecheck
- SDK 消费包测试
- gRPC 客户端测试
- Remote Bridge
- SSH
- 远程 Session Ingress
- 多进程并发竞态测试

## 12. 测试覆盖情况

测试规模：

- 约 733 个测试文件
- 约 204,238 行
- 测试覆盖 Query、Tool、Provider、MCP、SDK、Session、Permission、Plugin 等主题

测试分类包括：

- `src/**/*.test.ts`
- `src/**/*.test.tsx`
- `tests/build`
- `tests/sdk`
- `scripts/*.test.ts`
- Web verify tests
- VSCode Extension Tests

官方测试入口：

```bash
bun test --feature=UNATTENDED_RETRY --max-concurrency=1
bun run test:full
bun run test:provider
bun run test:coverage
bun run typecheck
```

当前离线状态：

- Node `v25.2.1`
- Bun 未安装
- npm `11.6.2`
- 根 `node_modules` 不存在
- Web `node_modules` 不存在
- VSCode Extension `node_modules` 不存在

因此本机没有执行任何官方测试。

## 13. UI 和外围覆盖

结构审阅：

- React 19
- 自定义 Ink 渲染
- Components
- Hooks
- Keybindings
- Diff UI
- Permission UI
- Task UI
- Agent UI
- Theme
- Web Astro
- VSCode Extension

未逐行阅读全部 100,000 多行 UI 代码。UI 不是 Algocode 的核心借鉴目标，因此只记录其与 Agent、Permission、Tool 和 Session 的边界。

## 14. 未覆盖或未验证范围

- 全部 611,951 行非测试代码
- 全部 204,238 行测试代码
- 全部 482 个 Component 文件
- 全部 297 个 Command 文件
- 所有 Feature Gate 的内部版本
- 所有真实 Provider API
- OS Keychain
- OAuth Callback
- 多 Provider OAuth Refresh
- Remote Bridge Service
- 云端 Session Service
- Computer Use
- Chrome Integration
- Voice
- Slack 或外部平台集成
- Workflow 和定时任务真实执行
- Plugin Marketplace 的所有来源
- Windows、macOS、Linux 的跨平台差异
- Node 22 与当前本机 Node 25 的行为差异

## 15. 证据可信度分级

| 级别 | 含义 | 示例 |
|---|---|---|
| A | 已读取完整源码或关键连续段 | CLI、QueryEngine、Query、Tool、Permission、Provider Shim、Session、MCP |
| B | 已审阅结构、接口和关键函数 | Plugin、Skills、UI、Remote、Bridge |
| C | 只做目录和文档盘点 | Web、VSCode、部分命令和外围服务 |
| D | 未执行，不能确认运行时结果 | 全部测试、Provider、Keychain、OAuth、gRPC、Plugin 安装 |

本设计文档的核心 Query 与 Tool 结论属于 A 级；扩展系统属于 B 级；测试和远程服务状态属于 D 级事实。

## 16. 最终覆盖评价

对 OpenClaude 的核心 Agent 运行链，当前覆盖足以支持：

- 理解 CLI 从启动到 QueryEngine 的路径
- 理解一次 Agent Turn 的状态机和恢复分支
- 理解 Tool、Permission、Hook 和 Session 的关系
- 理解 Provider Shim 和 Descriptor 架构
- 理解 MCP、Plugin、Skill 和 SDK 的边界
- 识别许可证、权限、Hook、Plugin、gRPC 和上下文恢复风险
- 为 Algocode 提炼独立实现所需的 AgentSession、Tool Contract、权限和预算设计

但是，不能据此声称：

- 全部源码已逐行理解
- 当前本机已验证运行
- 全部 Provider 和功能 Gate 行为一致
- 衍生代码可以自由复制
- 测试一定通过

后续如果只借鉴设计思想，可以继续基于本台账展开独立实现；如果考虑代码复用，必须优先完成许可证审查。
