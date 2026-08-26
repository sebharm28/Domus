import unittest
from pathlib import Path

from domus import db
from domus.intents import _parse_edit_intents, _parse_profile_intents
from domus.todos import _add_or_merge_todo, handle_update_todo
from domus.context import record_intent_context
from domus.intents import Intent


class Wave2EditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave2_edits.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        self.chat_id = 1001

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_rename_that_uses_context(self) -> None:
        _, todo = _add_or_merge_todo(
            self.db_path,
            "call landlord",
            "Alex",
            due_date=None,
            category="admin",
        )
        assert todo is not None
        record_intent_context(
            self.db_path,
            self.chat_id,
            Intent(name="add_todo", item="call landlord"),
            todo_id=todo.id,
        )

        intents = _parse_edit_intents("rename that to pay rent")
        self.assertIsNotNone(intents)
        assert intents is not None
        reply = handle_update_todo(intents[0], self.db_path, self.chat_id)
        self.assertIn("pay rent", reply.lower())
        updated = db.list_open_todos(self.db_path)[0]
        self.assertEqual(updated.text, "pay rent")

    def test_actually_due_tomorrow_uses_context(self) -> None:
        _, todo = _add_or_merge_todo(
            self.db_path,
            "power bi report",
            "Alex",
            due_date=None,
            category="personal",
        )
        assert todo is not None
        record_intent_context(
            self.db_path,
            self.chat_id,
            Intent(name="add_todo", item="power bi report"),
            todo_id=todo.id,
        )

        intents = _parse_edit_intents("actually that's due tomorrow")
        self.assertIsNotNone(intents)
        assert intents is not None
        reply = handle_update_todo(intents[0], self.db_path, self.chat_id)
        self.assertIn("Updated", reply)
        updated = db.list_open_todos(self.db_path)[0]
        self.assertIsNotNone(updated.due_date)

    def test_meant_correction_updates_context_task_not_latest_bulk(self) -> None:
        _add_or_merge_todo(
            self.db_path,
            "curry paste",
            "Alex",
            due_date=None,
            category="shopping",
        )
        _, bank = _add_or_merge_todo(
            self.db_path,
            "going to the bank",
            "Alex",
            due_date=None,
            category="admin",
        )
        assert bank is not None
        record_intent_context(
            self.db_path,
            self.chat_id,
            Intent(name="add_todo", item="going to the bank"),
            todo_id=bank.id,
        )

        reply = handle_update_todo(
            Intent(name="update_todo", item="going to the bank"),
            self.db_path,
            self.chat_id,
        )
        self.assertIn("going to the bank", reply)
        items = {todo.text: todo for todo in db.list_open_todos(self.db_path)}
        self.assertEqual(items["going to the bank"].text, "going to the bank")
        self.assertEqual(items["curry paste"].text, "curry paste")


class Wave2ProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave2_profiles.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        db.upsert_user_profile(self.db_path, 42, "Alex")

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_profile_diet_intent(self) -> None:
        intents = _parse_profile_intents("I'm vegetarian")
        self.assertIsNotNone(intents)
        assert intents is not None
        self.assertEqual(intents[0].name, "update_profile")
        self.assertEqual(intents[0].category, "diet")

    def test_profile_apartment_intent(self) -> None:
        intents = _parse_profile_intents("my apartment is A")
        self.assertIsNotNone(intents)
        assert intents is not None
        self.assertEqual(intents[0].item, "a")
        self.assertEqual(intents[0].category, "apartment")


if __name__ == "__main__":
    unittest.main()
