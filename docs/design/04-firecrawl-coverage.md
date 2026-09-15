# Firecrawl 阅读覆盖台账

> 对应设计文档：`04-firecrawl-design.md`  
> 分析日期：2026-09-15  
> 分析对象：`C:\Users\Administrator\Desktop\firecrawl-main\firecrawl-main`  
> 快照状态：没有可确认的 Git 元数据，没有 `node_modules`、`apps/api/node_modules`、`apps/js-sdk/node_modules` 或 Python `.venv`

## 1. 覆盖结论

Firecrawl 是一个超大型多语言 monorepo。本次没有声称对全部源码逐行阅读，覆盖策略如下：

1. 服务端顶层目录、应用目录、SDK 目录和基础设施文件已盘点。
2. API 启动、路由、核心控制器、抓取瀑布、Transformer、Crawl、Batch、Map、Search、NuQ、Redis 状态、计费、Webhook、ZDR 和自托管链路做核心精读。
3. 各语言 SDK 做公共接口、默认版本、异步能力和 Watcher 结构审阅。
4. 274 个测试文件没有逐行阅读，按文件分布、测试主题和主要测试入口审阅。
5. UI、CLI、Workflow、Kubernetes 示例和外围集成只做结构级覆盖。
6. 没有执行构建和测试，因为当前仓库没有安装依赖。

## 2. 仓库规模

### 2.1 服务端源码

统计范围为 `apps/api` 下的 TypeScript、TSX、JavaScript、MJS 和 CJS 文件，排除 `node_modules` 与 `dist`。

| 范围 | 文件数 | 行数 |
|---|---:|---:|
| `apps/api` 代码 | 818 | 207,995 |
| API 测试文件 | 274 | 68,444 |
| 测试调用行 | 未单独统计文件 | 2,439 |
| Python SDK | 130 | 33,664 |

### 2.2 `apps/api/src` 模块

| 模块 | 文件数 | 行数 | 覆盖级别 |
|---|---:|---:|---|
| `__tests__` | 114 | 33,796 | 主题与关键用例审阅 |
| `controllers` | 117 | 25,503 | 核心控制器精读 |
| `lib` | 240 | 66,755 | 核心辅助和状态层精读 |
| `scraper` | 137 | 30,694 | 核心抓取链精读 |
| `services` | 153 | 41,554 | 队列、Worker、Billing、Webhook 精读 |

### 2.3 OpenAPI

| 文件 | 路径数 |
|---|---:|
| `apps/api/openapi.json` | 20 |
| `apps/api/v1-openapi.json` | 18 |
| `apps/api/openapi-v0.json` | 5 |

OpenAPI 不覆盖全部实际路由，尤其是内部、WebSocket、Admin、Labs、Exchange 和 MCP 路由。

## 3. 核心源码精读清单

以下文件已阅读完整文件或按关键连续段精读。

### 3.1 启动、路由和配置

| 文件 | 行数 | 内容 |
|---|---:|---|
| `apps/api/src/index.ts` | 312 | Express 启动、路由、错误处理和优雅关闭 |
| `apps/api/src/harness.ts` | 1,252 | 开发、容器和多 Worker 启动器 |
| `apps/api/src/routes/v2.ts` | 709 | v2 全路由及中间件顺序 |
| `apps/api/src/config.ts` | 约 600+ | 环境变量、队列、存储、外部服务和安全配置 |
| `apps/api/src/routes/v1.ts` | 约 200+ | v1 路由与兼容策略 |
| `apps/api/src/routes/v0.ts` | 约 30 | v0 旧路由 |
| `docker-compose.yaml` | 约 200 | 自托管服务拓扑和默认配置 |
| `SELF_HOST.md` | 约 100 | 自托管边界、安全和持久化说明 |

### 3.2 Scrape、Crawl、Batch、Map 和 Search

| 文件 | 行数 | 内容 |
|---|---:|---|
| `controllers/v2/scrape.ts` | 693 | 同步 Scrape、权限、计费、信号量和直接执行 |
| `controllers/v2/crawl.ts` | 362 | Crawl 创建、Prompt 参数生成、队列和 Kickoff |
| `controllers/v2/batch-scrape.ts` | 466 | Batch 创建、URL 清洗、Append 和任务展开 |
| `controllers/v2/crawl-status.ts` | 405 | Crawl/Batch 状态、分页、结果聚合和警告 |
| `controllers/v2/crawl-status-ws.ts` | 244 | WebSocket 增量文档流 |
| `controllers/v2/crawl-cancel.ts` | 68 | Crawl/Batch 取消 |
| `controllers/v2/crawl-errors.ts` | 163 | 失败任务和 robots 阻断查询 |
| `controllers/v2/map.ts` | 326 | Map 请求、威胁过滤、计费和响应 |
| `controllers/v2/search.ts` | 503 | Search 请求、ZDR、权限、计费和审计 |
| `controllers/v2/queue-status.ts` | 89 | 团队队列状态查询 |

### 3.3 抓取引擎和转换

| 文件 | 行数 | 内容 |
|---|---:|---|
| `main/runWebScraper.ts` | 172 | Worker 到 ScrapeURL 的封装和 Crawl 重试 |
| `scraper/scrapeURL/index.ts` | 1,848 | Meta、特性、瀑布、错误处理和超时 |
| `scraper/scrapeURL/engines/index.ts` | 1,099 | 引擎注册、能力矩阵、质量和选择 |
| `scraper/scrapeURL/transformers/index.ts` | 700 | 文档转换管线 |
| `scraper/scrapeURL/transformers/llmExtract.ts` | 1,605 | LLM 提取、摘要、Schema 和成本 |
| `scraper/scrapeURL/lib/promptInjectionGuard.ts` | 217 | Prompt Injection 分类器 |
| `lib/html-to-markdown.ts` | 172 | HTTP、Go、Turndown 三级转换 |
| `scraper/WebScraper/crawler.ts` | 1,091 | URLs 过滤、robots、Sitemap 和范围内 Crawl |
| `lib/map-utils.ts` | 429 | Index、Fire Engine、Sitemap 和 Cosine 排序 |
| `search/execute.ts` | 427 | Search 聚合、抓取、威胁过滤、计费和 Highlight |

### 3.4 Worker、队列和状态

| 文件 | 行数 | 内容 |
|---|---:|---|
| `services/worker/scrape-worker.ts` | 1,863 | Scrape、Kickoff、Sitemap、发现、计费和落库 |
| `services/queue-jobs.ts` | 901 | Job 入队、并发门控、PG/FDB 路由和等待 |
| `services/worker/nuq.ts` | 1,770 | PostgreSQL NuQ、锁、Group 和监听 |
| `services/worker/nuq-router.ts` | 760 | PG/FDB 路由、标记和外部容量 |
| `services/worker/nuq-worker-runner.ts` | 232 | Worker 循环、健康检查和优雅关闭 |
| `services/worker/crawl-logic.ts` | 214 | Crawl 完成和审计 |
| `lib/crawl-redis.ts` | 1,024 | Crawl Redis 状态、锁和完成修复 |
| `lib/concurrency-queue-reconciler.ts` | 367 | 并发队列漂移修复 |
| `lib/zdr-helpers.ts` | 97 | ZDR 模式解析 |
| `lib/zdrcleaner.ts` | 118 | ZDR GCS 清理 |
| `services/webhook/delivery.ts` | 300 | Webhook 过滤、HMAC、队列和日志 |
| `services/webhook/queue.ts` | 约 220 | RabbitMQ 持久 Webhook 队列 |

### 3.5 数据模型和配置

| 文件 | 行数 | 内容 |
|---|---:|---|
| `controllers/v2/types.ts` | 2,791 | v2 API Schema 和 Document 类型 |
| `db/schema/public.ts` | 约 800+ | 主 PostgreSQL schema |
| `db/schema/index-db.ts` | 约 80+ | Index 和 Engpicker schema |
| `services/worker/nuq-fdb/queue.ts` | 约 1,400+ | FoundationDB 队列实现 |
| `apps/api/package.json` | 约 160 | 依赖、Worker scripts 和测试命令 |

## 4. 抓取引擎覆盖

已盘点并核对的引擎：

- `exchange`
- `index`
- `index;documents`
- `x-twitter`
- `wikipedia`
- `fire-engine;chrome-cdp`
- `fire-engine(retry);chrome-cdp`
- `fire-engine;chrome-cdp;stealth`
- `fire-engine(retry);chrome-cdp;stealth`
- `fire-engine;tlsclient`
- `fire-engine;tlsclient;stealth`
- `playwright`
- `fetch`
- `pdf`
- `document`
- `image`

已确认：

- `Engine` 联合类型
- `engineHandlers` 注册表
- `engineMRTs` 超时估算表
- `engineOptions` 能力与质量矩阵
- `buildFallbackList` 的选择和过滤逻辑
- `shouldUseIndex` 的缓存跳过条件
- `scrapeURLWithEngine` 的引擎调用边界
- 文件预取和浏览器交接路径

未逐行阅读所有具体引擎实现，例如 Fire Engine 内部服务、Rust PDF 库和 MinerU 服务本体。

## 5. PDF、Office、图片和媒体覆盖

已阅读或核对：

- PDF/FirePDF 的目录结构和核心路径
- PDF parser mode：fast、auto、ocr
- pages、blocks、pageMarkers
- 本地 Rust/pdfplumber 路径
- MinerU 路径
- FirePDF 同步和异步路径
- 大文件 by-reference 与 GCS 交接
- Document 和 Image 在瀑布中的文件预取逻辑
- 图片 OCR 的团队 flag 和 `imageOcrGate`

未执行：

- 真实 PDF 解析
- OCR
- MinerU
- FirePDF 服务部署
- 大 PDF 异步任务恢复

## 6. Crawl 和 Batch 覆盖

已核对完整链路：

```text
Controller
  -> StoredCrawl
  -> Crawl Group
  -> Kickoff Job
  -> Sitemap Job
  -> Discovered Scrape Jobs
  -> URL Lock
  -> Done Markers
  -> Finish Crawl
  -> Webhook / DB log / Cleanup
```

覆盖内容包括：

- includePaths 和 excludePaths
- maxDepth 和 maxDiscoveryDepth
- crawlEntireDomain 和 allowBackwardCrawling
- allowExternalLinks
- allowSubdomains
- robots.txt
- Sitemap include、skip、only
- URL 规范化和相似 URL 去重
- Redirect 范围检查
- 原子 URL 锁定
- Crawl 并发限制
- 完成标记重试和 repair
- Batch 的 invalidURLs、append 和 maxConcurrency
- 状态分页和 10 MiB 响应限制
- WebSocket catchup、document 和 done
- Cancel 和 Errors 接口

## 7. Map 和 Search 覆盖

Map：

- Redirect 解析
- Index 查询
- Fire Engine Map 查询
- Sitemap
- 缓存 48 小时
- URL 清洗
- 同域、子域和路径过滤
- Cosine Similarity
- 威胁过滤
- Credits 和日志

Search：

- Web、News、Image、Developer、Tools
- Search Query Builder
- Developer 并发查询
- Provider Tools
- Threat 过滤
- 搜索结果 Scrape
- Highlights 影子或应用模式
- Search credits
- Search ZDR 和 anonymous
- Search 结果追踪

未逐行展开 Alexandria、Research Index 和内部 Search Provider 的全部实现。

## 8. NuQ、并发和恢复覆盖

已阅读：

- NuQ PG Job API
- Group API
- Job Lock 和续租
- Job Finish 和 Fail
- `LISTEN` 通知
- RabbitMQ 队列信号
- FDB 路由
- 团队和 Job 后端标记
- Crawl 级后端固定
- 团队队列上限
- Crawl `maxConcurrency`
- Team semaphore 同步 Scrape
- Job backlog timeout
- `QueueFullError`
- Concurrency Queue reconciler
- Crawl Done Marker repair
- Worker 健康检查、metrics 和 graceful shutdown

未执行：

- PG NuQ 集成测试
- FoundationDB 健康测试
- RabbitMQ 断线恢复测试
- Reconciler 故障注入
- 大规模并发压力测试

## 9. API 和 SDK 覆盖

服务端已盘点：

- v0、v1、v2 路由
- WebSocket
- Auth middleware
- Credits middleware
- Country check
- Blocklist
- Idempotency
- request timing
- v2 schema
- OpenAPI 文件
- MCP Action Logs
- Browser、Monitor、Slack、Support 和 Research 扩展路由

SDK 已审阅：

| SDK | 覆盖 |
|---|---|
| Python | 顶层 v2、`.v1`、Async、Watcher、Pydantic、方法清单 |
| Node.js | v2 继承、`.v1` 惰性客户端、Watcher、WebSocket 回退 |
| Go | API 文件和模型结构 |
| Java | 客户端和模型目录结构 |
| Rust | Client、各 endpoint 模块和测试目录 |
| Ruby | Client、HTTP client 和 models |
| PHP | Client、Laravel Tools 和测试 |
| .NET | Client、Models、Exceptions 和测试 |
| Elixir | Client 和生成器结构 |

未逐行阅读每种 SDK 的全部实现。

## 10. 测试覆盖情况

测试规模：

- 274 个测试文件
- 68,444 行
- 2,439 行 `it(...)` 或 `test(...)`
- 包含 E2E with auth、E2E no auth、Snips、控制器测试、lib 测试和 scraper 测试

测试目录包含：

- `src/__tests__/e2e_noAuth`
- `src/__tests__/e2e_withAuth`
- `src/__tests__/e2e_full_withAuth`
- `src/__tests__/e2e_v1_withAuth`
- `src/__tests__/snips/v0`
- `src/__tests__/snips/v1`
- `src/__tests__/snips/v2`
- `src/routes` 路由测试
- 各模块附近单元和集成测试

未执行原因：

- `apps/api/node_modules` 不存在
- 根 `node_modules` 不存在
- 没有安装 pnpm workspace 依赖
- 无法启动 Vitest、TypeScript 和 Supertest
- 无法启动 Redis、PostgreSQL、RabbitMQ、Playwright 等服务

因此设计文档中的行为结论来自源码和配置，不代表已通过本机运行验证。

## 11. 自托管和部署覆盖

已阅读：

- `SELF_HOST.md`
- `docker-compose.yaml`
- API Dockerfile
- Compose 服务依赖
- NuQ PostgreSQL
- FoundationDB Compose
- Playwright 服务
- Redis
- RabbitMQ
- 环境变量默认值

已确认：

- 默认 API 无认证
- 默认不挂载 Redis、RabbitMQ、NuQ PostgreSQL 持久卷
- 只有 API 默认发布到宿主
- FoundationDB 默认是可选后端
- Playwright 有资源限制
- API 默认 4 CPU、8 GB 内存限制
- Playwright 默认 2 CPU、4 GB 内存限制

未执行：

- Docker Compose build
- 容器启动
- K8s 或 Helm 安装
- 生产安全验收
- 备份恢复测试

## 12. 未覆盖或未验证范围

以下内容没有按“逐行设计审计”处理：

- `apps/ui` 全部前端
- `firecrawl-cli` 全部命令
- `firecrawl-skills` 和 `firecrawl-workflows`
- Kubernetes 和 Helm 所有 manifest
- Fire Engine 私有服务实现
- FirePDF 服务本体
- Rust PDF 原生库内部算法
- MinerU 模型服务
- 所有第三方依赖源码
- 所有语言 SDK 的全部测试
- 所有 274 个 API 测试文件的每一行
- ClickHouse、Bigtable、Pub/Sub 的真实云集成
- Slack、Monitor、Browser 的长生命周期测试

## 13. 证据可信度分级

| 级别 | 含义 | 示例 |
|---|---|---|
| A | 已读取完整源码或关键连续段，并在文档中引用行为 | v2 routes、Scrape、Crawl、NuQ、Reconciler |
| B | 已审阅接口、目录和关键函数，但未覆盖全部实现 | 各语言 SDK、Map/Search Provider |
| C | 只做结构盘点或根据配置推断 | UI、CLI、K8s、第三方服务 |
| D | 未执行，不能确认运行时结果 | 测试、容器、云服务、压力测试 |

本设计文档的大部分核心结论属于 A 级；产品外围和能力边界属于 B 或 C 级；测试和部署状态属于 D 级事实，即“未执行”。

## 14. 最终覆盖评价

对 Firecrawl 的核心服务端运行链，覆盖已经足以支持以下工作：

- 理解同步 Scrape 与异步 Crawl/Batch 的差异
- 理解引擎瀑布和 Transformer 的扩展方式
- 理解 Crawl、Map、Search 的状态和复用关系
- 理解 NuQ、并发限制和恢复机制
- 识别自托管、ZDR、安全和多存储风险
- 为 Algocode 设计抓取 Fetcher、任务状态、缓存和预算控制

对完整 Firecrawl 的全部私有服务、外围模块和每个测试用例，当前没有足够证据声称已经逐行验证。后续如需直接复用某些实现，应先针对目标模块补充依赖安装、运行测试和小规模故障注入。
