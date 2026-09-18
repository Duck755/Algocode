# 配置参考

Algocode 的配置由多个 YAML 文件合并得到。字段名同时支持 camelCase 和 snake_case，但为保持和内置模型一致，推荐优先使用 camelCase。

## 加载顺序

最终配置由低到高合并：

1. 内置默认值。
2. 用户全局配置。
3. 项目配置 `.algocode/config.yaml`。
4. 项目本地覆盖 `.algocode/config.local.yaml`。
5. `ALGOCODE_*` 环境变量。
6. CLI 显式参数。

全局配置默认位于 Algocode 数据目录下的 `config.yaml`，通常为：

```text
%LOCALAPPDATA%\algocode\config.yaml   # Windows
~/.local/share/algocode/config.yaml   # Linux
~/Library/Application Support/algocode/config.yaml  # macOS
```

## 最小示例

```yaml
version: 1

project:
  language: auto
  sourceRoot: .

defaults:
  provider: openai
  model: openai/gpt-5-mini

runtime:
  maxStepsPerPhase: 30
  maxToolCallsPerPhase: 50
  maxCandidates: 3

acceptancePolicy:
  requireCorrectness: true
  minMedianImprovementPercent: 5.0
  maxPeakMemoryRegressionPercent: 10.0

policy:
  approval:
    mode: interactive
  sandbox:
    backend: auto
    timeoutSeconds: 120
    maxOutputBytes: 1000000
```

## `project`

项目级默认值。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `language` | `auto` / `cpp` / `python` | `auto` | 主语言。同时存在 Python 和 C++ 时，`auto` 优先 C++。 |
| `sourceRoot` | path | `.` | 相对仓库根目录的源码目录。 |

## `providers`

模型服务商映射。键是 Provider Key，值是 Provider 配置。

```yaml
providers:
  openai:
    type: openai-compatible
    baseUrl: https://api.openai.com/v1
    credentialRef: local://openai
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `type` | string | `openai-compatible` | 当前支持 `openai-compatible` 或 `anthropic`。 |
| `baseUrl` | string | 空 | 服务端 Base URL。 |
| `apiKeyEnv` | string | 空 | 指定读取 Key 的环境变量名；不要直接写 Key。 |
| `credentialRef` | string | 空 | 凭证引用，支持 `env://<NAME>` 或 `local://<NAME>`。 |

## `models`

模型别名映射。键是 Model Key，值为模型配置。

```yaml
models:
  openai/gpt-5-mini:
    provider: openai
    model: gpt-5-mini
    contextWindow: 128000
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `provider` | string | `default` | 指向 `providers` 中的 Key。 |
| `model` | string | 必填 | 服务端模型 ID。 |
| `contextWindow` | int | `128000` | 上下文窗口大小，必须大于 0。 |

## `defaults`

当前项目默认使用哪个 Provider 和 Model。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `provider` | string | `default` | 默认 Provider Key。 |
| `model` | string | `default` | 默认 Model Key。 |

## `runtime`

Agent 运行预算。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `maxStepsPerPhase` | int | `30` | 每个阶段最多模型轮次。 |
| `maxToolCallsPerPhase` | int | `50` | 每个阶段最多工具调用次数。 |
| `maxCandidates` | int | `3` | 单任务最多候选数量。 |
| `network` | bool | `false` | Agent 默认是否允许网络工具。 |

## `correctness`

Correctness 默认策略。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `mode` | string | `hybrid` | 默认验证模式，通常为 `cases`、`oracle`、`stress` 或 `hybrid`。 |
| `requireDeterminism` | bool | `true` | 是否要求输出确定。 |
| `protectedFiles` | list | 见源码 | Agent 不可修改的受保护路径。 |

## `benchmark` / `benchmarks`

`benchmark` 是默认 Benchmark 参数，`benchmarks` 可以按命名规格覆盖。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `method` | string | `process` | 测量方式。当前仅进程级 Benchmark 可用。 |
| `warmup` | int | `2` | Warmup 次数，必须大于等于 0。 |
| `repeats` | int | `5` | 正式采样次数，必须大于 0。 |
| `primaryMetric` | string | `wall_time` | 主指标：`wall_time`、`cpu_time`、`peak_memory` 或 `page_faults`。 |
| `direction` | string | `minimize` | 优化方向，`minimize` 或 `maximize`。 |

## `acceptancePolicy`

接受候选时的硬性门槛。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `requireCorrectness` | bool | `true` | Correctness 未通过时禁止接受。 |
| `minMedianImprovementPercent` | float | `0.0` | 最小 Median 提升百分比。 |
| `maxPeakMemoryRegressionPercent` | float / null | `null` | 允许的最大峰值内存回退百分比。 |
| `maxCompileTimeRegressionPercent` | float / null | `null` | 允许的最大编译时间回退百分比。 |
| `maxVariationPercent` | float / null | `null` | 允许的最大样本波动百分比。 |

## `storage`

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `artifactRetentionDays` | int | `90` | 产物保留天数，必须大于 0。 |

## `policy`

Policy、Approval 和 Sandbox 的组合配置。

### `policy.approval`

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `mode` | string | `non-interactive` | `interactive` 或 `non-interactive`。非交互模式下，`ask` 策略通常会失败关闭。 |

### `policy.sandbox`

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `mode` | string | `process` | 当前支持 `trusted-local` 或 `process`。 |
| `backend` | string | `auto` | `auto`、`native`、`docker`、`wsl2` 或 `disabled`。 |
| `image` | string | `algocode-sandbox:latest` | Docker 后端镜像。 |
| `wslDistro` | string | `Ubuntu` | WSL2 发行版。 |
| `network` | bool | `false` | 是否允许网络。 |
| `timeoutSeconds` | int | `120` | 默认超时秒数。 |
| `maxOutputBytes` | int | `1000000` | 单次输出大小上限。 |
| `memoryMb` | int | `2048` | 内存上限。 |
| `cpus` | float | `2.0` | CPU 配额。 |
| `pidsLimit` | int | `256` | PID 上限。 |
| `readOnlyRoot` | bool | `true` | 根目录只读。 |
| `tmpfsSizeMb` | int | `64` | tmpfs 大小。 |
| `allowedEnv` | list | `PATH` 等 | 允许透传的环境变量。 |

### `policy.rules`

每个规则描述某类工具调用应如何处理。

```yaml
policy:
  rules:
    - action: write_file
      resource: "*.py"
      effect: allow
      layer: project
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `action` | string | 必填 | 工具动作名。 |
| `resource` | string | `*` | 匹配资源模式。 |
| `effect` | `allow` / `ask` / `deny` | `ask` | 决策结果。 |
| `layer` | string | `project` | `hard`、`managed`、`user`、`project` 或 `default`。 |

### `policy.defaultEffect`

没有匹配规则时的默认效果，取值为 `allow`、`ask` 或 `deny`，默认 `ask`。
