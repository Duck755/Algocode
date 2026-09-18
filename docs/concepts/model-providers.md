# 模型 Provider

Algocode 通过统一的 `ProviderAdapter` 抽象模型调用。

## 支持的 Provider

- OpenAI-compatible 服务。
- Anthropic Claude。
- DeepSeek、OpenRouter、Kimi、智谱 GLM、MiniMax、火山引擎豆包、通义千问 Qwen 等 OpenAI-compatible 服务。

## API Key 存储

API Key 不写入项目配置，而保存在用户本机凭证文件中。项目配置只保存 `env://` 或 `local://` 引用。

## 模型日志

每次模型调用都会记录脱敏后的请求、响应、用量、耗时和错误。日志位于：

```text
.algocode/cache/model-logs/
```
