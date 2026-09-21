# Configuration

Algocode uses layered configuration. The effective precedence, from lowest to highest, is:

1. Built-in defaults.
2. User-global configuration.
3. Project configuration at `.algocode/config.yaml`.
4. Local project overrides at `.algocode/config.local.yaml`.
5. `ALGOCODE_*` environment variables.
6. Explicit CLI options.

## Common Areas

| Area | Purpose |
| --- | --- |
| `project` | Project language and source root. |
| `providers` | Model provider connection details. |
| `models` | Model aliases and context windows. |
| `defaults` | Default provider and model. |
| `runtime` | Per-phase steps, tool-call limits, and candidate limits. |
| `correctness` | Correctness validation and protected files. |
| `benchmark` | Default benchmark parameters. |
| `acceptancePolicy` | Performance thresholds used to accept a candidate. |
| `policy` | Tool policy, approval, and sandbox settings. |

## Minimal Project Configuration

`.algocode/config.yaml`:

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

Local overrides are useful for machine-specific settings:

```yaml
policy:
  sandbox:
    backend: native
    timeoutSeconds: 180
```

See the [Configuration Reference](../reference/config.md) for all fields.
