# Contributing

感谢你对本项目感兴趣。欢迎提交缺陷报告、文档改进和功能 Pull Request。

## 开发环境

需要 Python 3.12：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -v
python tests/integration_smoke.py
```

Windows PowerShell 使用：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m unittest discover -v
python tests\integration_smoke.py
```

## 提交 Pull Request

1. 从 `main` 创建功能分支。
2. 保持改动范围清晰，并为行为变化补充测试。
3. 确认单元测试和 HTTP 冒烟测试均通过。
4. 不要提交 `.env`、数据库、日志、Token、邮箱授权码或真实公网 IP。
5. 在 Pull Request 中说明改动目的、验证方式和兼容性影响。

提交信息建议使用简洁的祈使句，例如：

```text
Add ntfy notification channel
Fix reminder retry interval
```

## 范围说明

本项目只负责提醒，不计划加入云端自动控制实体 SIM、保存运营商账户密码或模拟
个人微信/QQ 登录等高风险功能。
