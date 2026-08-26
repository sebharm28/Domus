import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from domus import db, food_db
from domus.briefing import build_evening_briefing
from domus.intents import _parse_profile_intents, _parse_with_rules
from domus.profiles import handle_log_dispreference
from domus.intents import Intent
from domus.reminders import handle_cancel_timer
from domus.todos import _add_or_merge_todo
from domus.undo import handle_undo as undo_handler


class CancelTimerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave4_cancel.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        self.chat_id = 55

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_cancel_timer_intent(self) -> None:
        intents = _parse_with_rules("cancel the reminder")
        self.assertEqual(intents[0].name, "cancel_timer")

    def test_cancel_pending_timer(self) -> None:
        fire_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.add_one_shot_reminder(
            self.db_path,
            "text Andreas",
            fire_at,
            self.chat_id,
            "Alex",
        )
        reply = handle_cancel_timer(self.db_path, self.chat_id)
        self.assertIn("Cancelled timer", reply)
        self.assertEqual(len(db.list_pending_one_shot_reminders(self.db_path, self.chat_id)), 0)


class UndoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave4_undo.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        self.chat_id = 77

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_undo_intent(self) -> None:
        intents = _parse_with_rules("undo")
        self.assertEqual(intents[0].name, "undo")

    def test_undo_last_add(self) -> None:
        _add_or_merge_todo(
            self.db_path,
            "milk",
            "Alex",
            due_date=None,
            category="shopping",
            chat_id=self.chat_id,
        )
        reply = undo_handler(self.db_path, self.chat_id)
        self.assertIn("Undid add", reply)
        self.assertEqual(len(db.list_open_todos(self.db_path)), 0)


class ShoppingDueDateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave4_shopping.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_shopping_add_strips_due_date(self) -> None:
        intents = _parse_with_rules("add milk to the list tomorrow")
        self.assertEqual(intents[0].category, "shopping")
        self.assertIsNone(intents[0].due_date)
        _, todo = _add_or_merge_todo(
            self.db_path,
            "milk",
            "Alex",
            due_date="2026-08-27",
            category="shopping",
        )
        assert todo is not None
        self.assertIsNone(todo.due_date)


class DispreferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave4_dislike.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        self.user_id = 9
        db.upsert_user_profile(self.db_path, self.user_id, "Alex")

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_i_do_not_like_mushrooms(self) -> None:
        intents = _parse_profile_intents("I do not like mushrooms")
        self.assertIsNotNone(intents)
        assert intents is not None
        self.assertEqual(intents[0].name, "log_dispreference")
        reply = handle_log_dispreference(intents[0], self.db_path, self.user_id)
        self.assertIn("mushrooms", reply.lower())
        profile = db.get_user_profile(self.db_path, self.user_id)
        assert profile is not None
        self.assertIn("mushrooms", (profile.dislikes or "").lower())


class EveningBriefingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave4_evening.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        food_db.init_food_tables(self.db_path)

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_evening_briefing_includes_tomorrow(self) -> None:
        tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
        db.add_todo(
            self.db_path,
            "pay rent",
            "Alex",
            due_date=tomorrow,
            category="admin",
        )
        text = build_evening_briefing(self.db_path)
        self.assertIn("pay rent", text)
        self.assertIn("Evening summary", text)


if __name__ == "__main__":
    unittest.main()
