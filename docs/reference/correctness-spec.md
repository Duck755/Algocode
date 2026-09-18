# Correctness Schema

Correctness 规格默认位于：

```text
.algocode/oracle/correctness.yaml
```

规格由 `CorrectnessSpec` 校验，未知字段会报错。字段使用 snake_case。

## 顶层字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `schema_version` | int | `1` | Schema 版本，必须大于等于 1。 |
| `mode` | enum | `cases` | `cases`、`oracle`、`stress` 或 `hybrid`。 |
| `run_command` | list[str] | `[]` | 候选运行命令。 |
| `source_root` | string | `.` | 相对 Worktree 的源码目录。 |
| `oracle_command` | list[str] | `[]` | Oracle 命令。 |
| `generator_command` | list[str] | `[]` | Stress 数据生成命令。 |
| `checker_command` | list[str] | `[]` | 自定义 Checker 命令。 |
| `cases` | list | `[]` | `cases` 或 `hybrid` 模式下的测试用例。 |
| `iterations` | int | `10` | Stress 迭代次数。 |
| `seed` | int | `0` | Stress 随机种子。 |
| `timeout_seconds` | int | `10` | 每个测试的默认超时秒数。 |
| `comparison` | enum | `exact` | 输出比较方式。 |
| `float_tolerance` | float | `1e-9` | 浮点比较容差。 |
| `require_determinism` | bool | `true` | 是否要求确定性输出。 |
| `visible_to_agent` | bool | `true` | 规格是否对 Agent 可见。 |
| `protected_files` | list[str] | 内置默认 | 受保护路径。 |

## `mode`

| 值 | 约束 | 说明 |
| --- | --- | --- |
| `cases` | 至少一个 `cases`；若用例没有 `expected_output`，必须提供 `oracle_command` | 固定用例验证。 |
| `oracle` | 必须提供 `oracle_command` | 每个输入交由 Oracle 判断。 |
| `stress` | 必须同时提供 `generator_command` 和 `oracle_command` | 随机压力测试。 |
| `hybrid` | 至少一个 `cases` 或 `oracle_command` | 固定用例与 Oracle 混合。 |

## `comparison`

| 值 | 说明 |
| --- | --- |
| `exact` | 精确比较输出。 |
| `line-trim` | 逐行去除首尾空白后比较。 |
| `token-normalized` | Token 归一化比较。 |
| `float-absolute` | 浮点绝对误差比较。 |
| `float-relative` | 浮点相对误差比较。 |
| `checker-command` | 使用 `checker_command` 判断。 |

使用 `checker-command` 时，必须提供 `checker_command`。

## `cases` 用例

```yaml
cases:
  - id: sample_1
    input: |
      3
      1 2 3
    expected_output: |
      6
    expected_exit_code: 0
    args: []
    timeout_seconds: 2
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 必填 | 用例 ID。 |
| `input` | string | `""` | stdin。 |
| `expected_output` | string / null | `null` | 期望 stdout。 |
| `expected_exit_code` | int | `0` | 期望退出码。 |
| `args` | list[str] | `[]` | 附加参数。 |
| `timeout_seconds` | int / null | `null` | 单用例超时；空则继承顶层值。 |

## 最小示例

```yaml
schema_version: 1
mode: cases
run_command:
  - python
  - main.py
comparison: exact
timeout_seconds: 5
cases:
  - id: basic
    input: "2\n3\n"
    expected_output: "5\n"
```

## 常见失败

- `cases` 模式下没有用例。
- `stress` 模式缺少 `generator_command` 或 `oracle_command`。
- `checker-command` 模式缺少 `checker_command`。
- 用例没有期望输出，同时没有 Oracle 命令。
