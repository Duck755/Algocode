# 测试

## 环境准备

建议使用虚拟环境安装开发依赖：

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

Windows PowerShell 可以运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## 运行测试

```bash
.venv/bin/python -m pytest
```

Windows：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

运行单个目录或文件：

```bash
.venv/bin/python -m pytest tests/unit
.venv/bin/python -m pytest tests/unit/test_vscode_command.py
```

## 测试类型

| 目录 | 作用 |
| --- | --- |
| `tests/unit` | 单元测试，覆盖配置、领域、服务、命令、Provider、Sandbox 等。 |
| `tests/integration` | 端到端流程、CLI、Report/Apply、Sandbox 等集成测试。 |
| `tests/contract` | 存储和 Projection 的契约测试。 |

## 常用测试策略

### Fake Provider

很多运行阶段测试使用 `DeterministicFakeProvider`，避免真实 API Key。CLI 也可使用：

```bash
algocode optimize --fake-provider
```

### Git 测试夹具

涉及 Baseline、Candidate、Apply 和 Rollback 的测试会创建临时 Git 仓库与 Worktree，验证真实 Git 状态变化。

### 环境依赖

普通测试不要求 Docker。Docker/WSL2 相关测试会在后端不可用时跳过或降级为环境检查。

## 代码检查

```bash
.venv/bin/python -m ruff check .
```

建议提交前同时运行：

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

## CI

GitHub Actions 负责测试、构建和发布。本地开发提交前至少运行目标单元测试和 `ruff`。
