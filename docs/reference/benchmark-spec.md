# Benchmark Schema

Benchmark 规格默认位于：

```text
.algocode/benchmarks/benchmark.yaml
```

规格由 `BenchmarkSpec` 校验，未知字段会报错。字段使用 snake_case。

## 顶层字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | int | `1` | Schema 版本。 |
| `scope` | enum | `stdin` | 当前支持 `process` 或 `stdin`；`function` 尚未启用。 |
| `run_command` | list[str] | `[]` | 运行命令。 |
| `source_root` | string | `.` | 相对 Worktree 的源码目录。 |
| `input` | string | `""` | Benchmark 输入。 |
| `warmup` | int | `2` | Warmup 次数。 |
| `repeats` | int | `5` | 正式采样次数。 |
| `timeout_seconds` | int | `30` | 单次运行超时。 |
| `metric` | enum | `wall_time` | 主指标。 |
| `direction` | string | `minimize` | `minimize` 或 `maximize`。 |
| `network` | bool | `false` | 是否允许网络。 |
| `max_variation_percent` | float / null | `null` | 样本波动上限。 |

## `metric`

| 值 | 说明 |
| --- | --- |
| `wall_time` | 墙上时钟时间。 |
| `cpu_time` | CPU 时间。 |
| `peak_memory` | 峰值内存。 |
| `page_faults` | 页错误数量。 |

## 示例

```yaml
schema_version: 1
scope: process
run_command:
  - python
  - main.py
input: ""
warmup: 3
repeats: 7
timeout_seconds: 30
metric: wall_time
direction: minimize
max_variation_percent: 10.0
```

## 比较键

Algocode 会组合 Spec Hash、Input Hash 和 Environment Hash 生成 Comparison Key。只有相同 Comparison Key 的 Baseline 与 Candidate 结果才会被直接比较，避免把不同命令、输入或环境混在一起。
