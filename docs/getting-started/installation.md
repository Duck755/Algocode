# 安装与环境检查

## 系统要求

- Python 3.11 或更高版本。
- Git。
- 优化 C++ 项目时需要 `g++` 或 `clang++`，并支持 C++17。
- 使用真实模型时需要至少一个 OpenAI-compatible 或 Anthropic Provider。
- Docker 或 WSL2 是可选的更强隔离方式。

## 安装

### 从 PyPI 安装

```bash
python -m pip install algocode-agent
algocode doctor
```

### 从源码开发安装

```powershell
python -m venv .venv
python -m pip install -e ".[dev]"
python -m algocode doctor
```

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m algocode doctor
```

如果 `algocode` 命令不可用，可以改用对应虚拟环境下的 `python -m algocode`。

### 安装 VS Code 扩展

Python 包内置 VS Code 扩展，可执行：

```bash
algocode vscode install
```

或直接运行：

```bash
python -m algocode vscode install
```

也可以使用 VS Code 扩展开发目录手动打包：

```bash
cd extensions/vscode
npm install
npm run compile
npx --yes @vscode/vsce package
```

## 检查环境

```bash
algocode doctor
```

`doctor` 会检查 Python、Git、SQLite、沙箱和可选 C++ 编译器。

## 配置模型 Provider

```bash
algocode api
algocode test
```

`api` 负责选择 Provider、模型并保存 API Key；`test` 发送最小请求验证连接。
