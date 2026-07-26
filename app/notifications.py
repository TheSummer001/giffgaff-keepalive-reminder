from __future__ import annotations

import asyncio
import html
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

import httpx

from .config import Settings


@dataclass(frozen=True)
class SendResult:
    channel: str
    success: bool
    detail: str


class NotificationService:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def enabled_channels(self) -> list[str]:
        channels: list[str] = []
        if self.settings.pushplus_token:
            channels.append("pushplus")
        if (
            self.settings.qq_smtp_user
            and self.settings.qq_smtp_auth_code
            and self.settings.qq_email_to
        ):
            channels.append("qq_email")
        return channels

    async def send(
        self, channel: str, title: str, html_content: str
    ) -> SendResult:
        try:
            if channel == "pushplus":
                await self._send_pushplus(title, html_content)
            elif channel == "qq_email":
                await asyncio.to_thread(
                    self._send_qq_email, title, html_content
                )
            else:
                return SendResult(channel, False, "unknown channel")
        except Exception as exc:  # noqa: BLE001 - persist provider failures
            return SendResult(channel, False, f"{type(exc).__name__}: {exc}")
        return SendResult(channel, True, "sent")

    async def send_all(self, title: str, html_content: str) -> list[SendResult]:
        return await asyncio.gather(
            *[
                self.send(channel, title, html_content)
                for channel in self.enabled_channels
            ]
        )

    async def _send_pushplus(self, title: str, html_content: str) -> None:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://www.pushplus.plus/send",
                json={
                    "token": self.settings.pushplus_token,
                    "title": title,
                    "content": html_content,
                    "template": "html",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if str(payload.get("code")) != "200":
                raise RuntimeError(
                    f"PushPlus rejected request: {payload.get('msg', payload)}"
                )

    def _send_qq_email(self, title: str, html_content: str) -> None:
        message = EmailMessage()
        message["Subject"] = title
        message["From"] = self.settings.qq_smtp_user
        message["To"] = self.settings.qq_email_to
        message.set_content(
            "这是一封 HTML 通知，请使用支持 HTML 的邮件客户端查看。"
        )
        message.add_alternative(html_content, subtype="html")

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            "smtp.qq.com", 465, context=context, timeout=20
        ) as smtp:
            smtp.login(
                self.settings.qq_smtp_user,
                self.settings.qq_smtp_auth_code,
            )
            smtp.send_message(message)


def reminder_html(
    *,
    stage_label: str,
    last_sms_date: str,
    days_elapsed: int,
    deadline_date: str,
    confirm_url: str,
    snooze_url: str,
) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;line-height:1.7;max-width:620px">
      <h2>giffgaff 保号{html.escape(stage_label)}</h2>
      <p>
        上次记录：<strong>{html.escape(last_sms_date)}</strong><br>
        已经过：<strong>{days_elapsed} 天</strong><br>
        180 天节点：<strong>{html.escape(deadline_date)}</strong><br>
        操作费用：<strong>£0.30</strong>
      </p>
      <p>请使用 giffgaff 卡向普通手机号码成功发送一条短信。</p>
      <p>
        <a href="{html.escape(confirm_url)}"
           style="background:#166534;color:white;padding:11px 18px;
                  text-decoration:none;border-radius:7px;display:inline-block">
          确认已发送短信
        </a>
        &nbsp;
        <a href="{html.escape(snooze_url)}">24 小时后再提醒</a>
      </p>
      <p style="color:#666;font-size:13px">
        打开链接不会直接完成操作，仍需在页面中再次确认。
      </p>
    </div>
    """


def simple_html(title: str, message: str) -> str:
    return (
        '<div style="font-family:Arial,sans-serif;line-height:1.7">'
        f"<h2>{html.escape(title)}</h2><p>{html.escape(message)}</p></div>"
    )
