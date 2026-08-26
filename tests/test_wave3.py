import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from domus import db, food_db
from domus.intents import _parse_profile_intents, _parse_with_rules
from domus.profiles import handle_log_preference
from domus.intents import Intent
from domus.reminders import handle_list_reminders
from domus.todos import handle_intent


class MealPhrasingTests(unittest.TestCase):
    def test_what_should_we_cook_tomorrow(self) -> None:
        intents = _parse_with_rules("what should we cook tomorrow?")
        self.assertEqual(intents[0].name, "suggest_meal")

    def test_recommendation_for_dinner_tomorrow(self) -> None:
        intents = _parse_with_rules("please make a recommendation for dinner tomorrow")
        self.assertEqual(intents[0].name, "suggest_meal")
        self.assertEqual(intents[0].item, "dinner")

    def test_lets_make_curry_still_plans(self) -> None:
        intents = _parse_with_rules("let's make curry with rice tonight")
        self.assertEqual(intents[0].name, "plan_meal")


class ReminderListingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave3_reminders.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        self.chat_id = 42

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_wheres_the_reminder_intent(self) -> None:
        intents = _parse_with_rules("where's the reminder?")
        self.assertEqual(intents[0].name, "list_reminders")

    def test_list_pending_one_shot(self) -> None:
        fire_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        db.add_one_shot_reminder(
            self.db_path,
            "text Andreas",
            fire_at,
            self.chat_id,
            "Alex",
        )
        reply = handle_list_reminders(self.db_path, chat_id=self.chat_id)
        self.assertIn("Pending timers", reply)
        self.assertIn("text Andreas", reply)

    def test_list_recent_fired_one_shot(self) -> None:
        fire_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        reminder = db.add_one_shot_reminder(
            self.db_path,
            "text Andreas",
            fire_at,
            self.chat_id,
            "Alex",
        )
        db.mark_one_shot_sent(self.db_path, reminder.id)
        reply = handle_list_reminders(self.db_path, chat_id=self.chat_id)
        self.assertIn("Recent timers", reply)
        self.assertIn("text Andreas", reply)


class PreferenceLearningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db_path = Path("data/test_wave3_prefs.db")
        if self.db_path.exists():
            self.db_path.unlink()
        db.init_db(self.db_path)
        food_db.init_food_tables(self.db_path)
        self.user_id = 7
        db.upsert_user_profile(self.db_path, self.user_id, "Alex")

    def tearDown(self) -> None:
        if self.db_path.exists():
            self.db_path.unlink()

    def test_i_really_like_currywurst_intent(self) -> None:
        intents = _parse_profile_intents("I really like currywurst")
        self.assertIsNotNone(intents)
        assert intents is not None
        self.assertEqual(intents[0].name, "log_preference")
        self.assertEqual(intents[0].item, "currywurst")

    def test_log_preference_saves_like_and_food(self) -> None:
        intent = Intent(name="log_preference", item="currywurst")
        reply = handle_log_preference(intent, self.db_path, self.user_id)
        self.assertIn("currywurst", reply)
        profile = db.get_user_profile(self.db_path, self.user_id)
        assert profile is not None
        self.assertIn("currywurst", (profile.likes or "").lower())
        food = food_db.find_food_by_name(self.db_path, "currywurst")
        self.assertIsNotNone(food)

    def test_liked_food_prioritized_in_suggestions(self) -> None:
        db.append_user_profile_list(self.db_path, self.user_id, "likes", "currywurst")
        food_db.add_custom_food(self.db_path, "currywurst")
        profile = db.get_user_profile(self.db_path, self.user_id)
        assert profile is not None
        suggestions = food_db.suggest_foods(
            self.db_path,
            meal_type="dinner",
            count=3,
            profiles=[profile],
        )
        self.assertTrue(any("currywurst" in food.name.lower() for food in suggestions))

    def test_log_preference_via_handler(self) -> None:
        intents = _parse_profile_intents("I love pasta")
        assert intents is not None
        reply = handle_intent(
            intents[0],
            self.db_path,
            "Alex",
            telegram_user_id=self.user_id,
        )
        self.assertIn("pasta", reply.lower())


if __name__ == "__main__":
    unittest.main()
