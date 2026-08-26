import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from domus import db
from domus.config import Settings
from domus.intents import (
    _parse_correction_intents,
    _parse_with_rules,
    parse_intents,
)
from domus.private_mode import apply_private_mode
from domus.todos import _add_or_merge_todo, format_export_list, handle_clear_shopping_list


def _test_settings(db_path: Path) -> Settings:
    return Settings(
        telegram_bot_token="test-token",
        openrouter_api_key="test-key",
        openrouter_model="test-model",
        database_path=db_path,
        briefing_hour=8,
    )


class IntentRuleTests(unittest.TestCase):
    def test_add_milk_to_list(self) -> None:
        intents = _parse_with_rules("add milk to the list")
        self.assertEqual(intents[0].name, "add_todo")
        self.assertIn("milk", (intents[0].item or "").lower())

    def test_bank_errand_with_tomorrow_in_follow_up(self) -> None:
        message = "please add going to the bank to the todo list. Have to do it tomorrow"
        intents = _parse_with_rules(message)
        self.assertEqual(intents[0].name, "add_todo")
        self.assertEqual(intents[0].category, "admin")
        self.assertIsNotNone(intents[0].due_date)

    def test_list_todos_natural_phrasing(self) -> None:
        intents = _parse_with_rules("could u show me what's on my todo list?")
        self.assertEqual(intents[0].name, "list_todos")

    def test_correction_for_tomorrow(self) -> None:
        intents = _parse_correction_intents("I said the task is for tomorrow")
        self.assertIsNotNone(intents)
        assert intents is not None
        self.assertEqual(intents[0].name, "update_todo")
        self.assertIsNotNone(intents[0].due_date)

    def test_meant_correction(self) -> None:
        intents = _parse_correction_intents("I meant going to the bank")
        self.assertIsNotNone(intents)
        assert intents is not None
        self.assertEqual(intents[0].name, "update_todo")
        self.assertIn("bank", (intents[0].item or "").lower())


class PrivateModeTests(unittest.TestCase):
    def test_private_prefix_strips_marker(self) -> None:
        text, private = apply_private_mode("/private add pay rent")
        self.assertTrue(private)
        self.assertEqual(text, "add pay rent")

    def test_private_in_reply_to_bot(self) -> None:
        text, private = apply_private_mode("/private add eggs", reply_to_bot=True)
        self.assertTrue(private)
        self.assertEqual(text, "add eggs")


class ParseIntentsRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_rules_match_skips_openrouter(self) -> None:
        settings = _test_settings(Path("data/unused.db"))
        with patch("domus.intents._parse_with_openrouter", new_callable=AsyncMock) as mock_llm:
            intents = await parse_intents("add milk to the list", settings)
            mock_llm.assert_not_called()
            self.assertEqual(intents[0].name, "add_todo")

    async def test_private_mode_skips_openrouter_even_when_unknown(self) -> None:
        settings = _test_settings(Path("data/unused.db"))
        with patch("domus.intents._parse_with_openrouter", new_callable=AsyncMock) as mock_llm:
            intents = await parse_intents("quantum flux capacitor", settings, private_mode=True)
            mock_llm.assert_not_called()
            self.assertEqual(intents[0].name, "unknown")

    async def test_openrouter_called_when_rules_unknown(self) -> None:
        settings = _test_settings(Path("data/unused.db"))
        fake_intents = [{"intent": "greeting", "item": None, "due_date": None, "category": None}]
        with patch("domus.intents._parse_with_openrouter", new_callable=AsyncMock) as mock_llm:
            from domus.intents import Intent

            mock_llm.return_value = [Intent(name="greeting")]
            intents = await parse_intents("quantum flux capacitor", settings)
            mock_llm.assert_called_once()
            self.assertEqual(intents[0].name, "greeting")


class ShoppingMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_shopping_merge.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_duplicate_shopping_item_bumps_quantity(self) -> None:
        first, todo = _add_or_merge_todo(
            self.db_path,
            "milk",
            "Alex",
            due_date=None,
            category="shopping",
        )
        self.assertIn("Added", first)
        second, _ = _add_or_merge_todo(
            self.db_path,
            "milk",
            "Alex",
            due_date=None,
            category="shopping",
        )
        self.assertIn("Updated to 2× milk", second)
        open_items = db.list_open_todos(self.db_path, category="shopping")
        self.assertEqual(len(open_items), 1)
        self.assertEqual(open_items[0].text, "milk")
        self.assertEqual(open_items[0].quantity, 2)

    def test_quantity_adds_to_existing_line(self) -> None:
        _add_or_merge_todo(self.db_path, "milk", "Alex", due_date=None, category="shopping")
        updated, _ = _add_or_merge_todo(
            self.db_path,
            "2 milk",
            "Alex",
            due_date=None,
            category="shopping",
        )
        self.assertIn("Updated to 3× milk", updated)
        item = db.list_open_todos(self.db_path, category="shopping")[0]
        self.assertEqual(item.text, "milk")
        self.assertEqual(item.quantity, 3)

    def test_add_quantity_parsed(self) -> None:
        intents = _parse_with_rules("add 2 milk to the list")
        self.assertEqual(intents[0].name, "add_todo")
        self.assertEqual(intents[0].item, "2 milk")

    def test_export_list_intent(self) -> None:
        intents = _parse_with_rules("export the list")
        self.assertEqual(intents[0].name, "export_list")

    def test_export_list_csv(self) -> None:
        intents = _parse_with_rules("export the shopping list as csv")
        self.assertEqual(intents[0].name, "export_list")
        self.assertEqual(intents[0].item, "csv")
        self.assertEqual(intents[0].category, "shopping")

    def test_clear_shopping_list_intent(self) -> None:
        intents = _parse_with_rules("clear the shopping list")
        self.assertEqual(intents[0].name, "clear_shopping_list")

    def test_export_shopping_csv(self) -> None:
        _add_or_merge_todo(self.db_path, "2 milk", "Alex", due_date=None, category="shopping")
        _add_or_merge_todo(self.db_path, "eggs", "Alex", due_date=None, category="shopping")
        csv_text = format_export_list(self.db_path, export_format="csv", category="shopping")
        self.assertIn("item,quantity,category", csv_text)
        self.assertIn("milk,2,shopping", csv_text)
        self.assertIn("eggs,1,shopping", csv_text)

    def test_clear_shopping_list_handler(self) -> None:
        _add_or_merge_todo(self.db_path, "milk", "Alex", due_date=None, category="shopping")
        reply = handle_clear_shopping_list(self.db_path)
        self.assertIn("Cleared 1 item", reply)
        self.assertEqual(len(db.list_open_todos(self.db_path, category="shopping")), 0)


if __name__ == "__main__":
    unittest.main()
