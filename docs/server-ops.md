# 服务器运维

这份说明对应当前已经跑起来的 `Python + systemd + nginx` 方案。

当前约定：

- 项目目录：`/opt/wechat-agent-ordering`
- 应用服务：`wechat-agent.service`
- 反向代理：`nginx`
- 应用端口：`8787`
- 对外入口：`80`

## 一次性准备

本地先安装：

```powershell
python -m pip install paramiko
```

设置服务器密码到环境变量：

```powershell
$env:WECHAT_AGENT_SERVER_PASSWORD="你的服务器密码"
```

## 常用命令

### 1. 同步代码并重启服务

```powershell
python scripts/deploy_server.py sync --host 你的服务器IP --user root
```

### 2. 只看服务状态

```powershell
python scripts/deploy_server.py status --host 你的服务器IP --user root
```

### 3. 如果你不想从环境变量读密码

```powershell
python scripts/deploy_server.py sync --host 你的服务器IP --user root --password 你的密码
```

不建议长期这么用，因为命令历史里会留下明文密码。

## 线上关键文件

- `/opt/wechat-agent-ordering/.env`
- `/etc/systemd/system/wechat-agent.service`
- `/etc/nginx/conf.d/wechat-agent.conf`

## 手工运维命令

### 查看服务

```bash
systemctl status wechat-agent.service
journalctl -u wechat-agent.service -n 50 --no-pager
```

### 重启服务

```bash
systemctl restart wechat-agent.service
```

### 查看本机健康检查

```bash
curl http://127.0.0.1:8787/api/health
curl http://127.0.0.1/api/health
```

## 下一步还需要什么

真正对外可用还差三项：

1. 腾讯云安全组放行 `80`
2. `.env` 里填模型 `API Key`
3. 后面若接公众号正式回调，再补域名和 `443`
