# 发布

## 版本号

版本号来自：

```text
src/algocode/__init__.py
```

Python 包和 VS Code 扩展应保持相同版本，例如当前版本为 `0.1.2`。

## 发布前检查

先运行发布验收 Gate：

```bash
algocode gate run
```

Gate 会检查代码结构、测试、关键文件和发布要求。若不需要重跑测试，可临时使用：

```bash
algocode gate run --skip-tests
```

同时运行测试和代码检查：

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

## 构建 Python 包

```bash
.venv/bin/python -m build
```

构建产物：

```text
dist/algocode_agent-<version>.tar.gz
dist/algocode_agent-<version>-py3-none-any.whl
```

本地安装验证：

```bash
.venv/bin/python -m pip install dist/algocode_agent-<version>-py3-none-any.whl
algocode doctor
```

## 发布 Python 包

GitHub Actions 会在推送版本 Tag 后构建并发布：

```bash
git tag v0.1.2
git push origin v0.1.2
```

发布后用户可安装：

```bash
python -m pip install algocode-agent
```

## 构建 VS Code 扩展

```bash
cd extensions/vscode
npm install
npm run compile
npx --yes @vscode/vsce package
```

生成的 VSIX 会内置到 Python 包资源中，并可通过：

```bash
algocode vscode install
```

安装到本地 VS Code。

## 发布清单

1. 更新 `src/algocode/__init__.py`。
2. 更新 `extensions/vscode/package.json`。
3. 更新文档中的版本引用。
4. 运行测试、`ruff` 和 `algocode gate run`。
5. 构建 Python 包与 VSIX。
6. 推送版本 Tag，由 CI 发布。
