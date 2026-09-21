# Correctness Schema

The Correctness specification is normally located at:

```text
.algocode/oracle/correctness.yaml
```

The file is validated by `CorrectnessSpec`; unknown fields are rejected. Fields use snake_case.

## Top-Level Fields

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `schema_version` | int | `1` | Schema version, at least 1. |
| `mode` | enum | `cases` | `cases`, `oracle`, `stress`, or `hybrid`. |
| `run_command` | list[str] | `[]` | Candidate run command. |
| `source_root` | string | `.` | Source directory relative to the worktree. |
| `oracle_command` | list[str] | `[]` | Oracle command. |
| `generator_command` | list[str] | `[]` | Stress input generator command. |
| `checker_command` | list[str] | `[]` | Custom checker command. |
| `cases` | list | `[]` | Cases used by `cases` or `hybrid`. |
| `iterations` | int | `10` | Stress iterations. |
| `seed` | int | `0` | Stress seed. |
| `timeout_seconds` | int | `10` | Default timeout per test. |
| `comparison` | enum | `exact` | Output comparison mode. |
| `float_tolerance` | float | `1e-9` | Floating-point tolerance. |
| `require_determinism` | bool | `true` | Require deterministic output. |
| `visible_to_agent` | bool | `true` | Whether the specification is visible to the Agent. |
| `protected_files` | list[str] | built-in defaults | Protected paths. |

## `mode`

| Value | Constraint | Description |
| --- | --- | --- |
| `cases` | At least one case; if a case has no `expected_output`, `oracle_command` is required. | Fixed-case validation. |
| `oracle` | `oracle_command` is required. | Every input is validated by the Oracle. |
| `stress` | Both `generator_command` and `oracle_command` are required. | Randomized stress testing. |
| `hybrid` | At least one case or `oracle_command`. | Fixed cases plus Oracle checks. |

## `comparison`

| Value | Description |
| --- | --- |
| `exact` | Exact output comparison. |
| `line-trim` | Trim leading and trailing whitespace per line. |
| `token-normalized` | Compare normalized tokens. |
| `float-absolute` | Absolute floating-point tolerance. |
| `float-relative` | Relative floating-point tolerance. |
| `checker-command` | Use `checker_command`. |

`checker-command` requires `checker_command`.

## Cases

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

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `id` | string | required | Case ID. |
| `input` | string | `""` | stdin. |
| `expected_output` | string / null | `null` | Expected stdout. |
| `expected_exit_code` | int | `0` | Expected exit code. |
| `args` | list[str] | `[]` | Extra arguments. |
| `timeout_seconds` | int / null | `null` | Per-case timeout; inherits the top-level value when empty. |

## Minimal Example

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

## Common Validation Failures

- `cases` mode has no cases.
- `stress` mode is missing `generator_command` or `oracle_command`.
- `checker-command` mode is missing `checker_command`.
- A case has no expected output and no Oracle command.
