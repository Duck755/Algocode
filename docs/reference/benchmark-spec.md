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
| `inputs` | list | `[]` | 多输入矩阵，与 `input` 互斥，见下文。 |
| `warmup` | int | `2` | Warmup 次数。 |
| `repeats` | int | `5` | 正式采样次数。 |
| `timeout_seconds` | int | `30` | 单次运行超时。 |
| `metric` | enum | `wall_time` | 主指标。 |
| `direction` | string | `minimize` | `minimize` 或 `maximize`。 |
| `network` | bool | `false` | 是否允许网络。 |
| `max_variation_percent` | float / null | `null` | 样本波动上限。 |

`max_variation_percent` 使用 MAD 鲁棒波动判断 comparison 是否有效。原始标准差波动
仍会写入报告，但单个系统调度尖峰只会产生质量 warning，不会单独否定整组结果。
`algocode init` 生成 process/wall_time 基准时默认写入 `15.0`。

## `metric`
## `inputs`

`inputs` 是可选的输入矩阵，仅在 `scope: stdin` 时生效。每个条目包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 唯一标识，也是样本的 `input_id`。 |
| `size` | int / null | 该输入的问题规模；声明后才会参与增长率拟合。 |
| `input` | string | stdin 内容。 |

声明了 `size` 的输入会分别统计：整体改善取各输入改善的中位数，波动取最差单输入波动。
当至少 3 个输入声明了 `size` 时，Algocode 还会对 `log(时间)` 与 `log(规模)` 做最小二乘
拟合，得到 `growthBaseline`、`growthCandidate`、`growthDelta` 和 `growthPoints`；斜率下降
可以豁免常数提升阈值，详见工作流中的 Decide 阶段。

`algocode init` 在入口程序从 stdin 读入时，会自动写入这族输入；也可手工编辑。

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
带规模输入的示例：

```yaml
schema_version: 1
scope: stdin
run_command:
  - python
  - main.py
inputs:
  - id: n1000
    size: 1000
    input: |
      1000
      5 3 8 1 9
  - id: n2000
    size: 2000
    input: |
      2000
      5 3 8 1 9
```

## 比较键

Algocode 会组合 Spec Hash、Input Hash 和 Environment Hash 生成 Comparison Key。只有相同 Comparison Key 的 Baseline 与 Candidate 结果才会被直接比较，避免把不同命令、输入或环境混在一起。
