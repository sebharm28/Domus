import unittest
from datetime import date
from pathlib import Path

from domus import db
from domus.dates import parse_assignee_hint
from domus.german import normalize_german_input
from domus.intents import _parse_with_rules, Intent
from domus.reminders import handle_ack_recurring_reminder
from domus.todos import handle_intent


class NlpPolishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_nlp_polish.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_german_we_need(self) -> None:
        translated = normalize_german_input("wir brauchen Milch")
        intents = _parse_with_rules(translated)
        self.assertEqual(intents[0].name, "add_todo")
        self.assertIn("milch", intents[0].item.lower())

    def test_german_add_to_list(self) -> None:
        translated = normalize_german_input("füge Butter zur Liste hinzu")
        intents = _parse_with_rules(translated)
        self.assertEqual(intents[0].name, "add_todo")
        self.assertIn("butter", intents[0].item.lower())

    def test_german_daily_briefing(self) -> None:
        translated = normalize_german_input("was steht heute an?")
        intents = _parse_with_rules(translated)
        self.assertEqual(intents[0].name, "daily_briefing")

    def test_assignee_give_to(self) -> None:
        text, assignee = parse_assignee_hint("give pay rent to Sebastian")
        self.assertEqual(assignee, "Sebastian")
        self.assertIn("pay rent", text)

    def test_assignee_possessive_task(self) -> None:
        text, assignee = parse_assignee_hint("Sebastian's task: clean bathroom")
        self.assertEqual(assignee, "Sebastian")
        self.assertEqual(text, "clean bathroom")

    def test_ack_recurring_intent(self) -> None:
        intents = _parse_with_rules("done with trash")
        self.assertEqual(intents[0].name, "ack_recurring_reminder")
        self.assertIn("trash", intents[0].item)

    def test_ack_recurring_advances_schedule(self) -> None:
        db.add_reminder(
            self.db_path,
            "take out the trash",
            recurrence="weekly:tuesday",
            created_by="You",
            next_due=date(2026, 8, 26),
        )
        reply = handle_ack_recurring_reminder(self.db_path, "trash")
        self.assertIn("Logged", reply)
        self.assertIn("Next due", reply)

    def test_ack_recurring_via_handler(self) -> None:
        db.add_reminder(
            self.db_path,
            "water plants",
            recurrence="daily",
            created_by="You",
            next_due=date(2026, 8, 26),
        )
        intent = Intent(name="ack_recurring_reminder", item="water plants")
        reply = handle_intent(intent, self.db_path, "You")
        self.assertIn("water plants", reply)


if __name__ == "__main__":
    unittest.main()
