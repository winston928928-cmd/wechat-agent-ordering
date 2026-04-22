# Provider 说明

## 默认选择

当前默认 provider 是：

- `dashscope`
- 默认模型：`qwen-plus`

这样选的原因很简单：

- 国内更容易直接接入
- 官方提供了 OpenAI 兼容的 `chat/completions` 接口
- 适合当前这个“先把聊天跑通”的阶段

## 当前已内置的 provider 预设

### `dashscope`

- base URL：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- 默认模型：`qwen-plus`
- API Key 环境变量：`DASHSCOPE_API_KEY`

### `deepseek`

- base URL：`https://api.deepseek.com`
- 默认模型：`deepseek-chat`
- API Key 环境变量：`DEEPSEEK_API_KEY`

## 通用环境变量

你也可以统一只配这些：

```powershell
$env:LLM_PROVIDER="dashscope"
$env:LLM_API_KEY="xxx"
$env:LLM_MODEL="qwen-plus"
```

如果同时配置了 `LLM_API_KEY` 和 provider 专属 key，优先使用 `LLM_API_KEY`。
