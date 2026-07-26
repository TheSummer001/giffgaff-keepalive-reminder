import unittest
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.database import Database
from app.reminders import (
    deadline,
    reminder_is_due,
    stage_for_days,
    suggested_action_date,
)
from app.security import InvalidToken, create_token, verify_token


TZ = ZoneInfo("Asia/Shanghai")


class ReminderTests(unittest.TestCase):
    def test_dates_from_initial_date(self):
        initial = date(2026, 7, 26)
        self.assertEqual(suggested_action_date(initial), date(2026, 12, 23))
        self.assertEqual(deadline(initial), date(2027, 1, 22))

    def test_stage_boundaries(self):
        self.assertIsNone(stage_for_days(139))
        self.assertEqual(stage_for_days(140).name, "prewarning")
        self.assertEqual(stage_for_days(150).name, "normal")
        self.assertEqual(stage_for_days(165).name, "important")
        self.assertEqual(stage_for_days(175).name, "urgent")
        self.assertEqual(stage_for_days(180).name, "overdue")

    def test_normal_stage_repeats_every_three_days(self):
        now = datetime(2026, 12, 26, 10, 0, tzinfo=TZ)
        initial = date(2026, 7, 26)
        self.assertTrue(
            reminder_is_due(
                now=now,
                last_sms_date=initial,
                last_success_at=now - timedelta(days=3),
                last_success_stage="normal",
                snoozed_until=None,
                reminder_hour=10,
            )
        )
        self.assertFalse(
            reminder_is_due(
                now=now,
                last_sms_date=initial,
                last_success_at=now - timedelta(days=2),
                last_success_stage="normal",
                snoozed_until=None,
                reminder_hour=10,
            )
        )

    def test_snooze_wins(self):
        now = datetime(2027, 1, 22, 10, 0, tzinfo=TZ)
        self.assertFalse(
            reminder_is_due(
                now=now,
                last_sms_date=date(2026, 7, 26),
                last_success_at=None,
                last_success_stage=None,
                snoozed_until=now + timedelta(hours=1),
                reminder_hour=10,
            )
        )


class SecurityTests(unittest.TestCase):
    def test_signed_token(self):
        token = create_token("secret", "confirm", expires_in_seconds=60)
        payload = verify_token("secret", token, "confirm")
        self.assertEqual(payload["purpose"], "confirm")
        with self.assertRaises(InvalidToken):
            verify_token("other-secret", token, "confirm")


class DatabaseTests(unittest.TestCase):
    def test_new_cycle_does_not_inherit_old_notification(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "test.db")
            started = datetime(2026, 7, 26, 10, 0, tzinfo=TZ)
            database.initialize(date(2026, 7, 26), started)
            database.add_event(
                event_type="reminder",
                channel="pushplus",
                stage="prewarning",
                status="success",
                message="sent",
                now=started + timedelta(days=140),
            )
            new_cycle = started + timedelta(days=141)
            database.mark_sms_sent(new_cycle.date(), new_cycle)
            self.assertIsNone(
                database.last_successful_notification(
                    "pushplus", new_cycle
                )
            )

    def test_backup_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = Database(root / "test.db")
            now = datetime(2026, 7, 26, 10, 0, tzinfo=TZ)
            database.initialize(now.date(), now)
            result = database.backup(root / "backups", now, 30)
            self.assertTrue(result.exists())


if __name__ == "__main__":
    unittest.main()
