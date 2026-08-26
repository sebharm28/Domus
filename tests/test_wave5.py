import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from domus import db
from domus.context import record_intent_context
from domus.intents import Intent, _parse_with_rules
from domus.snooze import handle_snooze_reminder
from domus.todos import _add_or_merge_todo, handle_intent
from domus.undo import handle_undo


class SnoozeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave5_snooze.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        self.chat_id = 88

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_snooze_intent(self) -> None:
        intents = _parse_with_rules("snooze pay rent until tomorrow")
        self.assertEqual(intents[0].name, "snooze_reminder")
        self.assertEqual(intents[0].item, "pay rent")
        self.assertIsNotNone(intents[0].due_date)

    def test_snooze_todo(self) -> None:
        tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
        day_after = (datetime.now().date() + timedelta(days=2)).isoformat()
        db.add_todo(
            self.db_path,
            "pay rent",
            "Alex",
            due_date=tomorrow,
            category="admin",
        )
        reply = handle_snooze_reminder(
            "snooze pay rent until tomorrow",
            self.db_path,
            chat_id=self.chat_id,
            item_hint="pay rent",
            due_date=day_after,
        )
        self.assertIn("Snoozed", reply)
        todo = db.list_open_todos(self.db_path)[0]
        self.assertEqual(todo.due_date, day_after)

    def test_snooze_one_shot_timer(self) -> None:
        fire_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        reminder = db.add_one_shot_reminder(
            self.db_path,
            "text Andreas",
            fire_at,
            self.chat_id,
            "Alex",
        )
        record_intent_context(
            self.db_path,
            self.chat_id,
            Intent(name="add_relative_reminder", item="text Andreas"),
        )
        reply = handle_snooze_reminder(
            "snooze the reminder for 30 minutes",
            self.db_path,
            chat_id=self.chat_id,
            delay_minutes=30,
        )
        self.assertIn("Snoozed timer", reply)
        pending = db.list_pending_one_shot_reminders(self.db_path, self.chat_id)
        self.assertEqual(len(pending), 1)
        self.assertNotEqual(pending[0].fire_at, reminder.fire_at)


class UndoExpandedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave5_undo.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        self.chat_id = 99

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_undo_remove(self) -> None:
        _, todo = _add_or_merge_todo(
            self.db_path,
            "bank",
            "Alex",
            due_date=None,
            category="personal",
            chat_id=self.chat_id,
        )
        assert todo is not None
        intents = _parse_with_rules("remove bank from the list")
        handle_intent(
            intents[0],
            self.db_path,
            "Alex",
            chat_id=self.chat_id,
        )
        reply = handle_undo(self.db_path, self.chat_id)
        self.assertIn('put "bank" back', reply)
        self.assertEqual(len(db.list_open_todos(self.db_path)), 1)

    def test_undo_snooze(self) -> None:
        tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
        day_after = (datetime.now().date() + timedelta(days=2)).isoformat()
        db.add_todo(
            self.db_path,
            "pay rent",
            "Alex",
            due_date=tomorrow,
            category="admin",
        )
        handle_snooze_reminder(
            "snooze pay rent until tomorrow",
            self.db_path,
            chat_id=self.chat_id,
            item_hint="pay rent",
            due_date=day_after,
        )
        reply = handle_undo(self.db_path, self.chat_id)
        self.assertIn("Undid snooze", reply)
        todo = db.list_open_todos(self.db_path)[0]
        self.assertEqual(todo.due_date, tomorrow)

    def test_undo_cancel_timer(self) -> None:
        fire_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        reminder = db.add_one_shot_reminder(
            self.db_path,
            "oven check",
            fire_at,
            self.chat_id,
            "Alex",
        )
        db.cancel_one_shot_reminder(self.db_path, self.chat_id)
        from domus.undo import record_cancel_timer

        record_cancel_timer(self.db_path, self.chat_id, reminder)
        reply = handle_undo(self.db_path, self.chat_id)
        self.assertIn("Undid cancel", reply)
        self.assertEqual(len(db.list_pending_one_shot_reminders(self.db_path, self.chat_id)), 1)


if __name__ == "__main__":
    unittest.main()
