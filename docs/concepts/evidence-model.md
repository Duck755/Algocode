# 证据模型

Algocode 不依赖模型的自我评价，而是把优化结果拆成三类可持久化证据。

## Correctness

验证候选是否复现基线行为，支持 `cases`、`oracle`、`stress` 和 `hybrid`。

它主要回答：

- 输出是否一致。
- 退出码是否一致。
- 边界、错误、状态变化是否保持一致。

## Contract

保护算法之外的行为，例如公开 API、配置语义、返回顺序、异常和结构不变量。

它主要回答：

- 优化是否改变了用户可观察契约。
- 是否删除了必要的检查。
- 是否改变了顺序、状态或错误行为。

## Benchmark

在受控环境下测量性能，记录 Warmup、重复样本、Median、原始波动、MAD 鲁棒波动、置信区间和环境 Hash。

它主要回答：

- 候选是否真的更快。
- 提升是否稳定。
- 测量是否可信。

Benchmark 会按同一 input 和 repeat 配对 Baseline/Candidate，使用配对置换检验和 bootstrap 置信区间。原始标准差波动只作为诊断；有效性和质量判断优先使用 MAD 鲁棒波动，避免单个系统调度尖峰否定整组结果。

当至少 3 个输入声明了 `size` 时，还会拟合 `growthBaseline`、`growthCandidate` 和 `growthDelta`。增长指数明显下降可以作为算法级改进证据。

## 证据顺序

Correctness 必须通过，Contract 必须通过，随后 Benchmark 才具有进入决策阶段的资格。
