# 简略工作流

这里是 Algocode 的最小使用链路。先看整体流程，再看 [完整工作流](workflow.md) 中的阶段细节、门控和失败处理。

```mermaid
flowchart TD
    Start(["algocode init"]) --> Contract["生成 Project Contract"]
    Contract --> Baseline["创建 Baseline 与初始 Task"]
    Baseline --> Optimize(["algocode optimize"])
    Optimize --> Analyze["Analyze 分析代码与约束"]
    Analyze --> Plan["Plan 生成优化计划"]
    Plan --> Generate["Generate Candidate 创建 Worktree"]
    Generate --> Implement["Implement 修改候选代码"]
    Implement --> Verify{"Correctness / Contract 通过？"}
    Verify -- 否 --> Repair["修复候选或创建新候选"]
    Repair --> Implement
    Verify -- 是 --> Benchmark["Benchmark 运行候选性能测试"]
    Benchmark --> Compare{"Benchmark 有效且可比较？"}
    Compare -- 否 --> Retry["检查状态或重试 optimize"]
    Retry --> Optimize
    Compare -- 是 --> Decide{"接受策略通过？"}
    Decide -- 否 --> Review["Review 后拒绝或重新规划"]
    Review --> Retry
    Decide -- 是 --> Accept["accept 记录决策"]
    Accept --> Apply["apply 写入用户工作区"]
    Apply --> Report["report 生成报告"]
    Apply -. "发现问题" .-> Rollback["rollback 回滚"]
```

## 四步理解

1. **初始化**：`algocode init` 检测项目、生成 Contract、创建 Task，并捕获 Baseline。
2. **优化**：`algocode optimize` 分析项目、制定计划，并在隔离候选工作区中实现优化。
3. **验证**：候选必须先通过 Correctness 和 Contract，然后才运行 Benchmark。
4. **落地**：用户查看 `status`、`review`、`diff`，确认后执行 `accept` 和 `apply`；需要时执行 `rollback`。

## 最常用命令

```bash
algocode init
algocode optimize
algocode status
algocode review
algocode diff
algocode accept <task-id> <candidate-id>
algocode apply
algocode rollback
```
