# Contract Schema

Project Contract 默认位于：

```text
.algocode/contract.json
```

它由 Contract Discovery 模型生成，用于记录算法之外必须保持的可观察行为。字段为 camelCase。

## 顶层字段

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `schemaVersion` | int | `1` | Schema 版本。 |
| `purpose` | string | 必填 | 项目目的。 |
| `entrypoints` | list[string] | `[]` | 程序入口。 |
| `publicApi` | list[object] | `[]` | 公开 API 清单。 |
| `configuration` | list[object] | `[]` | 配置字段语义。 |
| `stateTransitions` | list[string] | `[]` | 状态转换约束。 |
| `errorContracts` | list[string] | `[]` | 错误行为契约。 |
| `observableOutputs` | object | 见下 | 确定性输出与易变输出。 |
| `invariants` | list[string] | `[]` | 结构不变量。 |
| `performanceGoal` | string | `""` | 性能目标。 |
| `mustNotChange` | list[string] | `[]` | 禁止改变的路径、符号或语义。 |
| `protectedFiles` | list[string] | `[]` | Contract 保护文件。 |
| `unknowns` | list[string] | `[]` | 尚未确定的项。 |
| `testObligations` | list[object] | `[]` | 可执行测试义务。 |
| `confidence` | float | `0.5` | 模型对契约的置信度，范围 0 到 1。 |
| `contractTestSource` | string | `""` | 编译/生成的 Contract Test 源码。 |
| `contractSource` | string | `"model"` | Contract 来源。 |

## `publicApi`

```json
{
  "publicApi": [
    {
      "symbol": "solve",
      "signature": "def solve(values: list[int]) -> int",
      "behavior": "returns the sum of all values"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `symbol` | string | 符号名。 |
| `signature` | string | 签名描述。 |
| `behavior` | string | 可观察行为。 |

## `configuration`

```json
{
  "configuration": [
    {
      "field": "workers",
      "default": "4",
      "variants": ["1", "4", "8"],
      "mustHonor": true
    }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `field` | string | 配置字段名。 |
| `default` | string | 默认值或语义描述。 |
| `variants` | list[string] | 需要保持行为的配置变体。 |
| `mustHonor` | bool | 是否必须遵守。 |

## `observableOutputs`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `deterministic` | list[string] | 应保持确定性的输出。 |
| `volatile` | list[string] | 允许变化的输出。 |

```json
{
  "observableOutputs": {
    "deterministic": ["stdout"],
    "volatile": ["timing", "process_id"]
  }
}
```

## `testObligations`

```json
{
  "testObligations": [
    {
      "target": "sort(items)",
      "assertion": "returns a non-descending sequence with the same elements",
      "kind": "behavior"
    }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `target` | string | 待验证目标，不可为空。 |
| `assertion` | string | 断言描述，不可为空。 |
| `kind` | string | 义务类型，默认 `behavior`。 |

## 示例片段

```json
{
  "schemaVersion": 1,
  "purpose": "solve a deterministic graph shortest-path problem",
  "entrypoints": ["main.py"],
  "publicApi": [],
  "stateTransitions": [],
  "errorContracts": ["invalid input must return a non-zero exit code"],
  "observableOutputs": {
    "deterministic": ["stdout"],
    "volatile": []
  },
  "invariants": ["output length must be non-negative"],
  "confidence": 0.9,
  "contractSource": "model"
}
```
