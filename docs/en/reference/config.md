# Configuration Reference

Algocode merges multiple YAML files. Field names accept both camelCase and snake_case, but camelCase is recommended for consistency with the built-in models.

## Loading Order

The effective configuration is merged from lowest to highest precedence:

1. Built-in defaults.
2. User-global configuration.
3. Project configuration at `.algocode/config.yaml`.
4. Local project overrides at `.algocode/config.local.yaml`.
5. `ALGOCODE_*` environment variables.
6. Explicit CLI options.

The global configuration normally lives in the Algocode data directory:

```text
%LOCALAPPDATA%\algocode\config.yaml   # Windows
~/.local/share/algocode/config.yaml   # Linux
~/Library/Application Support/algocode/config.yaml  # macOS
```

## Minimal Example

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

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `language` | `auto` / `cpp` / `python` | `auto` | Primary language. When both Python and C++ are present, `auto` prefers C++. |
| `sourceRoot` | path | `.` | Source directory relative to the repository root. |

## `providers`

A map of Provider Keys to provider configuration.

```yaml
providers:
  openai:
    type: openai-compatible
    baseUrl: https://api.openai.com/v1
    credentialRef: local://openai
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | string | `openai-compatible` | Currently supports `openai-compatible` or `anthropic`. |
| `baseUrl` | string | empty | Provider base URL. |
| `apiKeyEnv` | string | empty | Environment variable that contains the key. Do not store the key directly. |
| `credentialRef` | string | empty | Credential reference using `env://<NAME>` or `local://<NAME>`. |

## `models`

A map of Model Keys to model configuration.

```yaml
models:
  openai/gpt-5-mini:
    provider: openai
    model: gpt-5-mini
    contextWindow: 128000
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `provider` | string | `default` | Provider Key. |
| `model` | string | required | Provider model ID. |
| `contextWindow` | int | `128000` | Context window size, greater than 0. |

## `defaults`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `provider` | string | `default` | Default Provider Key. |
| `model` | string | `default` | Default Model Key. |

## `runtime`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `maxStepsPerPhase` | int | `30` | Maximum model turns per phase. |
| `maxToolCallsPerPhase` | int | `50` | Maximum tool calls per phase. |
| `maxCandidates` | int | `3` | Maximum candidates per task. |
| `network` | bool | `false` | Whether network tools are allowed by default. |

## `correctness`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `mode` | string | `hybrid` | Default validation mode: usually `cases`, `oracle`, `stress`, or `hybrid`. |
| `requireDeterminism` | bool | `true` | Require deterministic output. |
| `protectedFiles` | list | see source | Paths the Agent cannot modify. |

## `benchmark` / `benchmarks`

`benchmark` defines defaults; `benchmarks` can override named specifications.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `method` | string | `process` | Measurement method. Only process-level benchmarks are currently enabled. |
| `warmup` | int | `2` | Warmup runs, greater than or equal to 0. |
| `repeats` | int | `5` | Measured samples, greater than 0. |
| `primaryMetric` | string | `wall_time` | `wall_time`, `cpu_time`, `peak_memory`, or `page_faults`. |
| `direction` | string | `minimize` | `minimize` or `maximize`. |

## `acceptancePolicy`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `requireCorrectness` | bool | `true` | Reject acceptance if Correctness fails. |
| `requireStatisticallySignificant` | bool | `true` | Require paired statistical significance and a confidence interval excluding zero. |
| `minMedianImprovementPercent` | float | `2.0` | Minimum paired median improvement percentage. |
| `maxPeakMemoryRegressionPercent` | float / null | `null` | Maximum allowed peak-memory regression percentage. |
| `maxCompileTimeRegressionPercent` | float / null | `null` | Maximum allowed compile-time regression percentage. |
| `maxVariationPercent` | float / null | `15.0` | Maximum MAD-based robust variation percentage. |

## `storage`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `artifactRetentionDays` | int | `90` | Artifact retention period in days, greater than 0. |

## `policy`

### `policy.approval`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `mode` | string | `non-interactive` | `interactive` or `non-interactive`. Calls that require approval fail closed in non-interactive mode. |

### `policy.sandbox`

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `mode` | string | `process` | `trusted-local` or `process`. |
| `backend` | string | `auto` | `auto`, `native`, `docker`, `wsl2`, or `disabled`. |
| `image` | string | `algocode-sandbox:latest` | Docker backend image. |
| `wslDistro` | string | `Ubuntu` | WSL2 distribution. |
| `network` | bool | `false` | Allow network access. |
| `timeoutSeconds` | int | `120` | Default timeout in seconds. |
| `maxOutputBytes` | int | `1000000` | Maximum captured output size. |
| `memoryMb` | int | `2048` | Memory limit. |
| `cpus` | float | `2.0` | CPU quota. |
| `pidsLimit` | int | `256` | PID limit. |
| `readOnlyRoot` | bool | `true` | Mount the root filesystem read-only. |
| `tmpfsSizeMb` | int | `64` | tmpfs size. |
| `allowedEnv` | list | `PATH`, etc. | Environment variables allowed through the sandbox. |

### `policy.rules`

```yaml
policy:
  rules:
    - action: write_file
      resource: "*.py"
      effect: allow
      layer: project
```

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `action` | string | required | Tool action name. |
| `resource` | string | `*` | Resource pattern. |
| `effect` | `allow` / `ask` / `deny` | `ask` | Decision effect. |
| `layer` | string | `project` | `hard`, `managed`, `user`, `project`, or `default`. |

### `policy.defaultEffect`

The default effect when no rule matches. Values are `allow`, `ask`, or `deny`; the default is `ask`.
