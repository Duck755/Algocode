# 配置

Algocode 的配置使用分层覆盖机制。最终生效顺序由低到高为：

1. 内置默认值。
2. 用户全局配置。
3. 项目配置 `.algocode/config.yaml`。
4. 本地项目覆盖 `.algocode/config.local.yaml`。
5. 环境变量 `ALGOCODE_*`。
6. 显式 CLI 参数。

## 常用配置

| 区域 | 作用 |
| --- | --- |
| `project` | 项目语言和源码根目录。 |
| `providers` | 模型服务商连接信息。 |
| `models` | 模型别名和上下文窗口。 |
| `defaults` | 默认 Provider 和模型。 |
| `runtime` | 每阶段步数、工具调用数和候选数限制。 |
| `correctness` | 正确性验证与受保护文件。 |
| `benchmark` | Benchmark 默认参数。 |
| `acceptancePolicy` | 接受候选时的性能门槛。 |
| `policy` | 工具策略、审批和沙箱设置。 |

## 最小项目配置

`.algocode/config.yaml`：

```yaml
project:
  language: auto
  sourceRoot: .

runtime:
  maxStepsPerPhase: 30
  maxToolCallsPerPhase: 50
  maxCandidates: 3
  maxRefinements: 2

acceptancePolicy:
  requireCorrectness: true
  requireStatisticallySignificant: true
  minMedianImprovementPercent: 2.0
  maxVariationPercent: 15.0
```

本地覆盖 `.algocode/config.local.yaml` 适合保存个人环境差异：

```yaml
policy:
  sandbox:
    backend: native
    timeoutSeconds: 180
```

完整字段说明见 [配置参考](../reference/config.md)。
