import unittest
from pathlib import Path

from domus import db, food_db
from domus.dates import parse_due_date
from domus.intents import _parse_edit_intents, _parse_with_rules
from domus.meals import handle_plan_meal, normalize_plan_meal_name
from domus.relative_reminders import parse_relative_reminder_phrase
from domus.todos import _add_or_merge_todo, handle_update_todo


class LogFixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_log_fixes.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        food_db.init_food_tables(self.db_path)

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_split_eggs_and_bread(self) -> None:
        intents = _parse_with_rules("add eggs and bread to the list")
        self.assertEqual(len(intents), 2)
        names = {intent.item for intent in intents}
        self.assertEqual(names, {"eggs", "bread"})

    def test_plan_meal_strips_tonight(self) -> None:
        self.assertEqual(normalize_plan_meal_name("curry with rice tonight"), "curry with rice")
        reply = handle_plan_meal(
            "let's make curry with rice tonight",
            self.db_path,
            "Alex",
            meal_name="curry with rice tonight",
        )
        self.assertIn('Planning "Curry with rice"', reply)

    def test_relative_reminder_to_first_word_order(self) -> None:
        parsed = parse_relative_reminder_phrase("remind me to leave my boyfriend in 2 minutes")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed[1], 2)
        self.assertIn("leave my boyfriend", parsed[0])

    def test_doctor_appointment_friday_gets_due_date(self) -> None:
        intents = _parse_with_rules("add doctor appointment friday")
        self.assertEqual(intents[0].name, "add_todo")
        self.assertIsNotNone(intents[0].due_date)
        text, due = parse_due_date("doctor appointment friday")
        self.assertEqual(text.strip(), "doctor appointment")
        self.assertIsNotNone(due)

    def test_apartment_shown_on_add_reply(self) -> None:
        reply, todo = _add_or_merge_todo(
            self.db_path,
            "buy filter",
            "Alex",
            due_date=None,
            category="household",
            apartment="a",
        )
        assert todo is not None
        self.assertIn("[a]", reply)

    def test_rename_skips_redundant_message(self) -> None:
        todo = db.add_todo(
            self.db_path,
            "finish power bi report",
            "Alex",
            category="personal",
        )
        intents = _parse_edit_intents("rename that to finish power bi report")
        assert intents is not None
        reply = handle_update_todo(intents[0], self.db_path, chat_id=1)
        self.assertNotIn("renamed to", reply)


if __name__ == "__main__":
    unittest.main()
