# MarkItDown 阅读覆盖台账

> 对应设计文档：`02-markitdown-design.md`  
> 分析日期：2026-09-15  
> 分析对象：`C:\Users\Administrator\Desktop\markitdown-main\markitdown-main`  
> 快照版本：`markitdown 0.1.8b1`

## 1. 覆盖结论

| 类别 | 文件数 | 行数或数量 | 覆盖方式 |
|---|---:|---:|---|
| 第一方 Python 源码 | 52 | 8,803 行 | 全部逐文件全文阅读 |
| Python 测试源码 | 44 | 10,632 行 | 全部逐文件检查，重点测试全文阅读 |
| `test_*` 函数 | 包含在测试文件内 | 386 | 通过源码和测试结构统计 |
| 主包 fixture | 31 | 二进制和文本样例 | 检查格式、用途和测试向量 |
| `pyproject.toml` | 4 | 4 个包 | 全文阅读 |
| README | 5 | 根 README 和 4 个包 README | 全文阅读 |
| Dockerfile | 2 | 主 CLI 和 MCP | 全文阅读 |
| 测试数据二进制 | 大量 | PDF、DOCX、PPTX、XLSX、MSG、图片、音频等 | 不解析二进制内容，按测试用途检查 |

## 2. `markitdown` 主包源码

| 文件 | 行数 | 阅读状态 | 主要职责 |
|---|---:|---|---|
| `src/markitdown/__about__.py` | 4 | 已全文阅读 | 版本号 |
| `src/markitdown/__init__.py` | 34 | 已全文阅读 | 公共导出 |
| `src/markitdown/__main__.py` | 286 | 已全文阅读 | CLI |
| `src/markitdown/_base_converter.py` | 105 | 已全文阅读 | Converter 和 Result 基类 |
| `src/markitdown/_exceptions.py` | 82 | 已全文阅读 | 异常模型 |
| `src/markitdown/_markitdown.py` | 851 | 已全文阅读 | 核心调度、流识别、转换注册 |
| `src/markitdown/_stream_info.py` | 32 | 已全文阅读 | StreamInfo |
| `src/markitdown/_uri_utils.py` | 75 | 已全文阅读 | file URI 和 data URI |
| `src/markitdown/converter_utils/__init__.py` | 0 | 已检查 | 空包 |
| `src/markitdown/converter_utils/docx/__init__.py` | 0 | 已检查 | 空包 |
| `src/markitdown/converter_utils/docx/pre_process.py` | 290 | 已全文阅读 | DOCX 预处理 |
| `src/markitdown/converter_utils/docx/math/__init__.py` | 0 | 已检查 | 空包 |
| `src/markitdown/converter_utils/docx/math/latex_dict.py` | 291 | 已全文阅读 | OMML 到 LaTeX 映射 |
| `src/markitdown/converter_utils/docx/math/omml.py` | 415 | 已全文阅读 | OMML 转 LaTeX |
| `src/markitdown/converters/__init__.py` | 54 | 已全文阅读 | 内置转换器导出 |
| `src/markitdown/converters/_audio_converter.py` | 101 | 已全文阅读 | 音频转换 |
| `src/markitdown/converters/_bing_serp_converter.py` | 120 | 已全文阅读 | Bing 搜索结果 |
| `src/markitdown/converters/_csv_converter.py` | 133 | 已全文阅读 | CSV 表格 |
| `src/markitdown/converters/_cu_converter.py` | 570 | 已全文阅读 | Azure Content Understanding |
| `src/markitdown/converters/_doc_intel_converter.py` | 258 | 已全文阅读 | Azure Document Intelligence |
| `src/markitdown/converters/_docx_converter.py` | 111 | 已全文阅读 | DOCX 转换 |
| `src/markitdown/converters/_epub_converter.py` | 185 | 已全文阅读 | EPUB 转换 |
| `src/markitdown/converters/_exiftool.py` | 57 | 已全文阅读 | ExifTool 调用 |
| `src/markitdown/converters/_html_converter.py` | 110 | 已全文阅读 | HTML 转换 |
| `src/markitdown/converters/_image_converter.py` | 138 | 已全文阅读 | 图片元数据和 LLM caption |
| `src/markitdown/converters/_ipynb_converter.py` | 103 | 已全文阅读 | Jupyter Notebook |
| `src/markitdown/converters/_llm_caption.py` | 50 | 已全文阅读 | 多模态 caption |
| `src/markitdown/converters/_markdownify.py` | 179 | 已全文阅读 | 自定义 HTML 到 Markdown |
| `src/markitdown/converters/_outlook_msg_converter.py` | 349 | 已全文阅读 | Outlook MSG |
| `src/markitdown/converters/_pdf_converter.py` | 589 | 已全文阅读 | PDF、表格、内存优化 |
| `src/markitdown/converters/_plain_text_converter.py` | 66 | 已全文阅读 | 文本转换 |
| `src/markitdown/converters/_pptx_converter.py` | 353 | 已全文阅读 | PowerPoint |
| `src/markitdown/converters/_rss_converter.py` | 488 | 已全文阅读 | RSS/Atom |
| `src/markitdown/converters/_transcribe_audio.py` | 58 | 已全文阅读 | 音频转写 |
| `src/markitdown/converters/_wikipedia_converter.py` | 91 | 已全文阅读 | Wikipedia |
| `src/markitdown/converters/_xlsx_converter.py` | 208 | 已全文阅读 | XLSX/XLS |
| `src/markitdown/converters/_youtube_converter.py` | 256 | 已全文阅读 | YouTube |
| `src/markitdown/converters/_zip_converter.py` | 130 | 已全文阅读 | ZIP 递归转换 |

## 3. `markitdown-mcp` 源码

| 文件 | 行数 | 阅读状态 | 主要职责 |
|---|---:|---|---|
| `src/markitdown_mcp/__about__.py` | 4 | 已全文阅读 | 版本 |
| `src/markitdown_mcp/__init__.py` | 9 | 已全文阅读 | 包导出 |
| `src/markitdown_mcp/__main__.py` | 139 | 已全文阅读 | MCP tool、stdio、HTTP、SSE |

## 4. `markitdown-ocr` 源码

| 文件 | 行数 | 阅读状态 | 主要职责 |
|---|---:|---|---|
| `src/markitdown_ocr/__about__.py` | 4 | 已全文阅读 | 版本 |
| `src/markitdown_ocr/__init__.py` | 31 | 已全文阅读 | 插件导出 |
| `src/markitdown_ocr/_docx_converter_with_ocr.py` | 228 | 已全文阅读 | DOCX OCR |
| `src/markitdown_ocr/_ocr_service.py` | 110 | 已全文阅读 | LLM Vision OCR 服务 |
| `src/markitdown_ocr/_pdf_converter_with_ocr.py` | 422 | 已全文阅读 | PDF OCR |
| `src/markitdown_ocr/_plugin.py` | 68 | 已全文阅读 | 插件注册 |
| `src/markitdown_ocr/_pptx_converter_with_ocr.py` | 253 | 已全文阅读 | PPTX OCR |
| `src/markitdown_ocr/_xlsx_converter_with_ocr.py` | 225 | 已全文阅读 | XLSX OCR |

## 5. `markitdown-sample-plugin` 源码

| 文件 | 行数 | 阅读状态 | 主要职责 |
|---|---:|---|---|
| `src/markitdown_sample_plugin/__about__.py` | 4 | 已全文阅读 | 版本 |
| `src/markitdown_sample_plugin/__init__.py` | 13 | 已全文阅读 | 插件导出 |
| `src/markitdown_sample_plugin/_plugin.py` | 71 | 已全文阅读 | RTF converter 示例 |

## 6. 主包测试文件

| 文件 | 行数 | 覆盖方式 |
|---|---:|---|
| `_test_vectors.py` | 279 | 全文阅读 |
| `test_charset_sample.py` | 120 | 全文阅读 |
| `test_cli_misc.py` | 62 | 全文阅读 |
| `test_cli_vectors.py` | 222 | 全文阅读 |
| `test_csv_blank_runs.py` | 35 | 全文阅读 |
| `test_csv_line_endings.py` | 53 | 全文阅读 |
| `test_cu_converter.py` | 1035 | 测试类、参数化和关键断言检查 |
| `test_docintel_html.py` | 57 | 测试函数和断言检查 |
| `test_docx_math.py` | 59 | 测试函数和断言检查 |
| `test_docx_math_accents.py` | 80 | 测试函数和断言检查 |
| `test_docx_math_symbols.py` | 102 | 测试函数和断言检查 |
| `test_docx_omml.py` | 48 | 测试函数和断言检查 |
| `test_docx_styles.py` | 152 | 测试函数和断言检查 |
| `test_epub_converter.py` | 115 | 全文阅读 |
| `test_file_paths.py` | 138 | 全文阅读 |
| `test_html_converter.py` | 153 | 全文阅读 |
| `test_image_converter.py` | 137 | 全文阅读 |
| `test_module_misc.py` | 1929 | 测试函数和关键场景检查 |
| `test_module_vectors.py` | 267 | 全文阅读 |
| `test_outlook_msg_ansi.py` | 394 | 测试函数和编码场景检查 |
| `test_pdf_masterformat.py` | 171 | 测试类和场景检查 |
| `test_pdf_memory.py` | 364 | 核心测试全文阅读 |
| `test_pdf_tables.py` | 1198 | 测试类和关键结构断言检查 |
| `test_pptx_empty_title.py` | 67 | 测试函数和断言检查 |
| `test_pptx_none_text.py` | 66 | 测试函数和断言检查 |
| `test_pptx_notes.py` | 58 | 测试函数和断言检查 |
| `test_pptx_svg.py` | 113 | 测试函数和断言检查 |
| `test_rss_converter.py` | 690 | 测试函数和断言检查 |
| `test_rss_titles.py` | 305 | 测试函数和断言检查 |
| `test_undetectable_charset.py` | 74 | 全文阅读 |
| `test_youtube_converter.py` | 168 | 全文阅读 |
| `test_zip_kwargs.py` | 136 | 全文阅读 |
| `tests/__init__.py` | 3 | 已检查 |

## 7. MCP 和插件测试

| 文件 | 行数 | 覆盖方式 |
|---|---:|---|
| `packages/markitdown-mcp/tests/test_http_transports.py` | 158 | 全文阅读 |
| `packages/markitdown-mcp/tests/test_stdio_protocols.py` | 227 | 全文阅读 |
| `packages/markitdown-mcp/tests/test_tool_errors.py` | 223 | 全文阅读 |
| `packages/markitdown-ocr/tests/test_docx_converter.py` | 428 | 全文阅读 |
| `packages/markitdown-ocr/tests/test_pdf_converter.py` | 247 | 全文阅读 |
| `packages/markitdown-ocr/tests/test_pptx_converter.py` | 201 | 全文阅读 |
| `packages/markitdown-ocr/tests/test_xlsx_converter.py` | 249 | 全文阅读 |
| `packages/markitdown-sample-plugin/tests/test_sample_plugin.py` | 43 | 全文阅读 |

## 8. 配置、构建和部署文件

| 文件 | 行数 | 阅读状态 | 说明 |
|---|---:|---|---|
| 根目录 `README.md` | 408 | 已全文阅读 | 总文档 |
| `packages/markitdown/README.md` | 55 | 已全文阅读 | 主包说明 |
| `packages/markitdown-mcp/README.md` | 142 | 已全文阅读 | MCP 说明 |
| `packages/markitdown-ocr/README.md` | 200 | 已全文阅读 | OCR 插件说明 |
| `packages/markitdown-sample-plugin/README.md` | 111 | 已全文阅读 | 插件教程 |
| `packages/markitdown/pyproject.toml` | 115 | 已全文阅读 | 主包依赖、CLI、Hatch |
| `packages/markitdown-mcp/pyproject.toml` | 70 | 已全文阅读 | MCP 包 |
| `packages/markitdown-ocr/pyproject.toml` | 57 | 已全文阅读 | OCR 插件和 entry point |
| `packages/markitdown-sample-plugin/pyproject.toml` | 70 | 已全文阅读 | 示例插件和 entry point |
| 根目录 `Dockerfile` | 34 | 已全文阅读 | CLI 镜像 |
| `packages/markitdown-mcp/Dockerfile` | 27 | 已全文阅读 | MCP 镜像 |
| `.pre-commit-config.yaml` | 5 | 已全文阅读 | Black pre-commit |
| `LICENSE` | 21 | 已检查 | MIT |
| `SECURITY.md` | 41 | 已检查 | 安全策略 |
| `CODE_OF_CONDUCT.md` | 9 | 已检查 | 社区规范 |
| `SUPPORT.md` | 25 | 已检查 | 支持说明 |

## 9. 数据 fixture 覆盖

`packages/markitdown/tests/test_files` 下共有 31 个文件，覆盖：

- DOCX、XLSX、XLS、PPTX
- PDF 和扫描 PDF
- Outlook MSG
- HTML、XML、RSS
- Jupyter Notebook
- EPUB
- CSV
- ZIP
- JPEG、WAV、MP3、M4A
- 随机二进制

OCR 包另有 22 个专用 DOCX、PDF、PPTX、XLSX fixture，用于验证图片在不同位置、扫描页和多图布局下的输出。

这些文件没有逐字节读取，因为它们是测试输入而不是项目实现。已检查测试向量、测试断言和文件用途。

## 10. 实际验证记录

### 10.1 环境检查

```text
系统 Python: 3.13.14
pytest: 未安装
markitdown: 未安装
hatch: 未安装
uv: 未安装
项目内虚拟环境: 不存在
```

因此无法直接执行官方测试套件。

### 10.2 静态编译

执行：

```powershell
python -m compileall -q packages
```

结果：通过。

### 10.3 测试统计

```text
Test files: 44
Test functions: 386
Main package fixture files: 31
Source files: 52
Source lines: 8,803
Test lines: 10,632
```

## 11. 明确排除项

1. 二进制 fixture 的内部字节结构。
2. 根目录之外的 Git 历史和上游提交记录。
3. `__pycache__`、构建目录和临时文件。
4. 未安装的第三方依赖源码。
5. 测试中依赖真实 Azure、真实网络和真实 LLM 的外部服务行为。

## 12. 覆盖完成度判断

针对 MarkItDown 自身实现的源码、公共接口、CLI、MCP、OCR 插件、示例插件、配置和测试结构，覆盖完成。

针对文档转换设计意图、扩展机制、安全问题、运行流程和对 Algocode 的借鉴价值，覆盖完成。

完整测试执行未完成，原因是当前源码快照没有安装项目测试环境。没有把“源代码静态可编译”表述为“全部测试通过”。

源码快照没有 `.git` 目录，无法确认上游提交 hash；版本以各包的 `__about__.py` 为准。
