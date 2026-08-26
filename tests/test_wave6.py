import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from domus import db
from domus.config import Settings
from domus.dates import parse_assignee_hint
from domus.intents import _parse_with_rules, Intent
from domus.memory import build_openrouter_context, record_exchange
from domus.person_context import handle_who_did_what, resolve_assignee_user_id
from domus.quiet_hours import is_quiet_hours, should_defer_reminder
from domus.redaction import redact_for_llm
from domus.todos import handle_intent


class Wave6FeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave6.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        self.seb_id = 100
        self.alex_id = 200
        db.upsert_user_profile(self.db_path, self.seb_id, "Sebastian")
        db.upsert_user_profile(self.db_path, self.alex_id, "Alex")

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_parse_assignee_hint(self) -> None:
        text, assignee = parse_assignee_hint("pay rent for Sebastian")
        self.assertEqual(text.strip(), "pay rent")
        self.assertEqual(assignee, "Sebastian")

    def test_assign_task_via_rules(self) -> None:
        intents = _parse_with_rules("add pay rent for Alex")
        self.assertEqual(intents[0].name, "add_todo")
        self.assertEqual(intents[0].assignee.lower(), "alex")

    def test_add_todo_stores_assignee(self) -> None:
        intent = Intent(name="add_todo", item="buy filter", assignee="Sebastian")
        reply = handle_intent(
            intent,
            self.db_path,
            "Alex",
            telegram_user_id=self.alex_id,
        )
        self.assertIn("Sebastian", reply)
        todos = db.list_open_todos(self.db_path)
        self.assertEqual(todos[0].assigned_to_user_id, self.seb_id)

    def test_complete_records_completed_by(self) -> None:
        todo = db.add_todo(self.db_path, "take out trash", "Sebastian")
        intent = Intent(name="complete_todo", item="trash")
        handle_intent(
            intent,
            self.db_path,
            "Sebastian",
            telegram_user_id=self.seb_id,
        )
        completed = db.get_open_todo(self.db_path, todo.id)
        self.assertIsNone(completed)
        with db.connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo.id,)).fetchone()
        self.assertEqual(row["completed_by_user_id"], self.seb_id)
        self.assertIsNotNone(row["completed_at"])

    def test_who_did_what(self) -> None:
        todo = db.add_todo(self.db_path, "dishes", "Alex")
        db.complete_todo_by_id(self.db_path, todo.id, completed_by_user_id=self.alex_id)
        reply = handle_who_did_what(self.db_path, days=7)
        self.assertIn("Alex", reply)
        self.assertIn("dishes", reply)

    def test_quiet_hours_wraparound(self) -> None:
        late = datetime(2026, 8, 26, 23, 0)
        early = datetime(2026, 8, 26, 6, 0)
        midday = datetime(2026, 8, 26, 12, 0)
        self.assertTrue(is_quiet_hours(late, start_hour=22, end_hour=7))
        self.assertTrue(is_quiet_hours(early, start_hour=22, end_hour=7))
        self.assertFalse(is_quiet_hours(midday, start_hour=22, end_hour=7))
        self.assertTrue(should_defer_reminder(late, start_hour=22, end_hour=7))

    def test_redaction_masks_patterns(self) -> None:
        settings = Settings(
            telegram_bot_token="",
            openrouter_api_key=None,
            openrouter_model="test",
            database_path=self.db_path,
            briefing_hour=8,
            evening_briefing_hour=20,
            quiet_hours_enabled=True,
            quiet_hours_start=22,
            quiet_hours_end=7,
            redaction_enabled=True,
            redaction_patterns=("Sebastian", r"\d+\s*€"),
        )
        safe, labels = redact_for_llm("Sebastian owes 50 € for rent", settings)
        self.assertNotIn("Sebastian", safe)
        self.assertNotIn("50 €", safe)
        self.assertEqual(len(labels), 2)

    def test_memory_turns_and_context(self) -> None:
        record_exchange(
            self.db_path,
            chat_id=1,
            user_id=self.seb_id,
            user_text="add milk",
            assistant_text='Added "milk".',
            intents=[Intent(name="add_todo", item="milk")],
        )
        context = build_openrouter_context(
            self.db_path,
            chat_id=1,
            user_id=self.seb_id,
        )
        self.assertIn("add milk", context)
        self.assertIn("Sebastian", context)

    def test_resolve_assignee_me(self) -> None:
        user_id = resolve_assignee_user_id(self.db_path, "me", current_user_id=self.seb_id)
        self.assertEqual(user_id, self.seb_id)


if __name__ == "__main__":
    unittest.main()
