import unittest
from pathlib import Path

from domus import db, food_db
from domus.diet import filter_foods_for_household, food_ok_for_profile
from domus.intents import _parse_with_rules
from domus.relative_reminders import parse_relative_reminder_phrase
from domus.todos import _add_or_merge_todo, format_todo_list


class Wave2bDietTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave2b_diet.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        food_db.init_food_tables(self.db_path)

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_vegetarian_filters_salmon(self) -> None:
        profile = db.UserProfile(
            telegram_user_id=1,
            display_name="Alex",
            username=None,
            apartment=None,
            diet="vegetarian",
            allergies=None,
            dislikes=None,
            updated_at="now",
        )
        foods = food_db.list_foods(self.db_path, meal_type="dinner")
        salmon = next(food for food in foods if "salmon" in food.name.lower())
        self.assertFalse(food_ok_for_profile(salmon, profile))
        filtered = filter_foods_for_household(foods, [profile])
        self.assertTrue(all("salmon" not in food.name.lower() for food in filtered))


class Wave2bApartmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave2b_apartment.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_add_with_apartment_hint(self) -> None:
        intents = _parse_with_rules("add buy filter for apartment A to the list")
        self.assertEqual(intents[0].name, "add_todo")
        self.assertEqual(intents[0].apartment, "a")

    def test_apartment_stored_on_todo(self) -> None:
        _, todo = _add_or_merge_todo(
            self.db_path,
            "buy filter",
            "Alex",
            due_date=None,
            category="maintenance",
            apartment="a",
        )
        assert todo is not None
        self.assertEqual(todo.apartment, "a")
        text = format_todo_list(db.list_open_todos(self.db_path))
        self.assertIn("[a]", text)


class Wave2bListFilterTests(unittest.TestCase):
    def test_show_admin_tasks(self) -> None:
        intents = _parse_with_rules("show admin tasks")
        self.assertEqual(intents[0].name, "list_todos")
        self.assertEqual(intents[0].category, "admin")


class Wave2bRelativeReminderTests(unittest.TestCase):
    def test_parse_thirty_minutes(self) -> None:
        parsed = parse_relative_reminder_phrase("remind me in 30 minutes the oven is on")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed[0], "the oven is on")
        self.assertEqual(parsed[1], 30)

    def test_parse_two_hours(self) -> None:
        parsed = parse_relative_reminder_phrase("remind us in 2 hours to take out the laundry")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed[1], 120)

    def test_relative_reminder_intent(self) -> None:
        intents = _parse_with_rules("remind me in 30 minutes the oven is on")
        self.assertEqual(intents[0].name, "add_relative_reminder")
        self.assertEqual(intents[0].delay_minutes, 30)


if __name__ == "__main__":
    unittest.main()
