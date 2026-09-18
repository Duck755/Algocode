# 策略、审批与沙箱

## Policy

Policy Engine 决定工具调用是 `allow`、`ask` 还是 `deny`。规则按 Hard、Managed、User、Project、Default 层级计算。

## Approval

当策略结果为 `ask` 时，需要 Approval Provider 返回批准决策。非交互模式下，需要批准的调用会失败。

## Sandbox

沙箱用于执行构建、测试和 Benchmark。支持 Native、Docker 和 WSL2，并限制环境变量、超时、内存、输出大小和网络访问。

## 保护文件

受保护文件不能被 Agent 修改，例如测试目录、Oracle、Benchmark 配置和契约文件。
