# 常见问题

## `optimize` 状态不是 `completed`

优化流程可能因为模型输出、验证失败、步骤预算或 Gate 被阻断。优先查看：

- `.algocode/cache/model-logs/`：模型请求和错误。
- `.algocode/cache/optimization-records/`：每次优化尝试的记录。
- `.algocode/current-task.json`：当前任务状态。

必要时可以重试，或运行 `algocode status` 查看推荐命令。

## `init` 失败

常见原因包括：

- 项目不是 Git 仓库，且自动初始化失败。
- 代码无法编译或运行。
- 没有可识别的 Python 或 C++ 入口。
- Provider 未配置或连接失败。

## `apply` 失败

常见原因包括：

- 候选尚未通过 `accept`。
- 用户工作区在优化期间发生了变化。
- 当前工作区状态与候选基线快照不一致。

## 其他证据位置

- Correctness：`.algocode/cache/artifacts/`。
- Benchmark：`.algocode/cache/artifacts/`。
- Contract：`.algocode/contract.json`。
