# Benchmark Schema

The Benchmark specification is normally located at:

```text
.algocode/benchmarks/benchmark.yaml
```

The file is validated by `BenchmarkSpec`; unknown fields are rejected. Fields use snake_case.

## Top-Level Fields

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `schema_version` | int | `1` | Schema version. |
| `scope` | enum | `stdin` | `process` or `stdin`; `function` is not enabled. |
| `run_command` | list[str] | `[]` | Run command. |
| `source_root` | string | `.` | Source directory relative to the worktree. |
| `input` | string | `""` | Benchmark input. |
| `inputs` | list | `[]` | Multi-input matrix, mutually exclusive with `input`. |
| `warmup` | int | `2` | Warmup runs. |
| `repeats` | int | `5` | Measured samples. |
| `timeout_seconds` | int | `30` | Timeout per run. |
| `metric` | enum | `wall_time` | Primary metric. |
| `direction` | string | `minimize` | `minimize` or `maximize`. |
| `network` | bool | `false` | Allow network access. |
| `max_variation_percent` | float / null | `null` | Maximum robust sample variation. |

`max_variation_percent` uses MAD-based robust variation. Raw standard deviation does not participate in validity, Decision, or user-visible warnings. Generated process/wall-time benchmarks default to `15.0`.

## `metric`

| Value | Description |
| --- | --- |
| `wall_time` | Wall-clock time. |
| `cpu_time` | CPU time. |
| `peak_memory` | Peak memory. |
| `page_faults` | Number of page faults. |

## `inputs`

`inputs` is an optional input matrix used with `scope: stdin`.

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Unique ID and sample `input_id`. |
| `size` | int / null | Problem size; declared sizes participate in growth fitting. |
| `input` | string | stdin content. |

Inputs with `size` are summarized separately. Overall improvement is the median of per-input improvements, and variation uses the worst input. With at least three sizes, Algocode fits `log(time)` against `log(size)` and records growth fields.

## Example

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

## Comparison Key

Algocode combines Spec Hash, Input Hash, and Environment Hash into a Comparison Key. Only results with the same key are compared directly, preventing accidental comparison across commands, inputs, or environments.
