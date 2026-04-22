# Agent API 说明

## 1. 目标

当前这套接口只解决一件事：

`让 Agent 能稳定地连续聊天`

还没有接工具调用，也没有接微信入口。

## 2. 接口列表

### `GET /api/health`

返回服务状态、当前 provider、默认模型、是否已配置模型 API Key。

### `POST /api/sessions`

创建一个新会话。

### `GET /api/sessions/{session_id}`

读取某个会话的本地历史。

### `POST /api/chat`

发送一条用户消息，让 Agent 回复。

请求体：

```json
{
  "session_id": "optional",
  "message": "你好，今天有点烦"
}
```

返回体核心字段：

```json
{
  "session_id": "会话 id",
  "assistant_message": "助手回复",
  "response_id": "模型响应 id",
  "model": "实际使用的模型"
}
```

## 3. 会话设计

当前会话同时保留两层状态：

1. 本地 JSON 文件历史  
   用于调试、页面回显、断点查看

2. 最近若干轮消息窗口  
   用于把连续对话历史一起发给当前模型

注意：

当前实现默认走兼容 `chat/completions` 的接口，因此会在每一轮请求里重新发送：

- 系统提示词
- 最近若干轮聊天记录

这样可以兼容阿里云百炼、DeepSeek 这类国内常见接口。

## 4. 下一步怎么接微信

等这一层稳定后，下一步只需要在“微信通道”里把收到的消息转发到：

- `POST /api/chat`

然后把 `assistant_message` 回发给微信即可。

也就是说，后面接 `CowAgent`、`weclaw`、`openclaw-weixin` 时，Agent 层本身不用大改。
