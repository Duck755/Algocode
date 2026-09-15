# DeepSeek Harness 详细设计文档

> 文档版本：分析稿 v1.0  
> 分析日期：2026-09-15  
> 分析对象：`C:\Users\Administrator\Desktop\deepseek-harness-master\deepseek-harness-master`  
> 项目版本：`@deepseek-ai/dsh-root 0.1.5-rc.2`  
> 项目定位：基于 Cordis、强调“一切皆插件”的 Coding Agent Harness  
> 运行时：Node.js `^22.19.0 || >=24.0.0`  
> 包管理器：pnpm `11.7.0`  
> 许可证：MIT

## 1. 分析范围说明

DeepSeek Harness 是一个大型 pnpm monorepo，包含：

- CLI Launcher
- 可组合 Profile
- Web GUI
- Headless One-shot Runner
- TypeScript SDK
- Python SDK 和随包 Node Runtime
- ACP Server
- Electron Desktop
- Cordis 插件框架和 Loader
- Session 事件溯源与持久化
- Agent Loop
- LLM Adapter 与模型发现
- Tool Registry 和 PTC 代码执行
- Sandbox、Approval 和 Permission Presets
- MCP、LSP、Skills、Workflow、Jobs 和 Schedule
- Subagent、Agent Teams 和 Remote
- Session Format 多代际迁移
- Web 传输、认证、浏览器客户端和桌面 Host
- Benchmark、Snapshot、E2E 和文档门禁

本次重点精读：

```text
dsh CLI
  -> Profile 与 Patch 组合
  -> Cordis Loader
  -> Session
  -> Agent Loop
  -> LLM Adapter
  -> Tool Pipeline
  -> Sandbox / Approval
  -> Web / Headless / SDK
```

Web UI、Desktop、全部工具、全部 Provider 和全部测试不会逐行展开，但会记录模块职责、关键边界和未验证范围。

## 2. 核心结论

DeepSeek Harness 最鲜明的设计不是某一个 Agent 功能，而是把整个产品拆成可组合插件。

可以概括为：

```text
DeepSeek Harness
  = Cordis 插件容器
  + Profile / Bundle / Patch 组合
  + 事件溯源 Session
  + Turn / Step Agent Loop
  + Provider Adapter
  + Scoped Tool Registry
  + Sandbox 与 Approval
  + 多 Surface：Web / Headless / SDK / ACP / Desktop
```

最重要的设计决策：

1. 不存在必须修改的特权 Agent Kernel。模型、工具、Session、沙箱和 UI 都以插件提供服务。
2. 所有可观察产品形态都由 `dsh` CLI 加载某个 Profile 产生，而不是多个独立应用入口。
3. Profile 由有序 Bundle Patch、用户 Patch 和 `--patch` Overlay 组合而成。
4. Session 是仅追加事件日志，模型消息历史从日志派生，不单独保存。
5. Agent Loop 把 Turn 定义为“输入被接纳到不再欠工作”，Step 定义为“一次模型请求及其工具调用”。
6. Tool Registry 通过 Scoped Layers 支持全局工具、Preset 工具和 Agent 私有工具。
7. Tool 执行采用 Pre、Guard、Execute、Post、Finalize、Result 多层流水线。
8. LLM 服务只定义 Provider 无关协议；具体协议和凭据属于 Adapter。
9. Sandbox、Approval、Tool、LLM 和 Session 都是正式能力 seam。
10. Session JSONL 有版本化格式、相邻迁移链、CRC/Zstd 和崩溃尾部修复。
11. Web、Headless、SDK、ACP 和 Desktop 共享同一套核心。
12. 项目对文档、生成目录、测试、Invariant 和类型契约的工程约束非常强。

## 3. 项目定位

DeepSeek Harness 面向：

- 本地 Coding Agent
- Web Coding GUI
- Headless 自动化
- TypeScript 和 Python SDK
- ACP 自动化客户端
- Electron Desktop
- 自定义 Agent 产品组合
- 插件作者
- 希望替换模型、工具、存储、沙箱或 UI 的部署方

它不只是一套提示词和工具，而是“构建 Coding Agent 产品”的插件运行时。

### 3.1 主要 Surface

| Surface | Profile | 用途 |
|---|---|---|
| Web | `web` | 浏览器聊天、工作区、设置和会话历史 |
| Headless | `headless` | 单任务运行后退出 |
| SDK | `sdk` | 标准 JSON-RPC SDK |
| SDK Minimal | `sdk-minimal` | 显式最小组合 |
| ACP | `acp` | 自动化 Agent Client Protocol 服务 |
| Desktop | `desktop` | Electron 内置 Host 与客户端 |
| TUI 自定义 | Custom Profile | 由用户组合 |

### 3.2 非目标

项目当前明确处于 Developer Preview，预稳定 API 可能破坏兼容。它不是一个以稳定插件 ABI 和企业长期支持为首要目标的成熟平台。

## 4. 技术栈

| 类别 | 技术 |
|---|---|
| 语言 | TypeScript、TSX、少量 Python 和原生代码 |
| 插件框架 | Cordis，vendored |
| Node | `^22.19.0 || >=24.0.0` |
| 包管理 | pnpm Workspaces |
| 构建 | tsc、tsdown |
| Web | Vite、浏览器插件客户端、自定义 Remote |
| Session | JSONL、Zstd、可选原生 addon |
| LLM | DeepSeek Chat Completions、pi-ai 多 Provider |
| Tool Schema | 自有 JSON Schema DSL |
| 代码执行 | Worker Thread Code Runtime |
| 沙箱 | Linux bwrap/Landlock、macOS Seatbelt、Windows ACL |
| CLI 配置 | YAML Profiles、YAML Patch Layers、`!!js` 表达式 |
| 测试 | Vitest、E2E、Snapshot、Benchmark |
| 文档 | 双语 Markdown、生成目录、链接和预算门禁 |
| Desktop | Electron、Node Host、IPC 和版本化 framing |

## 5. 仓库规模

统计范围是 `packages`、`apps`、`python` 和 `scripts` 下的 TS、TSX、JS、MJS 和 Python 文件，并排除 `node_modules`、`lib`、`dist` 和 `coverage`。

| 范围 | 文件数 | 行数 |
|---|---:|---:|
| 源码候选 | 3,704 | 790,140 |
| 测试文件 | 1,278 | 373,672 |
| 所有文件 | 10,319 | 约 71 MB |

主要大型包：

| 包 | 文件数 | 行数 |
|---|---:|---:|
| `api/session-controller` | 79 | 21,731 |
| `client/ui-conversation` | 92 | 19,908 |
| `experimental/inspector` | 175 | 19,563 |
| `experimental/webworker-runtime` | 117 | 18,459 |
| `client/ui-chat` | 100 | 18,019 |
| `client/ui-primitives` | 100 | 14,952 |
| `core/agent-loop` | 34 | 13,980 |
| `client/ui-trajectory` | 40 | 13,155 |
| `core/tools` | 22 | 12,895 |
| `subagent/subagent` | 38 | 11,476 |
| `session/session-persistence-jsonl` | 29 | 11,468 |
| `typert/generator` | 28 | 11,023 |
| `api/gateway` | 21 | 10,722 |
| `client/connection` | 33 | 10,385 |
| `subprocess/subprocess-local` | 31 | 10,260 |

## 6. Cordis 基础

### 6.1 插件

Cordis 插件可以：

- 是带 `inject` 和 `apply(ctx)` 的函数
- 是 `Service` 子类
- 注册服务
- 注册类型化事件
- 注册可撤销副作用
- 声明依赖后等待服务可用

### 6.2 Context

`ctx` 是服务容器：

- `ctx.sessions`
- `ctx.llm`
- `ctx.tools`
- `ctx.agents`
- `ctx.sandbox`
- `ctx.approval`
- `ctx.systemPrompt`
- `ctx.sessionPersistence`
- `ctx.subagents`
- `ctx.webServer`
- `ctx.connection`

插件通过 key 获取能力，不直接依赖另一个具体实现。

### 6.3 Event 分发

Cordis 支持五种事件模式：

| 模式 | 是否等待 | 用途 |
|---|---|---|
| `emit` | 否 | 观察通知 |
| `waterfall` | 否，但可异步 | 中间件式包裹和短路 |
| `parallel` | 是 | 并行观察 |
| `serial` | 是 | 顺序终止检查 |
| `bail` | 否 | 首个 Bail 值停止 |

Waterfall 监听器必须调用 `next()` 才能委托下游。直接返回会短路。

### 6.4 可逆副作用

注册通过：

- `ctx.effect()`
- `ctx.on()`

安装，并在 Fiber 卸载时撤销。提示词片段、工具、Adapter、事件监听器和 UI 行都遵循该模型。

## 7. Profile、Bundle 和 Patch

### 7.1 Profile

Profile 位于：

```text
$DSH_HOME/profiles/<name>/
  package.json
  cordis.patch.yml
  cordis.yml
```

`package.json` 中的 `dsh.profile.bundles` 定义有序 Bundle 列表。

内置 Profile：

- `web`
- `headless`
- `sdk`
- `sdk-minimal`
- `acp`
- Desktop 由 Electron 应用管理

### 7.2 Bundle

Bundle 是 npm 包，提供：

```json
{
  "dsh": {
    "bundle": {
      "patch": "./cordis.patch.yml"
    }
  }
}
```

核心 Bundle：

- `@deepseek-ai/dsh-base`
- `@deepseek-ai/dsh-web-app`
- `@deepseek-ai/dsh-headless`
- `@deepseek-ai/dsh-sdk-app`
- `@deepseek-ai/dsh-sdk-minimal`
- `@deepseek-ai/dsh-acp-app`

### 7.3 Patch 组合顺序

```text
空条目列表
  -> Profile 中的每个 Bundle Patch
  -> Profile 自己的 cordis.patch.yml
  -> $DSH_HOME/cordis.patch.yml
  -> CLI --patch Overlay
  -> Telemetry Disable Overlay
```

Patch 会替换目标行的整个 `config`，不是递归合并。新增配置必须在 Patch 中重述它拥有的全部键。

### 7.4 热重载

- `web` 和自定义 Profile 默认 Live Patch Reload
- `headless`、`sdk`、`sdk-minimal`、`acp` 使用 Startup-only
- Live Reload 只监听配置 Patch
- 模块 HMR 由 `cordis-plugin-hmr` 单独控制，默认关闭

### 7.5 `--dump-config`

```bash
dsh --profile web --dump-config
```

可打印组合后的完整插件树，并标出每行的来源和 Patch 修改者。

### 7.6 环境文件安全

启动器分层读取：

1. 继承的 Process Environment
2. 当前项目 `.env`
3. `$DSH_HOME/.env`

项目 `.env` 不允许覆盖：

- PATH
- HOME
- NODE_OPTIONS
- NODE_PATH
- LD_PRELOAD
- BASH_ENV
- GIT_SSH
- EDITOR
- TLS 和 Proxy 等启动级变量

只有 Harness Home 的 `.env` 可以设置 Proxy 变量。该项目对“仓库内配置文件劫持启动环境”的防护很强。

## 8. CLI 启动

### 8.1 `dsh`

入口是 `apps/cli/src/bin.ts`。

解析三种模式：

- Profile Boot
- Plugin 管理
- Dump Config

CLI Launcher 只消费自己的 Flags：

- `--profile`
- `--from-default-profile`
- `--patch`
- `--dump-config`
- `--dump-default-config`

第一个无法识别的 Token 之后的所有参数原样交给被启动的 App Plugin。

### 8.2 Plugin 管理

```bash
dsh plugin --profile tui add <package>
dsh plugin --profile tui remove <package>
```

本质是在 Profile 目录内转发给 pnpm。

### 8.3 模块解析

Bundle 从两个锚点解析：

1. 当前 dsh 安装
2. Profile 目录

安装自带 Bundle 时优先从 dsh 安装解析，避免 Profile 覆盖核心实现。普通 Node 用 Symlink 建立模块回退；打包 Exe 使用 ESM Proxy。

### 8.4 启动失败策略

- Plugin 无法 Resolve：Fail Loud
- Enabled Entry 保持 Pending：Fail Loud
- Entry 初始化异常：保留原始 Stack
- 未处理 Promise Rejection：打印单条诊断并退出
- 终端所有者可通过 Release Hook 恢复 Raw Mode 和键盘协议

## 9. Session 事件溯源

### 9.1 核心原则

```text
Model-visible ⟺ Logged
```

任何进入模型请求的内容必须能从 Session Log 重建。

### 9.2 SessionEvent

事件类型包括：

- `turn/start`
- `turn/end`
- `step/start`
- `step/end`
- `system/message`
- `user/message`
- `assistant/message`
- `assistant/attempt`
- `tool/call`
- `tool/result`
- `request/header`
- `request/context`
- `session/end-seed`
- Compact、Hook、Todo、FS、Subagent、Workflow 等扩展事件

### 9.3 Surface

Surface 事件才产生模型消息：

- `system/message`
- `user/message`
- `assistant/message`
- `tool/result`

Surface Operation：

- `append`
- `replace(startSeq, endSeq)`

压缩使用 Replace 遮蔽旧节点，但不会删除原始 Log。

### 9.4 消息历史

`deriveMessages()`：

1. 读取事件日志。
2. 增量折叠 Surface。
3. 缓存每个节点的投影。
4. 返回新的 Frozen Message 数组。

内部消息不可变，避免派生历史与真实请求不一致。

### 9.5 Todo/Progress 等仅日志事件

非模型可见事件可以进入日志用于回放、UI、审计和恢复，但不产生 LLM Message。

### 9.6 序列号

Session 使用多个品牌类型：

- `SessionSeq`：已存在事件
- `SessionLogOffset`：前缀长度或读取位置，可等于事件数
- `SessionSeqCursor`：包含 `-1`
- `OptionalSessionSeq`：显式 `null`

## 10. Agent Turn 与 Step 生命周期

### 10.1 定义

| 概念 | 定义 |
|---|---|
| Turn | 从领取首条输入到不再欠工作 |
| Step | 一次模型请求加它调用的工具 |
| Request Series | 一段可复用模型消息前缀 |
| Inbox | Turn 或 Step 边界等待的输入 |

### 10.2 Turn 流程

```text
turn/start
  -> claim next-step input and queued message
  -> system-prompt/assemble
  -> agent/pre-step
  -> step/start
  -> agent/request
  -> prepareCall
  -> system/message
  -> user/message
  -> request/header
  -> derive frozen request
  -> llm/stream
  -> assistant/message or assistant/attempt
  -> tool/call
  -> tools/pre-execute
  -> tools/execute
  -> tools/post-execute
  -> tool/result
  -> step/end
  -> another step or agent/turn-stopping
turn/end
```

### 10.3 Inbox

支持：

- `followup()`：下一 Turn
- `steer()`：最近 Step
- `inject()`：下一次 Pre-step 的上下文，不主动唤醒
- `send()`：指定目标与是否 Wake

取消时可以保留 Inbox，也可以清空。

### 10.4 Agent Status

- `idle`
- `running`

`whenIdle()` 等待当前全部工作、替换工作和维护任务。

### 10.5 Maintenance

`runMaintenance()` 在真正 Idle 时执行非 Turn 任务，例如最终 Flush、子 Agent 锁或清理。维护期间的输入进入 Inbox，直到维护结束。

### 10.6 事件域

| 域 | 用途 |
|---|---|
| `session/*` | 持久事实 |
| `agent/*` | 实时协调、状态、Inbox、请求拦截 |
| `llm/*` | 模型流 |
| `tools/*` | 工具流水线 |
| `fs/*` | 文件效果策略 |
| `approval/*` | 审批 |
| `subagent/*` | 子 Agent |
| `workflow/*` | 工作流 |

## 11. Agent Loop 实现

`packages/core/agent-loop/src/agent.ts` 约 619 行。

### 11.1 ReactLoopAgent

核心职责：

- 维护 Idle / Running / Maintenance Phase
- 管理 ReactLoopInbox
- 驱动 Turn
- 驱动 Step
- 构建冻结请求
- 记录 Session Event
- 调用 LLM Stream
- 执行 Tool Calls
- 触发 Turn Stopping
- 处理取消与恢复

### 11.2 Pre-step

`agent/pre-step` 是 Waterfall：

- 可拒绝当前 Step
- 可替换进入 Step 的 Message
- 可声明新 Request Series
- 输入被拒绝后，Turn 可以零 Step 关闭

### 11.3 Request

`agent/request` 可替换 `LlmCallConfig`。

调用 `prepareCall()` 后，Adapter 能力、上下文窗口、System Prompt Update 模式和 Retry Policy 被绑定到一次对 Adapter 代际的调用，避免设置热更新导致跨代混合。

### 11.4 请求冻结

Loop：

1. 记录 `request/header`
2. 记录 `request/context`
3. 从 Session Surface 派生 Message
4. Deep Freeze 所有消息和请求
5. 发送不可变 `GenerateOptions`

请求是 Session Log 的纯函数。

### 11.5 流结算

每次模型尝试最终记录：

- `assistant/message`：成功或 Interrupted 前缀，包含完整紧凑 Stream
- `assistant/attempt`：失败、重试、取消或 Stream Error，不进入模型历史

硬崩溃发生在 Settlement 前时，不留下持久 Attempt Stream。

### 11.6 工具调度

工具按 Execution Mode 分类：

- `parallel`
- `exclusive`

Exclusive 调用形成 Barrier，Parallel 工具可共享滚动池。

结果按模型请求顺序提交，工具完成后产生 `tool/result`。

## 12. LLM 服务

### 12.1 Provider 无关词汇

`dsh-llm` 定义：

- Message
- Content Block
- Tool Schema
- Tool Call
- Stream Chunk
- Finish Reason
- Token Usage
- Replay State
- Model Capability
- Context Window
- Reasoning Effort
- System Prompt Update Mode
- Failure Code

### 12.2 Adapter

Adapter 负责：

- Provider 协议
- 认证
- URL
- SSE 解析
- Tool Call 序列化
- Reasoning Content
- 图片投影
- Provider Error
- Provider Retry Policy

### 12.3 `LlmRuntime`

服务提供：

- Adapter Registry
- Configurable Provider Directory
- Model Discovery
- Exact Model Resolution
- Call Config Validation
- Prepared Call
- Streaming
- `llm/stream` Waterfall

### 12.4 Prepared Call

`prepareCall()` 绑定：

- Adapter Registration
- Model Metadata
- Resolved Config
- Retry Policy
- Input Modalities
- System Prompt Update Mode
- Adapter Defaults
- One-shot Dispatch

Prepared Call 只能 Dispatch 一次，配置不匹配会以 `INVALID_PREPARED_CALL` 失败。

### 12.5 Stream 协议

流最终一定以 `finish` 结束：

- success
- error
- aborted

失败 Code 包括：

- `NO_ADAPTER`
- `MISSING_CREDENTIAL`
- `INVALID_CREDENTIAL`
- `AUTH`
- `RATE_LIMIT`
- `QUOTA`
- `CONTEXT_WINDOW_EXCEEDED`
- `INVALID_REQUEST`
- `SERVER`
- `TRANSPORT`
- `TIMEOUT`
- `ABORTED`
- `EMPTY_RESPONSE`
- `STREAM_CLOSED`
- `MALFORMED_RESPONSE`
- `UNSUPPORTED_CONTENT`
- `UNSUPPORTED_REASONING_EFFORT`

调用方依据 Code 路由，不解析消息文本。

### 12.6 Retry

`dsh-llm` 本身只尝试一次 Provider。

`dsh-llm-retry` 监听 `agent/request-error`：

- 读取 Adapter 的 Retry Policy
- 决定是否重试
- 同一步骤继续
- 不重复 Pre-step 和 User Message

### 12.7 Token Meter

`dsh-token-meter`：

- 计算请求上下文压力
- 处理 Cache Read 和 Cache Creation
- 根据路由定价图片
- 为自动压缩提供阈值
- 支持 Turn Usage 和 Context Breakdown
- 缺少 Provider Usage 时使用字符启发式

## 13. DeepSeek Adapter

### 13.1 路由

默认 Provider：

```text
deepseek-official
```

默认模型目录包含：

- `deepseek-flash`
- `deepseek-v4-flash`
- `deepseek-v4-pro`
- `deepseek-v4-flash-vision-exp`

建议上下文窗口为 1,000,000 Token。

### 13.2 请求能力

支持：

- Chat Completions
- Streaming SSE
- Thinking
- reasoning effort：off、low、high、max
- 图片
- DeepSeek Files API
- Base64 图片回退
- 缓存 Usage
- System Prompt Update `in-history`
- Request Extensions

### 13.3 图片

图片处理：

1. 解析持久 Attachment。
2. 按 Pixel Budget 和 Byte Budget 生成请求版本。
3. 生成 WebP 或 JPEG。
4. 优先上传 Files API。
5. 使用 File ID。
6. Files 失败时整请求回退为 Base64。
7. 超预算的旧图片以占位符保留。
8. 每个请求版本都有确定性身份。

### 13.4 错误归一化

- 401/403：AUTH
- 配额：QUOTA
- 429：RATE_LIMIT
- 400 上下文：CONTEXT_WINDOW_EXCEEDED
- 其他 400：INVALID_REQUEST
- 5xx：SERVER
- 其他：HTTP_Status

### 13.5 动态配置

连接端点、凭据、模型目录、Thinking、图片预算都在每次操作时重新解析。进行中的 Stream 保持启动时快照，下一请求读取新配置。

## 14. Tool Registry

### 14.1 Tool Definition

一个 Tool 声明：

- Name
- Description
- Parameters Schema
- Output Schema
- `execute`
- `finalizeContent`
- `timeoutMs`
- `isConcurrencySafe`
- `presentCall`
- `presentResult`

只有 Name、Description 和 Parameters 进入模型请求。Execute、Timeout、Presentation 等不会泄漏。

### 14.2 Schema DSL

支持：

- string
- number
- integer
- boolean
- null
- array
- object
- json
- oneOf

参数是隐式开放 Object Root，逐属性使用 `required: true`。输出根可以是任意 JSON Root。

### 14.3 Scoped Registry

工具注册支持：

- 全局层
- Agent/Preset 作用域层
- 限制
- Guard
- Shadowing
- PTC Transport

限制可以 Allow 或 Deny。多个 Restriction 取交集。

### 14.4 工具执行流水线

```text
tools/pre-execute
  -> Monotonic Guards
  -> tools/execute
  -> Tool Body
  -> tools/post-execute
  -> finalizeContent
  -> tools/result
  -> tool/result Session Event
```

Pre-execute 可：

- allow
- deny
- ask

Guard 只能 Deny 或 Abstain，不能把 Deny 变回 Allow。

Post-execute 可：

- accept
- replace content
- replace value
- block
- attach additional context

### 14.5 取消

每个 Tool 都接收 `exec.signal`，必须协作取消。

- Dispatch 前取消：`ABORTED_BEFORE_DISPATCH`
- Body 后取消：成功结果可替换为 `ABORTED`
- Timeout：`TOOL_TIMEOUT`
- 异常：结构化失败
- 未知 Tool：`UNKNOWN_TOOL`

同进程代码无法被强制 Hard Kill，只能依赖协作取消。

### 14.6 结果存储

大结果可以由 `spill` 策略转为预览和文件位置。日志保留模型实际可见内容。

## 15. PTC 代码工具模式

PTC 是 Programmatic Tool Calling。

Tool Presentation Mode：

- `native`
- `ptc`
- `both`

### 15.1 Native

所有可见 Tool Schema 直接发送给模型。

### 15.2 PTC

模型只看到：

- `run_code`
- 生成的 TypeScript 或 Python SDK
- SDK 说明

模型在程序内调用：

```ts
tools.bash(...)
tools.read(...)
```

子调用重新进入完整 Tool Pipeline，并使用父调用身份关联。

### 15.3 并发

PTC 子调用遵循 Tool 自身 `isConcurrencySafe`，默认并发上限 10。Exclusive 调用形成 Barrier。

### 15.4 限制

- 中间值只存在 Execution 局部，不能从 Session Log 回放。
- 中间值没有统一字节上限，可能耗尽 Worker 内存。
- 每次 `run_code` 都是新状态，不是持久 REPL。
- 纯 PTC 模式下直接调用其他 Tool 会以 `UNKNOWN_TOOL` 拒绝。
- 同一 Agent 当前不能逐 Tool 混合 Native 与 PTC。

## 16. Sandbox

### 16.1 模式

| 模式 | 文件效果 |
|---|---|
| `read-only` | 只允许必需写入 Sink，例如 `/dev/null` |
| `workspace-write` | 允许工作区和临时目录 |
| `danger-full-access` | 不隔离，直接 Spawn |

Sandbox 只约束文件效果。网络与进程可见性不在该 Service 的定义内。

### 16.2 平台后端

- Linux：bwrap，回退 Landlock
- macOS：Seatbelt
- Windows：ACL Restricted Token

Windows 和旧 Landlock ABI 可能报告 `partial` Enforcement，说明不能完整实现所承诺的文件效果。

### 16.3 强制策略

`ctx.sandbox.confine(argv, policy)`：

- 返回包装后的 Argv
- 报告 Enforcement 完整性
- 返回 Denial Signatures
- 返回 Runner Failure Rules

受限策略下，静默无隔离透传不合法。不存在可用 Sandbox 时 Fail Closed。

### 16.4 Approval

`ctx.approval` 是一次性审批 Seam：

- `ask`
- `never`

结果：

- allowed-once
- denied
- cancelled
- unavailable

没有 Answerer 时 Fail Closed。当前没有 allow-always、持久规则或撤销机制。

## 17. Session 持久化

### 17.1 JSONL Backend

每会话独立文件：

```text
session.v3.jsonl.zstd
session.v3.jsonl
```

默认 Zstd，带 Checksum 帧；可配置为原始 JSONL。

### 17.2 写入

- 批次追加
- 每批可 Fsync
- 第一次 Append 原子 Materialize
- POSIX 使用硬链接抢占
- Windows 使用 Write-through Rename
- 同 ID 多进程写由 Lease 阻止

### 17.3 Generation

已发布 Generation 永不移动、覆盖或删除。

历史格式：

- v0
- v1
- v2
- v3/current

读取时选择最高规范 Generation，可沿相邻迁移链转换历史格式。写打开会发布新 Current Generation。

### 17.4 崩溃恢复

- 撕裂尾部不会提供给 Reader
- 写路径在首次 Append 前截断撕裂尾部
- 未闭合 Turn/Step 会插入恢复边界
- 未记录的 Tool Call 合成 `TOOL_NOT_STARTED`
- 已记录但无结果的 Tool Call 合成 `TOOL_OUTCOME_UNKNOWN`

### 17.5 持久性边界

Append 是 Best-effort，Flush 才是 Durability Barrier。最终子 Agent 结算会尝试 Flush，但 Flush Listener 无法证明任意后端真正持久化。

### 17.6 通用风险

- 格式迁移和旧 Generation 管理复杂。
- Crash 可能丢失已接受但尚未进入 Session Log 的 Inbox Message。
- 多进程共享同一存储仍需要持久邮箱和跨进程租约。
- Session Header 的 CWD 和 Preset 对恢复有语义影响。

## 18. Compaction

`compaction-basic` 在模型上下文接近上限时处理长会话。

### 18.1 默认策略

- 阈值：Context Window 的 80%
- 保留：最近的 16%
- 摘要输出上限：8192 Token
- 自动压缩：开启
- 溢出恢复：1 次

### 18.2 流程

1. 检查 Token Pressure。
2. 可选地先修剪超大 Tool Result。
3. 选择最旧平衡范围。
4. 保留 System Prompt Surface 0。
5. 调用摘要模型。
6. 验证摘要确实缩小 Context。
7. 追加 `compaction/start`。
8. 追加 `compaction/summary`。
9. Replace 旧 Surface Range。
10. 追加 `compaction/end`。

### 18.3 恢复

Provider 返回 `CONTEXT_WINDOW_EXCEEDED` 时：

- 绕过普通阈值
- 尝试一次最大头部缩减
- 只在 Surface Replacement Generation 前进后重试

### 18.4 不安全项

- 系统提示词、Tool Schema 和部分不可分单元可能无法缩减。
- Token Meter 缺精确 Tokenizer 时只是估计。
- Compaction 使用额外模型调用和成本。
- Replace 会使被替换范围的 Prompt Cache 失效。

## 19. System Prompt 与上下文

### 19.1 System Prompt

System Prompt 是 Surface Node 0，不在 Request Header 中复制。

Adapter 可声明：

- `systemPromptUpdate: in-history`

此时 Prompt 变更可以追加在缓存历史之后，而不重写首条 System Message。

不具备该能力的 Route 会把最新文本归并到首条 System Node。

### 19.2 Context Plugins

内置上下文包括：

- Agent Instructions
- Project Instructions
- Session Reference
- Time Context
- Tmux Context
- File References
- Goal
- Plan
- Approval Policy
- Sandbox Policy

上下文通过 `agent.inject()` 或 Pre-step 进入，并保留来源。

### 19.3 Prompt Cache

系统非常重视：

- 稳定 Row Order
- 稳定 Tool Order
- Surface 仅追加
- `in-history` 更新
- Prefix-preserving Compaction
- 明确记录 Cache Impact

但任何 Tool Set、System Prompt、Model 或 Image 表示变化都可能破坏 Prefix Cache。

## 20. Web Surface

### 20.1 启动

```bash
dsh web
dsh --profile web --no-open --port 8080
```

默认：

```text
http://127.0.0.1:3080
```

默认尝试打开浏览器。

### 20.2 认证

- 每个进程生成随机启动 Token
- 启动 URL 带 Token
- `GET /` 接受 Token
- 写入绑定 Host 的签名 Cookie
- Cookie：HttpOnly、SameSite=Strict、Path=/
- 默认 30 天
- 静态资源公开

### 20.3 Host 和 Origin 校验

在认证前：

- Host 必须为 Loopback 或 Trusted Host
- Origin 必须等于 Host
- `Sec-Fetch-Site: cross-site` 拒绝
- DNS Rebinding 和跨站请求受防护

### 20.4 限制

- 不支持绑定 `0.0.0.0`
- Loopback HTTP 不设置 Secure Cookie
- 没有 Logout API，需要清 Cookie 或删除 Grant
- LAN 地址只在启动时采样一次
- Session 文件媒体 Route 可以读取已注册 Workspace 之外的临时路径

### 20.5 传输

- HTTP POST 一元 Remote
- `/api/remote.mux` WebSocket
- 精确 GET、HEAD、POST Route
- 流式文件上传
- Remote Stream Generation
- 断线指数退避和 Jitter
- 页面 Offline 时暂停自动重连

## 21. Desktop

Electron Desktop：

- 在签名资源内携带固定 dsh Runtime
- 启动内置 Node Desktop Host
- Host 加载 dsh Backend 和匹配的客户端图
- 使用版本化 Framer Pipe 传输 RPC 和 Remote Stream
- Node IPC 只承载生命周期控制
- 渲染进程通过 `dsh-app://`
- 不开放 Web Server 或 Loopback Port
- 插件事务由内置 pnpm 和私有 Store 管理

Desktop Profile 与 CLI Profile 共享 `$DSH_HOME` 产品数据，但 Executable、Package State 和 Activation 独立。

## 22. Headless、SDK 和 ACP

### 22.1 Headless

```bash
dsh --profile headless "run the tests"
```

流程：

1. Mount Base
2. 解析 Task
3. 创建 Agent
4. 执行 Turn
5. 打印 Durable Result
6. Exit

不挂载 HTTP、Web Runtime 或浏览器插件。

### 22.2 TypeScript SDK

SDK Profile 挂载 JSON-RPC Server。

stdout 仅属于 JSON-RPC，避免日志污染协议。

### 22.3 Python SDK

Python Runtime Wheel 包装普通 dsh CLI：

- 选择 `sdk` Profile
- 使用明确 Harness Home
- 提供 Profile 和 Patch 选择
- 外部插件通过 `dsh plugin` 安装

### 22.4 ACP

ACP Profile 提供自动化专用 Agent Client Protocol Server。

ACP 子 Agent 当前以一次性 Seam 为主，尚未支持完整可继续远程子 Agent。

## 23. Subagent

### 23.1 Subagent Seam

`ctx.subagents` 支持多个命名 Provider：

- in-process spawn
- in-process fork
- ACP
- Codex
- Claude Code
- DSH SDK

同一个组合可并存多个 Provider。

### 23.2 一次性 Subagent

- 一次 Prompt
- 一个结果
- 可设置 Provider、Model、Reasoning Effort 和 Max Tokens
- 可设置 Output Schema
- 可设置 Tool Filter
- 可设置 Persona
- 可设置 Delegation Depth
- 调用方持有 `SubagentRun` 并必须 Dispose

### 23.3 可继续 Subagent

每次是一个持久 Session：

```text
Persisted Session
  -> zero or one Activation
  -> AgentHandle
  -> Inbox
  -> owned child Activations
```

支持：

- `sendMessage`
- Queue
- Steer
- Interrupt
- Cold Resume
- Parent/Child 相邻消息
- 子级优先释放

限制：

- 仅相邻 Agent 可互发消息
- 无持久 Parent Mailbox
- 进程内 Activation 不跨进程协调
- 未记录消息可能因崩溃丢失
- 可继续 ACP 尚未完成

### 23.4 Agent Teams

实验性 Agent Teams 在 Subagent 上增加：

- 持久 Roster
- 任务板
- Mailbox

默认显式启用。

## 24. MCP、Skill、Hook 和 Workflow

### 24.1 MCP

仓库包含 MCP Client 包和配置支持。MCP Tool 发现后通过 `ctx.tools.register()` 进入统一工具池。

MCP 适合外部能力接入，但仍属于高权限 Tool 边界。

### 24.2 Skill

Skill 文件系统和 Registry 提供可发现、加载和调用的技能。Skill 可以是一个目录和说明文件，通过工具或命令进入 Agent。

### 24.3 Hooks

Hooks 桥接：

- Claude Code
- Codex
- 通用 Hook Protocol

Hook 可以影响：
- Pre-step
- Request
- Tool Pre/Post
- Turn Stopping
- Session Start
- Compaction 等

Hook 是高权限扩展点。

### 24.4 Workflow

Workflow 提供：

- 独立生命周期
- Phase
- Log
- Agent Start/End
- Workflow Start/End
- `workflow` Tool
- Worker Thread Provider

它适合多阶段、可恢复或脚本化流程。

## 25. Jobs、Terminal 和 Schedule

### 25.1 Jobs

- `job_list`
- `job_output`
- `job_kill`

后台任务回归 Job Registry，并与 Agent Session 关联。

### 25.2 Terminal

支持持久终端：

- open
- read
- send
- signal
- list
- close

底层依赖跨平台 PTY，Windows 使用 ConPTY。

### 25.3 Schedule

Schedule 可以创建、列出和删除定时任务，并可以与 Goal 和 Agent 轮次驱动集成。

## 26. 配置和凭据

### 26.1 Harness Home

默认：

```text
$DSH_HOME
~/.dsh
```

包含：

- Profiles
- Settings
- Credentials
- Sessions
- Storage
- Agent Presets
- Plugin State
- Anonymous Identity

### 26.2 Settings

`$DSH_HOME/settings.yaml` 可热重载。

模型 Adapter 的 Settings Section 可以：

- 启用或禁用 Provider
- 修改 Base URL
- 修改模型目录
- 修改 Thinking
- 修改图片预算
- 修改 Retry Policy

### 26.3 Credentials

凭据来源：

1. 继承环境
2. 管理凭据文件
3. Project `.env`
4. User `.env`

Adapter 按请求解析 Credential Reference，而不是把密钥复制进每个请求对象。

### 26.4 配置错误原则

- 自包含错误在加载时 Fail Loud
- 动态错误在最早可解析点 Fail Loud
- 不静默跳过缺失引用
- 不把 Schema 默认值藏在 `run()` 中
- 可变部署参数属于 Config

## 27. 可观测性和隐私

### 27.1 Telemetry

默认模式是 `FEEDBACK_ONLY`。

- Session Log 只在用户明确反馈后上传
- 匿名 User ID 存在 `$DSH_HOME/.anonymous-user-id`
- 删除文件可重置身份
- `DSH_TELEMETRY_DISABLED` 任意非空值都会禁用
- `0` 和 `false` 也视为禁用，采用隐私优先策略

### 27.2 Trace

- Session Event
- Model Attribution
- Provider Request ID
- LLM Attempt
- Turn Usage
- Context Breakdown
- Tool Result Metadata
- Workflow Event
- Subagent Event

### 27.3 日志与隐私

Session 可能包含：

- Prompt
- 文件内容
- Shell 输出
- Tool 参数
- 结果
- 路径
- 外部 API 数据

必须按照敏感数据管理，而不是普通 Debug Log。

## 28. 文档和工程约束

项目对文档约束很强：

- 中英双语配对
- 每段一物理行
- 每个事实只有一个权威位置
- 链接校验
- Mermaid 校验
- 文档预算
- 生成目录校验
- 第三方 Notice 校验
- 包路径校验
- Export JSDoc 校验
- 运行时 Invariant 规则
- Agent Note 记录非平凡架构决策
- Session Format 发布记录

这说明项目把“设计事实必须可验证”当作工程质量的一部分。

## 29. 测试和质量保障

测试规模：

- 约 1,278 个测试文件
- 约 373,672 行测试代码

测试类型：

- Unit
- E2E
- Snapshot
- Expected Output
- Web Snapshot
- Performance Benchmark
- Stress
- Migration
- Cross-process Lease
- Crash Recovery
- Loader Composition
- Package Invariant
- Documentation Gate
- Static Architecture Gate

当前机器：

- Node.js `v25.2.1`
- pnpm `11.7.0`
- npm `11.6.2`
- Python `3.13.14`
- `uv` 未安装
- 根 `node_modules` 不存在

因此本轮没有执行：

- `pnpm install`
- `pnpm run build`
- `pnpm run test`
- `pnpm run typecheck`
- `pnpm run test:e2e`
- `pnpm run test:snapshot`
- `pnpm run website:build`

## 30. 主要设计优点

1. Cordis 真正确立了“插件可替换”，不是仅做表面 Hook。
2. Profile、Bundle 和 Patch 让产品组合可审计和可覆盖。
3. 事件溯源 Session 为回放、Fork、Web、SDK 和 Telemetry 提供统一事实源。
4. Turn/Step 生命周期定义严格，工具和模型行为可重建。
5. LLM Service 与 Provider Adapter 边界清晰。
6. Prepared Call 绑定 Adapter 代际，避免热更新竞态。
7. Tool Schema DSL 同时服务 Runtime 校验、输出校验、TypeScript SDK、Python SDK 和 MCP。
8. Tool Pipeline 将审批、沙箱、Timeout、结果改写和 UI 分离。
9. Sandbox 是正式 Seam，支持 Linux、macOS 和 Windows。
10. Approval 默认 Fail Closed，没有 Answerer 时拒绝。
11. Session JSONL 具备版本、迁移、Zstd、Checksum 和崩溃恢复。
12. Web 有 Token、签名 Cookie、Host、Origin 和跨站防护。
13. Headless、SDK、ACP、Web、Desktop 共享核心。
14. PTC 为大量工具提供了减少 Tool Schema 提示词成本的路径。
15. 文档、生成物和 Invariant 门禁非常强。

## 31. 主要风险和限制

### P1：Developer Preview 破坏兼容

README 明确声明未来会有破坏性变更。公共 API、插件协议和 Session 行为都可能变化。

### P1：插件组合复杂度

Profile、Bundle、Patch、`!!js`、Overlay 和 Live Reload 很灵活，但排查最终配置必须依赖 `--dump-config`。一个 Patch 替换整行 Config 而不是深合并，容易误删其他键。

### P1：Session 格式和迁移责任

已发布 Session Generation 不允许降级或回退。迁移链、Zstd、Checksum、跨进程 Lease 和崩溃修复都很强，但维护成本高。

### P1：Sandbox 不是完整隔离

Sandbox 只定义文件效果，不定义网络和进程可见性。Windows 和旧 Landlock 可能是 `partial`。它降低风险，但不是不可信代码的完整安全边界。

### P1：Tool Timeout 依赖协作

Timeout 由 Wrapper 实现，Tool 必须 Forward `exec.signal`。同进程代码无法硬杀，违反协作约定就可能超出 Deadline。

### P1：Web Cookie 无 Secure

随附 Web 设计只用于 Loopback HTTP，因此 Cookie 不设置 Secure。如果把同一 Authority 暴露到明文网络，Bearer Cookie 可能泄漏。产品明确不支持 `0.0.0.0` 绑定，但底层 WebServer 支持。

### P1：Session 可能包含敏感数据

Prompt、文件、Shell、Tool Result 和外部响应都会写入 JSONL。必须把 Session Root 当作敏感数据目录。

### P1：可继续 Subagent 不是跨进程一致协议

Activation、Ownership Graph 和 Inbox 只存在于单进程。两个 Harness 进程共享存储时没有持久 Mailbox 和跨进程 Leak 协议。

### P2：PTC 中间值不可回放

PTC 程序内部中间值只存在于执行局部，无法从 Session Log 重建，也没有统一字节上限。它可能造成内存压力，并降低审计完整性。

### P2：配置和模块规则复杂

模块解析有安装锚点、Profile 锚点、Symlink、ESM Proxy、Packaged Exe 和跨进程 Lock 等分支，理解成本高。

### P2：多 Surface 增加测试矩阵

Web、Desktop、CLI、Headless、SDK、ACP 各自有环境、协议和快照要求，完整验证代价高。

### P2：Telemetry 虽默认隐私优先，但仍需部署审查

默认只在反馈后上传 Session Log，但外部 Provider、Webhook 和网络工具仍然会接触真实数据。

### P2：测试无法在当前环境执行

没有 `node_modules`，因此无法从源码验证任何声称的行为。当前结论来自源码、文档和静态盘点。

## 32. 对 Algocode 的可借鉴设计

### 32.1 建议直接借鉴

1. **Session Event Log 作为事实源**  
   Algocode 应有自己的 `SessionEvent`，记录 User、Assistant、Tool Call、Tool Result、Run、Optimize、Checkpoint 和 Error。

2. **Turn 与 Step 分离**  
   Turn 是用户任务，Step 是模型请求加工具调用。它们的状态必须独立记录。

3. **模型可见即已记录**  
   进入模型的 Prompt、Context、Tool Schema 和 User Message 都能从 Session Log 重建。

4. **Tool Pipeline**  
   使用 Pre、Guard、Execute、Post、Finalize、Result 分层，但规模可以从简。

5. **能力 Seam**  
   定义：
   - Model
   - Tool
   - Workspace
   - Runner
   - Storage
   - Permission

6. **配置 Dry-run**  
   `algocode config dump` 应能打印最终有效配置和来源。

7. **Fail Closed**  
   无审批、无沙箱或无法解析权限时，高风险操作应拒绝。

8. **Format Version**  
   本地 Session 和 Cache 从第一天就带版本号与迁移入口。

9. **内容级结果存储**  
   大 Output 转存文件，模型只看预览和定位。

10. **可重建请求**  
    每次模型调用记录 Provider、Model、Tool Schema、Context 和 Message Prefix 的来源。

### 32.2 改造后借鉴

1. **Cordis 不必直接引入**  
   Algocode 可用 Python Protocol、Registry 和 Dependency Injection 实现相近 Seam，不必引入完整插件框架。

2. **Profile/Patch 可简化为 TOML**  
   支持少量明确 Overlay，不做任意 `!!js`。

3. **PTC 暂时不做**  
   先做 Native Tool Calling。只有工具数量和 Schema Token 成本成为真实问题，再引入代码工具。

4. **Sandbox 先做 Workspace Boundary**  
   第一版要求所有写操作位于 Workspace，不允许指定任意外部路径。

5. **Approval 支持持久规则**  
   DeepSeek Harness 当前只有 One-shot Approval。Algocode 可以设计更完整的 Allow Rule，但必须明确作用域和撤销。

6. **Session Format 只保留一个当前版本**  
   先支持 JSONL v1，后续再做迁移。

7. **Web/Remote 延后**  
   先把 CLI 和本地 Session 做好，再考虑 HTTP。

8. **Subagent 先做一次性**  
   持久 Subagent 和 Agent Team 会引入复杂生命周期，应等核心任务稳定后再做。

### 32.3 不要直接照搬

1. 不要实现五层事件分发、Profile、Bundle、Patch 和动态 HMR 全套。
2. 不要让 Tool Timeout 只依赖协作而缺少外部进程强制终止策略。
3. 不要把网络权限混同为文件 Sandbox。
4. 不要把大 Prompt 和文件内容长期明文保存在无保护的临时目录。
5. 不要在没有明确 Session Schema 的情况下一开始就做 Fork 和 Compact。
6. 不要把所有产品 Surface 都塞入单仓库第一阶段。
7. 不要复制内部 Project 名称和未公开模型 ID。
8. 不要在 Algocode 没有 Traction 前实现多个 SDK 和 Desktop。

## 33. 面向 Algocode 的最小落地路线

### 阶段 1：Session 与 Runner

```text
algocode run <algorithm-task>
algocode session list
algocode session show <id>
```

实现：

- Session Event Log
- Turn / Step
- Model Adapter
- Tool Registry
- Read、Search、Patch、Run Test
- Workspace Boundary
- JSONL v1

### 阶段 2：权限与沙箱

实现：

- read-only
- workspace-write
- danger-full-access
- Approval：ask、never、allow-rule
- 子进程 Timeout
- 输出截断
- 审计事件

### 阶段 3：优化循环

```text
algocode optimize <target>
algocode benchmark <profile>
algocode compare <run-a> <run-b>
```

实现：

- 基线测量
- Patch 迭代
- Test Gate
- Benchmark Gate
- 回归检测
- 成本预算
- 收敛条件

### 阶段 4：Provider 与压缩

实现：

- 第二 Provider
- Context Budget
- Tool Result Pruning
- Summary Compaction
- Model Fallback
- Token Cost

### 阶段 5：服务化和插件

按需增加：

- MCP
- HTTP
- Remote Runner
- Workflow
- Subagent

## 34. 最终评价

DeepSeek Harness 是当前分析项目中最完整的“Agent 产品运行时”设计之一。它把模型、工具、Session、沙箱、权限、Web、SDK 和桌面都变成了可组合能力，工程约束也非常强。

它最值得 Algocode 学习和重新实现的部分是：

1. Session 事件溯源。
2. Turn 与 Step 生命周期。
3. Tool Execution Pipeline。
4. Sandbox 与 Approval Fail Closed。
5. Prepared Model Call。
6. Tool Result Pruning 与 Compaction。
7. 配置来源可审计。
8. 模型可见内容可回放。

但它不适合被 Algocode 直接搬入。原因是：

- 项目处于 Developer Preview
- 插件和 Patch 系统复杂
- Session 迁移和维护成本高
- Sandbox 不是完整安全边界
- 多 Surface 带来巨大测试矩阵

对 Algocode，最合理的方向是取其原则、缩其骨架：

```text
Event-sourced Session
+ simple provider adapters
+ scoped tool registry
+ explicit permission modes
+ workspace sandbox
+ budgeted model loop
+ deterministic optimization and benchmark gates
```

这套结构已经足以支撑算法优化 Agent，同时不会在早期就被完整 Harness 平台的复杂度拖住。
