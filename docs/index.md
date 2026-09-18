# Algocode 文档

Algocode 是一个面向 C++ / Python 的可验证算法优化 Agent。它会在隔离的 Git Worktree 中生成候选实现，并通过 Correctness、Contract 和 Benchmark 三类证据验证结果，只有用户显式执行 `accept` 和 `apply` 后才会修改原项目。

它同时提供 CLI 和 VS Code 扩展两个入口，适合终端自动化和编辑器内操作。

本站按使用路径组织文档：

- [快速开始](getting-started/quickstart.md)：先跑通最小流程。
- [命令手册](commands/index.md)：查看每个命令的用途和使用方式。
- [完整工作流](user-guide/workflow.md)：理解从初始化到应用回滚的完整链路。
- [核心概念](concepts/architecture.md)：理解 Algocode 的架构与验证体系。
- [参考文档](reference/cli.md)：查询 CLI、配置、Schema 和项目目录。
- [开发与维护](development/code-structure.md)：了解如何贡献代码、测试和发布。
