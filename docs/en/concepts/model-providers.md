# Model Providers

Algocode abstracts model calls through a unified `ProviderAdapter`.

## Supported Providers

- OpenAI-compatible services.
- Anthropic Claude.
- OpenAI-compatible services such as DeepSeek, OpenRouter, Kimi, Zhipu GLM, MiniMax, Volcano Engine Doubao, and Qwen.

## API Key Storage

API keys are not written to project configuration. They are stored in a local credential file, while project configuration stores only `env://` or `local://` references.

## Model Logs

Each model call records a redacted request, response, usage, duration, and error. Logs live in:

```text
.algocode/cache/model-logs/
```
