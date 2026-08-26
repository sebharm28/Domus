import unittest
from pathlib import Path

from domus import db
from domus.context import record_intent_context
from domus.intents import Intent, _parse_with_rules
from domus.todos import _add_or_merge_todo, handle_clear_todos, handle_intent


class ClearTodosTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_clear_todos.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_empty_the_todo_list_intent(self) -> None:
        intents = _parse_with_rules("empty the todo list")
        self.assertEqual(intents[0].name, "clear_todos")

    def test_no_you_should_empty_the_todo_list(self) -> None:
        intents = _parse_with_rules("no you should empty the todo list!")
        self.assertEqual(intents[0].name, "clear_todos")

    def test_wipe_todos_intent(self) -> None:
        intents = _parse_with_rules("wipe todos")
        self.assertEqual(intents[0].name, "clear_todos")

    def test_clear_shopping_still_shopping_only(self) -> None:
        intents = _parse_with_rules("clear the shopping list")
        self.assertEqual(intents[0].name, "clear_shopping_list")

    def test_clear_todos_handler(self) -> None:
        _add_or_merge_todo(self.db_path, "bank", "Alex", due_date=None, category="personal")
        _add_or_merge_todo(self.db_path, "milk", "Alex", due_date=None, category="shopping")
        reply = handle_clear_todos(self.db_path)
        self.assertIn("Cleared 2", reply)
        self.assertEqual(len(db.list_open_todos(self.db_path)), 0)


class ContextRemoveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_context_remove.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        self.chat_id = 1001

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_remove_it_uses_context(self) -> None:
        _, todo = _add_or_merge_todo(
            self.db_path,
            "bank",
            "Alex",
            due_date=None,
            category="personal",
        )
        assert todo is not None
        record_intent_context(
            self.db_path,
            self.chat_id,
            Intent(name="add_todo", item="bank"),
            todo_id=todo.id,
        )

        intents = _parse_with_rules("remove it from the list")
        self.assertEqual(intents[0].name, "remove_todo")
        reply = handle_intent(
            intents[0],
            self.db_path,
            "Alex",
            chat_id=self.chat_id,
        )
        self.assertIn('Removed "bank"', reply)
        self.assertEqual(len(db.list_open_todos(self.db_path)), 0)

    def test_complete_it_uses_context(self) -> None:
        _, todo = _add_or_merge_todo(
            self.db_path,
            "milk",
            "Alex",
            due_date=None,
            category="shopping",
        )
        assert todo is not None
        record_intent_context(
            self.db_path,
            self.chat_id,
            Intent(name="list_todos"),
            todo_id=todo.id,
        )

        intents = _parse_with_rules("bought it")
        self.assertEqual(intents[0].name, "complete_todo")
        reply = handle_intent(
            intents[0],
            self.db_path,
            "Alex",
            chat_id=self.chat_id,
        )
        self.assertIn('Checked off "milk"', reply)
        self.assertEqual(len(db.list_open_todos(self.db_path)), 0)


if __name__ == "__main__":
    unittest.main()
