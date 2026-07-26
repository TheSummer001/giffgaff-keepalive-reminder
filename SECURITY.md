# Security Policy

## Supported versions

安全修复目前仅针对 `main` 分支和最新发布版本。

## Reporting a vulnerability

请不要在公开 Issue 中披露未修复的漏洞。请使用 GitHub 仓库的
**Security → Report a vulnerability** 私密报告入口，并提供：

- 受影响版本或 commit
- 复现步骤
- 可能影响
- 建议修复方式（如有）

维护者会尽快确认问题。在修复发布前，请避免公开披露细节。

## Deployment notes

- 永远不要提交 `.env`。
- QQ SMTP 必须使用授权码，不能使用 QQ 密码。
- 生产环境应使用 HTTPS，并设置 `SECURE_COOKIES=true`。
- `APP_SECRET` 和 `ADMIN_PASSWORD` 应使用独立的高强度随机值。
- 如果凭据曾出现在日志、截图、Issue 或聊天记录中，应立即轮换。
- 管理页面不应在未加密的公网 HTTP 上长期暴露。
