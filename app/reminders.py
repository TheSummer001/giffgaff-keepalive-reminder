from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class ReminderStage:
    name: str
    label: str
    minimum_days: int
    interval: timedelta | None


STAGES = (
    ReminderStage("prewarning", "提前预告", 140, None),
    ReminderStage("normal", "建议操作", 150, timedelta(days=3)),
    ReminderStage("important", "重要提醒", 165, timedelta(days=1)),
    ReminderStage("urgent", "紧急提醒", 175, timedelta(hours=12)),
    ReminderStage("overdue", "已到180天节点", 180, timedelta(hours=6)),
)


def age_days(last_sms_date: date, today: date) -> int:
    return max(0, (today - last_sms_date).days)


def deadline(last_sms_date: date) -> date:
    return last_sms_date + timedelta(days=180)


def suggested_action_date(last_sms_date: date) -> date:
    return last_sms_date + timedelta(days=150)


def stage_for_days(days: int) -> ReminderStage | None:
    current: ReminderStage | None = None
    for stage in STAGES:
        if days >= stage.minimum_days:
            current = stage
    return current


def reminder_is_due(
    *,
    now: datetime,
    last_sms_date: date,
    last_success_at: datetime | None,
    last_success_stage: str | None,
    snoozed_until: datetime | None,
    reminder_hour: int,
) -> bool:
    if snoozed_until and now < snoozed_until:
        return False
    if now.hour < reminder_hour:
        return False

    stage = stage_for_days(age_days(last_sms_date, now.date()))
    if stage is None:
        return False
    if last_success_at is None:
        return True
    if last_success_stage != stage.name:
        return True
    if stage.interval is None:
        return False
    return now - last_success_at >= stage.interval
