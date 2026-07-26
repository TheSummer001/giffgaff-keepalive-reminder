from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

from .config import Settings
from .database import Database
from .notifications import NotificationService, reminder_html, simple_html
from .reminders import (
    age_days,
    deadline,
    reminder_is_due,
    stage_for_days,
)
from .security import create_token


class ReminderScheduler:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        notifications: NotificationService,
    ):
        self.settings = settings
        self.database = database
        self.notifications = notifications
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        while not self._stop_event.is_set():
            now = datetime.now(self.settings.timezone)
            try:
                await self.check(now)
            except Exception as exc:  # noqa: BLE001 - keep scheduler alive
                self.database.add_event(
                    event_type="scheduler_error",
                    channel=None,
                    stage=None,
                    status="failed",
                    message=f"{type(exc).__name__}: {exc}",
                    now=now,
                )
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.settings.check_interval_seconds,
                )
            except TimeoutError:
                pass

    async def check(self, now: datetime) -> None:
        await self._maybe_backup(now)
        await self._maybe_heartbeat(now)
        await self._maybe_send_reminders(now)

    async def _maybe_send_reminders(self, now: datetime) -> None:
        state = self.database.get_state()
        last_sms_date = date.fromisoformat(str(state["last_sms_date"]))
        snoozed_until = (
            datetime.fromisoformat(str(state["snoozed_until"]))
            if state["snoozed_until"]
            else None
        )
        cycle_started_at = datetime.fromisoformat(
            str(state["cycle_started_at"])
        )
        days = age_days(last_sms_date, now.date())
        stage = stage_for_days(days)
        if stage is None:
            return

        confirm_token = create_token(
            self.settings.app_secret,
            "confirm",
            expires_in_seconds=35 * 24 * 60 * 60,
            extra={"cycle": state["cycle_started_at"]},
        )
        snooze_token = create_token(
            self.settings.app_secret,
            "snooze",
            expires_in_seconds=35 * 24 * 60 * 60,
            extra={"cycle": state["cycle_started_at"]},
        )
        html_content = reminder_html(
            stage_label=stage.label,
            last_sms_date=last_sms_date.isoformat(),
            days_elapsed=days,
            deadline_date=deadline(last_sms_date).isoformat(),
            confirm_url=(
                f"{self.settings.public_base_url}/confirm/{confirm_token}"
            ),
            snooze_url=(
                f"{self.settings.public_base_url}/snooze/{snooze_token}"
            ),
        )
        title = f"【{stage.label}】giffgaff SIM 保号"

        for channel in self.notifications.enabled_channels:
            previous = self.database.last_successful_notification(
                channel, cycle_started_at
            )
            previous_at = previous[0] if previous else None
            previous_stage = previous[1] if previous else None
            if not reminder_is_due(
                now=now,
                last_sms_date=last_sms_date,
                last_success_at=previous_at,
                last_success_stage=previous_stage,
                snoozed_until=snoozed_until,
                reminder_hour=self.settings.reminder_hour,
            ):
                continue
            result = await self.notifications.send(
                channel, title, html_content
            )
            self.database.add_event(
                event_type="reminder",
                channel=channel,
                stage=stage.name,
                status="success" if result.success else "failed",
                message=result.detail,
                now=now,
            )

    async def _maybe_heartbeat(self, now: datetime) -> None:
        if now.day != 1 or now.hour < self.settings.reminder_hour:
            return
        marker = f"{now:%Y-%m}"
        if self.database.event_exists("heartbeat", marker):
            return

        results = await self.notifications.send_all(
            "giffgaff 提醒服务月度心跳",
            simple_html(
                "服务运行正常",
                f"{now:%Y-%m-%d %H:%M} 定时检查和通知服务正在运行。",
            ),
        )
        success = any(result.success for result in results)
        detail = "; ".join(
            f"{result.channel}: {result.detail}" for result in results
        )
        self.database.add_event(
            event_type="heartbeat",
            channel="all",
            stage=None,
            status="success" if success else "failed",
            message=marker if success else f"{marker} | {detail}",
            now=now,
        )

    async def _maybe_backup(self, now: datetime) -> None:
        if now.hour < 2:
            return
        marker = f"{now:%Y-%m-%d}"
        if self.database.event_exists("backup", marker):
            return
        try:
            self.database.backup(
                self.settings.backup_dir,
                now,
                self.settings.backup_retention_days,
            )
        except Exception as exc:  # noqa: BLE001
            self.database.add_event(
                event_type="backup",
                channel=None,
                stage=None,
                status="failed",
                message=f"{marker} | {type(exc).__name__}: {exc}",
                now=now,
            )
            return
        self.database.add_event(
            event_type="backup",
            channel=None,
            stage=None,
            status="success",
            message=marker,
            now=now,
        )
