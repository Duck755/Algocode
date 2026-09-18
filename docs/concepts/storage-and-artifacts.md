# 存储与产物

Algocode 使用 SQLite 保存事件和投影，并使用文件 Artifact Store 保存大体积内容。

## Event Store

- 所有关键状态通过事件写入。
- 每个聚合都有单调递增的 `seq`。
- 写入时使用预期序号做并发控制。
- Projection 在同一事务中更新。

## Artifact Store

Artifact 用于保存：

- Correctness 规格和结果。
- Benchmark 规格、样本和比较结果。
- Context Snapshot。
- 模型日志。
- 优化记录。
- Candidate Patch。

Artifact 使用内容寻址，写入时会记录 digest 和元数据。SQLite 中的引用只保存 `ArtifactRef`，实际内容存放在文件系统中。

## 项目内目录

项目状态主要位于 `.algocode/`，其中 `cache/` 不应手工编辑。

完整目录说明见 [项目目录](../reference/project-layout.md)。

## 状态推导

`algocode status` 会读取 Task 投影和 Event Store。当前阶段、轮次、工具数量、active tool、last tool 和阶段耗时都由事件序列推导，而不是维护另一套易失状态。
