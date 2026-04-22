# WeChat Agent Ordering

这是一个先做“能稳定聊天”的微信陪伴 Agent 原型。

当前已经完成：

- 国内模型对接，默认支持 `dashscope / qwen-plus`
- 本地多轮对话
- 本地 JSON 会话存储
- 长期记忆提取与后台手动编辑
- 会话级 / 用户级长期记忆隔离
- 自用聊天页 `/`
- 自用后台 `/admin`
- 公众号回调接入
- 公众号两种回复模式：
  - 只配 `WECHAT_OFFICIAL_TOKEN`：被动回复
  - 再配 `WECHAT_OFFICIAL_APP_ID` 和 `WECHAT_OFFICIAL_APP_SECRET`：先返回 `success`，再主动回发客服消息

## 快速运行

### 1. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 2. 配环境变量

先参考 `.env.example`。

最少这样就能跑本地聊天：

```powershell
$env:LLM_PROVIDER="dashscope"
$env:DASHSCOPE_API_KEY="你的百炼 API Key"
```

如果想切到 DeepSeek：

```powershell
$env:LLM_PROVIDER="deepseek"
$env:DEEPSEEK_API_KEY="你的 DeepSeek API Key"
$env:LLM_MODEL="deepseek-chat"
```

### 3. 启动服务

```powershell
python src/agent_server.py
```

启动后可直接打开：

- [http://127.0.0.1:8787](http://127.0.0.1:8787)
- [http://127.0.0.1:8787/admin](http://127.0.0.1:8787/admin)

### 4. 跑测试

```powershell
python -m unittest discover -s tests -v
```

## 公众号接入

### 只做最小接入

```powershell
$env:WECHAT_OFFICIAL_TOKEN="你在公众号后台配置的 token"
```

回调默认路径：

- `/wechat/official/callback`

### 开启更稳的主动回发

如果模型响应较慢，推荐再加这两个：

```powershell
$env:WECHAT_OFFICIAL_APP_ID="你的公众号 AppID"
$env:WECHAT_OFFICIAL_APP_SECRET="你的公众号 AppSecret"
```

这样流程会变成：

1. 微信把消息发到你的回调接口
2. 你的服务先快速返回 `success`
3. 服务后台调模型
4. 通过客服消息接口把真正回复主动发回微信

## 记忆说明

当前有两层记忆：

1. 短期记忆  
最近若干轮对话会一起发给模型，所以它能接住上下文。

2. 长期记忆  
系统会从对话里抽取稳定信息，比如称呼、喜欢、不喜欢、地点、身份角色；你也可以在 `/admin` 里手动改。
现在默认支持按会话或按微信用户隔离长期记忆，不会把不同用户混到一起。

## 主要文件

- `src/app/server.py`：HTTP 服务、聊天接口、公众号回调
- `src/app/llm_client.py`：兼容 `chat/completions` 的模型请求
- `src/app/memory_store.py`：长期记忆提取与渲染
- `src/app/wechat_official.py`：公众号签名校验和 XML 处理
- `src/app/wechat_official_api.py`：公众号 `access_token` 和客服消息发送
- `src/app/channel_store.py`：微信用户与 session 绑定
- `static/index.html`：本地聊天页
- `static/admin.html`：自用后台
- `prompts/chat_agent.md`：陪聊型 Agent 提示词
- `compose.yaml`：Docker 部署入口
- `docs/deployment.md`：云服务器部署说明
- `docs/server-ops.md`：当前服务器运维脚本说明
- `scripts/deploy_server.py`：同步代码到服务器并重启服务

## 当前接口

- `GET /api/health`
- `POST /api/sessions`
- `GET /api/sessions/{session_id}`
- `POST /api/chat`
- `GET /api/admin/sessions`
- `GET /api/admin/memory`
- `POST /api/admin/memory`
- `GET /api/admin/channel-bindings`
- `GET /wechat/official/callback`
- `POST /wechat/official/callback`
