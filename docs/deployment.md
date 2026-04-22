# 部署说明

这套项目现在最适合直接部署到一台 Linux 云服务器上。

默认方案：

- 应用服务：`Docker`
- HTTPS 和反向代理：`Caddy`
- 数据持久化：挂载本地 `./data`

## 你需要准备

1. 一台 Linux 云服务器
2. 一个能解析到这台服务器公网 IP 的域名
3. 模型 API Key
4. 微信公众号的 `Token / AppID / AppSecret`

## 第一步：把代码放到服务器

可以直接在服务器上拉仓库：

```bash
git clone https://github.com/winston928928-cmd/wechat-agent-ordering.git
cd wechat-agent-ordering
```

## 第二步：准备环境变量

复制一份环境文件：

```bash
cp .env.example .env
```

最少把这些填上：

```env
LLM_PROVIDER=dashscope
DASHSCOPE_API_KEY=你的百炼Key
AGENT_NAME=暖心搭子
WECHAT_OFFICIAL_TOKEN=你公众号后台配置的Token
WECHAT_OFFICIAL_APP_ID=你的公众号AppID
WECHAT_OFFICIAL_APP_SECRET=你的公众号AppSecret
```

如果你想用 DeepSeek，就改成：

```env
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的DeepSeekKey
LLM_MODEL=deepseek-chat
```

## 第三步：改域名

编辑 `deploy/Caddyfile`，把：

```text
your.domain.com
```

替换成你的真实域名，比如：

```text
agent.yourdomain.com
```

同时把这个域名的 DNS A 记录指向你的云服务器公网 IP。

## 第四步：启动

```bash
docker compose up -d --build
```

启动后可以看状态：

```bash
docker compose ps
docker compose logs -f app
docker compose logs -f caddy
```

## 第五步：验证

健康检查地址：

```text
https://你的域名/api/health
```

如果正常，你会看到类似：

```json
{
  "status": "ok"
}
```

## 第六步：配置公众号回调

把公众号后台的服务器地址配置成：

```text
https://你的域名/wechat/official/callback
```

注意：

- `Token` 要和 `.env` 里的 `WECHAT_OFFICIAL_TOKEN` 一致
- 如果配了 `AppID/AppSecret`，服务会走“先返回 success，再主动回发客服消息”的更稳模式

## 目录说明

- `compose.yaml`：应用和 HTTPS 入口
- `Dockerfile`：应用镜像
- `deploy/Caddyfile`：域名和反向代理
- `data/`：会话、记忆、微信 token 缓存

## 现阶段限制

- 当前已经支持按会话或微信用户隔离长期记忆，但还不是完整多租户
- 当前公众号只支持文本消息
- 还没接内容审核、限流和多租户
