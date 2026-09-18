# 快速开始

## CLI 最快路径

在待优化项目根目录执行：

```bash
algocode init
algocode optimize
```

然后查看证据和状态：

```bash
algocode status
algocode review
algocode diff
```

确认候选后，接受并应用：

```bash
algocode accept <task-id> <candidate-id>
algocode apply
```

需要回滚时：

```bash
algocode rollback
```

## VS Code 最快路径

先安装扩展：

```bash
algocode vscode install
```

然后在 VS Code 中：

1. 打开 C++ 或 Python 项目。
2. 在文件资源管理器或编辑器中右键 `.py`、`.cpp`、`.cc` 或 `.cxx` 文件。
3. 选择 `Algocode -> 优化 Optimize`。
4. 查看原生 Diff 和 Review。
5. 选择 `Apply All` 应用，或之后使用 `Rollback` 回滚。

## 推荐阅读顺序

1. 阅读 [完整工作流](../user-guide/workflow.md)，理解每个阶段在做什么。
2. 遇到不确定状态时使用 [命令手册](../commands/index.md) 查找对应命令。
3. 想理解为什么 Algocode 能保证安全时，阅读 [证据模型](../concepts/evidence-model.md)。
