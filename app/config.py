from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    timezone_name: str
    data_dir: Path
    public_base_url: str
    app_secret: str
    admin_password: str
    secure_cookies: bool
    pushplus_token: str
    qq_smtp_user: str
    qq_smtp_auth_code: str
    qq_email_to: str
    initial_last_sms_date: str
    reminder_hour: int
    check_interval_seconds: int
    backup_retention_days: int

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "reminder.db"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("DATA_DIR", "/app/data"))
        return cls(
            app_name=os.getenv("APP_NAME", "giffgaff 保号提醒"),
            timezone_name=os.getenv("TIMEZONE", "Asia/Shanghai"),
            data_dir=data_dir,
            public_base_url=os.getenv(
                "PUBLIC_BASE_URL", "http://127.0.0.1:18080"
            ).rstrip("/"),
            app_secret=os.getenv("APP_SECRET", ""),
            admin_password=os.getenv("ADMIN_PASSWORD", ""),
            secure_cookies=_env_bool("SECURE_COOKIES", False),
            pushplus_token=os.getenv("PUSHPLUS_TOKEN", "").strip(),
            qq_smtp_user=os.getenv("QQ_SMTP_USER", "").strip(),
            qq_smtp_auth_code=os.getenv("QQ_SMTP_AUTH_CODE", "").strip(),
            qq_email_to=os.getenv("QQ_EMAIL_TO", "").strip(),
            initial_last_sms_date=os.getenv("INITIAL_LAST_SMS_DATE", "2026-07-26"),
            reminder_hour=int(os.getenv("REMINDER_HOUR", "10")),
            check_interval_seconds=int(
                os.getenv("CHECK_INTERVAL_SECONDS", "900")
            ),
            backup_retention_days=int(os.getenv("BACKUP_RETENTION_DAYS", "30")),
        )

    def validate(self) -> None:
        if not self.app_secret or self.app_secret == "change-me":
            raise RuntimeError("APP_SECRET must be set to a strong random value")
        if not self.admin_password or self.admin_password == "change-me":
            raise RuntimeError("ADMIN_PASSWORD must be set")
        if not 0 <= self.reminder_hour <= 23:
            raise RuntimeError("REMINDER_HOUR must be between 0 and 23")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
