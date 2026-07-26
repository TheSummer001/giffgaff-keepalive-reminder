# giffgaff Keepalive Reminder

[![CI](https://github.com/TheSummer001/giffgaff-keepalive-reminder/actions/workflows/ci.yml/badge.svg)](https://github.com/TheSummer001/giffgaff-keepalive-reminder/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个自托管的 giffgaff SIM 保号提醒服务。通过 PushPlus 和 QQ 邮箱发送通知，
在人工确认已经发送短信后重新计算周期。

> 本项目不是 giffgaff 官方产品，与 giffgaff 没有隶属或合作关系。运营商政策
> 可能变化，请定期核对官方说明。本项目不会自动操作 SIM 或发送短信。

## 功能

- PushPlus 微信通知和 QQ 邮箱双通道提醒
- 第 140、150、165、175、180 天分级升级提醒
- 一次性签名确认链接与 24 小时延后
- 密码保护的移动端管理页面
- SQLite 事件记录、每日备份和月度服务心跳
- Docker Compose 和 1Panel 友好部署
- 单张 SIM、低资源占用，无需保存 giffgaff 账户密码

## 默认提醒规则

| 距上次短信 | 等级 | 频率 |
|---:|---|---|
| 140 天 | 提前预告 | 一次 |
| 150 天 | 建议操作 | 每 3 天 |
| 165 天 | 重要提醒 | 每天 |
| 175 天 | 紧急提醒 | 每 12 小时 |
| 180 天起 | 已到节点 | 每 6 小时 |

所有日期和时间默认使用 `Asia/Shanghai`。每月 1 日发送服务心跳，每天自动备份
SQLite 数据库并保留最近 30 天。

## 准备通知凭据

### PushPlus

登录 PushPlus 后取得个人 Token，填入 `PUSHPLUS_TOKEN`。

### QQ 邮箱

在 QQ 邮箱设置中开启 SMTP 服务并生成授权码：

- `QQ_SMTP_USER`：发件 QQ 邮箱
- `QQ_SMTP_AUTH_CODE`：SMTP 授权码，不是 QQ 密码
- `QQ_EMAIL_TO`：接收通知的邮箱

不要把 Token、授权码或 `.env` 提交到 Git。

## 部署

复制配置：

```bash
cp .env.example .env
```

生成应用密钥：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

编辑 `.env`，至少设置：

```dotenv
PUBLIC_BASE_URL=http://你的公网IP:18080
APP_SECRET=刚生成的随机值
ADMIN_PASSWORD=独立的强密码
PUSHPLUS_TOKEN=你的PushPlusToken
QQ_SMTP_USER=你的QQ邮箱
QQ_SMTP_AUTH_CODE=你的SMTP授权码
QQ_EMAIL_TO=接收通知的邮箱
```

启动：

```bash
mkdir -p data
sudo chown -R 10001:10001 data
docker compose up -d --build
docker compose ps
docker compose logs --tail=100
```

容器使用 UID `10001` 的非 root 用户运行，因此首次部署时需要保证 `data`
目录可写。在 1Panel 中也可以使用终端执行上述两条准备命令。

浏览器访问：

```text
http://你的公网IP:18080
```

登录后先点击“发送测试通知”，确认微信和 QQ 邮箱都能收到消息。

## 1Panel 和阿里云

1. 在阿里云安全组中放行 TCP 18080。
2. 使用 1Panel 的 Compose 功能导入 `docker-compose.yml`，或在终端启动。
3. 将项目目录和 `data` 目录纳入服务器备份。
4. 可用外部监控服务定时访问 `/health`。

当前使用公网 HTTP 时，管理密码会以未加密连接传输。因此：

- 管理密码必须是独立密码，不能复用。
- 日常确认优先使用通知中的一次性签名链接。
- 长期运行建议绑定域名，通过 1Panel 反向代理启用 HTTPS，并把
  `SECURE_COOKIES` 改为 `true`。

## 数据与恢复

- 主数据库：`data/reminder.db`
- 每日备份：`data/backups/reminder-YYYYMMDD.db`

恢复前停止容器，将选定的备份文件复制为 `data/reminder.db`，再启动容器。

## 本地测试

提醒日期和签名令牌测试不依赖第三方服务：

```bash
python -m unittest discover -v
python tests/integration_smoke.py
```

如需快速模拟提醒，可临时将数据库里的 `last_sms_date` 改为相应历史日期，或在
测试环境调整系统日期。不要直接修改生产数据库；生产环境请通过管理页面记录。

## 安全

不要提交 `.env`、数据库、确认链接或任何真实凭据。生产环境建议使用 HTTPS，
并设置 `SECURE_COOKIES=true`。漏洞请按照 [SECURITY.md](SECURITY.md) 私密报告。

## 参与贡献

欢迎 Issue 和 Pull Request，开发与提交规范见
[CONTRIBUTING.md](CONTRIBUTING.md)。

## License

[MIT](LICENSE) © 2026 TheSummer001
